// Рендер мокапов в PNG: NODE_PATH=$(npm root -g) node src/render.cjs
const path = require('path');
const { chromium } = require('playwright');
(async () => {

const root = path.resolve(__dirname, '..');
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 2 });
await page.goto('file://' + path.join(root, 'mockup.html'));
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(300);
const cards = await page.$$('.card');
for (const [i, card] of cards.entries()) {
  await card.screenshot({ path: path.join(root, 'preview', `2026-10-08_tsoft-tshirt_${'ABC'[i]}.png`) });
}
await page.screenshot({ path: path.join(root, 'preview', '2026-10-08_tsoft-tshirt_all.png'), fullPage: true });
await browser.close();
console.log('ok', cards.length);
})();
