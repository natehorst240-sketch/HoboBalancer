// Regressions for the second review of PR #12.
const { chromium } = require('playwright');
const REV = 'grp-3c129433';
const GND = { name: 'GND LT', sens: 320, tach: 340, unit: 'GRAMS', plane: 'MR hub weights', positions: [0, 90, 180, 270], max: 400 };
const v2 = (calibration, coef, runs) => JSON.stringify({ version: 2, profile: { name: 'A109', rev: REV, tasks: [GND] }, aircraft: 'N1', session: 's',
  calibration, coef, installed: {}, runs, task: 'GND LT', weights: {}, now: {} });
const run = (cal, sens, tach, min) => ({ task: 'GND LT', aircraft: 'N1', session: 's', profileRev: REV, calibration: cal, when: new Date(Date.UTC(2026, 10, 1, 12, min)),
  rpm: 384, level: 0.5, phase: 20, change: { moves: [] }, sens, tach, verified: true, source: 'manual' });
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  const ok = (c, n) => { console.log((c ? 'ok   ' : 'FAIL ') + n); if (!c) process.exitCode = 1; };
  const txt = id => p.$eval('#' + id, e => e.textContent);
  const val = sel => p.$eval(sel, e => e.value);
  const set = async (sel, v) => { await p.fill(sel, v); await p.dispatchEvent(sel, 'change'); };
  const load = async s => { await p.evaluate(x => localStorage.setItem('hobo-solver', x), s); await p.reload(); };
  await p.goto('file://' + require('path').resolve(__dirname, '..', 'index.html'));

  // 1. Changing calibration must not solve the old calibration's run with the new coefficient.
  await set('#aircraft', 'N731HC'); await set('#calibration', 'cal-A');
  await set('#sens', '100');
  await p.fill('#rpm', '384'); await p.fill('#level', '1.0'); await p.fill('#phase', '0'); await p.click('#add');
  const solA = await txt('solVec');
  await set('#calibration', 'cal-B');
  const solB = await txt('solVec');
  ok(/no usable runs/.test(solB), `cal-B shows no solution from cal-A's run (cal-A: ${solA}; cal-B: ${solB})`);
  ok(/other sensor calibration/.test(await p.$eval('#runs', e => e.textContent)), 'cal-A run listed as not used under cal-B');
  await set('#calibration', 'cal-A');
  ok((await txt('solVec')) === solA, 'back on cal-A the same solution returns');

  // 2. Version 2 migration assigns each coefficient to the calibration that produced it.
  await load(v2('cal-A', { 'N1|grp-3c129433|GND LT': { sens: 250, tach: 12 } }, [run('cal-A', 250, 12, 0)]));
  ok((await val('#sens')) === '250.0', 'single-calibration v2 coefficient lands under that calibration');
  await set('#calibration', '');
  ok((await val('#sens')) === '320.0', 'and not under blank calibration');
  await load(v2('cal-B', { 'N1|grp-3c129433|GND LT': { sens: 250, tach: 12 } }, [run('cal-A', 300, 20, 0), run('cal-B', 250, 12, 5)]));
  ok((await val('#sens')) === '320.0', 'coefficient used under two calibrations is not reused (seed instead)');
  ok(/held back/.test(await txt('addMsg')), 'ambiguous coefficient reported: ' + await txt('addMsg'));
  await set('#calibration', 'cal-A');
  ok((await val('#sens')) === '320.0', 'ambiguous coefficient not under cal-A either');
  await load(v2('cal-C', { 'N1|grp-3c129433|GND LT': { sens: 210, tach: 5 } }, []));
  ok((await val('#sens')) === '320.0' && /held back/.test(await txt('addMsg')), 'coefficient with no runs is held back (ownership unknown), not put on the active calibration');

  // 3. Pending changes belong to aircraft, profile and session.
  await load(v2('', {}, []));
  await set('#aircraft', 'A'); await p.fill('[data-chg="0"]', '10');
  await set('#aircraft', 'B');
  ok((await val('[data-chg="0"]')) === '', "A's pending change not shown for B");
  await p.fill('#rpm', '384'); await p.fill('#level', '0.5'); await p.fill('#phase', '10'); await p.click('#add');
  ok((await val('[data-inst="0"]')) === '0', "B's inventory untouched by A's pending change");
  await set('#aircraft', 'A');
  ok((await val('[data-chg="0"]')) === '10', "A's pending change still there for A");
  await set('#session', 's2');
  ok((await val('[data-chg="0"]')) === '', 'pending change not carried into another session');

  ok(errs.length === 0, 'no page errors ' + errs.join(' | '));
  await b.close();
})();
