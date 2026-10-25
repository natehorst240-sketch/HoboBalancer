# sim_sensors.py: Python port of sim_acquisition.m with the accelerometer as a parameter.
# Compares the ADXL357 baseline with the KX134 (and the LSM6DSO32) at 0.10 and 0.02 IPS.
# Run: python3 sim_sensors.py   (needs numpy and scipy). Results recorded in design-notes-2026-10-22.md.
import numpy as np
from scipy.signal import butter, lfilter
rng = np.random.default_rng(1)
g = 386.09; rpm = 395; f = rpm/60; w = 2*np.pi*f; T = 1/f
sensors = [  # name, ODR, noise g/rtHz, LSB g, LPF Hz
    ('ADXL357 +/-10 g 20-bit', 4000, 80e-6, 10/2**19, 1000),
    ('KX134 +/-64 g 16-bit', 3200, 130e-6, 64/2**15, 800),
    ('KX134 +/-64 g, noise x2 (margin)', 3200, 260e-6, 64/2**15, 800),
    ('LSM6DSO32 +/-32 g 16-bit', 3330, 220e-6, 32/2**15, 800),
]
jit = 5e-6  # magnetic pickup
for v_ips in (0.10, 0.02):
    print(f'\ntrue 1/rev {v_ips} IPS at 151.3 deg, 0.6 IPS 4/rev, magnetic pickup tach')
    print(f'{"sensor":36s} {"N":>4s} {"IPS mean":>9s} {"IPS std":>8s} {"ph std":>7s}')
    for name, fs, nd, lsb, fc in sensors:
        b, a_ = butter(4, fc/(fs/2))
        for N in (16, 32, 64):
            est = []
            for tr in range(40):
                nrev = N + 2; t = np.arange(0, nrev*T, 1/fs)
                a = -(v_ips*w/g)*np.sin(w*t + np.deg2rad(151.3)) - (0.6*4*w/g)*np.sin(4*w*t + 1.0)
                a = a + nd*np.sqrt(fs/2)*rng.standard_normal(t.size)
                a = lfilter(b, a_, a); a = np.round(a/lsb)*lsb
                edges = np.arange(nrev)*T + jit*rng.standard_normal(nrev)
                acc = 0
                for k in range(1, N+1):
                    i = (t >= edges[k]) & (t < edges[k+1])
                    ph = 2*np.pi*(t[i]-edges[k])/(edges[k+1]-edges[k])
                    acc += 2*np.mean(a[i]*np.exp(-1j*ph))
                V = (acc/N)*g/(1j*w); est.append((abs(V), np.degrees(np.angle(V)) % 360))
            e = np.array(est)
            print(f'{name:36s} {N:4d} {e[:,0].mean():9.4f} {e[:,0].std():8.4f} {e[:,1].std():7.2f}')
