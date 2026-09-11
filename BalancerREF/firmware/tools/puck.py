"""USB/BLE console and timestamped JSONL logger for BalancerREF.

Examples:
  python tools/puck.py --port COM5 --acquire --profile TR-VERT --log runs.jsonl
  python tools/puck.py --ble --acquire --continuous --runs 10 --log runs.jsonl
  python tools/puck.py --ble --command '{"cmd":"status"}'
  python tools/puck.py --port COM5 --flight on
  python tools/puck.py --port COM5 --download flight.jsonl
  python tools/puck.py --port COM5 --erase
"""
import argparse
import asyncio
import datetime
import json
import sys
import time
from pathlib import Path

SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"


class Lines:
    def __init__(self):
        self.buffer = bytearray()
        self.discard = False
        self.queue = asyncio.Queue(maxsize=100)

    def feed(self, data):
        for b in data:
            if b == 10:
                if not self.discard and self.buffer:
                    try:
                        obj = json.loads(self.buffer)
                        if not isinstance(obj, dict):
                            raise ValueError("expected object")
                        self.queue.put_nowait(obj)
                    except (ValueError, asyncio.QueueFull):
                        print("Discarded malformed/incomplete frame or full receive queue", file=sys.stderr)
                self.buffer.clear()
                self.discard = False
            elif not self.discard:
                if len(self.buffer) >= 8192:
                    self.discard = True
                    self.buffer.clear()
                else:
                    self.buffer.append(b)


async def receive_download(lines, path, record, timeout):
    """Store every log/boot record verbatim until download_end; nothing is erased on the puck."""
    count = 0
    with Path(path).open("a", encoding="utf-8") as out:
        while True:
            obj = await asyncio.wait_for(lines.queue.get(), timeout)
            kind = obj.get("type")
            if kind in ("log", "boot"):
                out.write(json.dumps(obj, separators=(",", ":"), allow_nan=False) + "\n")
                count += 1
                continue
            record(obj)
            if kind == "download_end":
                if not obj.get("complete", False):
                    raise RuntimeError("puck reported an incomplete download; do not erase")
                if obj.get("records") is not None and count != int(obj["records"]):
                    raise RuntimeError(f"received {count} records, puck holds {obj['records']}; do not erase")
                print(f"Downloaded {count} records to {path}")
                return count
            if kind == "error":
                raise RuntimeError(obj.get("message"))


