#include "flightlog.hpp"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace flight {
namespace {
constexpr double pi = 3.14159265358979323846;

int split(char *s, char **fields, int max) {
    int n = 0;
    fields[n++] = s;
    for (char *p = s; *p && n < max; ++p)
        if (*p == ',') { *p = 0; fields[n++] = p + 1; }
    return n;
}

bool number(const char *s, double &out) {
    if (!*s) return false;
    char *end = nullptr;
    out = std::strtod(s, &end);
    return end != s && *end == 0 && std::isfinite(out);
}

// ddmm.mmmm / dddmm.mmmm with hemisphere letter to signed degrees.
bool coordinate(const char *s, const char *hemi, double &out) {
    double v;
    if (!number(s, v) || !*hemi) return false;
    const double deg = std::floor(v / 100.0), minutes = v - deg * 100.0;
    if (minutes < 0 || minutes >= 60) return false;
    out = deg + minutes / 60.0;
    if (*hemi == 'S' || *hemi == 'W') out = -out;
    else if (*hemi != 'N' && *hemi != 'E') return false;
    return true;
}
}  // namespace

bool Nmea::feed(char c) {
    if (c == '$') { inSentence_ = true; len_ = 0; return false; }
    if (!inSentence_) return false;
    if (c == '\r' || c == '\n') {
        inSentence_ = false;
        if (!len_) return false;
        buf_[len_] = 0;
        const bool ok = parseSentence();
        len_ = 0;
        return ok;
    }
    if (len_ >= sizeof(buf_) - 1) { inSentence_ = false; len_ = 0; ++rejected_; return false; }
    buf_[len_++] = c;
    return false;
}

bool Nmea::parseSentence() {
    char *star = std::strchr(buf_, '*');
    if (!star || std::strlen(star) != 3) { ++rejected_; return false; }
    uint8_t sum = 0;
    for (char *p = buf_; p < star; ++p) sum ^= uint8_t(*p);
    char hex[3] = {star[1], star[2], 0};
    char *end = nullptr;
    const long given = std::strtol(hex, &end, 16);
    if (*end || given != sum) { ++rejected_; return false; }
    *star = 0;
    char *fields[24];
    const int n = split(buf_, fields, 24);
    const char *id = fields[0];
    if (std::strlen(id) != 5) { ++rejected_; return false; }
    const char *type = id + 2;
    bool ok = false;
    if (!std::strcmp(type, "RMC")) ok = parseRmc(fields, n);
    else if (!std::strcmp(type, "GGA")) ok = parseGga(fields, n);
    else return false;  // other sentences are simply ignored, not counted as rejected
    if (ok) ++sentences_; else ++rejected_;
    return ok;
}

// $xxRMC,hhmmss.ss,A,ddmm.mm,N,dddmm.mm,E,speed_knots,course,ddmmyy,...
bool Nmea::parseRmc(char **f, int n) {
    if (n < 10) return false;
    Fix next = fix_;
    next.valid = f[2][0] == 'A';
    double lat = 0, lon = 0;
    if (next.valid) {
        if (!coordinate(f[3], f[4], lat) || !coordinate(f[5], f[6], lon)) return false;
        next.lat = lat; next.lon = lon;
        double knots = 0, course = 0;
        if (!number(f[7], knots)) return false;
        next.speedMps = knots * 0.514444;
        next.courseDeg = number(f[8], course) ? std::fmod(std::fmod(course, 360.0) + 360.0, 360.0) : next.courseDeg;
    }
    next.timeValid = false;
    if (std::strlen(f[1]) >= 6 && std::strlen(f[9]) == 6) {
        double t = 0;
        if (!number(f[1], t)) return false;
        const int hh = int(t / 10000), mm = int(t / 100) % 100;
        const double ss = t - hh * 10000 - mm * 100;
        const int dd = (f[9][0] - '0') * 10 + (f[9][1] - '0');
        const int mo = (f[9][2] - '0') * 10 + (f[9][3] - '0');
        const int yy = (f[9][4] - '0') * 10 + (f[9][5] - '0');
        if (hh < 24 && mm < 60 && ss < 61 && dd >= 1 && dd <= 31 && mo >= 1 && mo <= 12) {
            next.hour = hh; next.minute = mm; next.second = ss;
            next.day = dd; next.month = mo; next.year = 2000 + yy;
            next.timeValid = true;
        }
    }
    fix_ = next;
    ++motion_;
    return true;
}

