#include "measurement.hpp"
#include "accelscale.hpp"
#include "rawsim.hpp"
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
using namespace puck;
static unsigned checks=0;
void check(bool condition,const char *name) {++checks;if(!condition){std::fprintf(stderr,"FAIL: %s\n",name);std::exit(1);}}
void near(double a,double b,double tolerance,const char *name) {check(std::abs(a-b)<tolerance,name);}
void phaseNear(double a,double b,double tolerance,const char *name) {near(wrapDegrees(a-b+180),180,tolerance,name);}
// Independent synthetic generator specifies VELOCITY, differentiates it into
// acceleration, adds gravity + 2/rev, and schedules discrete hardware events.
Result simulate(Config c,double hz=40,double ips=0.30,double phase=57,
                uint32_t start=0,bool skip=false,bool reverse=false,bool noiseEdge=false,
                bool noTach=false,bool clip=false,bool wander=false) {
    static Measurement m;m.begin(c,80000000);
    const double amplitude=ips/ metresToInches *2*pi*hz /gravity;
    constexpr double duration=8;
    uint64_t nextTach=0;const uint64_t end=uint64_t(duration*80000000);
    const uint64_t period=uint64_t(80000000/hz);
    for(uint64_t tick=0;tick<end;tick+=48000) { // 1666.7 Hz decimated IIS3DWB rate
        while(nextTach<=tick) {
            if(!noTach)m.tach(start+uint32_t(nextTach));
            if(noiseEdge&&!noTach)m.tach(start+uint32_t(nextTach+100));
            nextTach+=period;
        }
        if(skip && tick==48000000)continue;
        const double angle=2*pi*hz*double(tick)/80000000;
        const double mod=wander?(0.2+0.8*(std::sin(angle/30)*0.5+0.5)):1;
        const float a=float(-amplitude*mod*std::sin(angle-phase*pi/180));
        Sample s{start+uint32_t(tick),{float(0.02*std::cos(angle*2)),0,float(1+(reverse?-a:a)+0.03*std::cos(2*angle))}};
        if(clip && tick==9600000)s.clipped=1; // X, not the selected Z axis
        m.sample(s);
    }
    auto r=m.finish(!noTach);return r;
}

