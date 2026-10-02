// Renders board.html into print files.
//   node build.cjs            -> out/ (preview PNG, full-size panel PDFs, A3 sheet PDF)
// Needs Playwright with Chromium, ImageMagick (convert) and Python with pypdf.
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');

const ROOT = __dirname;
const OUT = path.join(ROOT, 'out');
const url = (q) => 'file://' + path.join(ROOT, 'board.html') + '?' + q;

async function open(browser, q, viewport) {
  const page = await browser.newPage({ viewport });
  await page.goto(url(q));
  await page.waitForSelector('body[data-ready="1"]');
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map((img) => img.complete ? null : new Promise((r) => { img.onload = img.onerror = r; })));
  });
  return page;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();

  // Preview of the whole board laid flat.
  const flat = await open(browser, 'mode=flat', { width: 1400, height: 900 });
  const full = path.join(OUT, '.preview-full.png');
  await flat.screenshot({ path: full, fullPage: true });
  await flat.close();
  execFileSync('convert', [full, '-resize', '3200x', path.join(OUT, 'preview.png')]);
  fs.unlinkSync(full);

  // One full-size PDF per panel (for a print shop, or to check at 100%).
  for (const [p, w] of [['left', 400], ['centre', 800], ['right', 400]]) {
    const page = await open(browser, `mode=panel&p=${p}`, { width: 1200, height: 900 });
    await page.pdf({ path: path.join(OUT, `panel-${p}-${w}x900mm.pdf`), width: `${w}mm`, height: '900mm', printBackground: true, pageRanges: '1' });
    await page.close();
  }

  // A3 sheets. The browser prints each sheet's crop marks and labels; the
  // artwork is then cut from the full-size panel PDFs (vector, nothing
  // re-rendered) and placed under them.
  const tiles = await open(browser, 'mode=tiles', { width: 1200, height: 900 });
  const sheets = await tiles.evaluate(() => [...document.querySelectorAll('.sheet')].map((s) => ({ ...s.dataset })));
  const parts = [];
  for (let i = 0; i < sheets.length; i++) {
    await tiles.evaluate((i) => document.querySelectorAll('.sheet').forEach((s, j) => { s.style.display = j === i ? '' : 'none'; }), i);
    const file = path.join(OUT, `.marks-${String(i + 1).padStart(2, '0')}.pdf`);
    await tiles.pdf({ path: file, width: `${sheets[i].sw}mm`, height: `${sheets[i].sh}mm`, printBackground: true, pageRanges: '1' });
    parts.push({ ...sheets[i], marks: file });
  }
  await tiles.close();
  await browser.close();

  const job = path.join(OUT, '.sheets.json');
  fs.writeFileSync(job, JSON.stringify(parts));
  execFileSync('python3', [path.join(ROOT, 'tile.py'), job, OUT, path.join(OUT, 'AWARE-board-A3-sheets.pdf')], { stdio: 'inherit' });
  parts.forEach((p) => fs.unlinkSync(p.marks));
  fs.unlinkSync(job);
  console.log('Wrote', fs.readdirSync(OUT).join(', '));
})();