// $xxGGA,hhmmss.ss,lat,N,lon,E,quality,numSats,hdop,alt,M,...
bool Nmea::parseGga(char **f, int n) {
    if (n < 10) return false;
    // Quality 0 (or empty) is the receiver saying it has no fix. If RMC has stopped, this is
    // the only sentence still arriving, so it must clear validity rather than leave the last
    // RMC position standing. A nonzero quality leaves validity to RMC.
    if (f[6][0] == 0 || f[6][0] == '0') fix_.valid = false;
    double sats = 0, alt = 0;
    if (!number(f[7], sats)) return false;
    fix_.sats = int(sats);
    if (number(f[9], alt)) fix_.altM = alt;
    return true;
}

void Gate::reset() { count_ = 0; sumSpeed_ = minSpeed_ = maxSpeed_ = sumCos_ = sumSin_ = 0; }

void Gate::add(const Fix &f) {
    if (!f.valid) return;
    if (!count_) minSpeed_ = maxSpeed_ = f.speedMps;
    minSpeed_ = std::fmin(minSpeed_, f.speedMps);
    maxSpeed_ = std::fmax(maxSpeed_, f.speedMps);
    sumSpeed_ += f.speedMps;
    const double a = f.courseDeg * pi / 180.0;
    sumCos_ += std::cos(a); sumSin_ += std::sin(a);
    ++count_;
}

double Gate::meanSpeed() const { return count_ ? sumSpeed_ / count_ : 0; }

double Gate::courseSpreadDeg() const {
    if (count_ < 2) return 0;
    const double r = std::hypot(sumCos_, sumSin_) / count_;
    if (r >= 1.0) return 0;
    if (r <= 1e-9) return 180;
    return std::sqrt(-2.0 * std::log(r)) * 180.0 / pi;
}

bool Gate::level(double dcVertical, bool stable) const {
    return stable && count_ >= minFixes && meanSpeed() >= minSpeedMps &&
           speedSpread() <= maxSpeedSpreadMps && courseSpreadDeg() <= maxCourseSpreadDeg &&
           std::fabs(dcVertical - 1.0) <= dcTolerance;
}

bool isoTime(const Fix &f, char *out, size_t n) {
    if (!f.timeValid) return false;
    return std::snprintf(out, n, "%04d-%02d-%02dT%02d:%02d:%02dZ", f.year, f.month, f.day,
                         f.hour, f.minute, int(f.second)) > 0;
}

size_t formatRecord(const Record &r, char *out, size_t n) {
    char t[24];
    const bool hasTime = isoTime(r.fix, t, sizeof(t));
    const char *axes = "XYZ";
    int len;
    if (!std::strcmp(r.type, "boot")) {
        len = std::snprintf(out, n, "{\"type\":\"boot\",\"t\":%s%s%s,\"up\":%lu,\"note\":\"%s\"}\n",
                            hasTime ? "\"" : "", hasTime ? t : "null", hasTime ? "\"" : "",
                            (unsigned long)r.uptimeMs, r.note ? r.note : "");
    } else {
        len = std::snprintf(out, n,
            "{\"type\":\"log\",\"seq\":%lu,\"run\":%lu,\"t\":%s%s%s,\"up\":%lu,\"prof\":\"%s\","
            "\"ax\":\"%c\",\"sg\":%d,\"v\":%s,\"s\":%s,\"pv\":%s,\"f\":%lu,"
            "\"rpm\":%.2f,\"cv\":%.4f,\"m\":[%.4f,%.4f,%.4f],\"p\":[%.1f,%.1f,%.1f],"
            "\"dc\":[%.3f,%.3f,%.3f],\"sc\":%.4f,"
            "\"fix\":%s,\"lat\":%.6f,\"lon\":%.6f,\"gs\":%.2f,\"crs\":%.1f,\"alt\":%.1f,\"sat\":%d,"
            "\"lvl\":%s,\"nfix\":%u,\"gsm\":%.2f,\"gss\":%.2f,\"css\":%.1f}\n",
            (unsigned long)r.seq, (unsigned long)r.run, hasTime ? "\"" : "", hasTime ? t : "null",
            hasTime ? "\"" : "", (unsigned long)r.uptimeMs, r.profile, axes[r.axis], r.sign,
            r.valid ? "true" : "false", r.stable ? "true" : "false", r.phaseValid ? "true" : "false",
            (unsigned long)r.flags, r.rpm, r.rpmCv, r.peak[0], r.peak[1], r.peak[2],
            r.phase[0], r.phase[1], r.phase[2], r.dc[0], r.dc[1], r.dc[2], r.scatter,
            r.fix.valid ? "true" : "false", r.fix.lat, r.fix.lon, r.fix.speedMps, r.fix.courseDeg,
            r.fix.altM, r.fix.sats, r.level ? "true" : "false", r.fixes, r.speedMean, r.speedSpread,
            r.courseSpread);
    }
    if (len <= 0 || size_t(len) >= n) return 0;
    return size_t(len);
}

}  // namespace flight
