# BalancerDisplay firmware

Handheld display unit for the BalancerCarrier: an ESP32-S3 that is a client of the carrier's
newline-delimited JSON protocol (BLE Nordic UART Service, or a UART cable) and shows status,
results and controls on a touch panel. It replaces the phone as the carrier's user interface.

Proof-of-concept board: **Freenove FNK0115B** (4.3 in 480x272 TN, resistive touch; the module is
an ESP32-S3-WROOM-1-N16R8 with 16 MB flash and 8 MB octal PSRAM; USB-C is a CH340C on UART0).
The panel is expected to change later with the MCU kept, so every pin, timing and resolution
lives in `src/board.hpp` and nothing else refers to the hardware.

- `src/protocol.*`: line reassembly and message parsing, no ESP dependencies.
  `tests/run_host_tests.sh` compiles it with GCC and both sanitizers and runs 74 checks against
  the carrier's message shapes (from `BalancerCarrier/firmware/src/main.cpp`).
- `src/display.*`: panel bring-up through `esp_lcd` (RGB), frame buffer in PSRAM.
- `src/transport.hpp`: the byte-level link interface the BLE and UART implementations fill in.

Build: `pio run` (PlatformIO, `espressif32@6.12.0`, ESP-IDF 5.5, same as the carrier). Flash
over the board's USB-C; the console is on the same port at 115200.
