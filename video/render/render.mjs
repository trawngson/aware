// Frame-exact renderer. Splits the timeline across workers; each worker drives
// its own headless Chromium, seeks every frame and pipes JPEG captures into
// ffmpeg. Segments are then joined and muxed with the audio track.
//
//   node render/render.mjs --out out/aware.mp4 [--fps 60] [--from 0] [--to 60]
//        [--workers 4] [--scale 1] [--audio out/mix.wav] [--crf 16]
import { createRequire } from "module";
import { spawn, execFileSync } from "child_process";
import fs from "fs";
import path from "path";

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require("playwright")); } catch { ({ chromium } = require("/opt/node22/lib/node_modules/playwright")); }

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith("--") ? [...a, [v.slice(2), arr[i + 1]]] : a), []));
const fps = +(args.fps || 60), from = +(args.from || 0), to = +(args.to || 60), workers = +(args.workers || 4);
const scale = +(args.scale || 1), crf = args.crf || "16", out = path.resolve(args.out || "out/aware.mp4");
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const ffmpeg = args.ffmpeg || process.env.FFMPEG || (() => {
  try { return execFileSync("python3", ["-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"]).toString().trim(); } catch { return "ffmpeg"; }
})();
const tmp = path.join(path.dirname(out), ".segments");
fs.mkdirSync(tmp, { recursive: true });

const first = Math.round(from * fps), last = Math.round(to * fps); // [first, last)
const total = last - first, per = Math.ceil(total / workers);
const W = Math.round(1920 * scale), H = Math.round(1080 * scale);
let done = 0;
const t0 = Date.now();

async function worker(i) {
  const a = first + i * per, b = Math.min(last, a + per);
  if (a >= b) return null;
  const seg = path.join(tmp, `seg${i}.mp4`);
  const ff = spawn(ffmpeg, ["-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", String(fps), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", crf, "-pix_fmt", "yuv420p", "-r", String(fps), "-movflags", "+faststart", seg], { stdio: ["pipe", "inherit", "inherit"] });
  const browser = await chromium.launch({ args: ["--allow-file-access-from-files", "--disable-web-security", "--hide-scrollbars"] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: scale });
  page.on("pageerror", (e) => console.error(`[w${i}]`, e));
  await page.goto("file://" + root + "/index.html?render");
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
  const cdp = await page.context().newCDPSession(page);
  for (let f = a; f < b; f++) {
    await page.evaluate((t) => window.seek(t), f / fps);
    const { data } = await cdp.send("Page.captureScreenshot", { format: "jpeg", quality: 94, optimizeForSpeed: true, clip: { x: 0, y: 0, width: 1920, height: 1080, scale: 1 } });
    if (!ff.stdin.write(Buffer.from(data, "base64"))) await new Promise((r) => ff.stdin.once("drain", r));
    done++;
    if (done % 60 === 0) {
      const el = (Date.now() - t0) / 1000;
      process.stdout.write(`\r${done}/${total} frames  ${(done / el).toFixed(1)} fps  eta ${Math.round((total - done) / (done / el))}s   `);
    }
  }
  await browser.close();
  ff.stdin.end();
  await new Promise((r) => ff.on("close", r));
  return seg;
}

const segs = (await Promise.all(Array.from({ length: workers }, (_, i) => worker(i)))).filter(Boolean);
console.log(`\nrendered ${total} frames in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
const list = path.join(tmp, "list.txt");
fs.writeFileSync(list, segs.map((s) => `file '${s}'`).join("\n"));
const joined = args.audio ? path.join(tmp, "joined.mp4") : out;
execFileSync(ffmpeg, ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", joined]);
if (args.audio) {
  execFileSync(ffmpeg, ["-y", "-loglevel", "error", "-i", joined, "-ss", String(from), "-t", String(to - from), "-i", path.resolve(args.audio),
    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out]);
}
console.log("wrote", out, `${W}x${H}`);
