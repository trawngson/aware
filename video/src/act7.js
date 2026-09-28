// ACT 7 · Back to the leaf (0:54–1:00). Every leaf converges into the logo,
// then the end card.
(window.BUILD = window.BUILD || []).push(() => {
  const { set, attr, P, K, E, clamp, mix, spring } = A;
  const reveal = window.reveal;
  window.FLASHES = window.FLASHES.concat([[55.55, 0.18, 0.3]]);
  const LC = { x: 960, y: 470, size: 460 }; // leaf box (the 524-unit icon viewBox)

  // Is a point (icon units) inside the leaf body: a circle with one square quadrant?
  const inLeaf = (x, y) => (x - 512) ** 2 + (y - 512) ** 2 <= 236 ** 2 || (x >= 512 && x <= 748 && y >= 276 && y <= 512);

  A.scene("a7a", 53.85, 56.3, (root) => {
    const m = A.build(root, `
      <div class="abs full" data-k="bg"><div class="bg-forest" data-k="forest"></div><div class="scrim-dark" style="background:radial-gradient(80% 75% at 50% 44%,rgba(7,20,13,.55),rgba(2,6,4,.96))"></div></div>
      <div class="abs c" data-k="glow" style="left:${LC.x}px;top:${LC.y}px;width:1200px;height:1200px;border-radius:50%;background:radial-gradient(closest-side,rgba(91,217,138,.34),transparent)"></div>
      <canvas data-k="cv" width="1920" height="1080" class="abs" style="left:0;top:0"></canvas>
      <svg data-k="leaf" class="abs c" viewBox="250 250 524 524" style="left:${LC.x}px;top:${LC.y}px;width:${LC.size}px;height:${LC.size}px;overflow:visible">
        <defs><clipPath id="endclip"><path d="${ART.LEAF_PATH}"/></clipPath>
          <linearGradient id="endg" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".8"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient></defs>
        <path d="${ART.LEAF_PATH}" fill="#4E9A52"/>
        <path data-k="stem" d="M352 672L298 726" stroke="#4E9A52" stroke-width="50" stroke-linecap="round" pathLength="1" stroke-dasharray="1 1"/>
        <path data-k="vein" d="M421 605L546 480" stroke="#fff" stroke-width="52" stroke-linecap="round" pathLength="1" stroke-dasharray="1 1"/>
        <g clip-path="url(#endclip)"><rect data-k="gl" x="0" y="200" width="160" height="700" fill="url(#endg)" transform="rotate(35 512 512)"/></g>
      </svg>
      <div class="abs" data-k="line" style="left:0;right:0;top:830px;text-align:center;white-space:nowrap">
        ${"One quick scan to".split(" ").map((w, i) => `<span class="disp" data-k="w${i}" style="display:inline-block;font-size:84px;font-weight:450;letter-spacing:-.035em;margin:0 .12em">${w}</span>`).join("")}
        ${"sort with ease.".split(" ").map((w, i) => `<span class="disp" data-k="w${i + 4}" style="display:inline-block;font-size:84px;color:#BFF0CF;margin:0 .12em">${w}</span>`).join("")}
      </div>
    `);
    // targets: evenly spread points inside the leaf, via rejection sampling
    const r = A.rng(2024), pts = [];
    let guard = 0;
    while (pts.length < 280 && guard++ < 40000) {
      const x = 270 + r() * 484, y = 270 + r() * 484;
      if (!inLeaf(x, y)) continue;
      if (pts.some((p) => (p.x - x) ** 2 + (p.y - y) ** 2 < 24 * 24)) continue;
      pts.push({ x, y });
    }
    const k = LC.size / 524;
    const parts = pts.map((p) => {
      const tx = LC.x + (p.x - 512) * k, ty = LC.y + (p.y - 512) * k;
      const a0 = r() * Math.PI * 2, R0 = 700 + r() * 700;
      const t0 = 53.9 + r() * 0.6;
      return { tx, ty, a0, R0, t0, d: 0.85 + r() * 0.45, spin: 2 + r() * 2.2, sz: 22 + r() * 16, c: ["#34A862", "#5BD98A", "#2E9E5B", "#BFF0CF", "#4E9A52"][Math.floor(r() * 5)], rot: r() * 6.28 };
    });
    const ctx = m.cv.getContext("2d");
    const leafShape = new Path2D("M0 -1H1V0A1 1 0 0 1 0 1A1 1 0 0 1 -1 0A1 1 0 0 1 0 -1Z");

    return (t) => {
      set(m.bg, { o: P(t, 53.85, 0.45) });
      set(m.forest, { s: 1.12 - 0.06 * P(t, 53.85, 2.5) });
      const solid = P(t, 55.3, 0.3);
      ctx.clearRect(0, 0, 1920, 1080);
      if (solid < 1) {
        for (const q of parts) {
          const u = clamp((t - q.t0) / q.d);
          if (u <= 0) continue;
          const e = E.ioC(u);
          const R = q.R0 * Math.pow(1 - e, 1.3);
          const a = q.a0 + q.spin * (1 - e) * 2.4;
          const x = q.tx + Math.cos(a) * R * 1.25, y = q.ty + Math.sin(a) * R * 0.72;
          const s = mix(q.sz, 13, e) / 2;
          ctx.save();
          ctx.globalAlpha = Math.min(1, u * 4) * (1 - solid);
          ctx.translate(x, y);
          ctx.rotate(q.rot + (1 - e) * 6);
          ctx.scale(s, s);
          ctx.fillStyle = q.c;
          ctx.fill(leafShape);
          ctx.restore();
        }
      }
      set(m.leaf, { o: solid, s: 1 + 0.04 * Math.exp(-(t - 55.3) * 5) * (t > 55.3 ? 1 : 0) });
      attr(m.stem, "stroke-dashoffset", 1 - P(t, 55.45, 0.15, E.outC));
      attr(m.vein, "stroke-dashoffset", 1 - P(t, 55.55, 0.18, E.outExpo));
      attr(m.gl, "x", mix(-60, 1000, P(t, 55.6, 0.5, E.ioC)));
      set(m.glow, { o: P(t, 54.2, 0.8) * (1 + 0.3 * Math.exp(-(t - 55.55) * 4) * (t > 55.55 ? 1 : 0)), s: 1 + 0.05 * Math.sin(t * 2) });
      for (let i = 0; i < 7; i++) {
        const t0 = 54.45 + i * 0.09;
        set(m["w" + i], { y: (1 - spring(t - t0, 220, 20)) * 50, o: clamp((t - t0) * 5) * (1 - P(t, 55.85, 0.3)) });
      }
    };
  });

  A.scene("a7b", 55.98, 60.01, (root) => {
    const m = A.build(root, `
      <div class="bg-dark" style="background:radial-gradient(90% 80% at 50% 30%,#18402A 0%,#07140D 60%,#020705 100%)"></div>
      <div class="abs full" data-k="drift"></div>
      <div class="abs c" data-k="tile" style="left:960px;top:300px;width:250px;height:250px;border-radius:58px;background:#fff;box-shadow:0 30px 70px rgba(0,0,0,.45),0 0 0 1px rgba(255,255,255,.5);overflow:hidden">
        <i data-k="shine" class="abs" style="top:-60px;bottom:-60px;left:0;width:110px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.95),transparent);transform:rotate(22deg);mix-blend-mode:soft-light"></i></div>
      <svg data-k="leaf" class="abs c" viewBox="250 250 524 524" style="left:${LC.x}px;top:${LC.y}px;width:${LC.size}px;height:${LC.size}px;overflow:visible">
        <path data-k="lp" d="${ART.LEAF_PATH}" fill="#4E9A52"/><path data-k="ls" d="M352 672L298 726" stroke="#4E9A52" stroke-width="50" stroke-linecap="round"/>
        <path d="M421 605L546 480" stroke="#fff" stroke-width="52" stroke-linecap="round"/></svg>
      <div class="abs" style="left:0;right:0;top:450px;text-align:center;white-space:nowrap">${[..."AWARE"].map((c, i) => `<span class="mask" style="height:215px"><span class="disp" data-k="a${i}" style="font-size:220px;line-height:1">${c}</span></span>`).join("")}</div>
      <div class="abs" data-k="tag" style="left:0;right:0;top:688px;text-align:center;font:350 76px/1 var(--display);color:#BFF0CF;letter-spacing:-.03em">Recycling made simple.</div>
      <div class="abs" data-k="i0" style="left:0;right:0;top:852px;text-align:center;font:500 32px/1 var(--ui);color:rgba(255,255,255,.82)">Recycling guidance based on Hanoi's waste-sorting regulations</div>
      <div class="abs" data-k="i1" style="left:0;right:0;top:910px;text-align:center;font:500 28px/1 var(--ui);color:rgba(255,255,255,.6)">iOS &amp; iPadOS 18+ · SwiftUI · Core ML · Ultralytics YOLO</div>
      <div class="abs" data-k="i2" style="left:0;right:0;top:960px;text-align:center;font:600 28px/1 var(--ui);color:#5BD98A">github.com/trawngson/aware</div>
    `);
    const dr = A.rng(8);
    const fall = Array.from({ length: 18 }, () => ({ x: dr() * 1920, y: dr() * 1080, v: 30 + dr() * 50, sz: 10 + dr() * 22, ph: dr() * 6.28, o: 0.12 + dr() * 0.22 }));
    Object.assign(m, A.build(m.drift, fall.map((f, i) => `<i data-k="f${i}" class="abs" style="left:0;top:0;width:${f.sz}px;height:${f.sz}px;border-radius:50% 0 50% 50%;background:#5BD98A;filter:blur(${f.sz > 24 ? 3 : 1}px)"></i>`).join("")));
    return (t) => {
      const mv = P(t, 55.98, 0.7, E.cam);
      const ls = mix(1, 180 / LC.size, mv);
      set(m.leaf, { y: mix(0, 300 - LC.y, mv), s: ls });
      const fillc = window.mixColor("4E9A52", "468749", mv);
      attr(m.lp, "fill", fillc); attr(m.ls, "stroke", fillc);
      set(m.tile, { s: spring(t - 56.2, 180, 16) });
      set(m.shine, { x: mix(-200, 420, P(t, 57.2, 0.7, E.ioC)) });
      for (let i = 0; i < 5; i++) reveal(m["a" + i], t, 56.55 + i * 0.06, 0.6);
      set(m.tag, { o: P(t, 57.0, 0.5), y: (1 - P(t, 57.0, 0.6, E.outC)) * 24 });
      for (let i = 0; i < 3; i++) set(m["i" + i], { o: P(t, 57.4 + i * 0.18, 0.5), y: (1 - P(t, 57.4 + i * 0.18, 0.6, E.outC)) * 16 });
      fall.forEach((f, i) => set(m["f" + i], { x: f.x + Math.sin(t * 0.8 + f.ph) * 40, y: ((f.y + f.v * (t - 56)) % 1180) - 50, r: t * 40 + f.ph * 50, o: f.o * P(t, 56.3, 1) }));
    };
  });

  // Vignette strength per section (light scenes get a softer one).
  window.vignetteAt = (t) => K(t, [[23.4, 1], [23.9, 0.3], [34.1, 0.3], [34.5, 0.7], [43.7, 0.7], [44.0, 0.25], [48.0, 0.25], [48.5, 0.8], [53.9, 0.8], [54.3, 1]]);
});
