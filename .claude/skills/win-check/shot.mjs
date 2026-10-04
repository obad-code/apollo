import { createRequire } from 'module';
const require = createRequire('/usr/local/lib/node_modules/');
let pw; try { pw = require('playwright'); } catch { pw = await import('/opt/node22/lib/node_modules/playwright/index.mjs'); }
const { chromium } = pw;
const [,, url, out, w = '1920', h = '1080', js = ''] = process.argv;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
const logs = [];
page.on('console', (m) => logs.push(`${m.type()}: ${m.text()}`));
page.on('pageerror', (e) => logs.push(`ERR: ${e.message}`));
await page.goto(url);
await page.waitForTimeout(2500);
if (js) { await page.evaluate(js); await page.waitForTimeout(2000); }
await page.screenshot({ path: out });
console.log(logs.slice(0, 15).join('\n'));
await browser.close();
