// Check mv2.js against balance-history rows as MicroBase Pro stores them (histrecs.dbf, read
// 2026-11-14 from a MicroBase Pro 2.2x install; MV2 firmware 1.34.101.75 for the 2016+ rows).
// Each row: the reading (NEWPK, NEWPH), the reference run DSS learned against (OLDPK, OLDPH),
// the move installed after that reference (WT1@LOC1 + WT2@LOC2 of the reference run's
// solution) and the SENS/TACH DSS learned. Run: node BalancerV2/solver/test_dss_histrecs.js
'use strict';
const M = require('./mv2.js');
let checks = 0;
const check = (c, n) => { checks++; if (!c) { console.error('FAIL: ' + n); process.exit(1); } };
const angNear = (a, b, tol) => Math.abs(M.mod360(a - b + 180) - 180) <= tol;

// [job, run, OLDPK, OLDPH, NEWPK, NEWPH, WT1, LOC1, WT2, LOC2, SENS, TACH]
const learned = [
  ['M-20J prop 1994', 2, 0.284, 214.1, 0.186, 63.7, 24.5, 240, 0, 270, 53.9, 74.0],
  ['M-20J prop 1994', 3, 0.284, 214.1, 0.020, 217.5, 9.1, 240, 6.8, 270, 58.2, 73.0],
  ['AS350 driveshaft 1994', 2, 0.438, 14.1, 0.254, 17.1, 11.7, 270, 0, 0, 63.2, 260.0],
  ['AS350 driveshaft 1994', 3, 0.254, 17.1, 0.039, 223.7, 3.6, 240, 12.1, 270, 53.0, 256.0],
  ['AS350 driveshaft 1994 b', 2, 0.2597, 210.3047, 0.6629, 223.7813, 2.1, 300, 0, 0, 5.0632, 187.6172],
  ['AS350 driveshaft 1994 b', 3, 0.2597, 210.3047, 0.1524, 70.6094, -0.7, 360, 1.0, 120, 3.8073, 170.8594],
  ['PT6 prop 1994', 2, 0.65, 37.8, 0.172, 86.1, -55.1992, 180, 0, 0, 100.3, 156.0],
  ['PT6 prop 1994', 3, 0.172, 86.1, 0.037, 351.1, 17.5, 270, 11.0999, 360, 115.6, 139.0],
  ['prop 2016-06-30', 2, 0.4234, 218.4792, 0.5601, 165.0673, 33.8, 231, 0, 0, 73.7097, 11.7794],
  ['prop 2016-06-30', 3, 0.4234, 218.4792, 0.0351, 273.5576, 15.6, 300, 15.6, 320, 75.9924, 15.5989],
  ['prop 2017-03-22', 2, 0.7689, 140.1349, 1.1152, 125.6258, 32.0, 315, 0, 0, 76.5807, 306.8251],
  ['prop 2017-03-22', 3, 0.7689, 140.1349, 0.0727, 49.209, 27.1, 69, 35.9, 111, 76.1497, 301.402],
];
for (const [job, run, opk, oph, npk, nph, w1, l1, w2, l2, sens, tach] of learned) {
  const m = M.learn({ level: opk, phase: oph }, { level: npk, phase: nph }, { moves: [{ amount: w1, angle: l1 }, { amount: w2, angle: l2 }] });
  const tight = run >= 2 && job.startsWith('prop 201');  // stored with 4 decimals by MV2 firmware
  const sTol = tight ? 0.0002 : 0.003, tTol = tight ? 0.02 : 0.7;
  check(m && Math.abs(m.sens - sens) / sens <= sTol, `${job} run ${run}: SENS ${m && m.sens} vs DSS ${sens}`);
  check(m && angNear(m.tach, tach, tTol), `${job} run ${run}: TACH ${m && m.tach} vs DSS ${tach}`);
}

// Solutions DSS displayed for N731HC on 2026-09-01 (A1090731.HST identified into MicroBase):
// [task, NEWPK, NEWPH, SENS, TACH, WT1, LOC1, WT2, LOC2]
const solved = [
  ['GND LT', 0.0849, 151.2785, 320, 340, 17.9214, 0, 20.4147, 90],
  ['HOV VT', 0.1693, 262.5645, 3, 340, 0.4509, 270, 0.2341, 0],
  ['80KT VT', 0.0926, 181.4615, 8, 340, 0.7022, 0, 0.2355, 90],
  ['MCP VT', 0.1443, 190.8888, 8, 340, 1.1401, 0, 0.1828, 90],
];
for (const [task, pk, ph, sens, tach, w1, l1, w2, l2] of solved) {
  const sol = M.solve([{ level: pk, phase: ph, sens, tach }]);
  const sp = M.split(sol.mag, sol.angle, [0, 90, 180, 270].map(a => ({ angle: a })));
  const at = a => { const x = sp.find(p => p.angle === a % 360); return x ? x.amount : 0; };
  check(Math.abs(at(l1) - w1) < 0.005 && Math.abs(at(l2) - w2) < 0.005, `${task}: split ${JSON.stringify(sp)} vs DSS ${w1}@${l1} ${w2}@${l2}`);
}
console.log(`PASS: ${checks} checks, mv2.js against MicroBase Pro histrecs rows`);
