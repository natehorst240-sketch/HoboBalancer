#include "measurement.hpp"
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
        if(clip && tick==9600000)s.g[0]=1.99f;
        m.sample(s);
    }
    auto r=m.finish(!noTach);return r;
}
int main() {
    Config c;c.axisConfirmed=true;
    check(validConfig(c),"defaults validate");
    auto r=simulate(c);
    check(r.valid && r.stable && r.phaseValid,"clean signal accepted");
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
    check(!simulate(c,40,.3,57,0,false,false,false,true).valid,"no tach never returns valid result");
    auto glitch=simulate(c,40,.3,57,0,false,false,true);
    check(glitch.rejectedEdges>0,"too-fast tach glitches rejected");near(glitch.rpm,2400,.01,"glitches do not replace anchor");
    auto clipped=simulate(c,40,.3,57,0,false,false,false,false,true);
    check((clipped.flags&Clipping)&&!clipped.valid,"clipping any axis invalidates acquisition");
    auto weak=simulate(c,40,0.001);check(weak.flags&WeakSignal,"weak phase flagged");check(!weak.phaseValid,"weak phase withheld");
    auto unstable=simulate(c,40,.3,57,0,false,false,false,false,false,true);
    check(unstable.flags&VibrationUnstable,"amplitude variation flagged");check(!unstable.stable,"variable vibration not stable");
    auto mr=simulate(c,2,.3,123);check(mr.valid,"120 RPM supported");near(mr.peak,.3,.0001,"MR low-frequency integration");
    auto tr=simulate(c,100,.3,201);check(tr.valid,"6000 RPM supported");phaseNear(tr.phase,201,.02,"TR high-frequency phase");
    c.axisConfirmed=false;check(!simulate(c).stable,"unconfirmed mounting not stable");
    c.gain=NAN;check(!validConfig(c),"NaN rejected");c=Config{};c.maxRpm=10000;check(!validConfig(c),"unsupported RPM rejected");
    c=Config{};c.sign=0;check(!validConfig(c),"invalid sign rejected");
    Measurement m;m.begin(Config{},80000000);m.fault(IoError|QueueOverflow|TimingError|Cancelled);
    check(!m.finish(false).valid,"hardware fault propagation");
    m.begin(Config{},80000000);check(m.tach(0),"first tach anchor accepted");
    check(m.tach(800000),"100 Hz tach accepted");near(m.tachTimeoutSeconds(),.03,.0001,"tach timeout follows measured speed");
    check(!m.tach(800001),"rejected glitch cannot refresh tach freshness");
    std::printf("PASS: %u checks, firmware measurement.cpp compiled and executed directly.\n",checks);
}
