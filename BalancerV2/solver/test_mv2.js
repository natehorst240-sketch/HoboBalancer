// Regression checks for mv2.js. Run: node BalancerV2/solver/test_mv2.js
'use strict';
const M = require('./mv2.js');
const fs = require('fs');
const path = require('path');
let checks = 0;
function check(ok, name) { checks++; if (!ok) { console.error('FAIL: ' + name); process.exit(1); } }
const near = (a, b, tol, name) => check(Math.abs(a - b) <= tol, `${name} (${a} vs ${b})`);
const angNear = (a, b, tol, name) => { const ok = Math.abs(M.mod360(a - b + 180) - 180) <= tol; if (name) check(ok, `${name} (${a} vs ${b})`); return ok; };
const prof = f => fs.readFileSync(path.join(__dirname, '..', 'profiles', f));

// ---- history import ----
// A1090731: MicroBase screen levels recorded in profiles/A109-procedure.md.
const h731 = M.decodeHistory(prof('A1090731.HST'));
const screen731 = [0.085, 0.028, 0.169, 0.093, 0.144];
check(h731.runs.length === 5, 'A1090731 has five runs');
h731.runs.forEach((r, i) => {
  check(r.verified, `A1090731 run ${i + 1} verified`);
  near(r.level, screen731[i], 0.0006, `A1090731 run ${i + 1} level matches screen`);
});
// A1090021: levels, phases, SENS and TACH as MicroBase Pro displays them (Identify Data
// preview, 2026-11-14). The solution block is garbled in runs 3, 6 and 8; the runs are still
// valid measurements.
const h021 = M.decodeHistory(prof('A1090021.HST'));
const screen021 = [[0.682, 354, 320.0, 340], [0.789, 25, 320.0, 340], [0.933, 37, 1206.0, 97], [0.682, 271, 739.2, 75],
  [0.248, 253, 666.5, 79], [0.197, 183, 394.3, 61], [0.410, 147, 276.7, 328], [0.213, 185, 184.8, 332]];
check(h021.runs.length === 8, 'A1090021 has eight runs');
h021.runs.forEach((r, i) => {
  const [lv, ph, se, ta] = screen021[i];
  check(r.verified && r.level != null, `A1090021 run ${i + 1} verified`);
  near(r.level, lv, 0.0006, `A1090021 run ${i + 1} level`); angNear(r.phase, ph, 0.6, `A1090021 run ${i + 1} phase`);
  near(r.sens, se, Math.max(0.06, se * 3e-4), `A1090021 run ${i + 1} SENS`); angNear(r.tach, ta, 0.6, `A1090021 run ${i + 1} TACH`);
});
// The change entered after each run, as MicroBase's Balance History shows it for this file
// (CHG1@LOC1, CHG2@LOC2 per row; signed, zero entries dropped).
const chg021 = [[], [[278.7, 180]], [[753.2, 90], [-753.2, 180]], [[301.8, 180]], [[102.8, 180]], [[-76.3, 90]], [[50.9, 90]], [[15.7, 90], [-36.1, 180]]];
h021.runs.forEach((r, i) => {
  const got = r.adj.filter(([a]) => Math.abs(a) > 1e-9).map(([a, l]) => [Math.round(a * 10) / 10, Math.round(l)]);
  check(JSON.stringify(got) === JSON.stringify(chg021[i]), `A1090021 row ${i + 1} change entries ${JSON.stringify(got)} vs MicroBase ${JSON.stringify(chg021[i])}`);
  check(r.changeOk, `A1090021 run ${i + 1} split entries sum to the combined change`);
  if (i) check(JSON.stringify(r.changeMoves.map(m => [Math.round(m.amount * 10) / 10, Math.round(m.angle)])) === JSON.stringify(chg021[i - 1]), `run ${i + 1} changeMoves are the previous row's entries`);
});
check(h731.runs.every(r => r.changeOk), 'A1090731 change blocks consistent');
check(M.c32(new Uint8Array([0xcd, 0x4c, 0xbc, 0xca]), 0) < 0 && Math.abs(M.c32(new Uint8Array([0xcd, 0x4c, 0xbc, 0x4a]), 0) - 753.2) < 0.01, 'C32 sign bit');
// The entered change in record N is the change before run N: learning each run from its
// predecessor with that change reproduces the SENS/TACH DSS recorded, run 4 included.
for (let i = 2; i < 8; i++) {
  const m = M.learn(h021.runs[i - 1], h021.runs[i], h021.runs[i].change);
  check(m && Math.abs(m.sens - h021.runs[i].sens) / h021.runs[i].sens < 0.001 && angNear(m.tach, h021.runs[i].tach, 0.1), `A1090021 run ${i + 1} learn reproduces DSS SENS/TACH`);
}
const bogus = M.decodeHistory(prof('A1090021.HST'));
bogus.runs[0].levelStored = 1e30; check(M.checkRun(bogus.runs[0], bogus.group).some(p => /level/.test(p)), 'implausible level rejected');

