#include "protocol.hpp"
#include "cJSON.h"
#include <cstdio>
#include <cstring>

namespace proto {
void LineAssembler::feed(const uint8_t *bytes, size_t n, const std::function<void(const char *, size_t)> &onLine) {
    for (size_t i = 0; i < n; ++i) {
        const char c = char(bytes[i]);
        if (c == '\n') {
            if (overflow_) { overflow_ = false; ++dropped_; }
            else if (len_) { buf_[len_] = 0; onLine(buf_, len_); }
            len_ = 0;
            continue;
        }
        if (overflow_) continue;
        if (c == '\r') continue;
        if (len_ == maxLine) { overflow_ = true; len_ = 0; continue; }
        buf_[len_++] = c;
    }
}

const char *flagName(uint32_t bit) {
    switch (bit) {
        case NoTach: return "no tach"; case TooFewRevs: return "few revs"; case SampleGap: return "sample gap";
        case Clipping: return "overrange"; case IoError: return "sensor I/O"; case QueueOverflow: return "queue overflow";
        case RpmUnstable: return "RPM unstable"; case VibrationUnstable: return "amplitude unstable";
        case WeakSignal: return "weak signal"; case AxisUnconfirmed: return "axis unconfirmed";
        case TimingError: return "timing"; case Cancelled: return "cancelled"; case PhaseUnstable: return "phase unstable";
        case SpeedBandUnconfirmed: return "speed band unset"; case ExtraTachPulses: return "extra tach pulses";
        default: return "?";
    }
}

namespace {
double num(const cJSON *o, const char *k) { const cJSON *v = cJSON_GetObjectItemCaseSensitive(o, k); return cJSON_IsNumber(v) ? v->valuedouble : nan; }
uint32_t u32(const cJSON *o, const char *k) { const double d = num(o, k); return std::isfinite(d) && d >= 0 ? uint32_t(d) : 0; }
bool boolean(const cJSON *o, const char *k) { return cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(o, k)); }
void str(const cJSON *o, const char *k, char *dst, size_t cap) {
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(o, k);
    if (cJSON_IsString(v) && v->valuestring) { std::strncpy(dst, v->valuestring, cap - 1); dst[cap - 1] = 0; } else dst[0] = 0;
}
void config(const cJSON *o, Config &c) {
    if (!cJSON_IsObject(o)) return;
    char a[4]; str(o, "axis", a, sizeof a); c.axis = a[0] ? a[0] : '?';
    const double s = num(o, "sign"), d = num(o, "phase_direction");
    c.sign = std::isfinite(s) ? int(s) : 0; c.phaseDirection = std::isfinite(d) ? int(d) : 0;
    c.gain = num(o, "gain"); c.phaseOffsetDeg = num(o, "phase_offset_deg"); c.durationS = num(o, "duration_s");
    c.minRpm = num(o, "min_rpm"); c.maxRpm = num(o, "max_rpm");
    c.axisConfirmed = boolean(o, "axis_confirmed"); c.speedBandConfirmed = boolean(o, "speed_band_confirmed");
}
void result(const cJSON *j, Result &r) {
    r.runId = u32(j, "run_id"); r.sequence = u32(j, "sequence"); r.flags = u32(j, "flags");
    r.revolutions = u32(j, "revolutions"); r.rejectedEdges = u32(j, "rejected_tach_edges"); r.extraEdges = u32(j, "extra_tach_edges");
    str(j, "profile", r.profile, sizeof r.profile); str(j, "message", r.message, sizeof r.message);
    r.continuous = boolean(j, "continuous"); r.valid = boolean(j, "valid"); r.stable = boolean(j, "stable");
    r.phaseValid = boolean(j, "phase_valid"); r.directionValid = boolean(j, "direction_valid");
    char q[24]; str(j, "quality", q, sizeof q);
    r.quality = !std::strcmp(q, "stable_vector") ? Quality::StableVector : !std::strcmp(q, "direction_only") ? Quality::DirectionOnly : Quality::Unreliable;
    r.rpm = num(j, "rpm"); r.rpmCv = num(j, "rpm_cv"); r.peak = num(j, "adjusted_ips_peak"); r.rms = num(j, "adjusted_ips_rms");
    r.phase = num(j, "adjusted_velocity_phase_deg");  // null -> NaN: withheld
    r.vectorScatter = num(j, "raw_vector_scatter_ips_peak"); r.amplitudeScatter = num(j, "raw_amplitude_scatter_ips_peak");
    r.phaseScatterDeg = num(j, "per_rev_phase_scatter_deg"); r.deltaIps = num(j, "raw_delta_ips_peak");
    const cJSON *axes = cJSON_GetObjectItemCaseSensitive(j, "raw_axes");
    int i = 0; const cJSON *a;
    cJSON_ArrayForEach(a, axes) {
        if (i >= 3) break;
        char n[4]; str(a, "axis", n, sizeof n); r.axes[i].name = n[0] ? n[0] : '?';
        r.axes[i].ipsPeak = num(a, "ips_peak"); r.axes[i].phaseDeg = num(a, "velocity_phase_deg"); r.axes[i].dcG = num(a, "dc_g");
        r.axes[i].clipped = boolean(a, "clipped"); ++i;
    }
    config(cJSON_GetObjectItemCaseSensitive(j, "config"), r.config);
}
void status(const cJSON *j, Status &s) {
    str(j, "profile", s.profile, sizeof s.profile); str(j, "sensor", s.sensor, sizeof s.sensor); str(j, "wake", s.wake, sizeof s.wake);
    s.acquiring = boolean(j, "acquiring"); s.continuous = boolean(j, "continuous"); s.sensorOk = boolean(j, "sensor_ok");
    s.flight = boolean(j, "flight"); s.usb = boolean(j, "usb"); s.inputPresent = boolean(j, "input_present");
    s.charging = boolean(j, "charging"); s.fuelGaugeOk = boolean(j, "fuel_gauge_ok");
    s.sequence = u32(j, "sequence"); s.outputDrops = u32(j, "output_drops"); s.captureDrops = u32(j, "capture_drops");
    s.queueDrops = u32(j, "sample_queue_drops"); s.ioErrors = u32(j, "i2c_errors"); s.lateReads = u32(j, "late_reads");
    s.batteryV = num(j, "battery_v"); s.batterySoc = num(j, "battery_soc_pct"); s.sampleRateHz = num(j, "sample_rate_hz");
    const cJSON *g = cJSON_GetObjectItemCaseSensitive(j, "gps");
    if (cJSON_IsObject(g)) { s.gpsPresent = boolean(g, "present"); s.gpsFix = boolean(g, "fix"); }
    const cJSON *xyz = cJSON_GetObjectItemCaseSensitive(j, "latest_xyz_g");
    s.haveXyz = cJSON_IsArray(xyz) && cJSON_GetArraySize(xyz) == 3;
    for (int i = 0; i < 3; ++i) {
        const cJSON *v = s.haveXyz ? cJSON_GetArrayItem(xyz, i) : nullptr;
        s.xyz[i] = cJSON_IsNumber(v) ? v->valuedouble : nan;
    }
    config(cJSON_GetObjectItemCaseSensitive(j, "config"), s.config);
}
size_t finish(char *buf, size_t cap, int n) {
    if (n <= 0 || size_t(n) >= cap || size_t(n) > maxCommand) { if (cap) buf[0] = 0; return 0; }
    return size_t(n);
}
}  // namespace

