// Host vibration simulator: runs a synthetic scenario through the firmware's own decodeBlock and
// Measurement code (tests/rawsim.hpp) and prints what the instrument would report.
//
//   tools/sim.sh                         run every preset, one line each, with the expected outcome
//   tools/sim.sh list                    list presets and settings
//   tools/sim.sh tr-max                  one preset, full result as JSON
//   tools/sim.sh rpm=390 ips=0.8 h2=1.2  any preset or the default, with settings overridden
//
// Not covered here: the ESP task/queue timing, SPI, and the tach front end. Those need the board.
#include "rawsim.hpp"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

using namespace puck;
namespace {
struct Preset { const char *name, *expect, *settings, *why; };
const Preset presets[] = {
    {"clean", "stable_vector", "", "2400 RPM, 0.3 IPS, harmonics and datasheet noise"},
    {"mr-min", "stable_vector", "rpm=300 ips=0.08", "lowest main-rotor case"},
    {"mr-typical", "stable_vector", "rpm=500 ips=0.5", "main rotor"},
    {"tr-max", "stable_vector", "rpm=2200 ips=2.0", "~2.2 g with gravity: clipped at the old +/-2 g range"},
    {"heavy-2rev", "stable_vector", "rpm=300 ips=0.08 h2=1.5", "2/rev 20x the 1/rev acceleration"},
    {"overrange", "unreliable", "rpm=2200 ips=30", "~18 g: must fail, never read low"},
    {"impact-selected", "unreliable", "spike=20", "one 20 g sample on the measured axis"},
    {"impact-other", "stable_vector", "spike=20 spike_axis=0", "one 20 g sample on an unused axis"},
    {"amp-wander", "direction_only", "amp_wander=60", "amplitude +/-60%, phase steady"},
    {"phase-wander", "unreliable", "phase_wander=45", "phase +/-45 degrees"},
    {"rpm-drift", "unreliable", "rpm_drift=10", "RPM ramps 10% over the run"},
    {"tach-jitter", "stable_vector", "rpm=2200 tach_jitter=50", "50 us RMS edge jitter"},
    {"tach-dropout", "unreliable", "tach_drop=20", "every 20th tach edge missing"},
    {"tach-glitch", "stable_vector", "tach_glitch=10", "extra edge 50 us after every 10th"},
    {"sample-gap", "unreliable", "gap_at=5 gap_ms=20", "20 ms of missed FIFO blocks"},
    {"weak", "unreliable", "ips=0.002", "below the 0.005 IPS floor"},
    {"noisy-mr", "stable_vector", "rpm=300 ips=0.08 noise=10", "10x datasheet noise at the lowest case"},
    {"unconfirmed", "unreliable", "confirmed=0", "mounting axis not confirmed"},
};

const char *qualityName(Quality q) {
    return q == Quality::StableVector ? "stable_vector" : q == Quality::DirectionOnly ? "direction_only" : "unreliable";
}
std::string flagNames(uint32_t f) {
    static const char *names[] = {"no_tach", "few_revs", "sample_gap", "clipping", "io", "queue", "rpm_unstable",
                                  "vib_unstable", "weak", "axis_unconfirmed", "timing", "cancelled", "phase_unstable"};
    std::string s;
    for (int b = 0; b < 13; b++)
        if (f & (1u << b)) { if (!s.empty()) s += ','; s += names[b]; }
    return s.empty() ? "-" : s;
}

bool apply(const char *kv, rawsim::Scenario &o, Config &c) {
    const char *eq = std::strchr(kv, '=');
    if (!eq) return false;
    const std::string k(kv, eq - kv);
    char *end = nullptr;
    const double v = std::strtod(eq + 1, &end);
    if (end == eq + 1 || *end) { std::fprintf(stderr, "bad number in %s\n", kv); std::exit(2); }
    struct { const char *key; double *field; } doubles[] = {
        {"rpm", &o.rpm}, {"ips", &o.ips}, {"phase", &o.phaseDeg}, {"duration", &o.durationS},
        {"gravity", &o.gravityG}, {"h2", &o.h2G}, {"h3", &o.h3G}, {"noise", &o.noiseScale},
        {"spike", &o.spikeG}, {"phase_wander", &o.phaseWanderDeg}, {"amp_wander", &o.ampWanderPct},
        {"rpm_drift", &o.rpmDriftPct}, {"tach_jitter", &o.tachJitterUs}, {"gap_at", &o.gapAtS},
        {"gap_ms", &o.gapMs}, {"gain", &c.gain}, {"phase_offset", &c.phaseOffsetDeg},
        {"min_rpm", &c.minRpm}, {"max_rpm", &c.maxRpm}};
    for (auto &d : doubles) if (k == d.key) { *d.field = v; return true; }
    if (k == "axis") { o.axis = c.axis = int(v); return true; }
    if (k == "spike_axis") { o.spikeAxis = int(v); return true; }
    if (k == "spikes") { o.spikes = int(v); return true; }
    if (k == "tach_drop") { o.tachDropEvery = int(v); return true; }
    if (k == "tach_glitch") { o.tachGlitchEvery = int(v); return true; }
    if (k == "seed") { o.seed = uint32_t(v); return true; }
    if (k == "sign") { c.sign = int(v); return true; }
    if (k == "confirmed") { c.axisConfirmed = v != 0; return true; }
    std::fprintf(stderr, "unknown setting %s (tools/sim.sh list)\n", k.c_str());
    std::exit(2);
}
void applyAll(const char *settings, rawsim::Scenario &o, Config &c) {
    std::string s(settings);
    size_t p = 0;
    while (p < s.size()) {
        const size_t q = s.find(' ', p);
        const std::string kv = s.substr(p, q == std::string::npos ? std::string::npos : q - p);
        if (!kv.empty()) apply(kv.c_str(), o, c);
        if (q == std::string::npos) break;
        p = q + 1;
    }
}
Config baseConfig() { Config c; c.axisConfirmed = true; c.durationS = 12; return c; }

Result simulate(const Config &c, const rawsim::Scenario &o) {
    static Measurement m;  // ~13 KB of sample buffer; keep it off the stack
    return rawsim::run(c, o, m);
}
void printJson(const char *name, const Config &c, const rawsim::Scenario &o, const Result &r) {
    const char *axes = "XYZ";
    std::printf("{\"scenario\":\"%s\",\"input\":{\"rpm\":%g,\"ips_peak\":%g,\"phase_deg\":%g,\"axis\":\"%c\"},\n", name,
                o.rpm, o.ips, o.phaseDeg, axes[c.axis]);
    std::printf(" \"quality\":\"%s\",\"valid\":%s,\"stable\":%s,\"phase_valid\":%s,\"direction_valid\":%s,\n",
                qualityName(r.quality), r.valid ? "true" : "false", r.stable ? "true" : "false",
                r.phaseValid ? "true" : "false", r.directionValid ? "true" : "false");
    std::printf(" \"flags\":%u,\"flag_names\":\"%s\",\"rpm\":%.3f,\"rpm_cv\":%.5f,\"revolutions\":%u,\"rejected_tach_edges\":%u,\n",
                r.flags, flagNames(r.flags).c_str(), r.rpm, r.rpmCv, r.revolutions, r.rejectedEdges);
    std::printf(" \"adjusted_ips_peak\":%.5f,\"adjusted_velocity_phase_deg\":", r.peak);
    if (r.directionValid) std::printf("%.2f", r.phase); else std::printf("null");
    std::printf(",\"raw_vector_scatter_ips_peak\":%.5f,\"raw_amplitude_scatter_ips_peak\":%.5f,\"per_rev_phase_scatter_deg\":%.2f,\n",
                r.vectorScatter, r.amplitudeScatter, r.phaseScatterDeg);
    std::printf(" \"raw_axes\":[");
    for (int a = 0; a < 3; a++)
        std::printf("%s{\"axis\":\"%c\",\"ips_peak\":%.5f,\"velocity_phase_deg\":%.2f,\"dc_g\":%.4f,\"clipped\":%s}",
                    a ? "," : "", axes[a], r.rawPeak[a], r.rawPhase[a], r.dcG[a], (r.clippedAxes >> a) & 1 ? "true" : "false");
    std::printf("]}\n");
}
int runAll() {
    std::printf("%-16s %-15s %-15s %-4s %8s %9s %8s %8s  %s\n", "preset", "expected", "got", "", "rpm", "ips", "ips_err", "ph_err",
                "flags");
    int failures = 0;
    for (const auto &p : presets) {
        rawsim::Scenario o; Config c = baseConfig();
        applyAll(p.settings, o, c);
        const Result r = simulate(c, o);
        const bool ok = !std::strcmp(p.expect, qualityName(r.quality));
        failures += !ok;
        const double phErr = wrapDegrees(r.phase - o.phaseDeg + 180) - 180;
        std::printf("%-16s %-15s %-15s %-4s %8.1f %9.4f %+7.2f%% %+7.2f  %s\n", p.name, p.expect, qualityName(r.quality),
                    ok ? "ok" : "FAIL", r.rpm, r.peak, o.ips ? (r.peak / o.ips - 1) * 100 : 0, phErr, flagNames(r.flags).c_str());
    }
    std::printf("%d of %zu presets matched their expected outcome.\n", int(sizeof presets / sizeof *presets) - failures,
                sizeof presets / sizeof *presets);
    return failures ? 1 : 0;
}
}  // namespace

int main(int argc, char **argv) {
    if (argc == 1) return runAll();
    if (!std::strcmp(argv[1], "list")) {
        for (const auto &p : presets) std::printf("%-16s %-15s %-28s %s\n", p.name, p.expect, p.settings, p.why);
        std::printf("\nsettings: rpm ips phase duration axis gravity h2 h3 noise spike spike_axis spikes phase_wander\n"
                    "          amp_wander rpm_drift tach_jitter tach_drop tach_glitch gap_at gap_ms seed\n"
                    "          gain sign phase_offset min_rpm max_rpm confirmed\n");
        return 0;
    }
    rawsim::Scenario o; Config c = baseConfig();
    const char *name = "custom";
    int first = 1;
    for (const auto &p : presets)
        if (!std::strcmp(argv[1], p.name)) { applyAll(p.settings, o, c); name = p.name; first = 2; }
    for (int i = first; i < argc; i++)
        if (!apply(argv[i], o, c)) { std::fprintf(stderr, "unknown preset %s (tools/sim.sh list)\n", argv[i]); return 2; }
    if (!validConfig(c)) { std::fprintf(stderr, "configuration rejected by validConfig()\n"); return 2; }
    printJson(name, c, o, simulate(c, o));
    return 0;
}
