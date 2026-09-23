#pragma once
#include <cstdint>
#include "accelscale.hpp"

// ST IIS3DWB on SPI2 (pins in board.hpp: GPIO12 SCK, 11 MOSI, 14 MISO, 17 CS), mode 3, 10 MHz.
// The sensor runs at its fixed 26.667 kHz ODR into its FIFO. INT1 is the FIFO watermark, which the
// MCPWM capture timer timestamps exactly like the old data-ready line; each watermark block of
// `decimation` samples is averaged into one measurement sample (boxcar decimation to 1666.7 Hz).
namespace accel {
constexpr double odrHz = 26666.67;
constexpr unsigned decimation = 16;
constexpr double sampleRateHz = odrHz / decimation;   // 1666.7 Hz, matches puck::sampleRate
constexpr unsigned lpfDivider = 10;                   // LPF2 at ODR/10 = 2.67 kHz anti-alias before the average

bool setup();                     // bus, reset, configuration; leaves the ODR off
bool start();                     // ODR on, FIFO streaming, watermark interrupts begin
void powerDown();                 // ODR off before deep sleep
// Drain one watermark block from the FIFO and return its mean in g plus per-axis clipping of the
// raw samples. False on bus error, wrong entry count or a non-accelerometer tag; `entries`
// reports what was actually read.
bool readBlock(Block &block, unsigned &entries);
bool present();
}
