#include "measurement.hpp"
#include <cmath>
#include <algorithm>

namespace puck {
bool validConfig(const Config &c) {
    return c.axis>=0 && c.axis<3 && (c.sign==1 || c.sign==-1) &&
        (c.phaseDirection==1 || c.phaseDirection==-1) &&
        std::isfinite(c.gain) && c.gain>=0.1 && c.gain<=10 &&
        std::isfinite(c.phaseOffsetDeg) && std::abs(c.phaseOffsetDeg)<=360 &&
        std::isfinite(c.durationS) && c.durationS>=6 && c.durationS<=30 &&
        std::isfinite(c.minRpm) && std::isfinite(c.maxRpm) &&
        c.minRpm>=120 && c.maxRpm<=6000 && c.maxRpm>c.minRpm;
}
double wrapDegrees(double x) { x=std::fmod(x,360); return x<0?x+360:x; }
void Measurement::begin(const Config &c,uint32_t hz) {
    config_=c; hz_=hz; count_=revs_=totalSamples_=rejected_=flags_=0;
    haveTach_=haveSample_=false; lastPeriod_=0; sumPeriod_=sumPeriod2_=0;
    for(int a=0;a<3;a++) sumC_[a]=sumS_[a]=sumPower_[a]=sumDc_[a]=0;
    if(!c.axisConfirmed) flags_|=AxisUnconfirmed;
}
void Measurement::sample(const Sample &s) {
    if(haveSample_) {
        const double dt=double(uint32_t(s.tick-previousSample_))/hz_;
        if(dt<0.00035 || dt>0.00095) flags_|=SampleGap;
    }
    haveSample_=true; previousSample_=s.tick;
    for(float a:s.g) {
        if(!std::isfinite(a)) { flags_|=IoError; return; }
        if(std::abs(a)>=1.95f) flags_|=Clipping; // +/-2g including gravity
    }
    if(!haveTach_) return;
    if(int32_t(s.tick-previousTach_)<0) { flags_|=TimingError; return; }
    if(uint32_t(s.tick-previousTach_)>hz_) { count_=0; return; }
    if(count_==maxCycleSamples) { flags_|=SampleGap; return; }
    samples_[count_++]=s;
}
double Measurement::tachTimeoutSeconds() const {
    return std::max(0.03,lastPeriod_?2.0*lastPeriod_/hz_:120.0/config_.minRpm);
}
bool Measurement::tach(uint32_t tick) {
    if(!haveTach_) { previousTach_=tick; haveTach_=true; count_=0; return true; }
    const uint32_t period=tick-previousTach_;
    const double rpm=period?60.0*hz_/period:1e20;
    if(rpm>config_.maxRpm) { ++rejected_; return false; } // do not replace good anchor
    if(rpm<config_.minRpm) {
        flags_|=NoTach; ++rejected_; previousTach_=tick; count_=0; return false;
    }
    fitCycle(tick,period);
    previousTach_=tick;lastPeriod_=period;
    // A DRDY just after tach can be serviced before the tach callback. Keep it.
    unsigned kept=0;
    for(unsigned i=0;i<count_;i++)
        if(uint32_t(samples_[i].tick-(tick-period))>=period &&
           uint32_t(samples_[i].tick-tick)<hz_/10) samples_[kept++]=samples_[i];
    count_=kept;return true;
}
// Fit DC + C*cos(theta) + S*sin(theta), rather than treating gravity as vibration.
// Each sample angle is interpolated between two actual tach edges, not fixed RPM.
void Measurement::fitCycle(uint32_t end,uint32_t period) {
    double m[3][3]{}, b[3][3]{}; unsigned n=0;
    for(unsigned i=0;i<count_;i++) {
        const uint32_t dt=samples_[i].tick-previousTach_;
        if(dt>=period) continue;
        const double angle=2*pi*dt/period;
        const double x[3]={1,std::cos(angle),std::sin(angle)};
        for(int j=0;j<3;j++) {
            for(int k=0;k<3;k++) m[j][k]+=x[j]*x[k];
            for(int a=0;a<3;a++) b[j][a]+=x[j]*samples_[i].g[a];
        }
        ++n;
    }
    const double expected=sampleRate*double(period)/hz_;
    if(n<12 || n<expected*0.90 || n>expected*1.10) { flags_|=SampleGap; return; }
    // Gaussian elimination with pivoting; RHS contains all three axes.
    for(int k=0;k<3;k++) {
        int pivot=k; for(int j=k+1;j<3;j++) if(std::abs(m[j][k])>std::abs(m[pivot][k])) pivot=j;
        if(std::abs(m[pivot][k])<1e-8) {flags_|=TimingError;return;}
        for(int j=0;j<3;j++) {std::swap(m[k][j],m[pivot][j]);std::swap(b[k][j],b[pivot][j]);}
        const double div=m[k][k];
        for(int j=0;j<3;j++) {m[k][j]/=div;b[k][j]/=div;}
        for(int i=0;i<3;i++) if(i!=k) {
            const double f=m[i][k];
            for(int j=0;j<3;j++) {m[i][j]-=f*m[k][j];b[i][j]-=f*b[k][j];}
        }
    }
    const double sec=double(period)/hz_, factor=gravity*metresToInches*sec/(2*pi);
    for(int a=0;a<3;a++) {
        // Integrating acceleration: velocity cosine=-accel sine/omega,
        // velocity sine=accel cosine/omega. Phase = time of positive velocity peak.
        const double c=-b[2][a]*factor, s=b[1][a]*factor;
        sumC_[a]+=c;sumS_[a]+=s;sumPower_[a]+=c*c+s*s;sumDc_[a]+=b[0][a];
    }
    sumPeriod_+=sec;sumPeriod2_+=sec*sec;++revs_;totalSamples_+=n;
    (void)end;
}
Result Measurement::finish(bool tachRecent) const {
    Result r; r.flags=flags_;r.revolutions=revs_;r.samples=totalSamples_;r.rejectedEdges=rejected_;
    if(!tachRecent || !haveTach_) r.flags|=NoTach;
    if(revs_<8) r.flags|=TooFewRevs;
    if(!revs_) return r;
    const double period=sumPeriod_/revs_;
    r.rpm=60/period;
    r.rpmCv=std::sqrt(std::max(0.0,sumPeriod2_/revs_-period*period))/period;
    for(int a=0;a<3;a++) {
        const double c=sumC_[a]/revs_,s=sumS_[a]/revs_;
        r.rawPeak[a]=std::hypot(c,s);r.rawPhase[a]=wrapDegrees(std::atan2(s,c)*180/pi);
        r.dcG[a]=sumDc_[a]/revs_;
    }
    const int a=config_.axis;const double raw=r.rawPeak[a];
    r.vectorScatter=std::sqrt(std::max(0.0,sumPower_[a]/revs_-raw*raw));
    r.peak=raw*config_.gain;r.rms=r.peak/std::sqrt(2.0);
    const double signedPhase=wrapDegrees(r.rawPhase[a]+(config_.sign<0?180:0));
    r.phase=wrapDegrees(config_.phaseDirection*signedPhase+config_.phaseOffsetDeg);
    r.accelerationPhase=wrapDegrees(signedPhase-90);
    if(r.rpmCv>0.02) r.flags|=RpmUnstable;
    if(r.vectorScatter>std::max(0.005,raw*0.2)) r.flags|=VibrationUnstable;
    if(raw<0.005 || raw<2*r.vectorScatter/std::sqrt(double(revs_))) r.flags|=WeakSignal;
    const uint32_t hard=NoTach|TooFewRevs|SampleGap|Clipping|IoError|QueueOverflow|TimingError|Cancelled;
    r.valid=!(r.flags&hard);
    r.stable=r.valid && !(r.flags&(RpmUnstable|VibrationUnstable|AxisUnconfirmed));
    r.phaseValid=r.stable && !(r.flags&WeakSignal);
    return r;
}
}
