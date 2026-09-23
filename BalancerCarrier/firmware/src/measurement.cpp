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
    config_=c; hz_=hz; count_=revs_=totalSamples_=rejected_=flags_=0; clipped_=0;
    haveTach_=haveSample_=pending_=false; lastPeriod_=pendingTach_=0; sumPeriod_=sumPeriod2_=0;
    for(int a=0;a<3;a++) sumC_[a]=sumS_[a]=sumCC_[a]=sumSS_[a]=sumCS_[a]=sumDc_[a]=0;
    if(!c.axisConfirmed) flags_|=AxisUnconfirmed;
}
void Measurement::sample(const Sample &s) {
    if(haveSample_) {
        const double dt=double(uint32_t(s.tick-previousSample_))/hz_;
        if(dt<0.00035 || dt>0.00095) flags_|=SampleGap;
    }
    haveSample_=true; previousSample_=s.tick;
    for(float a:s.g) if(!std::isfinite(a)) { flags_|=IoError; return; }
    // Judged per raw sample upstream (accelscale.hpp); an unused axis clipping must not
    // discard a clean selected-axis measurement, so only the selected axis is a fault.
    clipped_|=s.clipped&7;
    if(s.clipped&(1u<<config_.axis)) flags_|=Clipping;
    if(!haveTach_) return;
    if(int32_t(s.tick-previousTach_)<0) { flags_|=TimingError; return; }
    if(uint32_t(s.tick-previousTach_)>hz_) { count_=0; pending_=false; return; }
    if(count_==maxCycleSamples) { flags_|=SampleGap; return; }
    samples_[count_++]=s;
    if(pending_ && int32_t(s.tick-pendingTach_)>=0) closeCycle();
}
double Measurement::tachTimeoutSeconds() const {
    return std::max(0.03,lastPeriod_?2.0*lastPeriod_/hz_:120.0/config_.minRpm);
}
// Each block's timestamp is its mean, 7.5 raw periods before the watermark that delivers it,
// so a tach edge in the second half of a block is seen before samples that precede it. An
// accepted edge therefore stays pending, and its revolution is fitted only once the first
// sample at or after the edge arrives, when every sample of that revolution is in.
bool Measurement::tach(uint32_t tick) {
    if(!haveTach_) { previousTach_=tick; haveTach_=true; count_=0; return true; }
    const uint32_t anchor=pending_?pendingTach_:previousTach_;
    const uint32_t period=tick-anchor;
    const double rpm=period?60.0*hz_/period:1e20;
    if(rpm>config_.maxRpm) { ++rejected_; return false; } // do not replace good anchor
    if(pending_) closeCycle(); // two edges with no sample between: fit with what arrived
    if(rpm<config_.minRpm) {
        flags_|=NoTach; ++rejected_; previousTach_=tick; count_=0; return false;
    }
    pending_=true; pendingTach_=tick; lastPeriod_=period;
    // A block timestamped after the edge may already be here (serviced before the tach callback).
    if(count_ && int32_t(samples_[count_-1].tick-tick)>=0) closeCycle();
    return true;
}
void Measurement::closeCycle() {
    const uint32_t tick=pendingTach_, period=tick-previousTach_;
    pending_=false;
    fitCycle(tick,period);
    previousTach_=tick;
    unsigned kept=0;
    for(unsigned i=0;i<count_;i++)
        if(uint32_t(samples_[i].tick-(tick-period))>=period &&
           uint32_t(samples_[i].tick-tick)<hz_/10) samples_[kept++]=samples_[i];
    count_=kept;
}
// Fit DC + 1/rev..fitHarmonics/rev cosine and sine terms, rather than treating gravity as
// vibration. A revolution holds a non-integer number of samples, so an unmodelled 2/rev leaks
// into the 1/rev estimate differently every revolution; fitting the low harmonics jointly
// removes that leakage. Only the DC and 1/rev terms are used.
// Each sample angle is interpolated between two actual tach edges, not fixed RPM.
void Measurement::fitCycle(uint32_t end,uint32_t period) {
    constexpr int P=2*fitHarmonics+1;
    double m[P][P]{}, b[P][3]{}; unsigned n=0;
    for(unsigned i=0;i<count_;i++) {
        const uint32_t dt=samples_[i].tick-previousTach_;
        if(dt>=period) continue;
        const double angle=2*pi*dt/period;
        double x[P];x[0]=1;
        for(int h=1;h<=fitHarmonics;h++) {x[2*h-1]=std::cos(h*angle);x[2*h]=std::sin(h*angle);}
        for(int j=0;j<P;j++) {
            for(int k=0;k<P;k++) m[j][k]+=x[j]*x[k];
            for(int a=0;a<3;a++) b[j][a]+=x[j]*samples_[i].g[a];
        }
        ++n;
    }
    const double expected=sampleRate*double(period)/hz_;
    if(n<12 || n<expected*0.90 || n>expected*1.10) { flags_|=SampleGap; return; }
    // Gauss-Jordan elimination with pivoting; RHS contains all three axes.
    for(int k=0;k<P;k++) {
        int pivot=k; for(int j=k+1;j<P;j++) if(std::abs(m[j][k])>std::abs(m[pivot][k])) pivot=j;
        if(std::abs(m[pivot][k])<1e-8) {flags_|=TimingError;return;}
        for(int j=0;j<P;j++) std::swap(m[k][j],m[pivot][j]);
        for(int a=0;a<3;a++) std::swap(b[k][a],b[pivot][a]);
        const double div=m[k][k];
        for(int j=0;j<P;j++) m[k][j]/=div;
        for(int a=0;a<3;a++) b[k][a]/=div;
        for(int i=0;i<P;i++) if(i!=k) {
            const double f=m[i][k];
            for(int j=0;j<P;j++) m[i][j]-=f*m[k][j];
            for(int a=0;a<3;a++) b[i][a]-=f*b[k][a];
        }
    }
    const double sec=double(period)/hz_, factor=gravity*metresToInches*sec/(2*pi);
    for(int a=0;a<3;a++) {
        // Integrating acceleration: velocity cosine=-accel sine/omega,
        // velocity sine=accel cosine/omega. Phase = time of positive velocity peak.
        const double c=-b[2][a]*factor, s=b[1][a]*factor;
        sumC_[a]+=c;sumS_[a]+=s;sumCC_[a]+=c*c;sumSS_[a]+=s*s;sumCS_[a]+=c*s;sumDc_[a]+=b[0][a];
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
    r.clippedAxes=clipped_;
    // Per-revolution covariance, projected along and across the mean vector.
    const double mc=sumC_[a]/revs_,ms=sumS_[a]/revs_;
    const double vcc=std::max(0.0,sumCC_[a]/revs_-mc*mc),vss=std::max(0.0,sumSS_[a]/revs_-ms*ms);
    const double vcs=sumCS_[a]/revs_-mc*ms;
    const double total=vcc+vss;
    double along=total/2;
    if(raw>0) along=(mc*mc*vcc+2*mc*ms*vcs+ms*ms*vss)/(raw*raw);
    along=std::min(std::max(along,0.0),total);
    const double across=total-along;
    r.vectorScatter=std::sqrt(total);r.amplitudeScatter=std::sqrt(along);
    r.phaseScatterDeg=std::atan2(std::sqrt(across),raw)*180/pi;
    r.peak=raw*config_.gain;r.rms=r.peak/std::sqrt(2.0);
    const double signedPhase=wrapDegrees(r.rawPhase[a]+(config_.sign<0?180:0));
    r.phase=wrapDegrees(config_.phaseDirection*signedPhase+config_.phaseOffsetDeg);
    r.accelerationPhase=wrapDegrees(signedPhase-90);
    // VibrationUnstable keeps its original meaning (combined scatter), so a stable vector is
    // judged exactly as before. PhaseUnstable applies the same 20% / 0.005 IPS limit to the
    // across-vector part alone (20% is about 11 degrees per revolution); a run that fails only
    // on amplitude still has a usable direction.
    const double limit=std::max(0.005,raw*0.2);
    if(r.rpmCv>0.02) r.flags|=RpmUnstable;
    if(r.vectorScatter>limit) r.flags|=VibrationUnstable;
    if(std::sqrt(across)>limit) r.flags|=PhaseUnstable;
    if(raw<0.005 || raw<2*r.vectorScatter/std::sqrt(double(revs_))) r.flags|=WeakSignal;
    const uint32_t hard=NoTach|TooFewRevs|SampleGap|Clipping|IoError|QueueOverflow|TimingError|Cancelled;
    r.valid=!(r.flags&hard);
    r.directionValid=r.valid && !(r.flags&(RpmUnstable|PhaseUnstable|AxisUnconfirmed|WeakSignal));
    r.stable=r.valid && !(r.flags&(RpmUnstable|VibrationUnstable|PhaseUnstable|AxisUnconfirmed));
    r.phaseValid=r.stable && r.directionValid;
    r.quality=r.phaseValid?Quality::StableVector:r.directionValid?Quality::DirectionOnly:Quality::Unreliable;
    return r;
}
}
