// ACT 2 · Title (0:06–0:12). The leaf draws itself from its sharp corner, the
// name unpacks into its acronym, then the leaf becomes the matte into the scan.
(window.BUILD = window.BUILD || []).push(() => {
  const { set, attr, P, K, E, clamp, mix, spring } = A;
  window.FLASHES = window.FLASHES.concat([[8.02, 0.16, 0.22]]);

  // Leaf position/size over time, shared with the matte in act 3.
  const LEAF0 = { x: 960, y: 500, size: 460 };
  const LOCK_SIZE = 200, LOCK_Y = 480;
  window.TITLE = { LEAF0, lock: null };

  A.scene("a2", 5.86, 12.3, (root) => {
    const WORDS = [["A", "I"], ["W", "aste-sorting"], ["A", "nd"], ["R", "ecycling"], ["E", "nhancement"]];
    const ROWY = (i) => 150 + i * 158, COLX = 700, STACK_S = 0.74, WM = 196;
    const rays = [0, 1, 2].map((i) => `<div class="abs" data-k="ray${i}" style="left:${300 + i * 520}px;top:-300px;width:${140 + i * 60}px;height:1800px;transform-origin:50% 0;background:linear-gradient(180deg,rgba(191,240,207,.16),rgba(191,240,207,0) 70%)"></div>`).join("");
    const m = A.build(root, `
      <div class="abs full" data-k="bgwrap" style="opacity:0"><div class="bg-forest" data-k="forest"></div><div class="scrim-dark"></div></div>
      <div class="abs full" data-k="rays" style="mix-blend-mode:screen;filter:blur(18px)">${rays}</div>
      <div data-k="dot" class="abs c" style="left:960px;top:540px;width:28px;height:28px;border-radius:50%;background:#BFF0CF;box-shadow:0 0 34px #BFF0CF"></div>
      <svg data-k="leaf" class="abs c" viewBox="250 250 524 524" style="left:${LEAF0.x}px;top:${LEAF0.y}px;width:${LEAF0.size}px;height:${LEAF0.size}px;overflow:visible">
        <defs>
          <clipPath id="leafclip"><path d="${ART.LEAF_PATH}"/></clipPath>
          <linearGradient id="leafgrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5EAE62"/><stop offset="1" stop-color="#3B7C40"/></linearGradient>
          <linearGradient id="glintgrad" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".75"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
        </defs>
        <g clip-path="url(#leafclip)">
          <path data-k="waveB" fill="#8FD39A" fill-opacity=".55"/>
          <path data-k="waveF" fill="url(#leafgrad)"/>
          <rect data-k="glint" x="-200" y="200" width="160" height="700" fill="url(#glintgrad)" transform="rotate(35 512 512)"/>
        </g>
        <path data-k="olA" d="M751 273V512A239 239 0 0 1 512 751A239 239 0 0 1 273 512" fill="none" stroke="#BFF0CF" stroke-width="11" stroke-linecap="round" pathLength="1" stroke-dasharray="1 1"/>
        <path data-k="olB" d="M751 273H512A239 239 0 0 0 273 512" fill="none" stroke="#BFF0CF" stroke-width="11" stroke-linecap="round" pathLength="1" stroke-dasharray="1 1"/>
        <path data-k="corner" d="M640 273H751V384" fill="none" stroke="#fff" stroke-width="18" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1 1"/>
        <path data-k="stem" d="M352 672L298 726" stroke="#468749" stroke-width="50" stroke-linecap="round" pathLength="1" stroke-dasharray="1 1"/>
        <path data-k="vein" d="M421 605L546 480" stroke="#fff" stroke-width="52" stroke-linecap="round" pathLength="1" stroke-dasharray="1 1"/>
      </svg>
      <div class="abs full" data-k="burstwrap"></div>
      ${WORDS.map(([L, w], i) => `
        <div class="abs disp nowrap" data-k="L${i}" style="left:0;top:0;font-size:${WM}px;line-height:1;transform-origin:0 0">${L}</div>
        <div class="abs mask" data-k="Wm${i}" style="left:${COLX + 150}px;top:${ROWY(i) + 20}px;height:140px;width:0">
          <span class="disp nowrap" data-k="W${i}" style="font-size:108px;font-weight:300;line-height:1.2;color:#BFF0CF;letter-spacing:-.035em">${w}</span></div>`).join("")}
      <div class="abs mask" style="left:0;right:0;top:${LOCK_Y + 128}px;text-align:center;height:100px"><span class="disp nowrap" data-k="tag" style="font-size:74px;font-weight:350;color:#BFF0CF;letter-spacing:-.03em;line-height:1.2">Recycling made simple.</span></div>
      <div class="abs disp nowrap" data-k="measure" style="left:0;top:-500px;font-size:${WM}px;line-height:1">${[..."AWARE"].map((c, i) => `<span data-k="ms${i}">${c}</span>`).join("")}</div>
    `);
    const burst = U.leafBurst("lb", 18, 21);
    Object.assign(m, A.build(m.burstwrap, burst.html));

    // Measure the horizontal wordmark and suffix widths once fonts are ready.
    const wmW = m.measure.getBoundingClientRect().width;
    const offs = [0, 1, 2, 3, 4].map((i) => m["ms" + i].offsetLeft);
    const total = LOCK_SIZE + 44 + wmW;
    const lockX0 = 960 - total / 2;
    const lock = { x: lockX0 + LOCK_SIZE / 2, y: LOCK_Y, size: LOCK_SIZE };
    window.TITLE.lock = lock;
    const wordX = lockX0 + LOCK_SIZE + 44;
    const sufW = WORDS.map((_, i) => m["W" + i].getBoundingClientRect().width + 48);

    function wave(level, amp, t, ph) {
      let d = `M240 ${level}`;
      for (let x = 240; x <= 790; x += 22) {
        const y = level + amp * Math.sin(x * 0.021 + t * 7 + ph) + amp * 0.45 * Math.sin(x * 0.043 - t * 5 + ph);
        d += `L${x} ${y.toFixed(1)}`;
      }
      return d + "L790 800L240 800Z";
    }

    return (t) => {
      set(m.bgwrap, { o: P(t, 5.95, 1.0, E.ioQ) });
      set(m.forest, { s: mix(1.16, 1.04, P(t, 5.9, 6.4, E.lin)) });
      for (let i = 0; i < 3; i++) set(m["ray" + i], { x: Math.sin(t * 0.4 + i) * 60, r: 18 + i * 4, o: 0.8 * P(t, 6.4, 1.2) * (0.6 + 0.4 * Math.sin(t * 1.3 + i * 2)) });

      // leaf transform: centered -> left of the acronym -> lockup -> matte
      const toStack = P(t, 8.35, 0.7, E.cam);
      const toLock = P(t, 10.25, 0.6, E.cam);
      let lx = mix(LEAF0.x, 420, toStack), ly = mix(LEAF0.y, 540, toStack), ls = mix(1, 0.62, toStack);
      lx = mix(lx, lock.x, toLock); ly = mix(ly, lock.y, toLock); ls = mix(ls, LOCK_SIZE / LEAF0.size, toLock);
      set(m.leaf, { x: lx - LEAF0.x, y: ly - LEAF0.y, s: ls, o: 1 - P(t, 11.02, 0.12) });

      // dot travels to the sharp corner
      const dp = P(t, 5.9, 0.4, E.ioC);
      const cx = LEAF0.x + (239 / 524) * LEAF0.size, cy = LEAF0.y - (239 / 524) * LEAF0.size;
      set(m.dot, { x: mix(0, cx - 960, dp), y: mix(0, cy - 540, dp) - Math.sin(dp * Math.PI) * 120, s: 1 - 0.5 * P(t, 6.25, 0.1), o: t < 6.36 ? 1 : 0 });

      // outline and corner
      attr(m.corner, "stroke-dashoffset", 1 - P(t, 6.28, 0.26, E.outC));
      set(m.corner, { o: 1 - P(t, 7.9, 0.3) });
      const ol = P(t, 6.5, 0.8, E.ioC);
      attr(m.olA, "stroke-dashoffset", 1 - ol);
      attr(m.olB, "stroke-dashoffset", 1 - ol);
      const olFade = 1 - P(t, 8.0, 0.35);
      set(m.olA, { o: olFade }); set(m.olB, { o: olFade });

      // liquid fill
      const fill = P(t, 7.15, 0.95, E.ioC);
      const level = mix(780, 236, fill);
      const amp = 22 * (1 - P(t, 7.7, 0.6)) * (fill > 0 ? 1 : 0);
      attr(m.waveF, "d", wave(level, amp, t, 0));
      attr(m.waveB, "d", wave(level - 14, amp * 1.2, t, 1.7));
      attr(m.stem, "stroke-dashoffset", 1 - P(t, 7.85, 0.2, E.outC));
      attr(m.vein, "stroke-dashoffset", 1 - P(t, 8.0, 0.2, E.outExpo));
      const gl = P(t, 8.08, 0.5, E.ioC);
      attr(m.glint, "x", mix(-60, 1000, gl));

      burst.update(m, t, 8.02, 500, 1.1);
      set(m.lb, { x: LEAF0.x, y: LEAF0.y });

      // acronym: letters drop in stacked, words slide out, then the FLIP to a wordmark
      for (let i = 0; i < 5; i++) {
        const drop = spring(t - (8.45 + i * 0.09), 240, 20);
        const fl = P(t, 10.28 + i * 0.045, 0.55, E.cam);
        const sx = COLX, sy = ROWY(i);
        const hx = wordX + offs[i], hy = LOCK_Y - WM / 2;
        const x = mix(sx, hx, fl), y = mix(sy, hy, fl) - Math.sin(fl * Math.PI) * 60 + (1 - drop) * -140;
        set(m["L" + i], { x, y, s: mix(STACK_S, 1, fl), o: clamp((t - 8.45 - i * 0.09) * 6) * (1 - P(t, 11.05, 0.25)) });

        const open = P(t, 8.85 + i * 0.25, 0.5, E.outExpo);
        const close = P(t, 10.02 + (4 - i) * 0.035, 0.26, E.inExpo);
        const w = sufW[i] * open * (1 - close);
        m["Wm" + i].style.width = w.toFixed(1) + "px";
        set(m["W" + i], { x: (1 - open) * -40, css: { "font-stretch": `${Math.round(mix(75, 100, open))}%` } });
      }

      const tg = P(t, 10.72, 0.5, E.outExpo);
      set(m.tag, { y: (1 - tg) * 100, o: tg * (1 - P(t, 11.02, 0.25)) });
    };
  });
});
