#pragma once
// Synthetic IIS3DWB source for host testing. Generates int16 samples at the full 26.667 kHz ODR,
// saturating at the ADC rail, and pushes them through the firmware's own decodeBlock and
// Measurement in the same order the firmware delivers them: each tach edge at its capture time,
// each 16-sample block at its watermark, timestamped at the block mean. Shared by the unit
// tests and tools/sim.cpp so what the simulator shows is what the tests assert.
#include "accelscale.hpp"
#include "measurement.hpp"
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace rawsim {
struct Scenario {
    double rpm = 2400, ips = .3, phaseDeg = 57;  // 1/rev velocity, peak IPS; phase of positive velocity peak
    double durationS = 12;
    int axis = 2;                                 // axis carrying gravity and the rotor vibration
    double gravityG = 1;
    double h2G = .3, h3G = .2;                    // 2/rev and 3/rev acceleration on that axis, g peak
    double noiseScale = 1;                        // multiple of the DS12569 noise density (0 = none)
    double spikeG = 0; int spikeAxis = 2; int spikes = 1;  // single-sample impacts, evenly spaced
    double phaseWanderDeg = 0;                    // slow +/- phase modulation of the 1/rev
    double ampWanderPct = 0;                      // slow +/- amplitude modulation of the 1/rev
    double rpmDriftPct = 0;                       // linear RPM change from start to end of run
    double tachJitterUs = 0;                      // RMS timing noise on each tach edge
    int tachDropEvery = 0;                        // lose every Nth tach edge
    int tachGlitchEvery = 0;                      // extra edge 50 us after every Nth edge
    double gapAtS = -1, gapMs = 0;                // drop blocks (missed watermarks) for gapMs
    uint32_t seed = 12345;
};

class Source {
public:
    explicit Source(uint32_t seed) : seed_(seed) {}
    double uniform() { seed_ = seed_ * 1664525u + 1013904223u; return (seed_ >> 8) / 16777216.0; }
    double gauss() { double t = 0; for (int i = 0; i < 12; i++) t += uniform(); return t - 6; }
private:
    uint32_t seed_;
};

inline puck::Result run(const puck::Config &c, const Scenario &o, puck::Measurement &m) {
    using puck::pi;
    constexpr double timerHz = 80000000, odr = 26666.67;
    const double tickPerRaw = timerHz / odr;
    const double noiseG = o.noiseScale * 75e-6 * std::sqrt(odr / 10);  // noise density over the LPF2 band
    m.begin(c, uint32_t(timerHz));
    Source rnd(o.seed);
    const unsigned total = unsigned(o.durationS * odr);
    const double wanderRate = 2 * pi / 25;  // modulation cycles per revolution
    double theta = 0; unsigned edge = 0, k = 0; bool tachSeen = false;
    int16_t block[16][3];
    for (unsigned i = 0; i < total; i++) {
        const double t = i / odr;
        const double hz = o.rpm / 60 * (1 + o.rpmDriftPct / 100 * t / o.durationS);
        const double omega = 2 * pi * hz;
        const double previous = theta - omega / odr;  // angle of the previous raw sample
        const double tick = i * tickPerRaw;
        if (i == 0 || std::floor(theta / (2 * pi)) > std::floor(previous / (2 * pi))) {
            // Interpolate the once-per-rev crossing between raw samples.
            const double frac = i == 0 ? 1 : (std::floor(theta / (2 * pi)) * 2 * pi - previous) / (theta - previous);
            const double edgeTick = tick - (1 - frac) * tickPerRaw + o.tachJitterUs * 80 * rnd.gauss();
            ++edge;
            if (!(o.tachDropEvery && edge % o.tachDropEvery == 0)) {
                m.tach(uint32_t(int64_t(std::max(0.0, edgeTick))));
                tachSeen = true;
                if (o.tachGlitchEvery && edge % o.tachGlitchEvery == 0) m.tach(uint32_t(int64_t(edgeTick + 4000)));
            }
        }
        const double th = theta;
        theta += omega / odr;
        const double wander = o.phaseWanderDeg * pi / 180 * std::sin(th / 2 / pi * wanderRate);
        const double scale = 1 + o.ampWanderPct / 100 * std::sin(th / 2 / pi * wanderRate);
        const double amp = o.ips / puck::metresToInches * omega / puck::gravity * scale;  // velocity -> accel peak, g
        const double vib = -amp * std::sin(th - o.phaseDeg * pi / 180 + wander) +
                           o.h2G * std::cos(2 * th) + o.h3G * std::sin(3 * th + 1);
        double g[3] = {0.25 * std::cos(2 * th) + 0.05, 0.1 * std::sin(3 * th), 0.02 * std::cos(th)};
        g[o.axis] = o.gravityG + vib;
        if (o.spikeG != 0 && o.spikes > 0 && (i + total / (2 * o.spikes)) % (total / o.spikes) == 0)
            g[o.spikeAxis] += o.spikeG;
        for (int ax = 0; ax < 3; ax++) {
            const double counts = std::round((g[ax] + noiseG * rnd.gauss()) / (accel::mgPerLsb * 0.001));
            block[k][ax] = int16_t(std::max(-32768.0, std::min(32767.0, counts)));  // ADC saturates at the rail
        }
        if (++k == 16) {
            k = 0;
            if (o.gapAtS >= 0 && t >= o.gapAtS && t < o.gapAtS + o.gapMs / 1000) continue;
            accel::Block b; accel::decodeBlock(block, 16, b);
            // Same timestamping as main.cpp: the watermark sample's tick minus 7.5 raw periods.
            puck::Sample s{uint32_t(uint64_t(tick - 7.5 * tickPerRaw + .5)), {b.g[0], b.g[1], b.g[2]}, b.clipped};
            m.sample(s);
        }
    }
    return m.finish(tachSeen);
}
}  // namespace rawsim
