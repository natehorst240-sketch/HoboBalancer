// MicroVib II file decoders and balance math. Plain script; also loadable in node for tests.
(function (root) {
  'use strict';
  const M = {};

  // ---- number formats used by the MicroVib ----
  // F16: [mant u8][exp u8], value = mant * 2^(exp-72). C32: [m0 m1 m2 exp], mant = m2 + m1/256 + m0/65536.
  M.f16 = (b, o) => (b[o + 1] || b[o]) ? b[o] * Math.pow(2, b[o + 1] - 72) : 0;
  M.c32 = (b, o) => b[o + 3] ? (b[o + 2] + b[o + 1] / 256 + b[o] / 65536) * Math.pow(2, b[o + 3] - 72) : 0;
  M.f32 = (b, o) => new DataView(b.buffer, b.byteOffset + o, 4).getFloat32(0, true);
  M.u16 = (b, o) => b[o] | (b[o + 1] << 8);
  const str = (b, o, n) => { let s = ''; for (let i = 0; i < n && b[o + i]; i++) s += String.fromCharCode(b[o + i]); return s; };

  // ---- .grp / head of .hst ----
  M.decodeGroup = function (bytes) {
    const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    const g = { name: str(b, 0, 8), tasks: [] };
    for (let i = 0; i < 10; i++) {
      const o = 16 + i * 180;
      const n = Math.min(b[o + 19], 8);
      const t = { name: str(b, o, 8), enabled: !!b[o + 8], sens: M.f16(b, o + 11), tach: M.f16(b, o + 15), flags: M.u16(b, o + 17), positions: [] };
      for (let k = 0; k < n; k++) {
        const e = o + 20 + 20 * k;
        t.positions.push({ unit: str(b, e, 8), angle: M.f16(b, e + 8), label: str(b, e + 10, 8) });
      }
      g.tasks.push(t);
    }
    return g;
  };

  // ---- .hst run records (86 bytes each after the 1816-byte group section) ----
  M.decodeHistory = function (bytes) {
    const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    const g = M.decodeGroup(b);
    const runs = [];
    for (let o = 1816; o + 86 <= b.length; ) {
      // records are located by the 03 c3 1b marker at +6
      if (!(b[o + 6] === 0x03 && b[o + 7] === 0xc3 && b[o + 8] === 0x1b)) { o++; continue; }
      const ti = b[o];
      const day = M.u16(b, o + 2), tm = M.u16(b, o + 4);
      const when = new Date(Date.UTC(1980, 0, 1) + (day * 86400 + tm * 2) * 1000);
      const adj = [[M.c32(b, o + 60), M.c32(b, o + 64)], [M.c32(b, o + 72), M.c32(b, o + 76)]];
      const sens = M.c32(b, o + 52), tach = M.c32(b, o + 56);
      const d = Math.abs(adj[0][1] - adj[1][1]) % 360;
      const mag = (d === 90 || d === 270) ? Math.hypot(adj[0][0], adj[1][0]) : d === 180 ? Math.abs(adj[0][0] - adj[1][0]) : adj[0][0] + adj[1][0];
      runs.push({
        task: g.tasks[ti] ? g.tasks[ti].name : String(ti), when, avgs: b[o + 21], rpm: M.f32(b, o + 24) * 60 / 64,
        levelRaw: M.f32(b, o + 28), phase: M.c32(b, o + 32), prevLevel: M.c32(b, o + 36), prevPhase: M.c32(b, o + 40),
        change: { mag: M.c32(b, o + 44), loc: M.c32(b, o + 48) }, sens, tach, adj,
        level: sens ? mag / sens : M.f32(b, o + 28)
      });
      o += 86;
    }
    return { group: g, runs };
  };

  // ---- balance math ----
  const D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const mod360 = a => ((a % 360) + 360) % 360;
  M.mod360 = mod360;
  // vibration vector in the phase frame as [re, im]
  M.vec = (level, phase) => [level * Math.cos(phase * D2R), level * Math.sin(phase * D2R)];

  // MicroVib single-step coefficient from a move: W (mag, loc) moved V_prev -> V_new.
  M.learn = function (prev, next, change) {
    const a = M.vec(prev.level, prev.phase), c = M.vec(next.level, next.phase);
    const d = [c[0] - a[0], c[1] - a[1]];
    const dm = Math.hypot(d[0], d[1]);
    if (!dm || !change.mag) return null;
    const da = Math.atan2(d[1], d[0]) * R2D;
    return { sens: change.mag / dm, tach: mod360(-da - change.loc), deltaLevel: dm };
  };

  // Blend an old coefficient with a measured one. w = trust in the new measurement (0..1).
  M.blend = function (old, meas, w) {
    const sens = Math.exp((1 - w) * Math.log(old.sens) + w * Math.log(meas.sens));
    const ox = Math.cos(old.tach * D2R), oy = Math.sin(old.tach * D2R);
    const mx = Math.cos(meas.tach * D2R), my = Math.sin(meas.tach * D2R);
    const tach = mod360(Math.atan2((1 - w) * oy + w * my, (1 - w) * ox + w * mx) * R2D);
    return { sens, tach };
  };

  // Weighted least-squares solution for one adjustment shared by several regimes.
  // regimes: [{level, phase, sens, tach, weight}]. Returns {mag, angle} on the rotor.
  M.solve = function (regimes) {
    let nr = 0, ni = 0, den = 0;
    for (const r of regimes) {
      const w = r.weight == null ? 1 : r.weight;
      if (!w || !r.sens) continue;
      const k = [Math.cos(-r.tach * D2R) / r.sens, Math.sin(-r.tach * D2R) / r.sens]; // e^{-i tach}/sens
      const v = M.vec(r.level, r.phase);
      // conj(k) * v
      nr += w * (k[0] * v[0] + k[1] * v[1]);
      ni += w * (k[0] * v[1] - k[1] * v[0]);
      den += w * (k[0] * k[0] + k[1] * k[1]);
    }
    if (!den) return null;
    const ur = -nr / den, ui = -ni / den; // u = conj(z)
    const mag = Math.hypot(ur, ui), angle = mod360(-Math.atan2(ui, ur) * R2D);
    return { mag, angle };
  };

  // Split a vector (mag at angle) onto the two adjacent positions bracketing it.
  M.split = function (mag, angle, positions) {
    const ps = positions.map(p => p.angle).sort((a, b) => a - b);
    if (ps.length < 2) return [{ angle: ps[0], amount: mag }];
    let i = 0;
    while (i < ps.length && ps[i] <= angle) i++;
    const a1 = ps[(i - 1 + ps.length) % ps.length], a2 = ps[i % ps.length];
    // solve mag*(cosA, sinA) = w1*(cos a1, sin a1) + w2*(cos a2, sin a2)
    const c1 = Math.cos(a1 * D2R), s1 = Math.sin(a1 * D2R), c2 = Math.cos(a2 * D2R), s2 = Math.sin(a2 * D2R);
    const det = c1 * s2 - s1 * c2;
    const vx = mag * Math.cos(angle * D2R), vy = mag * Math.sin(angle * D2R);
    if (Math.abs(det) < 1e-9) return [{ angle: a1, amount: mag }];
    const w1 = (vx * s2 - vy * c2) / det, w2 = (c1 * vy - s1 * vx) / det;
    return [{ angle: a1, amount: w1 }, { angle: a2, amount: w2 }].filter(x => Math.abs(x.amount) > 1e-6);
  };

  // Predicted vibration after applying an adjustment vector z (mag at angle) to a regime.
  M.predict = function (r, mag, angle) {
    const v = M.vec(r.level, r.phase);
    const dv = M.vec(mag / r.sens, -angle - r.tach);
    const x = v[0] + dv[0], y = v[1] + dv[1];
    return { level: Math.hypot(x, y), phase: mod360(Math.atan2(y, x) * R2D) };
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = M; else root.MV2 = M;
})(typeof window !== 'undefined' ? window : globalThis);
