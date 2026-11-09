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
// Expected speed band around rpm, narrower than 2:1, set explicitly as a profile would.
Config band(Config c,double rpm) {
    c.minRpm=std::max(120.0,rpm*0.8);c.maxRpm=std::min(6000.0,rpm*1.25);c.speedBandConfirmed=true;return c;
}
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

// ---- Raw path: int16 at the full 26.667 kHz ODR -> Decimator (anti-alias FIR) -> Measurement. ----
// Steady-state gain of the FIR to a sine at f Hz, by running it through the real Decimator.
double firGain(double f) {
    static accel::Decimator d;d.reset();
    int16_t raw[16][3]{};accel::Block b;double peak=0;
    for(unsigned blk=0;blk<400;blk++) {
        for(unsigned i=0;i<16;i++){const double t=(blk*16+i)/26666.67;raw[i][0]=int16_t(std::lround(10000*std::sin(2*pi*f*t)));}
        if(d.push(raw,16,b) && blk>40) peak=std::max(peak,std::abs(double(b.g[0])));
    }
    return peak/(10000*accel::mgPerLsb*0.001);
}
void decodeTests() {
    near(32767*accel::mgPerLsb*0.001,accel::fullScaleG,.02,"full-scale count is the configured range");
    int16_t raw[16][3]{};
    for(auto &v:raw){v[0]=2049;v[1]=-2049;v[2]=0;}
    check(accel::clipFlags(raw,16)==0,"mid-range block not clipped");
    raw[5][2]=32767;check(accel::clipFlags(raw,16)==4,"one saturated raw sample flags its axis");
    raw[5][2]=-32768;check(accel::clipFlags(raw,16)==4,"negative rail flagged");
    raw[5][2]=int16_t(accel::clipRaw-1);check(accel::clipFlags(raw,16)==0,"just below threshold not clipped");
    raw[5][2]=int16_t(accel::clipRaw);check(accel::clipFlags(raw,16)==4,"threshold is clipped");
    raw[5][2]=0;raw[9][0]=int16_t(-accel::clipRaw);check(accel::clipFlags(raw,16)==1,"axes flagged independently");
    raw[9][0]=2049;
    static accel::Decimator d;accel::Block b;
    double tapSum=0;for(unsigned k=0;k<accel::firTaps;k++)tapSum+=d.tap(k);near(tapSum,1,1e-5,"FIR has unity DC gain");
    check(d.tap(0)==d.tap(accel::firTaps-1)&&d.tap(20)==d.tap(accel::firTaps-21),"FIR is symmetric (linear phase)");
    unsigned primedAt=0;
    for(unsigned k=1;k<=accel::firBlocks+1;k++) if(d.push(raw,16,b)&&!primedAt) primedAt=k;
    check(primedAt==accel::firBlocks,"FIR output only once its history is full");
    near(b.g[0],2049*0.000488,1e-5,"raw to g at 0.488 mg/LSB through the FIR");near(b.g[1],-2049*0.000488,1e-5,"negative raw to g");
    raw[5][2]=32767;d.push(raw,16,b);check(b.clipped==4,"clipping judged on raw samples, not the filtered value");
    d.reset();check(!d.push(raw,16,b),"reset empties the FIR");
    // Passband to 4/rev at 6000 RPM, stopband from the lowest frequency that aliases into it.
    near(firGain(6.4),1,1e-3,"FIR passband at MR 1/rev");near(firGain(100),1,1e-3,"FIR passband at 6000 RPM 1/rev");
    near(firGain(400),1,1e-3,"FIR passband at 4/rev, 6000 RPM");
    check(firGain(1266.7)<3e-4&&firGain(1706.7)<3e-4&&firGain(3293.3)<3e-4&&firGain(9000)<3e-4,"FIR stopband at least 70 dB down");
}
using RawRun=rawsim::Scenario;
Result simulateRaw(Config c,const RawRun &o) {static Measurement m;return rawsim::run(c,o,m);}
// Tach edges land at arbitrary points inside blocks here, so these also cover a block whose
// mean timestamp precedes an edge that was delivered first, and 2/3-rev harmonic leakage.
// 2200 RPM at 2.0 IPS plus gravity is ~2.2 g: the case the old +/-2 g range clipped.
void envelopeTests() {
    Config base;base.axisConfirmed=true;
    const double rpms[]={300,500,1900,2200},ipss[]={0.08,0.5,2.0};
    char name[96];
    for(double rpm:rpms) for(double ips:ipss) {
        RawRun o;o.rpm=rpm;o.ips=ips;o.phaseDeg=rpm/7;
        auto r=simulateRaw(band(base,rpm),o);
        std::snprintf(name,sizeof name,"%.0f RPM %.2f IPS stable vector at 16 g",rpm,ips);
        check(r.valid&&r.stable&&r.phaseValid&&r.clippedAxes==0&&r.quality==Quality::StableVector,name);
        std::snprintf(name,sizeof name,"%.0f RPM %.2f IPS amplitude",rpm,ips);near(r.peak,ips,ips*0.01+0.0005,name);
        std::snprintf(name,sizeof name,"%.0f RPM %.2f IPS phase",rpm,ips);phaseNear(r.phase,o.phaseDeg,1.0,name);
        std::snprintf(name,sizeof name,"%.0f RPM %.2f IPS gravity",rpm,ips);near(r.dcG[2],1,.002,name);
    }
    // Beyond the range: a saturated waveform must fail, never report a falsely small IPS.
    Config c=band(base,2400);
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
    // A rotor-locked tone 40 Hz above the 1666.7 Hz output rate aliases exactly onto 1/rev at
    // 2400 RPM. The old 16-sample average passed it as a stable 0.036 IPS 1/rev vector.
    RawRun tone;tone.ips=0;tone.toneHz=1666.667+40;tone.toneG=1;
    auto rt=simulateRaw(c,tone);
    check(rt.peak<0.001,"aliased tone does not become a 1/rev vector");
    check(rt.quality!=Quality::StableVector,"aliased tone alone is not a stable vector");
    tone.ips=0.3;rt=simulateRaw(c,tone);
    check(rt.stable,"real 1/rev under an alias tone stays stable");near(rt.peak,.3,.003,"alias tone leaves 1/rev amplitude");
    phaseNear(rt.phase,57,1,"alias tone leaves 1/rev phase");
    tone.ips=0;tone.toneHz=2*1666.667-40;rt=simulateRaw(c,tone);check(rt.peak<0.001,"second alias band rejected");
    // The first tach edge anywhere inside a FIFO block, or the FIR delay after it: samples
    // timestamped before the first anchor arrive after it and must be dropped, not faulted.
    unsigned sweepFailures=0;
    for(int k=0;k<96;k++) {RawRun o;o.firstEdgeRaw=k;auto rr=simulateRaw(c,o);if(!rr.stable||(rr.flags&TimingError))++sweepFailures;}
    check(sweepFailures==0,"first tach edge swept across six FIFO blocks stays stable");
    // Two tach marks per revolution. With the band set for the real 1200 RPM the second pulse
    // is too fast, RPM stays right, and the run fails instead of reading 2/rev as 1/rev.
    Config c1200=band(base,1200);
    RawRun twice;twice.rpm=1200;twice.pulsesPerRev=2;
    auto r2=simulateRaw(c1200,twice);
    check((r2.flags&ExtraTachPulses)&&!r2.valid&&r2.quality==Quality::Unreliable,"two pulses per revolution is a hard fault");
    near(r2.rpm,1200,1,"two pulses per revolution keep true RPM inside the band");
    check(r2.extraEdges>=r2.revolutions/2,"extra edges counted");
    // Without a confirmed band the same tach reads 2400 RPM; it must not be a stable vector.
    Config wide=base;auto rw2=simulateRaw(wide,twice);
    check((rw2.flags&SpeedBandUnconfirmed)&&!rw2.stable&&!rw2.directionValid,"unconfirmed band gives no stable vector");
    RawRun bounce;bounce.tachGlitchEvery=1;auto rb=simulateRaw(c,bounce);
    check(rb.stable&&rb.extraEdges==0&&!(rb.flags&ExtraTachPulses),"contact bounce on every edge is not an extra pulse");
}

int main() {
    Config c;c.axisConfirmed=true;
    check(validConfig(c),"defaults validate");
    check(!c.speedBandConfirmed,"speed band starts unconfirmed");
    Config wideBand=c;wideBand.speedBandConfirmed=true;check(!validConfig(wideBand),"confirmed band must be narrower than 2:1");
    c=band(c,2400);check(validConfig(c),"narrow confirmed band validates");
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
    c=band(Config{},2400);c.axisConfirmed=true;
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
    auto mr=simulate(band(c,120),2,.3,123);check(mr.valid,"120 RPM supported");near(mr.peak,.3,.0001,"MR low-frequency integration");
    auto tr=simulate(band(c,6000),100,.3,201);check(tr.valid,"6000 RPM supported");phaseNear(tr.phase,201,.02,"TR high-frequency phase");
    c.axisConfirmed=false;check(!simulate(c).stable,"unconfirmed mounting not stable");
    check(!simulate(c).directionValid,"unconfirmed mounting gives no direction");
    c.speedBandConfirmed=true;check(!simulate(c).stable,"unconfirmed mounting not stable even with a band");
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
