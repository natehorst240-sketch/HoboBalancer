#pragma once
#include <cstddef>
#include <cstdint>

namespace puck {
constexpr double pi = 3.14159265358979323846;
constexpr double gravity = 9.80665;
constexpr double metresToInches = 39.37007874015748;
constexpr double sampleRate = 26666.67 / 16;  // IIS3DWB ODR decimated by 16 = 1666.7 Hz
constexpr unsigned maxCycleSamples = 1100;
enum Fault : uint32_t {
    NoTach=1, TooFewRevs=2, SampleGap=4, Clipping=8, IoError=16,
    QueueOverflow=32, RpmUnstable=64, VibrationUnstable=128,
    WeakSignal=256, AxisUnconfirmed=512, TimingError=1024, Cancelled=2048
};
struct Config {
    int axis=2, sign=1, phaseDirection=1;
    bool axisConfirmed=false;
    double gain=1, phaseOffsetDeg=0, durationS=12, minRpm=120, maxRpm=6000;
};
bool validConfig(const Config &c);
double wrapDegrees(double x);
struct Sample { uint32_t tick; float g[3]; };
struct Result {
    uint32_t flags=0, revolutions=0, samples=0, rejectedEdges=0;
    double rpm=0, rpmCv=0, vectorScatter=0;
    double rawPeak[3]{}, rawPhase[3]{}, dcG[3]{};
    double peak=0, rms=0, phase=0, accelerationPhase=0;
    bool valid=false, stable=false, phaseValid=false;
};
// No ESP dependencies: exactly the same implementation is tested on the host.
class Measurement {
public:
    void begin(const Config &config, uint32_t timerHz);
    void sample(const Sample &s);
    bool tach(uint32_t tick); // true only when an edge is accepted as a timing anchor
    double tachTimeoutSeconds() const;
    void fault(uint32_t bits) { flags_ |= bits; }
    Result finish(bool tachRecent) const;
private:
    void fitCycle(uint32_t end, uint32_t period);
    Config config_{};
    Sample samples_[maxCycleSamples]{};
    unsigned count_=0, revs_=0, totalSamples_=0, rejected_=0;
    uint32_t hz_=0, previousTach_=0, previousSample_=0, lastPeriod_=0, flags_=0;
    bool haveTach_=false, haveSample_=false;
    double sumPeriod_=0, sumPeriod2_=0;
    double sumC_[3]{},sumS_[3]{},sumPower_[3]{},sumDc_[3]{};
};
}