bool parse(const char *line, size_t length, Message &out) {
    out = Message{};
    cJSON *j = cJSON_ParseWithLength(line, length);
    if (!j) return false;
    bool ok = false;
    if (cJSON_IsObject(j)) {
        char type[24]; str(j, "type", type, sizeof type);
        if (type[0]) {
            ok = true;
            str(j, "firmware", out.firmware, sizeof out.firmware);
            str(j, "message", out.text, sizeof out.text);
            if (!std::strcmp(type, "status")) { out.type = Type::Status; status(j, out.status); }
            else if (!std::strcmp(type, "result")) { out.type = Type::Result; result(j, out.result); }
            else if (!std::strcmp(type, "started")) out.type = Type::Started;
            else if (!std::strcmp(type, "error")) out.type = Type::Error;
            else if (!std::strcmp(type, "profile")) out.type = Type::Profile;
            else if (!std::strcmp(type, "history")) out.type = Type::History;
            else if (!std::strcmp(type, "comparison_proposal")) out.type = Type::Comparison;
        }
    }
    cJSON_Delete(j);
    return ok;
}

size_t cmdStatus(char *buf, size_t cap) { return finish(buf, cap, std::snprintf(buf, cap, "{\"cmd\":\"status\"}\n")); }
size_t cmdStop(char *buf, size_t cap) { return finish(buf, cap, std::snprintf(buf, cap, "{\"cmd\":\"stop\"}\n")); }
size_t cmdHistory(char *buf, size_t cap) { return finish(buf, cap, std::snprintf(buf, cap, "{\"cmd\":\"history\"}\n")); }
size_t cmdStart(char *buf, size_t cap, bool continuous) {
    return finish(buf, cap, continuous ? std::snprintf(buf, cap, "{\"cmd\":\"start\",\"continuous\":true}\n") : std::snprintf(buf, cap, "{\"cmd\":\"start\"}\n"));
}
size_t cmdProfile(char *buf, size_t cap, const char *name) {
    if (std::strcmp(name, "MR-VERT") && std::strcmp(name, "TR-VERT")) { if (cap) buf[0] = 0; return 0; }
    return finish(buf, cap, std::snprintf(buf, cap, "{\"cmd\":\"profile\",\"value\":\"%s\"}\n", name));
}
size_t cmdConfig(char *buf, size_t cap, const ConfigChange &c) {
    cJSON *j = cJSON_CreateObject();
    cJSON_AddStringToObject(j, "cmd", "config");
    if (c.axis == 'X' || c.axis == 'Y' || c.axis == 'Z') { const char a[2] = {c.axis, 0}; cJSON_AddStringToObject(j, "axis", a); }
    if (c.sign == 1 || c.sign == -1) cJSON_AddNumberToObject(j, "sign", c.sign);
    if (std::isfinite(c.minRpm)) cJSON_AddNumberToObject(j, "min_rpm", c.minRpm);
    if (std::isfinite(c.maxRpm)) cJSON_AddNumberToObject(j, "max_rpm", c.maxRpm);
    if (std::isfinite(c.durationS)) cJSON_AddNumberToObject(j, "duration_s", c.durationS);
    if (std::isfinite(c.gain)) cJSON_AddNumberToObject(j, "gain", c.gain);
    if (std::isfinite(c.phaseOffsetDeg)) cJSON_AddNumberToObject(j, "phase_offset_deg", c.phaseOffsetDeg);
    const bool printed = cJSON_PrintPreallocated(j, buf, int(cap > 2 ? cap - 2 : 0), false);
    cJSON_Delete(j);
    if (!printed) { if (cap) buf[0] = 0; return 0; }
    const size_t n = std::strlen(buf);
    buf[n] = '\n'; buf[n + 1] = 0;
    return finish(buf, cap, int(n + 1));
}
}  // namespace proto
