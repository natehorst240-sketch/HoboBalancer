#pragma once
// BalancerDisplay: the handheld display unit. Everything that is specific to the display
// hardware lives in this one file; the UI (LVGL) and the carrier link never touch a pin or a
// resolution directly. Swapping the panel means writing a new board_*.hpp and selecting it
// here, with no change elsewhere, as long as the MCU stays an ESP32-S3.
//
// Proof-of-concept board: Freenove FNK0115B, 4.3" 480x272 TN, ILI6485 panel on the parallel
// RGB bus, XPT2046 resistive touch and the microSD on one SPI bus, CH340C USB-serial on UART0.
// Pins and timing are taken from Freenove's own sketches (Freenove_ESP32_S3_Display_FNK0115:
// Sketch_10.1_TFT_Test/TFT_Display.h, Sketch_09.1_Touch/Touch.h, Sketch_04.1_SD_Test) and
// the 4.3inch_ESP32-S3_TN schematic, read 2026-11-09. The SD and touch sketches agree on the
// SPI pins; the schematic's text labels near the XPT2046 are ambiguous and were not used.
#define BOARD_FNK0115B 1

namespace board {
constexpr const char *name = "FNK0115B 4.3in TN";

// ---- panel: parallel RGB565, 16 bits, full frame buffer in PSRAM ------------------------
namespace panel {
constexpr int width = 480, height = 272;
constexpr int de = 40, vsync = 41, hsync = 39, pclk = 42;
constexpr int r[5] = {45, 48, 47, 21, 14};        // R0..R4
constexpr int g[6] = {5, 6, 7, 15, 16, 4};         // G0..G5
constexpr int b[5] = {8, 3, 46, 9, 1};             // B0..B4
constexpr int backlight = 2;                       // SY7201 EN/PWM, high = on
// Timing from TFT_Display.cpp for the TN variants.
constexpr int pclkHz = 9000000;
constexpr int hsyncFrontPorch = 8, hsyncPulse = 4, hsyncBackPorch = 43;
constexpr int vsyncFrontPorch = 8, vsyncPulse = 4, vsyncBackPorch = 12;
constexpr bool pclkActiveNeg = true, hsyncIdleLow = false, vsyncIdleLow = false;
}  // namespace panel

// ---- touch: XPT2046 resistive, SPI shared with the microSD -------------------------------
namespace touch {
constexpr bool resistive = true;
constexpr int sck = 12, mosi = 11, miso = 13, cs = 38, irq = 18;
// Raw ADC extents at the screen corners from Touch.h; refine with a calibration screen.
constexpr int rawXMin = 170, rawXMax = 3800, rawYMin = 250, rawYMax = 3800;
}  // namespace touch

namespace sd { constexpr int cs = 10; }           // same SPI bus as the touch controller
constexpr int bootButton = 0;

// ---- carrier link ---------------------------------------------------------------------
// BLE needs no pins. The wired fallback is a 3.3 V UART on the expansion header; IO17, IO19
// and IO20 have no other function on the B variant (19/20 are the capacitive-touch I2C pins,
// unpopulated here). UART0 is taken by the CH340C. Verify the header silkscreen before wiring.
namespace link { constexpr int uartTx = 17, uartRx = 19; constexpr int uartBaud = 115200; }

// Not on this board: battery sense, speaker, native USB on the connector (CH340C instead).
}  // namespace board
