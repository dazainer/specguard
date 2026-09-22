// Read-only browser audit against actual API data. Seed a full fixture run first.
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
const base = process.env.SPECGUARD_UI_URL || 'http://127.0.0.1:5173';
const output = process.env.SPECGUARD_UI_OUTPUT || '../benchmark-runs/ui-audit';
await mkdir(output, { recursive: true });
const response = await fetch(`${base}/api/evaluations/runs`);
assert.ok(response.ok, 'Start the API and frontend first');
const runs = await response.json();
const full = runs.find(r => r.status === 'completed' && !r.pruned && r.report?.generated.mutation);
assert.ok(full, 'Create a completed mutation comparison before this audit');
const routes = ['/', `/evaluations/${full.id}`];
for (const status of ['failed', 'cancelled']) {
 const run = runs.find(r => r.status === status);
 if (run) routes.push(`/evaluations/${run.id}`);
}
const browser = await chromium.launch();
const results = []; const errors = [];
try {
 for (const width of [375, 768, 1440]) {
  const context = await browser.newContext({ viewport: { width, height: 900 } });
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(e.message));
  for (const [i, route] of routes.entries()) {
   await page.goto(base + route, { waitUntil: 'networkidle' });
   if (i === 0) await page.locator('.sg-runs tbody tr').first().waitFor();
   else await page.locator('.sg-track').waitFor();
   if (i === 1) {
    await page.locator('.sg-mutant summary').first().waitFor();
    await page.locator('.sg-mutant summary').first().click();
    await page.locator('.sg-log summary').first().click();
   }
   assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Page overflow ${width} ${route}`);
   const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
   results.push({ width, route, violations: axe.violations.map(v => ({ id: v.id, impact: v.impact, targets: v.nodes.map(n => n.target) })) });
   await page.screenshot({ path: `${output}/${i}-${width}.png`, fullPage: true });
   assert.equal(axe.violations.length, 0, JSON.stringify(results.at(-1)));
  }
  await context.close();
 }
 const page = await browser.newPage();
 await page.goto(base + routes[1], { waitUntil: 'networkidle' });
 await page.keyboard.press('Tab');
 assert.equal(await page.locator(':focus').innerText(), 'Skip to content');
 assert.notEqual(await page.locator(':focus').evaluate(e => getComputedStyle(e).outlineStyle), 'none');
 await page.keyboard.press('Enter');
 assert.equal(await page.locator(':focus').getAttribute('id'), 'main');
 await page.getByRole('checkbox', { name: /only where suites disagree/i }).focus();
 await page.keyboard.press('Space');
 assert.ok(await page.getByRole('checkbox', { name: /only where suites disagree/i }).isChecked());
 const mutant = page.locator('.sg-mutant summary').first();
 if (await mutant.count()) {
  await mutant.focus(); await page.keyboard.press('Enter');
  assert.ok(await page.locator('.sg-mutant').first().evaluate(e => e.open));
 }
 await page.emulateMedia({ reducedMotion: 'reduce' });
 assert.equal(await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior), 'auto');
 for (const format of ['JSON', 'Markdown', 'CSV']) {
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: format, exact: true }).click();
  assert.equal(await (await download).failure(), null);
 }
 assert.deepEqual(errors, []);
 console.log(`PASS: ${results.length} real-data viewport/a11y checks, keyboard, reduced motion, exports`);
} finally {
 await writeFile(`${output}/audit.json`, JSON.stringify({ results, errors }, null, 2));
 await browser.close();
}
