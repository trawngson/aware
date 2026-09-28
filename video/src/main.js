// Boot: wait for fonts and images, build every scene, then expose seek(t).
// ?render hides the player (used by the renderer); ?t=12.5 opens at a time.
(async function () {
  "use strict";
  const params = new URLSearchParams(location.search);
  const rendering = params.has("render");
  if (rendering) document.body.classList.add("render");

  const faces = [
    '800 100px "Bricolage Grotesque"', '300 100px "Bricolage Grotesque"', '500 100px "Bricolage Grotesque"',
    '400 20px "Inter"', '600 20px "Inter"', '700 20px "Inter"', "Hoàn Kiếm",
  ];
  await Promise.all(faces.slice(0, 6).map((f) => document.fonts.load(f, "AWARE Hoàn Kiếm")));
  await document.fonts.ready;

  const images = ["forest.jpg", "forest_blur.jpg", "lamp.jpg", "turtle.jpg", "spiral.jpg", "avatar.png"];
  await Promise.all(images.map((n) => { const i = new Image(); i.src = "assets/img/" + n; return i.decode().catch(() => {}); }));

  U.ensureFilters();
  for (const b of window.BUILD) b();

  // Film grain: one noise tile, jittered every frame.
  const g = document.getElementById("grain");
  const ctx = g.getContext("2d");
  const img = ctx.createImageData(512, 512);
  const r = A.rng(7);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = 110 + r() * 145;
    img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  g.style.width = "2048px"; g.style.height = "2048px"; g.style.imageRendering = "pixelated";

  const flash = document.getElementById("flash"), fade = document.getElementById("fade"), vig = document.getElementById("vignette");
  A.onFrame((t) => {
    const f = Math.floor(t * 60);
    A.set(g, { x: -Math.floor(A.hash(f) * 512), y: -Math.floor(A.hash(f + 999) * 512) });
    let fl = 0;
    for (const [t0, a, d] of window.FLASHES || []) if (t >= t0 && t < t0 + d) fl = Math.max(fl, a * (1 - (t - t0) / d));
    A.set(flash, { o: fl });
    A.set(fade, { o: Math.max(A.P(t, 59.25, 0.75, A.E.ioQ), 1 - A.P(t, 0, 0.12)) });
    A.set(vig, { o: window.vignetteAt ? window.vignetteAt(t) : 1 });
  });

  const stage = document.getElementById("stage");
  function fit() {
    if (rendering) return;
    const s = Math.min(innerWidth / 1920, (innerHeight - 48) / 1080);
    stage.style.transform = `scale(${s})`;
  }
  fit(); addEventListener("resize", fit);

  let t = parseFloat(params.get("t") || "0");
  A.seek(t);
  window.__ready = true;
  if (rendering) return;

  const pp = document.getElementById("pp"), sc = document.getElementById("scrub"), tc = document.getElementById("tc");
  let playing = false, last = 0;
  const show = () => { A.seek(t); sc.value = t; tc.textContent = t.toFixed(2); };
  function loop(now) {
    if (!playing) return;
    t += (now - last) / 1000; last = now;
    if (t >= 60) { t = 60; playing = false; pp.textContent = "Play"; }
    show();
    requestAnimationFrame(loop);
  }
  pp.onclick = () => { playing = !playing; pp.textContent = playing ? "Pause" : "Play"; if (t >= 60) t = 0; last = performance.now(); requestAnimationFrame(loop); };
  sc.oninput = () => { t = +sc.value; show(); };
  addEventListener("keydown", (e) => {
    if (e.code === "Space") { e.preventDefault(); pp.click(); }
    if (e.key === "ArrowRight") { t = Math.min(60, t + (e.shiftKey ? 0.1 : 1)); show(); }
    if (e.key === "ArrowLeft") { t = Math.max(0, t - (e.shiftKey ? 0.1 : 1)); show(); }
  });
  show();
})();
