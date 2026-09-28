// Render chosen timestamps to PNGs for review: node render/preview.mjs out_dir 0.5 1.2 ...
import { createRequire } from "module";
import path from "path";
import fs from "fs";
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require("playwright")); } catch { ({ chromium } = require("/opt/node22/lib/node_modules/playwright")); }
const [out, ...times] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const browser = await chromium.launch({ args: ["--allow-file-access-from-files", "--disable-web-security"] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.goto("file://" + root + "/index.html?render");
await page.waitForFunction(() => window.__ready === true, null, { timeout: 30000 });
for (const t of times) {
  const t0 = Date.now();
  await page.evaluate((t) => window.seek(t), parseFloat(t));
  await page.screenshot({ path: `${out}/t${String(t).padStart(5, "0")}.png` });
  process.stdout.write(`${t}:${Date.now() - t0}ms `);
}
console.log();
if (errors.length) console.log("ERRORS:\n" + errors.join("\n"));
await browser.close();
