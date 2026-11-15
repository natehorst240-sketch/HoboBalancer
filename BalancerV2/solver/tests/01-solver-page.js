const { chromium } = require('playwright');
const S = require('path').resolve(__dirname, '..', '..');
(async () => {
  const b = await chromium.launch(); const ctx = await b.newContext(); const p = await ctx.newPage();
  const errs = []; p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  const url = 'file://' + S + '/solver/index.html';
  const txt = id => p.$eval('#' + id, e => e.textContent);
  const ok = (c, n) => { console.log((c ? 'ok   ' : 'FAIL ') + n); if (!c) process.exitCode = 1; };
  await p.goto(url);
  // 1. aircraft required
  await p.fill('#level', '1'); await p.fill('#phase', '10'); await p.click('#add');
  ok(/aircraft first/.test(await txt('addMsg')), 'run refused without aircraft');
  // 2. learning with a removal, A109 GND LT
  await p.fill('#aircraft', 'N731HC'); await p.dispatchEvent('#aircraft', 'change');
  await p.fill('#rpm', '384'); await p.fill('#level', '1.0'); await p.fill('#phase', '0'); await p.click('#add');
  await p.fill('[data-inst="90"]', '10'); await p.dispatchEvent('[data-inst="90"]', 'change');
  const after = await p.evaluate(() => MV2.predict({ level: 1, phase: 0, sens: 200, tach: 30 }, 2, 270));
  await p.fill('#rpm', '384.5'); await p.fill('#level', String(after.level)); await p.fill('#phase', String(after.phase));
  await p.fill('[data-chg="90"]', '-2'); await p.fill('#learnLimit', '0'); await p.fill('#trust', '1');
  await p.click('#add');
  const m2 = await txt('addMsg'); ok(/learned: measured SENS 200\.0 TACH 30\.0/.test(m2), 'removal learned exactly: ' + m2);
  ok(!/NaN/.test(await p.$eval('#sens', e => e.value)), 'SENS is a number after removal');
  ok((await p.$eval('[data-inst="90"]', e => e.value)) === '8', 'installed weight updated by the removal');
  await p.fill('#rpm', '420'); await p.fill('#level', '0.5'); await p.fill('#phase', '100'); await p.fill('[data-chg="0"]', '5'); await p.click('#add');
  ok(/coefficient kept: RPM differs/.test(await txt('addMsg')), 'RPM mismatch blocks learning');
  // T/R BAL must not combine with GND LT (both grams)
  await p.click('button[data-t="T/R BAL"]');
  await p.fill('#rpm', '2000'); await p.fill('#level', '0.6'); await p.fill('#phase', '45'); await p.click('#add');
  ok(!/GND LT/.test(await p.$eval('#multi', e => e.textContent)), 'T/R BAL not combined with GND LT');
  ok(/Predicted level after washers and wheel: [0-9.]+ IPS/.test(await txt('auxNote')), 'aux card predicts from installed move');
  // HOV LT shares MR hub weights with GND LT -> combined
  await p.click('button[data-t="HOV LT"]'); await p.fill('#rpm', '384'); await p.fill('#level', '0.3'); await p.fill('#phase', '200'); await p.click('#add');
  const multi = await p.$eval('#multi', e => e.textContent);
  ok(/GND LT/.test(multi) && /HOV LT/.test(multi), 'GND LT and HOV LT combined on MR hub weights');
  // 3. another aircraft does not see these runs or coefficients
  await p.fill('#aircraft', 'N109XX'); await p.dispatchEvent('#aircraft', 'change'); await p.click('button[data-t="GND LT"]');
  ok((await p.$$('#runs tr')).length === 1 && (await p.$eval('#sens', e => e.value)) === '320.0', 'other aircraft starts clean at the seed');
  // 4. imports
  await p.setInputFiles('#file', S + '/profiles/A1090021.HST');
  const m4 = await txt('addMsg'); ok(/8 runs, 8 passed checks, 0 kept out/.test(m4), 'A1090021 imports (levels verified against MicroBase): ' + m4);
  await p.setInputFiles('#file', S + '/profiles/A1090731.HST');
  const m5 = await txt('addMsg'); ok(/5 runs, 5 passed checks/.test(m5) && /Showing session/.test(m5), 'A1090731 imported: ' + m5);
  ok(/0\.08[45]/.test(await p.$eval('#runs', e => e.textContent)), 'imported GND LT level shown');
  // 5. stations at 0 and 180 only: a request at 90 must not show an increasing move
  await p.evaluate(() => {
    const st = JSON.parse(localStorage.getItem('hobo-solver'));
    st.profile = { name: 'TWO', rev: 'test-two', tasks: [
      { name: 'PROP L', sens: 10, tach: 0, unit: 'GRAMS', plane: '', positions: [0, 180], max: 50 },
      { name: 'PROP R', sens: 10, tach: 0, unit: 'GRAMS', plane: '', positions: [0, 180], max: 50 }] };
    st.task = 'PROP L'; st.aircraft = 'TWIN'; st.session = 's1';
    const sol = MV2.solve([{ level: 1, phase: 0, sens: 10, tach: 0 }]);
    const ph = MV2.mod360(sol.angle - 90);
    st.runs.push({ task: 'PROP L', aircraft: 'TWIN', session: 's1', profileRev: 'test-two', level: 1, phase: ph, rpm: 2000, when: new Date(), change: { moves: [] }, verified: true });
    st.runs.push({ task: 'PROP R', aircraft: 'TWIN', session: 's1', profileRev: 'test-two', level: 0.4, phase: 30, rpm: 2000, when: new Date(), change: { moves: [] }, verified: true });
    localStorage.setItem('hobo-solver', JSON.stringify(st));
  });
  await p.reload();
  const note = await txt('solNote'); const pred = +(/after the move shown: ([0-9.]+)/.exec(note) || [])[1];
  ok(pred <= 1.0 && /no installable move/.test(await txt('solPos')), 'orthogonal stations: no increasing move, predicted ' + pred);
  ok(/solved alone/.test(await p.$eval('#multi', e => e.textContent)), 'two props with no shared plane not combined');
  // 6. legacy state migrates under unassigned/legacy
  await p.evaluate(() => localStorage.setItem('hobo-solver', JSON.stringify({ profile: { name: 'A109', tasks: [] }, coef: { 'GND LT': { sens: 300, tach: 10 } }, runs: [{ task: 'GND LT', when: new Date(), level: 0.5, phase: 20, change: { mag: 0 } }], task: 'GND LT', weights: {} })));
  await p.reload();
  ok((await p.$eval('#aircraft', e => e.value)) === 'unassigned' && (await p.$eval('#session', e => e.value)) === 'legacy' && (await p.$eval('#sens', e => e.value)) === '300.0' && (await p.$$('#runs tr')).length === 2, 'legacy state kept under unassigned/legacy');
  ok(errs.length === 0, 'no page errors ' + errs.join(' | '));
  await b.close();
})();
