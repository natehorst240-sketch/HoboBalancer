#pragma once
#include <cstdint>
#include <cmath>
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

constexpr unsigned decimation = 16;     // raw samples per FIFO watermark block and per output sample

struct Block {
    float g[3];         // decimated sample, g
    uint8_t clipped;    // bit a set when any raw sample of this block on axis a reached clipRaw
};

// Clipping is judged on every raw sample, before any filtering, so a single saturated sample
// cannot hide inside a filtered value.
inline uint8_t clipFlags(const int16_t (*raw)[3], unsigned n) {
    uint8_t c = 0;
    for (unsigned i = 0; i < n; ++i)
        for (int a = 0; a < 3; ++a)
            if (std::abs(int32_t(raw[i][a])) >= clipRaw) c |= uint8_t(1u << a);
    return c;
}

// Anti-alias low-pass and decimation by 16, 26.667 kHz -> 1666.7 Hz.
//
// A plain 16-sample average is not an anti-alias filter: its sidelobes pass content near
// k x 1666.7 Hz straight down into the rotor band. A rotor-locked tone there (a gear-mesh
// order, for example) then aliases onto 1/rev and reads as a stable, convincing 1/rev vector.
// Host test: a 1 g tone at 1706.7 Hz with no 1/rev input read 0.036 IPS at 2400 RPM.
//
// This is a 161-tap linear-phase FIR (windowed sinc, Kaiser beta 7.86, cutoff 833 Hz):
// passband flat within 0.02% to 400 Hz (4/rev at 6000 RPM, every harmonic the fit uses) and
// at least 79 dB down from 1266.7 Hz, the lowest frequency that aliases into 0-400 Hz. Its
// delay is exactly groupDelayRaw raw periods before the newest sample of the block; the
// sample timestamp must be shifted by that, which removes the delay from the phase.
constexpr unsigned firTaps = 161;
constexpr double groupDelayRaw = (firTaps - 1) / 2.0;  // 80 raw periods, 3.0 ms
constexpr unsigned firBlocks = (firTaps + decimation - 1) / decimation;  // blocks of history to fill the filter

class Decimator {
public:
    Decimator() {
        constexpr double pi = 3.14159265358979323846, fc = 833.33 / 26666.67, beta = 7.857;
        double sum = 0, w[firTaps];
        for (unsigned k = 0; k < firTaps; ++k) {
            const double n = double(k) - groupDelayRaw, r = n / groupDelayRaw;
            const double sinc = n == 0 ? 2 * fc : std::sin(2 * pi * fc * n) / (pi * n);
            w[k] = sinc * besselI0(beta * std::sqrt(1 - r * r)) / besselI0(beta);
            sum += w[k];
        }
        for (unsigned k = 0; k < firTaps; ++k) taps_[k] = float(w[k] / sum);  // unity DC gain
        reset();
    }
    // Forget history, e.g. after a lost or malformed block: the next firBlocks-1 blocks only refill.
    void reset() { head_ = 0; filled_ = 0; }
    // Feed one block of n raw samples. Returns true and fills `out` once the filter holds firTaps
    // samples; before that `out.clipped` is still set but `out.g` must not be used.
    bool push(const int16_t (*raw)[3], unsigned n, Block &out) {
        out.clipped = clipFlags(raw, n);
        for (unsigned i = 0; i < n; ++i) {
            for (int a = 0; a < 3; ++a) ring_[head_][a] = float(raw[i][a]);
            head_ = (head_ + 1) % firTaps;
            if (filled_ < firTaps) ++filled_;
        }
        if (filled_ < firTaps) return false;
        float acc[3] = {0, 0, 0};
        unsigned j = head_;  // oldest sample; taps are symmetric, so order only needs to be consistent
        for (unsigned k = 0; k < firTaps; ++k) {
            const float h = taps_[k];
            for (int a = 0; a < 3; ++a) acc[a] += h * ring_[j][a];
            if (++j == firTaps) j = 0;
        }
        for (int a = 0; a < 3; ++a) out.g[a] = float(acc[a] * mgPerLsb * 0.001);
        return true;
    }
    float tap(unsigned k) const { return taps_[k]; }
private:
    static double besselI0(double x) {
        double term = 1, sum = 1;
        for (int k = 1; k < 40; ++k) { term *= (x / (2 * k)) * (x / (2 * k)); sum += term; }
        return sum;
    }
    float taps_[firTaps];
    float ring_[firTaps][3];
    unsigned head_ = 0, filled_ = 0;
};
}  // namespace accel
