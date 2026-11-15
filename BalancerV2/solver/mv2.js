// MicroVib II file decoders and balance math. Plain script; also loadable in node for tests.
(function (root) {
  'use strict';
  const M = {};

  // ---- number formats used by the MicroVib ----
  // F16: [mant u8][exp u8], value = mant * 2^(exp-72). C32: [m0 m1 m2 exp], mant = m2 + m1/256 + m0/65536.
  M.f16 = (b, o) => (b[o + 1] || b[o]) ? b[o] * Math.pow(2, b[o + 1] - 72) : 0;
  // C32 sign: bit 7 of the exponent byte (A1090021.HST record 3 holds 753.2 as cd 4c bc 4a and
  // -753.2 as cd 4c bc ca; MicroBase shows both). Verified 2026-11-14.
  M.c32 = (b, o) => { const e = b[o + 3]; if (!e) return 0; const v = (b[o + 2] + b[o + 1] / 256 + b[o] / 65536) * Math.pow(2, (e & 0x7f) - 72); return e & 0x80 ? -v : v; };
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

  // Profile revision: FNV-1a over the 1816-byte group section, so a .grp and the .hst files
  // recorded under it carry the same revision, and a changed group is a different revision.
  M.groupRev = function (bytes) {
    const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    let h = 0x811c9dc5;
    for (let i = 0; i < Math.min(b.length, 1816); i++) { h ^= b[i]; h = Math.imul(h, 0x01000193) >>> 0; }
    return 'grp-' + h.toString(16).padStart(8, '0');
  };

  // ---- .hst run records (86 bytes each after the 1816-byte group section) ----
  // Field formats verified 2026-11-14 against MicroBase Pro's own decoding of A1090731 and
  // A1090021 (13 runs): RPM at +24 is IEEE float32 x 60/64; the level at +28, phase, previous
  // level/phase, entered change, SENS, TACH and the solution vectors are all C32. Reading the
  // level as float32 was wrong by powers of two (the "range factor" of earlier notes).
  M.decodeHistory = function (bytes) {
    const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    const g = M.decodeGroup(b);
    g.rev = M.groupRev(b);
    const runs = [];
    for (let o = 1816; o + 86 <= b.length; ) {
      // records are located by the 03 c3 1b marker at +6
      if (!(b[o + 6] === 0x03 && b[o + 7] === 0xc3 && b[o + 8] === 0x1b)) { o++; continue; }
      const ti = b[o];  // taskIndex
      const day = M.u16(b, o + 2), tm = M.u16(b, o + 4);
      const when = new Date(Date.UTC(1980, 0, 1) + (day * 86400 + tm * 2) * 1000);
      const adj = [[M.c32(b, o + 60), M.c32(b, o + 64)], [M.c32(b, o + 72), M.c32(b, o + 76)]];
      const sens = M.c32(b, o + 52), tach = M.c32(b, o + 56);
      const d = Math.abs(adj[0][1] - adj[1][1]) % 360;
      const mag = (d === 90 || d === 270) ? Math.hypot(adj[0][0], adj[1][0]) : d === 180 ? Math.abs(adj[0][0] - adj[1][0]) : adj[0][0] + adj[1][0];
      const run = {
        task: g.tasks[ti] ? g.tasks[ti].name : String(ti), taskIndex: ti, when, avgs: b[o + 21], rpm: M.f32(b, o + 24) * 60 / 64,
        levelStored: M.c32(b, o + 28), phase: M.c32(b, o + 32), prevLevel: M.c32(b, o + 36), prevPhase: M.c32(b, o + 40),
        change: { mag: M.c32(b, o + 44), loc: M.c32(b, o + 48) }, sens, tach, adj,
        // `adj` is the change entered AFTER this run (MicroBase's CHG1/LOC1, CHG2/LOC2 columns on
        // this row), as the two split entries, signed. `change` is the combined vector of the
        // change entered BEFORE this run, which is what this run's SENS/TACH were learned from.
        levelFromSolution: sens ? mag / sens : NaN
      };
      run.problems = M.checkRun(run, g);
      run.verified = run.problems.length === 0;
      // An unverified record carries no level: nothing downstream can mistake it for a measurement.
      run.level = run.verified ? run.levelStored : null;
      // The split entries that make up this run's `change`: the previous record's adj block,
      // but only when a change was actually entered (combined change non-zero) and the rows
      // belong to the same task. Otherwise the previous adj is DSS's proposed solution, not an
      // entry (A1090731: every run is the first of its task, TRIAL still set), and there is no
      // change. Consistent when the entries' vector sum equals the combined change within 1%.
      const prev = runs[runs.length - 1];
      const cm = M.changeVector(run.change);
      run.changeMoves = cm && prev && prev.taskIndex === run.taskIndex ? prev.adj.filter(([a]) => Math.abs(a) > 1e-9).map(([a, l]) => ({ amount: a, angle: l })) : [];
      const cv = M.changeVector({ moves: run.changeMoves });
      run.changeOk = !cm ? true : !!cv && Math.hypot(cv[0] - cm[0], cv[1] - cm[1]) <= 0.01 * Math.hypot(cm[0], cm[1]) + 1e-6;
      runs.push(run);
      o += 86;
    }
    return { group: g, runs };
  };

  // Plausibility of one decoded .hst record: the measurement fields (level, phase, RPM, SENS,
  // TACH, entered change) must be finite and in range. The solution block is checked
  // separately (run.solutionOk) because it is garbled in some records while the measurement is
  // fine; MicroBase shows those runs normally.
  M.checkRun = function (r, g) {
    const p = [];
    const fin = x => typeof x === 'number' && isFinite(x);
    if (!g.tasks[r.taskIndex === undefined ? 0 : r.taskIndex]) p.push('task index outside the group');
    if (!(fin(r.rpm) && r.rpm > 30 && r.rpm < 20000)) p.push('RPM implausible');
    if (!(fin(r.phase) && r.phase >= 0 && r.phase < 360)) p.push('phase outside 0-360');
    if (!(fin(r.sens) && r.sens > 0 && r.sens < 1e5)) p.push('SENS implausible');
    if (!(fin(r.tach) && r.tach >= 0 && r.tach < 360)) p.push('TACH outside 0-360');
    if (![r.change.mag, r.change.loc].every(x => fin(x) && Math.abs(x) < 1e5)) p.push('entered change garbled');
    if (!(fin(r.levelStored) && r.levelStored >= 0 && r.levelStored < 50)) p.push('level implausible');
    return p;
  };

  // ---- balance math ----
  const D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const mod360 = a => ((a % 360) + 360) % 360;
  M.mod360 = mod360;
  // vibration vector in the phase frame as [re, im]
  M.vec = (level, phase) => [level * Math.cos(phase * D2R), level * Math.sin(phase * D2R)];

  // The adjustment actually installed between two runs, as one signed vector on the rotor.
  // change: {mag, loc} (mag < 0 is a removal at loc) or {moves: [{amount, angle}, ...]} for a
  // move spread over several positions; removals are negative amounts. Returns [x, y] or null.
  M.changeVector = function (change) {
    if (!change) return null;
    const moves = change.moves || [{ amount: change.mag, angle: change.loc }];
    let x = 0, y = 0;
    for (const m of moves) {
      if (!isFinite(m.amount) || !isFinite(m.angle)) return null;
      x += m.amount * Math.cos(m.angle * D2R); y += m.amount * Math.sin(m.angle * D2R);
    }
    return Math.hypot(x, y) > 1e-9 ? [x, y] : null;
  };

  // MicroVib single-step coefficient from a move: adjustment W moved V_prev -> V_new.
  // W is the signed installed vector, so a removal (-2 g at 90) is learned as +2 g at 270.
  M.learn = function (prev, next, change) {
    const a = M.vec(prev.level, prev.phase), c = M.vec(next.level, next.phase);
    const d = [c[0] - a[0], c[1] - a[1]];
    const dm = Math.hypot(d[0], d[1]);
    const w = M.changeVector(change);
    if (!dm || !w || !isFinite(dm)) return null;
    const wm = Math.hypot(w[0], w[1]), wa = Math.atan2(w[1], w[0]) * R2D;
    const da = Math.atan2(d[1], d[0]) * R2D;
    return { sens: wm / dm, tach: mod360(-da - wa), deltaLevel: dm };
  };

  // Can the move from run `prev` to run `next` be learned from? Both must be the same aircraft,
  // component and profile revision with the same sensor calibration, at a matching RPM.
  // Returns a list of reasons it cannot (empty means compatible).
  M.compatible = function (prev, next, opts) {
    const tol = (opts && opts.rpmTolerance) || 0.02, why = [];
    for (const k of ['aircraft', 'task', 'profileRev', 'calibration'])
      if ((prev[k] || '') !== (next[k] || '')) why.push(k + ' differs');
    if (!(prev.rpm > 0 && next.rpm > 0)) why.push('RPM missing on one run');
    else if (Math.abs(prev.rpm - next.rpm) / next.rpm > tol) why.push(`RPM differs by more than ${tol * 100}%`);
    if (prev.verified === false || next.verified === false) why.push('unverified run');
    return why;
  };

  // Blend an old coefficient with a measured one. w = trust in the new measurement (0..1).
  // Returns null if either coefficient is not a usable (positive, finite) sensitivity.
  M.blend = function (old, meas, w) {
    if (!(old && meas && old.sens > 0 && meas.sens > 0 && isFinite(old.sens) && isFinite(meas.sens) && isFinite(old.tach) && isFinite(meas.tach))) return null;
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

  // Installable move for a requested correction vector (mag at angle, adjustment units at the
  // reference radius). stations: [{angle, radius?, lo, hi, step?}], where [lo, hi] is the change
  // allowed at that station (a weight: -installed .. max - installed; a tab: -max .. max) and
  // step the smallest installable increment. Minimises |requested - achieved| over the actual
  // station angles and radii, then rounds to whole steps without leaving the bounds. Returns
  // {moves: [{angle, amount}], achieved: {mag, angle}, miss} where `achieved` is the vector the
  // rounded move really applies; predict from that, never from the request.
  M.place = function (mag, angle, stations, refRadius) {
    const ref = refRadius || 1, n = stations.length;
    const ex = stations.map(s => (s.radius || ref) / ref * Math.cos(s.angle * D2R));
    const ey = stations.map(s => (s.radius || ref) / ref * Math.sin(s.angle * D2R));
    const tx = mag * Math.cos(angle * D2R), ty = mag * Math.sin(angle * D2R);
    const lo = stations.map(s => Math.min(0, s.lo == null ? -Infinity : s.lo));
    const hi = stations.map(s => Math.max(0, s.hi == null ? Infinity : s.hi));
    const a = new Array(n).fill(0);
    const miss = v => { let x = tx, y = ty; for (let i = 0; i < n; i++) { x -= v[i] * ex[i]; y -= v[i] * ey[i]; } return Math.hypot(x, y); };
    // Bounded least squares by cyclic coordinate descent: convex, and n is at most a dozen.
    for (let it = 0; it < 500; it++) {
      let moved = 0;
      for (let i = 0; i < n; i++) {
        const nn = ex[i] * ex[i] + ey[i] * ey[i]; if (!nn) continue;
        let rx = tx, ry = ty; for (let j = 0; j < n; j++) if (j !== i) { rx -= a[j] * ex[j]; ry -= a[j] * ey[j]; }
        const v = Math.min(hi[i], Math.max(lo[i], (rx * ex[i] + ry * ey[i]) / nn));
        moved = Math.max(moved, Math.abs(v - a[i])); a[i] = v;
      }
      if (moved < 1e-9) break;
    }
    // Round to installable steps inside the bounds, then improve one step at a time.
    const step = stations.map(s => s.step > 0 ? s.step : 0);
    const snap = (v, i) => { if (!step[i]) return v; const q = Math.round(v / step[i]) * step[i]; return q > hi[i] + 1e-9 ? q - step[i] : q < lo[i] - 1e-9 ? q + step[i] : q; };
    let r = a.map(snap), best = miss(r);
    for (let it = 0; it < 200; it++) {
      let improved = false;
      for (let i = 0; i < n; i++) for (const d of [-1, 1]) {
        if (!step[i]) continue;
        const v = r[i] + d * step[i]; if (v > hi[i] + 1e-9 || v < lo[i] - 1e-9) continue;
        const t = r.slice(); t[i] = v; const m = miss(t);
        if (m < best - 1e-12) { r = t; best = m; improved = true; }
      }
      if (!improved) break;
    }
    if (miss(new Array(n).fill(0)) <= best) { r = new Array(n).fill(0); best = miss(r); }
    let ax = 0, ay = 0; for (let i = 0; i < n; i++) { ax += r[i] * ex[i]; ay += r[i] * ey[i]; }
    return {
      moves: stations.map((s, i) => ({ angle: s.angle, amount: Math.abs(r[i]) < 1e-9 ? 0 : r[i] })).filter(m => m.amount),
      achieved: { mag: Math.hypot(ax, ay), angle: mod360(Math.atan2(ay, ax) * R2D) }, miss: best
    };
  };

  // Placement under rotor rules from the aircraft procedure (DSS AN-MV2-A109 rev 03: main rotor
  // "only adjacent blades should have balance weights"; tail rotor "maximum number of bolts on
  // the balance flange is four", "maximum weight per balance flange is 100 grams").
  // rules: {maxLoaded, adjacentOnly, maxTotal}; installed: weight now at each station, parallel
  // to `stations` (stations in angular order, so index neighbours are angular neighbours).
  // Every allowed set of stations is tried: the loaded ones must stay in the set (a loaded
  // station may still be emptied by a removal), others are added up to maxLoaded, adjacency and
  // the total are checked on the result, and the M.place result with the smallest miss wins.
  // Returns that result plus `set` (station indices), or null when the current installation
  // already breaks the rules so no placement can be offered.
  M.placeConstrained = function (mag, angle, stations, rules, installed) {
    const n = stations.length, inst = installed || new Array(n).fill(0), r = rules || {};
    const loaded = []; inst.forEach((w, i) => { if (w > 1e-9) loaded.push(i); });
    const maxLoaded = r.maxLoaded > 0 ? r.maxLoaded : n;
    const maxTotal = r.maxTotal != null ? r.maxTotal : Infinity;
    if (loaded.length > maxLoaded) return null;
    const adjacentSet = set => {
      if (set.length < 2) return true;
      if (set.length > 2) return false;
      const d = set[1] - set[0];
      return d === 1 || (set[0] === 0 && set[1] === n - 1);
    };
    let best = null;
    const subset = [];
    const consider = () => {
      const set = loaded.concat(subset).sort((x, y) => x - y);
      if (r.adjacentOnly && !adjacentSet(set)) return;
      const st = stations.map((s, i) => set.includes(i) ? s : Object.assign({}, s, { lo: 0, hi: 0 }));
      let p = M.place(mag, angle, st);
      let total = 0; inst.forEach(w => { total += w; }); p.moves.forEach(m => { total += m.amount; });
      if (total > maxTotal + 1e-9) {
        // Over the total limit: scale the additions down to what the limit leaves, keep the
        // removals, snap to steps, and take the partial correction that results.
        const adds = p.moves.filter(m => m.amount > 0).reduce((q, m) => q + m.amount, 0);
        const allow = Math.max(0, maxTotal - (total - adds));
        if (!adds) return;
        const moves = p.moves.map(m => {
          if (m.amount <= 0) return m;
          const s = stations.find(x => x.angle === m.angle), step = s && s.step > 0 ? s.step : 0;
          const v = m.amount * allow / adds;
          return { angle: m.angle, amount: step ? Math.floor(v / step + 1e-9) * step : v };
        }).filter(m => Math.abs(m.amount) > 1e-9);
        let ax = 0, ay = 0;
        for (const m of moves) { const s = stations.find(x => x.angle === m.angle); const rr = s.radius || 1; ax += m.amount * rr * Math.cos(m.angle * D2R); ay += m.amount * rr * Math.sin(m.angle * D2R); }
        const miss = Math.hypot(mag * Math.cos(angle * D2R) - ax, mag * Math.sin(angle * D2R) - ay);
        p = { moves, achieved: { mag: Math.hypot(ax, ay), angle: mod360(Math.atan2(ay, ax) * R2D) }, miss, capped: true };
      }
      if (!best || p.miss < best.miss - 1e-12 || (Math.abs(p.miss - best.miss) <= 1e-12 && set.length < best.set.length)) best = Object.assign({ set }, p);
    };
    const free = []; for (let i = 0; i < n; i++) if (!loaded.includes(i)) free.push(i);
    (function rec(start) {
      consider();
      if (loaded.length + subset.length >= maxLoaded) return;
      for (let k = start; k < free.length; k++) { subset.push(free[k]); rec(k + 1); subset.pop(); }
    })(0);
    return best;
  };

  // Split a vector (mag at angle) onto the two adjacent positions bracketing it. Exact only when
  // the two bracketing positions are less than 180 deg apart and negative amounts are allowed;
  // use M.place for anything that will be installed.
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