// ---- Raw path: int16 at the full 26.667 kHz ODR -> decodeBlock -> Measurement. ----
void decodeTests() {
    near(32767*accel::mgPerLsb*0.001,accel::fullScaleG,.02,"full-scale count is the configured range");
    int16_t raw[16][3]{};
    for(auto &v:raw){v[0]=2049;v[1]=-2049;v[2]=0;}
    accel::Block b;accel::decodeBlock(raw,16,b);
    near(b.g[0],2049*0.000488,1e-6,"raw to g at 0.488 mg/LSB");near(b.g[1],-2049*0.000488,1e-6,"negative raw to g");
    check(b.clipped==0,"mid-range block not clipped");
    raw[5][2]=32767;accel::decodeBlock(raw,16,b);
    check(b.g[2]<1.1f,"one saturated sample barely moves the mean");
    check(b.clipped==4,"one saturated raw sample flags its axis before averaging");
    raw[5][2]=-32768;accel::decodeBlock(raw,16,b);check(b.clipped==4,"negative rail flagged");
    raw[5][2]=int16_t(accel::clipRaw-1);accel::decodeBlock(raw,16,b);check(b.clipped==0,"just below threshold not clipped");
    raw[5][2]=int16_t(accel::clipRaw);accel::decodeBlock(raw,16,b);check(b.clipped==4,"threshold is clipped");
    raw[5][2]=0;raw[9][0]=int16_t(-accel::clipRaw);accel::decodeBlock(raw,16,b);check(b.clipped==1,"axes flagged independently");
}
using RawRun=rawsim::Scenario;
Result simulateRaw(Config c,const RawRun &o) {static Measurement m;return rawsim::run(c,o,m);}
// Tach edges land at arbitrary points inside blocks here, so these also cover a block whose
// mean timestamp precedes an edge that was delivered first, and 2/3-rev harmonic leakage.
// 2200 RPM at 2.0 IPS plus gravity is ~2.2 g: the case the old +/-2 g range clipped.
void envelopeTests() {
    Config c;c.axisConfirmed=true;
    const double rpms[]={300,500,1900,2200},ipss[]={0.08,0.5,2.0};
    char name[96];
    for(double rpm:rpms) for(double ips:ipss) {
        RawRun o;o.rpm=rpm;o.ips=ips;o.phaseDeg=rpm/7;
        auto r=simulateRaw(c,o);
        std::snprintf(name,sizeof name,"%.0f RPM %.2f IPS stable vector at 16 g",rpm,ips);
        check(r.valid&&r.stable&&r.phaseValid&&r.clippedAxes==0&&r.quality==Quality::StableVector,name);
        std::snprintf(name,sizeof name,"%.0f RPM %.2f IPS amplitude",rpm,ips);near(r.peak,ips,ips*0.01+0.0005,name);
        std::snprintf(name,sizeof name,"%.0f RPM %.2f IPS phase",rpm,ips);phaseNear(r.phase,o.phaseDeg,1.0,name);
        std::snprintf(name,sizeof name,"%.0f RPM %.2f IPS gravity",rpm,ips);near(r.dcG[2],1,.002,name);
    }
    // Beyond the range: a saturated waveform must fail, never report a falsely small IPS.
    RawRun over;over.rpm=2200;over.ips=30; // ~18 g peak
    auto ro=simulateRaw(c,over);
    check((ro.flags&Clipping)&&!ro.valid&&!ro.directionValid&&ro.quality==Quality::Unreliable,"saturated selected axis is unreliable");
    RawRun spike;spike.spikeG=20;
    auto rs=simulateRaw(c,spike);
    check((rs.flags&Clipping)&&!rs.valid,"single clipped impact on selected axis invalidates");
    spike.spikeAxis=0;rs=simulateRaw(c,spike);
    check(rs.valid&&rs.stable&&rs.clippedAxes==1,"clipped impact on unused axis keeps result");
    near(rs.peak,.3,.003,"unused-axis impact leaves selected amplitude");
    RawRun wander;wander.phaseWanderDeg=45;
    auto rw=simulateRaw(c,wander);
    check(rw.flags&PhaseUnstable,"phase wander flagged");
    check(!rw.directionValid&&rw.quality==Quality::Unreliable,"inconsistent angle is unreliable");
    check(rw.phaseScatterDeg>15,"phase scatter reports the wander");
    check(simulateRaw(c,RawRun{}).phaseScatterDeg<1,"clean run has small phase scatter");
}

