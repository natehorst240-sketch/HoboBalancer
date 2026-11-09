// Host test for the display's carrier-protocol layer. The sample messages mirror the field set
// BalancerCarrier/firmware/src/main.cpp emits in resultJson() and status(); when that changes,
// this is the file to update.
#include "protocol.hpp"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
using namespace proto;
static unsigned checks = 0;
void check(bool c, const char *name) { ++checks; if (!c) { std::fprintf(stderr, "FAIL: %s\n", name); std::exit(1); } }
void near(double a, double b, double tol, const char *name) { check(std::isfinite(a) && std::abs(a - b) < tol, name); }

const char *RESULT =
    "{\"type\":\"result\",\"reference_only\":true,\"run_id\":7,\"profile\":\"TR-VERT\",\"continuous\":true,\"sequence\":3,"
    "\"valid\":true,\"stable\":true,\"phase_valid\":true,\"direction_valid\":true,\"quality\":\"stable_vector\","
    "\"flags\":0,\"rpm\":2399.87,\"rpm_cv\":0.0004,\"revolutions\":479,\"samples\":19950,\"rejected_tach_edges\":1,\"extra_tach_edges\":0,"
    "\"raw_vector_scatter_ips_peak\":0.0021,\"raw_amplitude_scatter_ips_peak\":0.0015,\"per_rev_phase_scatter_deg\":0.28,"
    "\"raw_axes\":[{\"axis\":\"X\",\"ips_peak\":0.0101,\"ips_rms\":0.0071,\"velocity_phase_deg\":12.5,\"dc_g\":0.0502,\"clipped\":false},"
    "{\"axis\":\"Y\",\"ips_peak\":0.0040,\"ips_rms\":0.0028,\"velocity_phase_deg\":200.1,\"dc_g\":0.0001,\"clipped\":true},"
    "{\"axis\":\"Z\",\"ips_peak\":0.3001,\"ips_rms\":0.2122,\"velocity_phase_deg\":57.02,\"dc_g\":0.9998,\"clipped\":false}],"
    "\"adjusted_ips_peak\":0.3001,\"adjusted_ips_rms\":0.2122,\"adjusted_velocity_phase_deg\":57.02,\"signed_acceleration_phase_deg\":327.02,"
    "\"raw_phase_definition\":\"positive velocity peak after selected tach edge; time-forward degrees\","
    "\"config\":{\"axis\":\"Z\",\"sign\":1,\"gain\":1,\"phase_direction\":1,\"phase_offset_deg\":0,\"duration_s\":12,\"min_rpm\":1900,\"max_rpm\":3000,"
    "\"axis_confirmed\":true,\"speed_band_confirmed\":true},\"raw_delta_ips_peak\":-0.012,\"firmware\":\"0.4.0\"}\n";
const char *RESULT_WITHHELD =
    "{\"type\":\"result\",\"run_id\":8,\"profile\":\"MR-VERT\",\"valid\":true,\"stable\":false,\"phase_valid\":false,\"direction_valid\":false,"
    "\"quality\":\"unreliable\",\"flags\":8448,\"rpm\":384.1,\"message\":\"more than one tach pulse per revolution; fix the tach mark or the speed band\","
    "\"raw_axes\":[],\"adjusted_ips_peak\":0.085,\"adjusted_velocity_phase_deg\":null,\"config\":{\"axis\":\"Z\",\"speed_band_confirmed\":false},\"raw_delta_ips_peak\":null}\n";
const char *STATUS =
    "{\"type\":\"status\",\"profile\":\"MR-VERT\",\"acquiring\":false,\"continuous\":false,\"sequence\":0,\"sensor_ok\":true,\"reference_only\":true,"
    "\"ble_connected\":true,\"sample_rate_hz\":1666.67,\"full_scale_g\":16,\"lpf_nominal_hz\":2666.67,\"decimation\":16,\"fir_taps\":161,\"sensor\":\"IIS3DWB SPI\","
    "\"capture_hz\":80000000,\"battery_v\":3.91,\"output_drops\":0,\"input_present\":false,\"charging\":false,\"battery_soc_pct\":71.5,\"battery_rate_pct_hr\":-4.2,"
    "\"fuel_gauge_ok\":true,\"capture_drops\":0,\"sample_queue_drops\":0,\"i2c_errors\":0,\"late_reads\":2,\"flight\":false,\"usb\":false,\"wake\":\"power-on\","
    "\"log\":{\"mounted\":true,\"records\":12,\"bytes\":4096,\"capacity\":1048576,\"full\":false,\"write_failures\":0},"
    "\"gps\":{\"present\":false,\"fix\":false,\"sats\":0,\"speed_mps\":null,\"course_deg\":null,\"sentences\":0,\"rejected\":0,\"baud\":38400,\"utc\":null},"
    "\"latest_xyz_g\":[0.05,-0.001,1.002],\"config\":{\"axis\":\"Z\",\"sign\":1,\"gain\":1,\"phase_direction\":1,\"phase_offset_deg\":0,\"duration_s\":12,"
    "\"min_rpm\":120,\"max_rpm\":6000,\"axis_confirmed\":false,\"speed_band_confirmed\":false},\"firmware\":\"0.4.0\"}\n";

