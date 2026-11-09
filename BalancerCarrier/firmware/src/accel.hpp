#pragma once
#include <cstdint>
#include "accelscale.hpp"

// ST IIS3DWB on SPI2 (pins in board.hpp: GPIO12 SCK, 11 MOSI, 14 MISO, 17 CS), mode 3, 10 MHz.
// The sensor runs at its fixed 26.667 kHz ODR into its FIFO. INT1 is the FIFO watermark, which the
// MCPWM capture timer timestamps exactly like the old data-ready line; each watermark block of
// `decimation` samples is pushed through the anti-alias FIR in accelscale.hpp, which emits one
// 1666.7 Hz measurement sample per block, delayed groupDelayRaw raw periods.
namespace accel {
constexpr double odrHz = 26666.67;
constexpr double sampleRateHz = odrHz / decimation;   // 1666.7 Hz, matches puck::sampleRate
constexpr unsigned lpfDivider = 10;                   // on-chip LPF2 at ODR/10 = 2.67 kHz, ahead of the FIR

bool setup();                     // bus, reset, configuration; leaves the ODR off
bool start();                     // ODR on, FIFO streaming, watermark interrupts begin
void powerDown();                 // ODR off before deep sleep
// Drain one watermark block from the FIFO through the FIR and return the decimated sample in g
// plus per-axis clipping of the raw samples. False on bus error, wrong entry count or a
// non-accelerometer tag (`entries` reports what was actually read); any failure also resets the
// FIR, because its history no longer is contiguous. `primed` is false while the FIR refills
// (the first firBlocks-1 blocks after start or a failure): the block was read correctly but
// `block.g` is not a sample yet.
bool readBlock(Block &block, unsigned &entries, bool &primed);
bool present();
}