int main() {
    Config c;c.axisConfirmed=true;
    check(validConfig(c),"defaults validate");
    auto r=simulate(c);
    check(r.valid && r.stable && r.phaseValid,"clean signal accepted");
    check(r.quality==Quality::StableVector && r.directionValid,"clean signal is a stable vector");
    near(r.rpm,2400,0.01,"RPM from tach");near(r.peak,0.30,0.0001,"velocity integration and units");
    near(r.rms,0.30/std::sqrt(2.0),0.0001,"RMS versus peak");
    phaseNear(r.phase,57,0.02,"positive velocity peak phase");
    phaseNear(r.accelerationPhase,327,0.02,"acceleration-to-velocity phase shift");
    near(r.dcG[2],1,0.0001,"gravity retained separately");near(r.rawPeak[0],0,0.0001,"2/rev rejected");
    auto wrapped=simulate(c,40,.3,357,0xffffff00U);
    check(wrapped.valid,"32-bit capture rollover valid");phaseNear(wrapped.phase,357,.02,"phase wraps across 360");
    auto reverse=simulate(c,40,.3,57,0,false,true);
    near(reverse.peak,.3,.0001,"polarity leaves magnitude unchanged");phaseNear(reverse.phase,237,.02,"polarity adds 180 degrees");
    c.sign=-1;c.gain=1.5;c.phaseOffsetDeg=30;c.phaseDirection=-1;
    auto calibrated=simulate(c);
    near(calibrated.peak,.45,.0001,"amplitude scale applied");near(calibrated.rawPeak[2],.3,.0001,"raw remains unchanged");
    phaseNear(calibrated.phase,153,.02,"sign, angle direction, offset applied in documented order");
    c=Config{};c.axisConfirmed=true;
    check(simulate(c,40,.3,57,0,true).flags&SampleGap,"missing sample detected");
    check(!simulate(c,40,.3,57,0,true).valid,"missing sample invalidates run");
    check(simulate(c,40,.3,57,0,false,false,false,true).flags&NoTach,"missing tach detected");
    auto noTach=simulate(c,40,.3,57,0,false,false,false,true);
    check(!noTach.valid && noTach.quality==Quality::Unreliable,"no tach never returns valid result");
    auto glitch=simulate(c,40,.3,57,0,false,false,true);
    check(glitch.rejectedEdges>0,"too-fast tach glitches rejected");near(glitch.rpm,2400,.01,"glitches do not replace anchor");
    auto clipped=simulate(c,40,.3,57,0,false,false,false,false,true);
    check(!(clipped.flags&Clipping)&&clipped.valid&&clipped.stable,"unused-axis clipping keeps selected-axis result");
    check(clipped.clippedAxes==1,"unused-axis clipping still reported");
    auto weak=simulate(c,40,0.001);check(weak.flags&WeakSignal,"weak phase flagged");check(!weak.phaseValid,"weak phase withheld");
    check(!weak.directionValid,"weak signal gives no direction");
    auto unstable=simulate(c,40,.3,57,0,false,false,false,false,false,true);
    check(unstable.flags&VibrationUnstable,"amplitude variation flagged");check(!unstable.stable,"variable vibration not stable");
    check(!(unstable.flags&PhaseUnstable),"amplitude-only variation keeps phase");
    check(unstable.directionValid&&unstable.quality==Quality::DirectionOnly,"amplitude-only variation is direction only");
    check(!unstable.phaseValid,"direction-only never qualifies for calibration");
    phaseNear(unstable.phase,57,.5,"direction-only phase still correct");
    check(unstable.amplitudeScatter>5*std::tan(unstable.phaseScatterDeg*pi/180)*unstable.rawPeak[2],"scatter lies along the vector");
    auto mr=simulate(c,2,.3,123);check(mr.valid,"120 RPM supported");near(mr.peak,.3,.0001,"MR low-frequency integration");
    auto tr=simulate(c,100,.3,201);check(tr.valid,"6000 RPM supported");phaseNear(tr.phase,201,.02,"TR high-frequency phase");
    c.axisConfirmed=false;check(!simulate(c).stable,"unconfirmed mounting not stable");
    check(!simulate(c).directionValid,"unconfirmed mounting gives no direction");
    c.gain=NAN;check(!validConfig(c),"NaN rejected");c=Config{};c.maxRpm=10000;check(!validConfig(c),"unsupported RPM rejected");
    c=Config{};c.sign=0;check(!validConfig(c),"invalid sign rejected");
    Measurement m;m.begin(Config{},80000000);m.fault(IoError|QueueOverflow|TimingError|Cancelled);
    check(!m.finish(false).valid,"hardware fault propagation");
    m.begin(Config{},80000000);check(m.tach(0),"first tach anchor accepted");
    check(m.tach(800000),"100 Hz tach accepted");near(m.tachTimeoutSeconds(),.03,.0001,"tach timeout follows measured speed");
    check(!m.tach(800001),"rejected glitch cannot refresh tach freshness");
    decodeTests();envelopeTests();
    std::printf("PASS: %u checks, firmware measurement.cpp and accelscale.hpp compiled and executed directly.\n",checks);
}