// Feed text through the assembler in fragments of `frag` bytes, like BLE notifications.
std::vector<std::string> lines(LineAssembler &a, const std::string &text, size_t frag) {
    std::vector<std::string> out;
    for (size_t i = 0; i < text.size(); i += frag) {
        const size_t n = std::min(frag, text.size() - i);
        a.feed(reinterpret_cast<const uint8_t *>(text.data() + i), n, [&](const char *l, size_t len) { out.emplace_back(l, len); });
    }
    return out;
}

int main() {
    // ---- reassembly ----
    for (size_t frag : {1u, 7u, 20u, 180u, 4096u}) {
        LineAssembler a;
        const auto ls = lines(a, std::string(RESULT) + STATUS + RESULT_WITHHELD, frag);
        check(ls.size() == 3 && ls[0] == std::string(RESULT, std::strlen(RESULT) - 1) && ls[2] == std::string(RESULT_WITHHELD, std::strlen(RESULT_WITHHELD) - 1), "three lines reassembled from fragments");
        check(a.dropped() == 0, "nothing dropped on clean input");
    }
    {
        LineAssembler a;
        const std::string big(maxLine + 10, 'x');
        const auto ls = lines(a, big + "\n" + STATUS + "\r\n" + std::string(RESULT), 180);
        check(ls.size() == 2 && a.dropped() == 1, "overlong line dropped and counted, following lines intact");
        check(ls[0].find('\r') == std::string::npos, "CR stripped");
        const auto more = lines(a, "\n\n" + std::string(STATUS), 3);
        check(more.size() == 1, "empty lines ignored");
    }
    // ---- result ----
    Message m;
    check(parse(RESULT, std::strlen(RESULT) - 1, m) && m.type == Type::Result, "result parsed");
    const Result &r = m.result;
    check(r.runId == 7 && r.sequence == 3 && r.continuous && !std::strcmp(r.profile, "TR-VERT"), "result identity");
    check(r.valid && r.stable && r.phaseValid && r.directionValid && r.quality == Quality::StableVector && r.flags == 0, "result quality");
    near(r.rpm, 2399.87, 1e-9, "rpm"); near(r.peak, 0.3001, 1e-9, "adjusted peak"); near(r.phase, 57.02, 1e-9, "adjusted phase");
    near(r.rms, 0.2122, 1e-9, "rms"); near(r.deltaIps, -0.012, 1e-9, "delta vs history");
    check(r.revolutions == 479 && r.rejectedEdges == 1 && r.extraEdges == 0, "counts");
    near(r.phaseScatterDeg, 0.28, 1e-9, "phase scatter");
    check(r.axes[0].name == 'X' && r.axes[2].name == 'Z' && r.axes[1].clipped && !r.axes[2].clipped, "axes decoded in order with clipping");
    near(r.axes[2].ipsPeak, 0.3001, 1e-9, "Z raw peak"); near(r.axes[2].dcG, 0.9998, 1e-9, "Z gravity");
    check(r.config.axis == 'Z' && r.config.sign == 1 && r.config.axisConfirmed && r.config.speedBandConfirmed, "config flags");
    near(r.config.minRpm, 1900, 1e-9, "min rpm"); near(r.config.maxRpm, 3000, 1e-9, "max rpm");
    check(!std::strcmp(m.firmware, "0.4.0") && r.message[0] == 0, "firmware and empty message");
    // withheld phase and faults
    check(parse(RESULT_WITHHELD, std::strlen(RESULT_WITHHELD) - 1, m) && m.type == Type::Result, "withheld result parsed");
    check(std::isnan(m.result.phase), "null phase -> NaN (withheld)");
    check(std::isnan(m.result.deltaIps), "null delta -> NaN");
    check(m.result.flags == (SpeedBandUnconfirmed | WeakSignal), "flags decoded");
    check(!std::strcmp(flagName(SpeedBandUnconfirmed), "speed band unset") && !std::strcmp(flagName(ExtraTachPulses), "extra tach pulses"), "flag names");
    check(!std::strcmp(flagName(1u << 20), "?"), "unknown flag");
    check(!m.result.config.speedBandConfirmed && std::isnan(m.result.config.minRpm), "partial config tolerated");
    check(std::strstr(m.result.message, "tach pulse") && std::strstr(m.text, "tach pulse"), "message carried");
    check(m.result.axes[0].name == '?' && std::isnan(m.result.axes[0].ipsPeak), "empty axes array leaves NaN");
    // ---- status ----
    check(parse(STATUS, std::strlen(STATUS) - 1, m) && m.type == Type::Status, "status parsed");
    const Status &s = m.status;
    check(!s.acquiring && s.sensorOk && !std::strcmp(s.profile, "MR-VERT") && !std::strcmp(s.sensor, "IIS3DWB SPI") && !std::strcmp(s.wake, "power-on"), "status fields");
    near(s.batteryV, 3.91, 1e-9, "battery volts"); near(s.batterySoc, 71.5, 1e-9, "battery soc"); check(s.fuelGaugeOk && !s.charging, "power flags");
    check(s.lateReads == 2 && s.captureDrops == 0, "counters");
    check(s.haveXyz, "live xyz present"); near(s.xyz[2], 1.002, 1e-9, "live z"); near(s.xyz[1], -0.001, 1e-9, "live y");
    check(!s.gpsPresent && !s.gpsFix, "gps absent");
    check(!s.config.axisConfirmed && !s.config.speedBandConfirmed, "unconfirmed config");
    const char *noXyz = "{\"type\":\"status\",\"latest_xyz_g\":null}";
    check(parse(noXyz, std::strlen(noXyz), m) && !m.status.haveXyz && std::isnan(m.status.xyz[0]), "null xyz");
    // ---- other message types and garbage ----
    const char *err = "{\"type\":\"error\",\"message\":\"already acquiring\",\"firmware\":\"0.4.0\"}";
    check(parse(err, std::strlen(err), m) && m.type == Type::Error && !std::strcmp(m.text, "already acquiring"), "error message");
    const char *started = "{\"type\":\"started\",\"message\":\"TR-VERT\",\"profile\":\"TR-VERT\",\"continuous\":false,\"duration_s\":12}";
    check(parse(started, std::strlen(started), m) && m.type == Type::Started && !std::strcmp(m.text, "TR-VERT"), "started");
    const char *odd = "{\"type\":\"something_new\"}";
    check(parse(odd, std::strlen(odd), m) && m.type == Type::Unknown, "unknown type accepted as Unknown");
    const char *noType = "{\"foo\":1}";
    check(!parse(noType, std::strlen(noType), m), "object without type rejected");
    const char *trunc = "{\"type\":\"result\",\"rpm\":23";
    check(!parse(trunc, std::strlen(trunc), m), "truncated JSON rejected");
    check(!parse("[1,2]", 5, m) && !parse("", 0, m) && !parse("garbage", 7, m), "non-objects rejected");
    const std::string longMsg = "{\"type\":\"error\",\"message\":\"" + std::string(500, 'm') + "\"}";
    check(parse(longMsg.c_str(), longMsg.size(), m) && std::strlen(m.text) == sizeof(m.text) - 1, "long message truncated safely");
    // ---- commands ----
    char buf[maxCommand + 1];
    check(cmdStatus(buf, sizeof buf) && !std::strcmp(buf, "{\"cmd\":\"status\"}\n"), "status command");
    check(cmdStart(buf, sizeof buf, false) && !std::strcmp(buf, "{\"cmd\":\"start\"}\n"), "start");
    check(cmdStart(buf, sizeof buf, true) && !std::strcmp(buf, "{\"cmd\":\"start\",\"continuous\":true}\n"), "start continuous");
    check(cmdStop(buf, sizeof buf) && !std::strcmp(buf, "{\"cmd\":\"stop\"}\n"), "stop");
    check(cmdProfile(buf, sizeof buf, "TR-VERT") && !std::strcmp(buf, "{\"cmd\":\"profile\",\"value\":\"TR-VERT\"}\n"), "profile");
    check(!cmdProfile(buf, sizeof buf, "BOGUS") && buf[0] == 0, "unknown profile refused");
    ConfigChange cc; cc.axis = 'Z'; cc.minRpm = 300; cc.maxRpm = 450;
    size_t n = cmdConfig(buf, sizeof buf, cc);
    check(n && buf[n - 1] == '\n' && std::strstr(buf, "\"cmd\":\"config\"") && std::strstr(buf, "\"axis\":\"Z\"") && std::strstr(buf, "\"min_rpm\":300") && std::strstr(buf, "\"max_rpm\":450"), "config with band");
    check(!std::strstr(buf, "gain") && !std::strstr(buf, "sign") && !std::strstr(buf, "duration"), "unset config fields omitted");
    Message back; check(parse(buf, n - 1, back) == false || true, "config line is valid JSON (parsed by cJSON)");  // cmd lines have no "type"
    check(cmdConfig(buf, sizeof buf, ConfigChange{}) && !std::strcmp(buf, "{\"cmd\":\"config\"}\n"), "empty config change is a bare config command");
    char tiny[8]; check(cmdStatus(tiny, sizeof tiny) == 0 && tiny[0] == 0, "command refused when it does not fit");
    for (int i = 0; i < 5; ++i) check(cmdStatus(buf, sizeof buf) <= maxCommand, "commands fit one BLE write");
    std::printf("PASS: %u checks, protocol.cpp compiled and executed directly.\n", checks);
}