check(h731.group.rev === M.groupRev(prof('A109.grp')), 'A1090731 was recorded under A109.grp');
check(h021.group.rev !== h731.group.rev, 'A1090021 carries a different group revision');

// ---- signed adjustment learning ----
// Forward model: true coefficient SENS 20 g/IPS, TACH 30 deg; remove 2 g at 90.
const truth = { sens: 20, tach: 30 };
const prev = { level: 1.0, phase: 0 };
const after = M.predict({ ...prev, ...truth }, 2, 270);  // -2 g at 90 is +2 g at 270
const meas = M.learn(prev, after, { mag: -2, loc: 90 });
check(meas && meas.sens > 0 && isFinite(meas.sens), 'removal gives a positive sensitivity');
near(meas.sens, 20, 1e-6, 'removal learns the true SENS');
angNear(meas.tach, 30, 1e-6, 'removal learns the true TACH');
const blended = M.blend({ sens: 25, tach: 40 }, meas, 0.5);
check(blended && isFinite(blended.sens) && isFinite(blended.tach), 'blend after a removal is finite');
check(M.blend({ sens: 25, tach: 40 }, { sens: -10, tach: 0 }, 0.5) === null, 'blend refuses a negative sensitivity');
const spread = M.learn(prev, M.predict({ ...prev, ...truth }, Math.hypot(3, 4), Math.atan2(4, 3) * 180 / Math.PI),
  { moves: [{ amount: 3, angle: 0 }, { amount: 4, angle: 90 }] });
near(spread.sens, 20, 1e-6, 'move spread over two positions learns SENS');
check(M.learn(prev, after, { mag: 0, loc: 0 }) === null, 'no change, no learning');

const runA = { aircraft: 'N731HC', task: 'GND LT', profileRev: 'r1', rpm: 384 };
check(M.compatible(runA, { ...runA, rpm: 385 }).length === 0, 'matched runs are compatible');
check(M.compatible(runA, { ...runA, rpm: 410 }).some(x => /RPM/.test(x)), 'RPM mismatch blocks learning');
check(M.compatible(runA, { ...runA, aircraft: 'N109XX' }).length > 0, 'other aircraft blocks learning');
check(M.compatible(runA, { ...runA, calibration: 'cal-2' }).length > 0, 'calibration change blocks learning');
check(M.compatible(runA, { ...runA, verified: false }).length > 0, 'unverified run blocks learning');

// ---- placement against real stations ----
// Stations at 0 and 180 only, request 10 g at 90. The old splitter put 10 g at 0, which raised
// vibration from 1.00 to 1.41 IPS while the display predicted zero.
const reg = { level: 1.0, phase: 0, sens: 10, tach: 0 };
const sol = M.solve([reg]);
const r90 = { ...reg, phase: M.mod360(reg.phase + (sol.angle - 90)) };  // same regime, rotated so the request is at 90
const solved = M.solve([r90]);
near(solved.angle, 90, 1e-6, 'test regime requests 90 deg');
const oldSplit = M.split(solved.mag, solved.angle, [{ angle: 0 }, { angle: 180 }]);
const oldPred = M.predict(r90, Math.abs(oldSplit[0].amount), oldSplit[0].amount < 0 ? 180 : oldSplit[0].angle);
check(oldPred.level > 1.4, 'old splitter reproduces the 1.41 IPS increase');
const weights = [{ angle: 0, lo: 0, hi: 400, step: 1 }, { angle: 180, lo: 0, hi: 400, step: 1 }];
const pl = M.place(solved.mag, solved.angle, weights);
const pred = M.predict(r90, pl.achieved.mag, pl.achieved.angle);
check(pred.level <= 1.0 + 1e-9, 'installable move never predicts an increase');
check(pl.moves.length === 0, 'no installable move helps with orthogonal stations');
// Four stations, 1 g steps: request 10 at 45 -> 7 + 7, achieved 9.90 at 45, and the
// prediction follows the rounded move, not the request.
const p4 = M.place(10, 45, [0, 90, 180, 270].map(a => ({ angle: a, lo: 0, hi: 400, step: 1 })));
check(p4.moves.length === 2 && p4.moves.every(m => m.amount === 7), 'rounded to whole grams on bracketing stations');
near(p4.achieved.mag, 7 * Math.SQRT2, 1e-9, 'achieved magnitude is the rounded move');
// Removal only where weight is installed: 5 g at 180 installed, request 3 g at 0.
const pr = M.place(3, 0, [{ angle: 0, lo: 0, hi: 0, step: 1 }, { angle: 180, lo: -5, hi: 395, step: 1 }]);
check(pr.moves.length === 1 && pr.moves[0].angle === 180 && pr.moves[0].amount === -3, 'removal of installed weight');
check(M.place(3, 0, [{ angle: 0, lo: 0, hi: 0, step: 1 }, { angle: 180, lo: 0, hi: 395, step: 1 }]).moves.length === 0,
  'cannot remove weight that is not installed');
