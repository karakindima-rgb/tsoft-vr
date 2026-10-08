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
for (const card of cards) {
  const key = await card.getAttribute('data-key');
  await card.screenshot({ path: path.join(root, 'preview', `2026-10-08_tsoft-tshirt_${key}.png`) });
}
await page.screenshot({ path: path.join(root, 'preview', '2026-10-08_tsoft-tshirt_all.png'), fullPage: true });
// печатные файлы → PNG 300 dpi с прозрачным фоном (референс для ChatGPT, макет для DTF)
const fs = require('fs');
const out = path.join(root, 'print', 'png');
fs.mkdirSync(out, { recursive: true });
for (const f of fs.readdirSync(path.join(root, 'print')).filter((x) => x.endsWith('.svg'))) {
  const svg = fs.readFileSync(path.join(root, 'print', f), 'utf8');
  const [, w, h] = svg.match(/width="([\d.]+)mm" height="([\d.]+)mm"/);
  const px = (mm) => Math.round((mm * 300) / 25.4);
  const p = await browser.newPage({ viewport: { width: px(w), height: px(h) } });
  await p.setContent(`<style>html,body{margin:0;background:transparent}svg{display:block;width:${px(w)}px;height:${px(h)}px}</style>${svg}`);
  await p.screenshot({ path: path.join(out, f.replace('.svg', '_300dpi.png')), omitBackground: true });
  await p.close();
}
await browser.close();
console.log('ok', cards.length);
})();
