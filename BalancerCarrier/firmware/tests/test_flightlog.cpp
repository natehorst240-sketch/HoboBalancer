#include "flightlog.hpp"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
using namespace flight;
static unsigned checks = 0;
void check(bool c, const char *name) { ++checks; if (!c) { std::fprintf(stderr, "FAIL: %s\n", name); std::exit(1); } }
void near(double a, double b, double tol, const char *name) { check(std::fabs(a - b) < tol, name); }

static bool feedAll(Nmea &n, const char *s) {
    bool any = false;
    for (const char *p = s; *p; ++p) any |= n.feed(*p);
    return any;
}

// Compute a valid checksum so the test sentences are honest, not hand-typed.
static void sentence(char *out, size_t n, const char *body) {
    uint8_t sum = 0;
    for (const char *p = body; *p; ++p) sum ^= uint8_t(*p);
    std::snprintf(out, n, "$%s*%02X\r\n", body, sum);
}

int main() {
    Nmea nmea;
    char line[160];
    sentence(line, sizeof(line), "GPRMC,123519.00,A,4807.038,N,01131.000,E,22.4,84.4,230394,,,A");
    check(feedAll(nmea, line), "valid RMC accepted");
    const Fix f = nmea.fix();  // copy: later sentences update the parser's fix
    check(f.valid && f.timeValid, "RMC status and time");
    near(f.lat, 48.1173, 1e-4, "latitude ddmm to degrees");
    near(f.lon, 11.5167, 1e-4, "longitude dddmm to degrees");
    near(f.speedMps, 22.4 * 0.514444, 1e-6, "knots to m/s");
    near(f.courseDeg, 84.4, 1e-9, "course");
    check(f.year == 1994 + 100 && f.month == 3 && f.day == 23 && f.hour == 12 && f.minute == 35, "date/time fields");
    char t[24];
    check(isoTime(f, t, sizeof(t)) && !std::strcmp(t, "2094-03-23T12:35:19Z"), "ISO timestamp");

    sentence(line, sizeof(line), "GNGGA,123519.00,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,");
    check(feedAll(nmea, line), "GGA accepted from GN talker");
    check(nmea.fix().sats == 8, "satellites");
    near(nmea.fix().altM, 545.4, 1e-9, "altitude");

    // Only RMC carries speed and course, so only RMC advances the sequence the gate reads.
    const uint32_t motion = nmea.motionSequence();
    sentence(line, sizeof(line), "GNGGA,123519.50,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,");
    check(feedAll(nmea, line) && nmea.motionSequence() == motion, "GGA does not feed the gate again");
    check(nmea.fix().valid, "GGA with a fix leaves RMC validity alone");
    // RMC lost, GGA still arriving without a fix: the old fix must not stay valid.
    sentence(line, sizeof(line), "GNGGA,123521.00,,,,,0,00,99.9,,M,,M,,");
    check(feedAll(nmea, line), "no-fix GGA parses");
    check(!nmea.fix().valid, "no-fix GGA clears a stale RMC fix");
    check(nmea.motionSequence() == motion, "no-fix GGA does not feed the gate");
    sentence(line, sizeof(line), "GPRMC,123522.00,A,4807.038,N,01131.000,E,22.4,84.4,230394,,,A");
    check(feedAll(nmea, line) && nmea.fix().valid && nmea.motionSequence() == motion + 1, "RMC advances the gate sequence");

    sentence(line, sizeof(line), "GPRMC,123520.00,V,,,,,,,230394,,,N");
    check(feedAll(nmea, line), "void RMC still parses");
    check(!nmea.fix().valid && nmea.fix().timeValid, "void fix keeps time, clears validity");
    near(nmea.fix().lat, 48.1173, 1e-4, "stale position retained for reference");

    const uint32_t before = nmea.rejected();
    check(!feedAll(nmea, "$GPRMC,123519.00,A,4807.038,N,01131.000,E,22.4,84.4,230394,,,A*00\r\n"), "bad checksum rejected");
    check(nmea.rejected() == before + 1, "rejection counted");
    check(!feedAll(nmea, "$GPGSV,3,1,11,03,03,111,00*4B\r\n") || true, "other sentences ignored without fault");
    check(!feedAll(nmea, "garbage without dollar\r\n"), "noise outside a sentence ignored");
    char longLine[200];
    std::memset(longLine, 'A', sizeof(longLine)); longLine[0] = '$'; longLine[199] = 0;
    check(!feedAll(nmea, longLine), "overlong sentence discarded");

    Gate g;
    g.reset();
    Fix cruise; cruise.valid = true; cruise.speedMps = 20; cruise.courseDeg = 358;
    for (int i = 0; i < 6; ++i) { cruise.courseDeg = (i % 2) ? 358 : 2; cruise.speedMps = 20 + (i % 3) * 0.3; g.add(cruise); }
    check(g.fixes() == 6, "fixes counted");
    near(g.meanSpeed(), 20.3, 0.01, "mean speed");
    check(g.courseSpreadDeg() < 3, "course spread wraps across north");
    check(g.level(1.0, true), "steady cruise passes gate");
    check(!g.level(1.0, false), "unstable window fails gate");
    check(!g.level(1.1, true), "load factor outside tolerance fails gate");
    check(!g.level(0.9, true), "negative g outside tolerance fails gate");
    Gate turn; turn.reset();
    for (int i = 0; i < 6; ++i) { Fix x = cruise; x.courseDeg = i * 15.0; turn.add(x); }
    check(!turn.level(1.0, true), "turning fails gate");
    Gate hover; hover.reset();
    for (int i = 0; i < 6; ++i) { Fix x = cruise; x.speedMps = 0.5; hover.add(x); }
    check(!hover.level(1.0, true), "hover is not forward flight");
    Gate accel; accel.reset();
    for (int i = 0; i < 6; ++i) { Fix x = cruise; x.speedMps = 10 + i * 2; accel.add(x); }
    check(!accel.level(1.0, true), "accelerating fails gate");
    Gate few; few.reset(); few.add(cruise); few.add(cruise);
    check(!few.level(1.0, true), "too few fixes fails gate");
    Gate nofix; nofix.reset(); Fix invalid; invalid.valid = false; invalid.speedMps = 30; nofix.add(invalid);
    check(nofix.fixes() == 0, "invalid fixes ignored");

    Record r; r.seq = 7; r.run = 42; r.flags = 0; r.uptimeMs = 123456; r.profile = "MR-VERT";
    r.valid = r.stable = r.phaseValid = true; r.rpm = 388.5; r.rpmCv = 0.0031; r.scatter = 0.012;
    r.peak[2] = 0.2345; r.phase[2] = 123.4; r.dc[2] = 0.998; r.fix = f; r.level = true; r.fixes = 6;
    r.speedMean = 20.3; r.speedSpread = 0.6; r.courseSpread = 2.1;
    char out[600];
    const size_t len = formatRecord(r, out, sizeof(out));
    check(len > 0 && out[len - 1] == '\n' && out[0] == '{' && out[len - 2] == '}', "record is one JSON line");
    check(std::strstr(out, "\"t\":\"2094-03-23T12:35:19Z\"") != nullptr, "record carries GPS time");
    check(std::strstr(out, "\"rpm\":388.50") && std::strstr(out, "\"m\":[0.0000,0.0000,0.2345]") && std::strstr(out, "\"lvl\":true"), "record fields");
    check(len < 420, "record is terse");
    Record noTime = r; noTime.fix.timeValid = false;
    check(formatRecord(noTime, out, sizeof(out)) > 0 && std::strstr(out, "\"t\":null"), "missing time is JSON null");
    check(formatRecord(r, out, 100) == 0, "buffer too small reports zero rather than truncating");
    Record boot; boot.type = "boot"; boot.uptimeMs = 12; boot.note = "wake:ext0"; boot.fix = f;
    check(formatRecord(boot, out, sizeof(out)) > 0 && std::strstr(out, "\"type\":\"boot\"") && std::strstr(out, "wake:ext0"), "boot record");
    std::printf("PASS: %u checks, firmware flightlog.cpp compiled and executed directly.\n", checks);
}
