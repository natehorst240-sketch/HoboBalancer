% sim_acquisition.m
% Simulate the v2 measurement chain before building it: a 1/rev + 4/rev vibration on an
% ADXL357 (20-bit, 4 kHz ODR, ~1 kHz LPF, 80 ug/rtHz noise), a tach with jitter and a fixed
% delay, synchronous demodulation per revolution, and averaging over N revolutions.
% Reports IPS and phase error versus N for the magnetic pickup (low jitter) and the
% Banner photo-tach (0.3 ms repeatability). Run from this folder: sim_acquisition
clear; clc;
addpath(fileparts(mfilename('fullpath')));   % so the mv2_* functions resolve from any folder rng(1);

% ---- scenario ----
rpm      = 395;              % main rotor below 40 kt (385 in forward flight)
v_ips    = 0.10;             % true 1/rev velocity, in/s peak
v_phase  = 151.3;            % true phase, deg (relative to the tach)
v4_ips   = 0.60;             % 4/rev content, typical cabin level at 140 kt
fs       = 4000;             % ADXL357 ODR
g        = 386.09;           % in/s^2 per g
noise_d  = 80e-6;            % g/rtHz, ADXL357 datasheet typical
lsb      = 10/2^19;          % g per count at +/-10 g, 20-bit
tach_delay = 0.3e-3;         % fixed sensor delay (Banner 0.3 ms); magnetic pickup ~0
jitters  = [5e-6, 0.3e-3];   % tach jitter std: magnetic pickup, Banner MHS
names    = {'magnetic pickup', 'Banner photo-tach'};
Ns       = [8 16 32 64 128 256];
trials   = 40;

f = rpm/60; w = 2*pi*f; T = 1/f;
% ADXL357 LPF: approximate the ~1 kHz response with two cascaded 2nd-order Butterworth
% biquads (bilinear transform, no toolbox needed)
[bb, ab] = lp_biquad(1000, fs);

fprintf('rotor %.0f RPM, true 1/rev %.3f IPS at %.1f deg, 4/rev %.2f IPS, noise %.0f ug/rtHz\n', rpm, v_ips, v_phase, v4_ips, noise_d*1e6);
for j = 1:numel(jitters)
    fprintf('\n%s, jitter %.3f ms, fixed delay %.2f ms\n', names{j}, jitters(j)*1e3, tach_delay*1e3);
    fprintf('%6s %12s %12s %12s %12s\n', 'N revs', 'IPS mean', 'IPS std', 'phase mean', 'phase std');
    for N = Ns
        est = zeros(trials, 2);
        for tr = 1:trials
            nrev = N + 2;
            t = (0:1/fs:nrev*T)';
            % acceleration in g: a = dv/dt, v = V cos(wt+phi) -> a = -V w sin(wt+phi)
            a = -(v_ips*w/g)*sin(w*t + deg2rad(v_phase)) - (v4_ips*4*w/g)*sin(4*w*t + 1.0);
            a = a + noise_d*sqrt(fs/2)*randn(size(t));           % sensor noise
            a = filter(bb, ab, filter(bb, ab, a));                % ADXL357 digital LPF, 4th order
            a = round(a/lsb)*lsb;                                 % 20-bit quantization
            % tach edges: once per rev at t = k*T, plus fixed delay plus jitter
            edges = (0:nrev-1)'*T + tach_delay + jitters(j)*randn(nrev, 1);
            % synchronous demodulation per revolution, then average N of them
            acc = 0;
            for k = 2:N+1
                idx = t >= edges(k) & t < edges(k+1);
                ph = 2*pi*(t(idx) - edges(k))/(edges(k+1) - edges(k));
                acc = acc + 2*mean(a(idx).*exp(-1i*ph));          % complex amplitude of 1/rev accel, in g
            end
            A = acc/N;                                            % a(t) = Re(A e^{i w t'}) with t' from the tach
            % velocity from acceleration: v = A/(i w), in in/s; recover phase of the cosine
            Vc = A*g/(1i*w);
            est(tr, :) = [abs(Vc), mod(rad2deg(angle(Vc)), 360)];
        end
        % remove the known fixed delay from the phase (it is calibrated out in use)
        pm = mod(mean(est(:,2)) + 360*f*tach_delay, 360);
        fprintf('%6d %12.4f %12.4f %12.1f %12.2f\n', N, mean(est(:,1)), std(est(:,1)), pm, std(est(:,2)));
    end
end
fprintf('\nTarget: resolve 0.02 IPS and a few degrees. Phase mean should land on %.1f after the delay correction.\n', v_phase);

