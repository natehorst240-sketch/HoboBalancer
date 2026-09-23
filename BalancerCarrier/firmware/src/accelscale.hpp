#pragma once
#include <cstdint>
#include <cstdlib>

// The single source of truth for accelerometer range. accel.cpp programs the register from
// fullScaleG, converts with mgPerLsb, and main.cpp reports fullScaleG; nothing else may assume a
// range. No ESP dependencies: this is compiled into the host tests.
//
// Fixed +/-16 g, never switched at run time. DS12569 Table 2 note: "Noise density is independent
// of the FS selected", and at 0.488 mg/LSB the step is ~1/28 of the ~3.9 mg RMS per-sample noise
// (75 ug/sqrt(Hz) over the 2.67 kHz LPF2), so the widest range costs no usable resolution. One
// range means no run can ever mix differently scaled samples.
namespace accel {
constexpr double fullScaleG = 16;
constexpr double mgPerLsb = 0.488;  // DS12569 Table 2, FS = +/-16 g
// The FIFO carries LPF2 output, which can round a saturated peak slightly below full scale.
// Treat anything within 5% of the rail as clipped.
constexpr int32_t clipRaw = 31129;  // 0.95 * 32767, about 15.2 g

struct Block {
    float g[3];         // block mean, g
    uint8_t clipped;    // bit a set when any raw sample on axis a reached clipRaw
};

// Average one FIFO block of raw little-endian samples. Clipping is judged on every raw sample,
// before averaging, so a single saturated sample cannot hide inside the mean.
inline void decodeBlock(const int16_t (*raw)[3], unsigned n, Block &out) {
    double sum[3] = {0, 0, 0};
    out.clipped = 0;
    for (unsigned i = 0; i < n; ++i)
        for (int a = 0; a < 3; ++a) {
            sum[a] += raw[i][a];
            if (std::abs(int32_t(raw[i][a])) >= clipRaw) out.clipped |= uint8_t(1u << a);
        }
    for (int a = 0; a < 3; ++a) out.g[a] = n ? float(sum[a] / n * mgPerLsb * 0.001) : 0.0f;
}
}  // namespace accel
