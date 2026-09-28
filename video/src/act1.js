// ACT 1 · Cold open (0:00–0:06). "Is this recyclable?" then "Stop guessing."
(window.BUILD = window.BUILD || []).push(() => {
  const { set, P, K, E, clamp, mix, spring, hash } = A;
  window.FLASHES = (window.FLASHES || []).concat([[4.0, 0.3, 0.16]]);

  A.scene("a1", 0, 6.02, (root) => {
    const CL = ART.CLASSES;
    const NT = 20, CX = 960, CY = 392, GAP = 318;
    let tiles = "";
    for (let n = 0; n < NT; n++) {
      const c = CL[n % 7];
      tiles += `<div class="itemtile c" data-k="tile${n}" style="left:${CX}px;top:${CY}px;width:256px;height:256px;
        background:radial-gradient(120% 120% at 30% 18%, ${c.tint}55, ${c.tint}12 70%);border:2px solid ${c.tint}70;
        box-shadow:0 0 0 0 transparent">${c.draw()}</div>`;
    }
    const groups = [
      ["Recyclable?", "#5BD98A", 470, 250], ["Food waste?", "#E0A23A", 1450, 235],
      ["Other waste?", "#B9C4BD", 430, 560], ["Hazardous?", "#F08A70", 1490, 575],
    ];
    const motes = Array.from({ length: 46 }, (_, i) => `<i data-k="mo${i}" class="abs" style="left:0;top:0;width:${3 + (i % 4)}px;height:${3 + (i % 4)}px;border-radius:50%;background:#BFF0CF"></i>`).join("");
    const ROW = "Recyclable?  Other waste?  Hazardous?  Food waste?  ";
    const m = A.build(root, `
      <div class="bg-dark"></div>
      <div class="abs full">${motes}</div>
      <div class="abs full" data-k="rows">
        ${[0, 1, 2, 3].map((i) => `<div class="abs disp nowrap" data-k="row${i}" style="left:0;top:${20 + i * 262}px;font-size:220px;color:transparent;-webkit-text-stroke:2px rgba(191,240,207,.17)">${ROW.repeat(4)}</div>`).join("")}
      </div>
      <div class="abs full" data-k="rig">
        <div data-k="glow" class="abs c" style="left:${CX}px;top:${CY}px;width:760px;height:760px;border-radius:50%"></div>
        <div data-k="dot" class="abs c" style="left:${CX}px;top:${CY}px;width:28px;height:28px;border-radius:50%;background:#BFF0CF;box-shadow:0 0 34px #BFF0CF"></div>
        ${tiles}
        ${U.bracket("br", "#BFF0CF", 10)}
        ${groups.map((g, i) => `<div class="abs c tagpill g-dark" data-k="bub${i}" style="left:${g[2]}px;top:${g[3]}px;font:600 44px/1 var(--ui);padding:24px 36px;color:${g[1]};border-color:${g[1]}66;letter-spacing:-.02em">${g[0]}</div>`).join("")}
        <div class="abs disp" data-k="q1" style="left:0;right:0;top:618px;text-align:center;font-size:80px;font-weight:300;color:#BFF0CF;letter-spacing:-.025em">Is this</div>
        <div class="abs disp nowrap" data-k="q2" style="left:0;right:0;top:700px;text-align:center;font-size:196px">${U.letters("recyclable?", "ql")}</div>
      </div>
      <div class="abs disp nowrap c" data-k="stop" style="left:960px;top:540px;font-size:270px;text-align:center;color:#fff">Stop guessing.</div>
    `);

    const mr = A.rng(11);
    const moteData = Array.from({ length: 46 }, () => ({ x: mr() * 1920, y: mr() * 1080, vx: (mr() - 0.5) * 18, vy: -6 - mr() * 16, ph: mr() * 6.28, o: 0.15 + mr() * 0.35 }));
    const steps = Array.from({ length: 12 }, (_, i) => 1.0 + i * 0.25);
    const QL = "recyclable?".length;

    return (t) => {
      // ambient motes
      moteData.forEach((d, i) => {
        const x = (((d.x + d.vx * t) % 1920) + 1920) % 1920, y = (((d.y + d.vy * t) % 1080) + 1080) % 1080;
        set(m["mo" + i], { x, y, o: d.o * (0.6 + 0.4 * Math.sin(t * 2 + d.ph)) * P(t, 0, 0.8) });
      });

      const sh = U.shake(t, 4.0, 22, 0.55);
      set(m.rig, { x: sh.x, y: sh.y, r: sh.r });

      // dot -> bracket
      const dotIn = spring(t - 0.05, 260, 16);
      set(m.dot, { s: dotIn * (1 - P(t, 0.34, 0.16)), o: t < 0.55 ? 1 : 0 });
      const beat = t > 1 && t < 4 ? Math.exp(-((t - 1) % 0.5) * 12) : 0;
      const bw = mix(28, 372, spring(t - 0.34, 190, 19)) + 14 * beat + P(t, 4.0, 0.5, E.outExpo) * 2200;
      U.setBracket(m, "br", CX, CY, bw, bw, bw * 0.24, bw * 0.13, P(t, 0.34, 0.4, E.outC));
      set(m.br, { x: CX - bw / 2, y: CY - bw / 2, o: t < 0.34 ? 0 : 1 - P(t, 4.0, 0.3) });

      // carousel
      let pos = 0;
      for (const s of steps) pos += E.outQuart(clamp((t - s) / 0.22));
      const idx = Math.round(pos);
      const tint = ART.CLASSES[((idx % 7) + 7) % 7].tint;
      m.glow.style.background = `radial-gradient(closest-side, ${tint}33, transparent)`;
      set(m.glow, { o: P(t, 0.5, 0.5) * (1 - P(t, 4.0, 0.2)), s: 1 + 0.06 * beat });
      const enter = P(t, 0.45, 0.7, E.cam);
      const lastStep = steps.filter((s) => s <= t).pop() || -9;
      const pop = 1 + 0.09 * Math.exp(-(t - lastStep) * 14);
      for (let n = 0; n < NT; n++) {
        const el = m["tile" + n];
        const d = Math.abs(n - pos);
        let s = d < 1 ? mix(1, 0.64, d) : Math.max(0.3, 0.64 - (d - 1) * 0.12);
        let o = d < 1 ? mix(1, 0.42, d) : Math.max(0, 0.42 - (d - 1) * 0.2);
        let x = (n - pos) * GAP + (1 - enter) * 420, y = 0, r = 0;
        if (d < 0.5) s *= pop;
        o *= enter;
        const sc = P(t, 4.0, 0.7, E.outExpo);
        if (sc > 0) {
          const a = hash(n + 3) * Math.PI * 2;
          x += Math.cos(a) * 1500 * sc; y += Math.sin(a) * 900 * sc; r = (hash(n) - 0.5) * 540 * sc; o *= 1 - P(t, 4.0, 0.35);
        }
        set(el, { x, y, s, r, o, blur: d > 1.2 ? (d - 1.2) * 5 : 0 });
      }

      // question
      set(m.q1, { y: (1 - spring(t - 1.0, 200, 22)) * 50, o: P(t, 1.0, 0.25) * (t < 4 ? 1 : 0) });
      for (let i = 0; i < QL; i++) {
        const lt = t - 1.18 - i * 0.034;
        const el = m["ql" + i];
        let r = 0;
        if (i === QL - 1) r = 14 * Math.sin((t - 2) * 26) * Math.exp(-(t - 2) * 7) * (t > 2 ? 1 : 0) + 14 * Math.sin((t - 3) * 26) * Math.exp(-(t - 3) * 7) * (t > 3 ? 1 : 0);
        set(el, { y: (1 - spring(lt, 280, 20)) * 110, o: clamp(lt * 7) * (t < 4 ? 1 : 0), r, css: { "font-weight": Math.round(mix(300, 800, P(lt, 0, 0.35, E.outC))) } });
      }

      // group bubbles (Hanoi's four waste groups)
      for (let i = 0; i < 4; i++) {
        const t0 = 2.75 + i * 0.25;
        const s = spring(t - t0, 320, 17);
        const out = P(t, 4.0, 0.14);
        set(m["bub" + i], { s: s * (1 + out * 0.5), o: clamp((t - t0) * 8) * (1 - out), y: Math.sin(t * 2.4 + i) * 6 });
      }

      // ghost rows + slam
      set(m.rows, { o: P(t, 3.96, 0.25) * (1 - P(t, 5.4, 0.35)) });
      for (let i = 0; i < 4; i++) set(m["row" + i], { x: (i % 2 ? -1400 : -300) + (i % 2 ? 1 : -1) * (t - 4) * 240 });
      const slam = P(t, 4.0, 0.42, E.outExpo);
      const sy = 1 - 0.975 * P(t, 5.5, 0.24, E.inExpo);
      const sx = (1 - 0.1 * P(t, 5.5, 0.24)) * (1 - 0.985 * P(t, 5.74, 0.2, E.inExpo));
      set(m.stop, { s: mix(1.7, 1, slam), sx, sy, o: (t >= 4 ? 1 : 0) * (t < 5.97 ? 1 : 0), blur: (1 - slam) * 10 });
      m.stop.style.color = t > 5.58 ? "#BFF0CF" : "#fff";
    };
  });
});
