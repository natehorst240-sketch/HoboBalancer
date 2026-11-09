// Third review of PR #12: learning must compare against the immediately preceding run of the
// task, whatever calibration it was under; v2 migration must not guess coefficient ownership.
const { chromium } = require('playwright');
const path = require('path');
const REV = 'grp-3c129433';
const GND = { name: 'GND LT', sens: 320, tach: 340, unit: 'GRAMS', plane: 'MR hub weights', positions: [0, 90, 180, 270], max: 400 };
const v2 = (calibration, coef, runs) => JSON.stringify({ version: 2, profile: { name: 'A109', rev: REV, tasks: [GND] }, aircraft: 'N1', session: 's',
  calibration, coef, installed: {}, runs, task: 'GND LT', weights: {}, now: {} });
// A v2 run records the coefficient in effect once it was added (sens, tach).
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
  const add = async (rpm, level, phase, chg) => {
    await p.fill('#rpm', rpm); await p.fill('#level', level); await p.fill('#phase', phase);
    for (const [a, v] of Object.entries(chg || {})) await p.fill(`[data-chg="${a}"]`, v);
    await p.click('#add'); return txt('addMsg');
  };
  await p.goto('file://' + path.resolve(__dirname, '..', 'index.html'));

  // 1. Run under cal-A at 1.0 IPS; under cal-B install 10 g; back on cal-A install another 10 g
  //    and read 0.6 IPS. 20 g moved the vector 0.4 IPS (sens 50); the old code compared against
  //    the cal-A run with only the latest 10 g and learned 25.
  await set('#aircraft', 'N731HC'); await set('#calibration', 'cal-A'); await p.fill('#learnLimit', '0'); await p.fill('#trust', '1');
  await add('384', '1.0', '0');
  await set('#calibration', 'cal-B'); await add('384', '0.8', '0', { 0: '10' });
  await set('#calibration', 'cal-A');
  const m1 = await add('384', '0.6', '0', { 0: '10' });
  ok(/coefficient kept: .*calibration/.test(m1), 'learning refused across an intervening other-calibration run: ' + m1);
  ok((await val('#sens')) === '320.0', 'coefficient unchanged (not 25)');
  ok((await val('[data-inst="0"]')) === '20', 'both installs still counted in the inventory');
  // The next cal-A run follows a cal-A run directly, so it learns, from that run only.
  const after = await p.evaluate(() => MV2.predict({ level: 0.6, phase: 0, sens: 50, tach: 0 }, 5, 0));
  const m2 = await add('384', String(after.level), String(after.phase), { 0: '5' });
  ok(/learned: measured SENS 50\.0 TACH 0\.0/.test(m2), 'consecutive same-calibration runs learn from the immediate predecessor: ' + m2);
  // An unverified (imported, failed-check) run in between also blocks learning.
  await p.evaluate(() => { const st = JSON.parse(localStorage.getItem('hobo-solver')); st.runs.push({ task: 'GND LT', aircraft: 'N731HC', session: st.session, profileRev: st.profile.rev, calibration: 'cal-A', when: new Date(), rpm: 384, level: null, phase: 0, change: { moves: [] }, verified: false, problems: ['test'], source: 'import' }); localStorage.setItem('hobo-solver', JSON.stringify(st)); });
  await p.reload();
  const m3 = await add('384', '0.3', '0', { 0: '5' });
  ok(/coefficient kept: .*unverified/.test(m3), 'unverified run in between blocks learning: ' + m3);

  // 2. Migration: cal-A run recorded sens 320 / tach 340; the coefficient was then changed to
  //    777 (under cal-B, say). 777 is not what any cal-A run saw, so it must be held back.
  await load(v2('cal-B', { 'N1|grp-3c129433|GND LT': { sens: 777, tach: 1 } }, [run('cal-A', 320, 340, 0)]));
  ok(/held back/.test(await txt('addMsg')), 'changed-after-run coefficient held back: ' + await txt('addMsg'));
  ok((await val('#sens')) === '320.0', 'cal-B shows the seed');
  await set('#calibration', 'cal-A');
  ok((await val('#sens')) === '320.0', 'cal-A shows the seed, not 777');
  const st = await p.evaluate(() => JSON.parse(localStorage.getItem('hobo-solver')));
  ok(st.coefHeldBack && Object.values(st.coefHeldBack).some(c => c.sens === 777), '777 kept in coefHeldBack');
  // Unchanged since the run under one calibration: proven, assigned there.
  await load(v2('cal-B', { 'N1|grp-3c129433|GND LT': { sens: 250, tach: 12 } }, [run('cal-A', 250, 12, 0)]));
  ok((await val('#sens')) === '320.0' && !/held back/.test(await txt('addMsg')), 'proven cal-A coefficient not shown under cal-B and not held back');
  await set('#calibration', 'cal-A');
  ok((await val('#sens')) === '250.0', 'proven coefficient assigned to cal-A');
  // No runs at all: ownership unknown, held back (seed value is simply dropped).
  await load(v2('cal-C', { 'N1|grp-3c129433|GND LT': { sens: 210, tach: 5 } }, []));
  ok(/held back/.test(await txt('addMsg')) && (await val('#sens')) === '320.0', 'coefficient with no runs held back, not guessed onto the active calibration');
  await load(v2('cal-C', { 'N1|grp-3c129433|GND LT': { sens: 320, tach: 340 } }, []));
  ok(!/held back/.test(await txt('addMsg')) && (await val('#sens')) === '320.0', 'seed-valued coefficient with no runs just dropped');

  ok(errs.length === 0, 'no page errors ' + errs.join(' | '));
  await b.close();
})();