async def session(args, send, lines):
    log = Path(args.log).open("a", encoding="utf-8") if args.log else None

    def record(obj):
        print(json.dumps(obj, indent=2))
        if log:
            log.write(json.dumps({"received_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                  "puck": obj}, allow_nan=False) + "\n")
            log.flush()

    try:
        commands = []
        if args.profile:
            commands.append({"cmd": "profile", "value": args.profile})
        commands.extend(json.loads(c) for c in args.command)
        flight = getattr(args, "flight", None)
        if flight:
            commands.append({"cmd": "flight", "value": flight == "on"})
        download = getattr(args, "download", None)
        if download:
            commands.append({"cmd": "download"})
        if getattr(args, "erase", False):
            commands.append({"cmd": "erase"})
        continuous = bool(getattr(args, "continuous", False))
        runs = int(getattr(args, "runs", 1) or 0)
        if args.acquire:
            commands.append({"cmd": "start", "continuous": True} if continuous else {"cmd": "start"})
        if not commands:
            commands.append({"cmd": "status"})
        # One command in flight. Boot messages are recorded, never mistaken for ACKs.
        expected = {"start": "started", "profile": "profile", "config": "status", "status": "status",
                    "history": "history", "compare": "comparison_proposal", "stop": "result",
                    "flight": "status", "download": "download_begin", "erase": "status"}
        for command in commands:
            if not isinstance(command, dict) or command.get("cmd") not in expected:
                raise ValueError("Unknown or missing cmd")
            payload = json.dumps(command, separators=(",", ":"), allow_nan=False).encode()
            if len(payload) > 255:
                raise ValueError("Commands must be at most 255 UTF-8 bytes")
            await send(payload)
            deadline = time.monotonic() + 10
            while True:
                obj = await asyncio.wait_for(lines.queue.get(), max(.01, deadline-time.monotonic()))
                record(obj)
                if obj.get("type") == "error":
                    raise RuntimeError(obj.get("message"))
                if obj.get("type") == expected[command["cmd"]]:
                    break
            if command["cmd"] == "download":
                await receive_download(lines, download, record, args.seconds)
        if args.acquire or any(c.get("cmd") == "start" for c in commands):
            # One result per window. Continuous: keep collecting until --runs results
            # (0 = until Ctrl+C), then stop; the stop returns a final cancelled partial.
            received = 0
            deadline = time.monotonic() + args.seconds
            while True:
                obj = await asyncio.wait_for(lines.queue.get(), max(.01, deadline-time.monotonic()))
                record(obj)
                if obj.get("type") == "result":
                    received += 1
                    deadline = time.monotonic() + args.seconds
                    if not continuous or (runs and received >= runs):
                        break
            if continuous:
                # A complete window may already be in flight when stop is sent; keep
                # reading until the cancelled partial (flag 2048) or an error arrives.
                await send(b'{"cmd":"stop"}')
                deadline = time.monotonic() + args.seconds
                while True:
                    obj = await asyncio.wait_for(lines.queue.get(), max(.01, deadline-time.monotonic()))
                    record(obj)
                    if obj.get("type") == "error":
                        break
                    if obj.get("type") == "result" and int(obj.get("flags") or 0) & 2048:
                        break
    finally:
        if log:
            log.close()


async def main(args):
    lines = Lines()
    if args.ble:
        from bleak import BleakClient, BleakScanner
        device = await BleakScanner.find_device_by_filter(
            lambda d, a: (a.local_name == "BalancerREF" or SERVICE in a.service_uuids), timeout=15)
        if device is None:
            raise RuntimeError("BalancerREF BLE advertisement not found")
        async with BleakClient(device) as client:
            await client.start_notify(TX, lambda _, data: lines.feed(data))

            async def send(data):
                await client.write_gatt_char(RX, data, response=True)

            await session(args, send, lines)
    else:
        import serial
        ser = serial.Serial(port=None, baudrate=115200, timeout=.1, write_timeout=2)
        ser.dtr = True
        ser.rts = False
        ser.port = args.port
        ser.open()

        async def receive():
            while True:
                data = await asyncio.to_thread(ser.read, 512)
                if data:
                    lines.feed(data)

        async def send(data):
            await asyncio.to_thread(ser.write, data+b"\n")

        reader = asyncio.create_task(receive())
        try:
            await session(args, send, lines)
        finally:
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                pass
            ser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    transport = parser.add_mutually_exclusive_group(required=True)
    transport.add_argument("--port", help="Native USB serial port, e.g. COM5")
    transport.add_argument("--ble", action="store_true")
    parser.add_argument("--profile", choices=["MR-VERT", "TR-VERT"])
    parser.add_argument("--command", action="append", default=[], help="One JSON command; repeat to sequence")
    parser.add_argument("--acquire", action="store_true")
    parser.add_argument("--continuous", action="store_true", help="With --acquire: back-to-back windows until --runs results")
    parser.add_argument("--runs", type=int, default=1, help="Continuous results to collect before stopping; 0 = until Ctrl+C")
    parser.add_argument("--seconds", type=float, default=35, help="Result timeout")
    parser.add_argument("--log", help="Append untouched firmware results with UTC timestamps to JSONL")
    parser.add_argument("--flight", choices=["on", "off"], help="Enable or disable autonomous flight logging mode")
    parser.add_argument("--download", metavar="FILE", help="Append the puck's stored flight log records to FILE")
    parser.add_argument("--erase", action="store_true", help="Erase the puck's flight log (after a verified download)")
    try:
        asyncio.run(main(parser.parse_args()))
    except KeyboardInterrupt:
        sys.exit(130)
    except (TimeoutError, RuntimeError, ValueError, OSError) as exc:
        print(f"Error: {exc or 'Timed out waiting for the puck'}", file=sys.stderr)
        sys.exit(1)