// Radius: a station at twice the reference radius needs half the mass.
const prad = M.place(10, 0, [{ angle: 0, radius: 2, lo: 0, hi: 100, step: 0.5 }], 1);
near(prad.moves[0].amount, 5, 1e-9, 'station radius scales the mass');
// Max per station is respected even when it leaves a residual.
const pmax = M.place(10, 0, [{ angle: 0, lo: 0, hi: 4, step: 1 }]);
check(pmax.moves[0].amount === 4, 'per-station maximum respected');

// ---- rotor rules (DSS AN-MV2-A109) ----
const mr = [0, 90, 180, 270].map(a => ({ angle: a, lo: 0, hi: 400, step: 1 }));
const adj = { maxLoaded: 2, adjacentOnly: true };
let pc = M.placeConstrained(100, 45, mr, adj, [0, 0, 0, 0]);
check(pc && pc.set.length === 2 && pc.set[0] === 0 && pc.set[1] === 1, 'empty rotor: adjacent pair bracketing the request');
// 100 g already on BLD B (180); request at 0 must not load TARGET (opposite blade).
const mrB = [0, 90, 180, 270].map((a, i) => ({ angle: a, lo: i === 2 ? -100 : 0, hi: i === 2 ? 300 : 400, step: 1 }));
pc = M.placeConstrained(50, 0, mrB, adj, [0, 0, 100, 0]);
check(pc && !pc.moves.some(m => m.angle === 0), 'weight on 180 forbids loading 0: ' + JSON.stringify(pc.moves));
check(pc.moves.some(m => m.angle === 180 && m.amount < 0), 'opposite request is met by removal from the loaded blade');
check(pc.set.every(i => i === 2 || i === 1 || i === 3) && pc.set.length <= 2, 'set stays adjacent to the loaded blade');
check(M.placeConstrained(50, 0, mrB, adj, [10, 0, 100, 0]) === null, 'already non-adjacent installation: no placement offered');
const tr = Array.from({ length: 12 }, (_, i) => ({ angle: i * 30, lo: 0, hi: 25, step: 1 }));
const trRules = { maxLoaded: 4, maxTotal: 100 };
pc = M.placeConstrained(40, 15, tr, trRules, new Array(12).fill(0));
check(pc && pc.set.length <= 4 && pc.moves.reduce((q, m) => q + m.amount, 0) <= 100, 'tail rotor within four bolts and 100 g');
const trLoaded = tr.map((s, i) => i < 4 ? { angle: s.angle, lo: -10, hi: 15, step: 1 } : s);
const inst4 = tr.map((_, i) => i < 4 ? 10 : 0);
pc = M.placeConstrained(30, 200, trLoaded, trRules, inst4);
check(pc && pc.moves.every(m => m.angle < 120), 'four bolts loaded: no fifth bolt, only those four move');
const trHeavy = tr.map((s, i) => i === 0 ? { angle: 0, lo: -90, hi: 25 - 90 + 90, step: 1 } : s);
pc = M.placeConstrained(20, 0, trHeavy, trRules, tr.map((_, i) => i === 0 ? 90 : 0));
check(pc && 90 + pc.moves.reduce((q, m) => q + m.amount, 0) <= 100 + 1e-9, 'flange total capped at 100 g');
check(M.placeConstrained(10, 0, mr, {}, [0, 0, 0, 0]).moves.length === 1, 'no rules: plain placement');

console.log(`PASS: ${checks} checks, mv2.js`);
