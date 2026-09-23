#pragma once
// In-flight logging support with no ESP dependencies: NMEA parsing, the
// level-flight gate, and the terse one-line record format. Compiled and tested
// unchanged on the host (tests/test_flightlog.cpp).
#include <cstddef>
#include <cstdint>

namespace flight {

struct Fix {
    bool valid = false;        // RMC status A with a position
    bool timeValid = false;    // RMC date and time present
    double lat = 0, lon = 0;   // degrees, south/west negative
    double speedMps = 0;       // ground speed
    double courseDeg = 0;      // track over ground, 0-360
    double altM = 0;           // GGA MSL altitude
    int sats = 0;              // GGA satellites used
    int year = 0, month = 0, day = 0, hour = 0, minute = 0;
    double second = 0;
};

// Incremental NMEA 0183 parser for RMC and GGA from any talker (GP/GN/GA...).
class Nmea {
public:
    // Feed one byte; returns true when a complete, checksum-valid RMC or GGA updated the fix.
    bool feed(char c);
    const Fix &fix() const { return fix_; }
    // Advances once per parsed RMC, the only sentence carrying speed and course. The flight
    // gate samples on this, so a GGA in the same epoch never counts the fix twice.
    uint32_t motionSequence() const { return motion_; }
    uint32_t sentences() const { return sentences_; }
    uint32_t rejected() const { return rejected_; }
private:
    bool parseSentence();
    bool parseRmc(char **f, int n);
    bool parseGga(char **f, int n);
    char buf_[120]{};
    unsigned len_ = 0;
    bool inSentence_ = false;
    Fix fix_{};
    uint32_t sentences_ = 0, rejected_ = 0, motion_ = 0;
};

// Accumulates fixes over one acquisition window and decides whether the
// aircraft was in steady level forward flight, so the window can be used as a
// balance sample. Thresholds are deliberately conservative.
struct Gate {
    static constexpr double minSpeedMps = 2.0;      // must actually be moving
    static constexpr double maxSpeedSpreadMps = 1.5;
    static constexpr double maxCourseSpreadDeg = 10.0;
    static constexpr double dcTolerance = 0.06;     // |vertical DC| within 1 g +/- this
    static constexpr unsigned minFixes = 3;

    void reset();
    void add(const Fix &f);       // ignored unless f.valid
    unsigned fixes() const { return count_; }
    double meanSpeed() const;
    double speedSpread() const { return count_ ? maxSpeed_ - minSpeed_ : 0; }
    double courseSpreadDeg() const;   // circular standard deviation, degrees
    // dcVertical: mean gravity reading on the selected axis in g, sign already applied so up is +1.
    bool level(double dcVertical, bool stable) const;
private:
    unsigned count_ = 0;
    double sumSpeed_ = 0, minSpeed_ = 0, maxSpeed_ = 0, sumCos_ = 0, sumSin_ = 0;
};

// One terse log record. Numbers are raw firmware values; nothing here is calibrated.
struct Record {
    const char *type = "log";     // "log" (window) or "boot"
    uint32_t seq = 0, run = 0, flags = 0, uptimeMs = 0;
    const char *profile = "";
    const char *note = nullptr;   // boot records: wake cause etc.
    bool valid = false, stable = false, phaseValid = false;
    double rpm = 0, rpmCv = 0, scatter = 0;
    double peak[3]{}, phase[3]{}, dc[3]{};
    int axis = 2, sign = 1;
    Fix fix{};                    // latest fix at the end of the window
    bool level = false;
    unsigned fixes = 0;
    double speedMean = 0, speedSpread = 0, courseSpread = 0;
};

// Writes "YYYY-MM-DDTHH:MM:SSZ" or returns false when the fix carries no time.
bool isoTime(const Fix &f, char *out, size_t n);
// Formats one JSON line (with trailing newline) into out; returns length or 0 if it did not fit.
size_t formatRecord(const Record &r, char *out, size_t n);

}  // namespace flight
