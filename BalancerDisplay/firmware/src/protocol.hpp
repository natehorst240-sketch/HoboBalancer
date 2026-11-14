#pragma once
// Carrier protocol: newline-delimited JSON over any Transport. This file has no ESP
// dependencies and is compiled into the host tests exactly as it runs on the display.
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <functional>

namespace proto {
// The carrier's largest message is 3072 bytes plus newline (BalancerCarrier main.cpp, Message).
constexpr size_t maxLine = 4096;
constexpr size_t maxCommand = 255;  // one BLE write

// Reassembles lines from fragments of any size (BLE notifications are at most 180 bytes). A
// line longer than maxLine, or any bytes before the first newline after such an overflow, are
// discarded and counted: a truncated line is never a measurement.
class LineAssembler {
public:
    void feed(const uint8_t *bytes, size_t n, const std::function<void(const char *, size_t)> &onLine);
    uint32_t dropped() const { return dropped_; }
    void reset() { len_ = 0; overflow_ = false; }
private:
    char buf_[maxLine + 1]{};
    size_t len_ = 0;
    bool overflow_ = false;
    uint32_t dropped_ = 0;
};

enum class Type : uint8_t { Unknown, Status, Result, Started, Error, Profile, History, Comparison };
enum class Quality : uint8_t { Unreliable, DirectionOnly, StableVector };
constexpr double nan = NAN;

// Carrier fault flags (BalancerCarrier measurement.hpp). Kept in sync by hand; the test checks
// the values the carrier documents in its README.
enum Flag : uint32_t {
    NoTach = 1, TooFewRevs = 2, SampleGap = 4, Clipping = 8, IoError = 16, QueueOverflow = 32,
    RpmUnstable = 64, VibrationUnstable = 128, WeakSignal = 256, AxisUnconfirmed = 512,
    TimingError = 1024, Cancelled = 2048, PhaseUnstable = 4096, SpeedBandUnconfirmed = 8192,
    ExtraTachPulses = 16384
};
const char *flagName(uint32_t bit);  // one bit -> short name, "?" if unknown

struct Config {
    char axis = '?'; int sign = 0, phaseDirection = 0;
    double gain = nan, phaseOffsetDeg = nan, durationS = nan, minRpm = nan, maxRpm = nan;
    bool axisConfirmed = false, speedBandConfirmed = false;
};
struct Axis { char name = '?'; double ipsPeak = nan, phaseDeg = nan, dcG = nan; bool clipped = false; };
struct Result {
    uint32_t runId = 0, sequence = 0, flags = 0, revolutions = 0, rejectedEdges = 0, extraEdges = 0;
    char profile[16]{};
    bool continuous = false, valid = false, stable = false, phaseValid = false, directionValid = false;
    Quality quality = Quality::Unreliable;
    double rpm = nan, rpmCv = nan, peak = nan, rms = nan, phase = nan;  // phase NaN when withheld
    double vectorScatter = nan, amplitudeScatter = nan, phaseScatterDeg = nan, deltaIps = nan;
    Axis axes[3];
    char message[96]{};
    Config config;
};
struct Status {
    char profile[16]{}, sensor[24]{}, wake[24]{};
    bool acquiring = false, continuous = false, sensorOk = false, flight = false, usb = false;
    bool inputPresent = false, charging = false, fuelGaugeOk = false, gpsPresent = false, gpsFix = false;
    uint32_t sequence = 0, outputDrops = 0, captureDrops = 0, queueDrops = 0, ioErrors = 0, lateReads = 0;
    double batteryV = nan, batterySoc = nan, sampleRateHz = nan;
    double xyz[3] = {nan, nan, nan};  // live g, NaN when the carrier has no fresh sample
    bool haveXyz = false;
    Config config;
};
struct Message {
    Type type = Type::Unknown;
    char text[160]{};      // "message" field: error text, profile name, started profile
    char firmware[16]{};
    Result result;         // valid when type == Result
    Status status;         // valid when type == Status
};

// Parse one line. Returns false when it is not a JSON object with a "type" string; such lines
// are ignored upstream. Unknown types return true with type Unknown.
bool parse(const char *line, size_t length, Message &out);

// Command builders. Each writes a complete line with newline into buf (at least maxCommand+1)
// and returns its length, or 0 if it would not fit a single BLE write.
size_t cmdStatus(char *buf, size_t cap);
size_t cmdStart(char *buf, size_t cap, bool continuous);
size_t cmdStop(char *buf, size_t cap);
size_t cmdProfile(char *buf, size_t cap, const char *name);  // "MR-VERT" or "TR-VERT"
size_t cmdHistory(char *buf, size_t cap);
// Only the fields given (non-NaN / non-zero axis) are sent; the carrier applies the rest unchanged.
struct ConfigChange { char axis = 0; int sign = 0; double minRpm = nan, maxRpm = nan, durationS = nan, gain = nan, phaseOffsetDeg = nan; };
size_t cmdConfig(char *buf, size_t cap, const ConfigChange &c);
}  // namespace proto
