import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location("puck", Path(__file__).resolve().parents[1]/"tools/puck.py")
puck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(puck)


class Transport(unittest.IsolatedAsyncioTestCase):
    async def test_fragmented_and_multiple_frames(self):
        lines = puck.Lines()
        data = '{"type":"result","label":"µ","rpm":3000}\n{"type":"status"}\n'.encode()
        for byte in data:
            lines.feed(bytes([byte]))
        self.assertEqual((await lines.queue.get())["label"], "µ")
        self.assertEqual((await lines.queue.get())["type"], "status")

    async def test_recover_from_bad_and_oversized_frames(self):
        lines = puck.Lines()
        lines.feed(b'{"truncated":\n'+b'x'*10000+b'\n{"type":"result"}\n')
        self.assertEqual(lines.queue.qsize(), 1)
        self.assertEqual((await lines.queue.get())["type"], "result")

    async def test_session_waits_for_ack_and_preserves_results(self):
        lines = puck.Lines()
        sent = []
        raw = {"type":"result", "raw_axes":[{"ips_peak":0.123}], "valid":False}

        async def send(data):
            command = json.loads(data)
            sent.append(command["cmd"])
            if command["cmd"] == "profile":
                lines.feed(b'{"type":"boot"}\n{"type":"profile"}\n')
            else:
                lines.feed(b'{"type":"started"}\n'+json.dumps(raw).encode()+b'\n')

        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder)/"runs.jsonl"
            args = SimpleNamespace(log=str(log), profile="TR-VERT", command=[], acquire=True, seconds=2)
            await puck.session(args, send, lines)
            records = [json.loads(x) for x in log.read_text().splitlines()]
            self.assertEqual(records[-1]["puck"], raw)
            self.assertIn("received_utc", records[-1])
        self.assertEqual(sent, ["profile", "start"])

    async def test_device_error_stops_following_commands(self):
        lines = puck.Lines()
        sent = []

        async def send(data):
            sent.append(data)
            lines.feed(b'{"type":"error","message":"sensor missing"}\n')

        args = SimpleNamespace(log=None, profile="TR-VERT", command=[], acquire=True, seconds=2)
        with self.assertRaisesRegex(RuntimeError, "sensor missing"):
            await puck.session(args, send, lines)
        self.assertEqual(len(sent), 1)

    async def test_continuous_collects_runs_then_stops(self):
        lines = puck.Lines()
        sent = []
        result = {"type":"result","continuous":True,"sequence":0,"raw_axes":[{"ips_peak":0.1}]}

        async def send(data):
            command = json.loads(data)
            sent.append(command)
            if command["cmd"] == "start":
                self.assertTrue(command["continuous"])
                lines.feed(b'{"type":"started","continuous":true}\n')
                for seq in (1, 2, 3):
                    lines.feed(json.dumps({**result, "sequence": seq}).encode()+b'\n')
            elif command["cmd"] == "stop":
                lines.feed(json.dumps({**result, "sequence": 3, "flags": 2048, "valid": False}).encode()+b'\n')

        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder)/"runs.jsonl"
            args = SimpleNamespace(log=str(log), profile=None, command=[], acquire=True, seconds=2,
                                   continuous=True, runs=2)
            await puck.session(args, send, lines)
            records = [json.loads(x)["puck"] for x in log.read_text().splitlines()]
        self.assertEqual([c["cmd"] for c in sent], ["start", "stop"])
        self.assertEqual([r.get("sequence") for r in records if r["type"] == "result"], [1, 2, 3, 3])
        self.assertEqual(records[-1]["flags"], 2048)

    async def test_single_run_sends_no_continuous_flag(self):
        lines = puck.Lines()
        sent = []

        async def send(data):
            sent.append(json.loads(data))
            lines.feed(b'{"type":"started"}\n{"type":"result"}\n')

        args = SimpleNamespace(log=None, profile=None, command=[], acquire=True, seconds=2)
        await puck.session(args, send, lines)
        self.assertEqual(sent, [{"cmd": "start"}])

    async def test_download_stores_records_and_checks_count(self):
        lines = puck.Lines()
        sent = []

        async def send(data):
            command = json.loads(data)
            sent.append(command["cmd"])
            if command["cmd"] == "download":
                lines.feed(b'{"type":"download_begin","records":3}\n')
                lines.feed(b'{"type":"boot","t":null,"up":12,"note":"power-on"}\n')
                lines.feed(b'{"type":"log","seq":1,"rpm":388.2,"lvl":true}\n')
                lines.feed(b'{"type":"log","seq":2,"rpm":389.0,"lvl":false}\n')
                lines.feed(b'{"type":"download_end","complete":true,"records":3}\n')

        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/"flight.jsonl"
            args = SimpleNamespace(log=None, profile=None, command=[], acquire=False, seconds=2, download=str(out))
            await puck.session(args, send, lines)
            records = [json.loads(x) for x in out.read_text().splitlines()]
        self.assertEqual(sent, ["download"])
        self.assertEqual([r["type"] for r in records], ["boot", "log", "log"])
        self.assertEqual(records[1]["seq"], 1)

    async def test_download_count_mismatch_is_an_error(self):
        lines = puck.Lines()

        async def send(data):
            lines.feed(b'{"type":"download_begin","records":2}\n')
            lines.feed(b'{"type":"log","seq":1}\n')
            lines.feed(b'{"type":"download_end","complete":true,"records":2}\n')

        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(log=None, profile=None, command=[], acquire=False, seconds=2,
                                   download=str(Path(folder)/"f.jsonl"))
            with self.assertRaisesRegex(RuntimeError, "do not erase"):
                await puck.session(args, send, lines)

    async def test_flight_and_erase_commands(self):
        lines = puck.Lines()
        sent = []

        async def send(data):
            sent.append(json.loads(data))
            lines.feed(b'{"type":"status","flight":true}\n')

        args = SimpleNamespace(log=None, profile=None, command=[], acquire=False, seconds=2, flight="on", erase=True)
        await puck.session(args, send, lines)
        self.assertEqual(sent, [{"cmd": "flight", "value": True}, {"cmd": "erase"}])


if __name__ == "__main__":
    unittest.main()
