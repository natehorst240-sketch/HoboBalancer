const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message));
  const ok = (c, n) => { console.log((c ? 'ok   ' : 'FAIL ') + n); if (!c) process.exitCode = 1; };
  const txt = id => p.$eval('#' + id, e => e.textContent);
  const val = sel => p.$eval(sel, e => e.value);
  const set = async (sel, v) => { await p.fill(sel, v); await p.dispatchEvent(sel, 'change'); };
  await p.goto('file://' + require('path').resolve(__dirname, '..', 'index.html'));
  await set('#aircraft', 'N731HC'); await set('#calibration', 'cal-A');
  // Pending change survives a settings re-render, then is learned.
  await p.fill('#rpm', '384'); await p.fill('#level', '1.0'); await p.fill('#phase', '0'); await p.click('#add');
  const after = await p.evaluate(() => MV2.predict({ level: 1, phase: 0, sens: 200, tach: 30 }, 2, 0));
  await p.fill('#level', String(after.level)); await p.fill('#phase', String(after.phase));
  await p.fill('#learnLimit', '0'); await p.fill('#trust', '1');
  await p.fill('[data-chg="0"]', '2');
  await set('#roundTo', '0.5'); await set('#maxPos', '300');          // both re-render
  ok((await val('[data-chg="0"]')) === '2', 'pending change kept across re-render');
  await p.click('#add');
  ok(/learned: measured SENS 200\.0 TACH 30\.0/.test(await txt('addMsg')), 'pending change learned: ' + await txt('addMsg'));
  ok((await val('[data-chg="0"]')) === '' && (await val('[data-inst="0"]')) === '2', 'pending cleared after add, installed updated');
  // A failed add keeps the pending change.
  await p.fill('[data-chg="90"]', '3'); await p.fill('#level', ''); await p.click('#add');
  ok(/required/.test(await txt('addMsg')) && (await val('[data-chg="90"]')) === '3', 'failed add keeps pending change');
  // Calibration scopes the coefficient.
  ok((await val('#sens')) === '200.0', 'cal-A uses learned SENS');
  await set('#calibration', 'cal-B');
  ok((await val('#sens')) === '320.0' && (await val('#tach')) === '340.0', 'cal-B starts from the profile seed');
  ok(/calibration "cal-B"/.test(await txt('coefKey')), 'coefficient identity shows calibration');
  await set('#calibration', 'cal-A');
  ok((await val('#sens')) === '200.0', 'back to cal-A restores its coefficient');
  // Import seeds under MicroVib only.
  await p.setInputFiles('#file', require('path').resolve(__dirname, '..', '..', 'profiles') + '/A1090731.HST');
  ok(/under sensor calibration "MicroVib"/.test(await txt('addMsg')) && (await val('#sens')) === '200.0', 'import seeds MicroVib, cal-A untouched');
  // State saved by the previous build (version 2, no calibration in the key) migrates.
  await p.evaluate(() => localStorage.setItem('hobo-solver', JSON.stringify({ version: 2, profile: { name: 'A109', rev: 'grp-3c129433', tasks: [{ name: 'GND LT', sens: 320, tach: 340, unit: 'GRAMS', plane: 'MR hub weights', positions: [0, 90, 180, 270], max: 400 }] },
    aircraft: 'N1', session: 's', calibration: '', coef: { 'N1|grp-3c129433|GND LT': { sens: 250, tach: 12 } }, installed: {}, runs: [], task: 'GND LT', weights: {}, now: {} })));
  await p.reload();
  ok((await val('#sens')) === '320.0' && /held back/.test(await txt('addMsg')), 'version 2 coefficient with no runs is held back, not assigned to the blank calibration');
  ok(errs.length === 0, 'no page errors ' + errs.join(' | '));
  await b.close();
})();
