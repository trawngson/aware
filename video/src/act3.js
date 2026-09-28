// ACT 3 · Point. Scan. Know. (0:11–0:24)
(window.BUILD = window.BUILD || []).push(() => {
  const { set, attr, P, K, E, clamp, mix, spring } = A;
  window.FLASHES = window.FLASHES.concat([[21.56, 0.14, 0.18], [22.02, 0.3, 0.22]]);
  const LEAFMASK = `url("data:image/svg+xml;utf8,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' viewBox='250 250 524 524'><path d='${ART.LEAF_PATH}'/></svg>`)}")`;
  const mixColor = (a, b, p) => {
    const pa = a.match(/\w\w/g).map((h) => parseInt(h, 16)), pb = b.match(/\w\w/g).map((h) => parseInt(h, 16));
    return "#" + pa.map((v, i) => Math.round(mix(v, pb[i], clamp(p))).toString(16).padStart(2, "0")).join("");
  };
  window.mixColor = mixColor;

  // Mask-up text reveal helper.
  const reveal = (el, t, t0, d = 0.5, dist = 1.05) => {
    const p = P(t, t0, d, E.outExpo);
    if (!el.__h) el.__h = Math.max(el.offsetHeight, el.parentNode.offsetHeight) * dist;
    set(el, { y: (1 - p) * el.__h });
    return p;
  };
  window.reveal = reveal;

  // ------------------------------------------------------------------ scan
  A.scene("a3", 11.0, 18.72, (root) => {
    const SX = 763.5, SY = 114; // screen origin in stage px when the rig is at scale 1
    const BOT = { l: 131.7, t: 80, r: 260.3, b: 440 };
    const callouts = [
      ["Runs on-device", "Nothing is uploaded"],
      ["5 MB YOLO26n model", "Core ML, FP16"],
      ["~25 ms per frame", "on a 2018 iPhone XR"],
      ["Hold steady for 1 s", "and the result opens itself"],
    ];
    const CY0 = 200, CDY = 180;
    const m = A.build(root, `
      <div class="bg-dark"></div>
      <div class="abs c" data-k="halo" style="left:960px;top:540px;width:1100px;height:1100px;border-radius:50%;background:radial-gradient(closest-side,rgba(91,217,138,.16),transparent)"></div>
      <div class="abs" data-k="rig" style="left:0;top:0;width:1920px;height:1080px;transform-origin:0 0;perspective:2600px">
        ${U.phone("ph", U.scanScreen("sc"), "left:751.5px;top:102px")}
      </div>
      <div class="abs mask" style="left:104px;top:150px;height:200px"><span class="disp nowrap" data-k="wPoint" style="font-size:190px">Point.</span></div>
      <div class="abs mask" style="left:104px;top:330px;height:200px"><span class="disp nowrap" data-k="wScan" style="font-size:190px">Scan.</span></div>
      <div class="abs" data-k="meter" style="left:112px;top:585px;width:540px">
        <div style="font:600 30px/1 var(--ui);color:#BFF0CF;letter-spacing:-.01em">Confidence</div>
        <div class="disp tab" data-k="mNum" style="font-size:160px;margin-top:14px;color:#F2C94C">58%</div>
        <div style="position:relative;height:16px;border-radius:8px;background:rgba(255,255,255,.1);margin-top:26px">
          <i data-k="mBar" class="abs" style="left:0;top:0;bottom:0;width:58%;border-radius:8px;background:linear-gradient(90deg,#F2C94C,#5BD98A 75%)"></i>
          <i class="abs" style="left:40%;top:-10px;width:2px;height:36px;background:rgba(255,255,255,.6)"></i>
          <i class="abs" style="left:75%;top:-10px;width:2px;height:36px;background:rgba(255,255,255,.6)"></i>
          <span class="abs nowrap" style="left:40%;top:40px;translate:-50% 0;font:500 28px/1.2 var(--ui);color:rgba(230,238,231,.75)">shown</span>
          <span class="abs nowrap" style="left:75%;top:40px;translate:-50% 0;font:500 28px/1.2 var(--ui);color:rgba(230,238,231,.75)">auto-confirm</span>
        </div>
      </div>
      ${callouts.map(([a, b], i) => `
        <div class="callout" data-k="co${i}" style="left:1290px;top:${CY0 + i * CDY}px">
          <i class="dt" data-k="cod${i}" style="left:-120px;top:24px"></i>
          <i class="ln" data-k="col${i}" style="left:-106px;top:30px;width:86px"></i>
          <div class="mask" style="display:block;height:62px"><div class="ttl" data-k="cot${i}">${a}</div></div>
          <div class="sub" data-k="cos${i}">${b}</div>
        </div>`).join("")}
      ${U.bracket("lift", "#5BD98A", 10)}
    `);
    const vfR = 0; // viewfinder uses its own bracket inside the screen

    return (t) => {
      // matte: the leaf from the title becomes a window onto this scene
      const L = window.TITLE.lock;
      if (t < 12.24) {
        const g = P(t, 11.1, 1.12, E.ioExpo);
        const size = mix(L.size, 3400, g);
        const cx = mix(L.x, 960, g), cy = mix(L.y, 540, g);
        const s = root.style;
        s.webkitMaskImage = s.maskImage = LEAFMASK;
        s.webkitMaskRepeat = s.maskRepeat = "no-repeat";
        s.webkitMaskSize = s.maskSize = `${size}px ${size}px`;
        s.webkitMaskPosition = s.maskPosition = `${cx - size / 2}px ${cy - size / 2}px`;
        s.opacity = P(t, 11.0, 0.14);
      } else if (root.style.maskImage) {
        const s = root.style;
        s.webkitMaskImage = s.maskImage = "none";
        s.opacity = 1;
      }

      // camera rig: portal close-up on the bottle label, pull back to the phone
      const pull = P(t, 12.2, 1.3, E.cam);
      const sc = mix(5.4, 1, pull) * (1 + 0.012 * Math.sin(t * 0.9));
      const fx = mix(SX + 196, 960, pull), fy = mix(SY + 300, 540, pull);
      const lift = P(t, 18.02, 0.5, E.inQ);
      const scale = sc * (1 - 0.22 * lift);
      set(m.rig, { x: 960 - fx * scale, y: 540 - fy * scale, s: scale, o: 1 - P(t, 18.1, 0.4) });
      set(m.ph, { ry: K(t, [[12.2, 0], [12.85, -22, E.outQ], [13.8, 0, E.ioC], [17.2, 0], [18.0, 6, E.ioQ]]), rx: K(t, [[12.2, 0], [12.85, 6, E.outQ], [13.8, 0, E.ioC]]) });
      set(m.halo, { o: pull * (1 - lift), s: 1 + 0.03 * Math.sin(t * 1.4) });

      // scan UI fades in during the pull-back
      const ui = P(t, 12.7, 0.5);
      for (const k of ["scNav", "scDet"]) set(m[k], { o: ui, y: (1 - ui) * 20 });
      set(m.scVf, { o: ui * (1 - P(t, 14.2, 0.3)) });
      const pulse = 0.5 + 0.5 * Math.sin((t - 12.7) * (Math.PI * 2 / 2.4));
      const vw = 150 * (1 + 0.06 * pulse) * (1 - 0.2 * P(t, 14.2, 0.3));
      U.setBracket(m, "scVfB", 196, 272, vw, vw, 40, 18, 1);
      set(m.scVfB, { x: 196 - vw / 2, y: 272 - vw / 2, o: 0.6 + 0.35 * pulse });
      for (let i = 0; i < 6; i++) set(m["scBok" + i], { x: Math.sin(t * 0.5 + i) * 10, y: Math.cos(t * 0.4 + i * 2) * 6 });

      // vision sweep
      const sw = P(t, 14.15, 0.75, E.ioQ);
      set(m.scSweep, { y: mix(-160, 560, sw), o: sw > 0 && sw < 1 ? 1 : 0 });
      set(m.scBVision, { o: P(t, 14.3, 0.35) * (1 - P(t, 15.3, 0.5)) });

      // detection box and confidence
      const conf = K(t, [[14.75, 58], [16.15, 92, E.outC]]);
      const green = P(conf, 72, 6);
      const col = mixColor("F2C94C", "5BD98A", green);
      const tight = spring(t - 14.75, 90, 13);
      const inf = mix(46, 10, tight);
      const b = m.scBox;
      set(b, { x: BOT.l - inf, y: BOT.t - inf, o: P(t, 14.72, 0.08) * (1 - P(t, 18.0, 0.06)), css: { width: `${BOT.r - BOT.l + inf * 2}px`, height: `${BOT.b - BOT.t + inf * 2}px`, "--bc": col, "box-shadow": `0 0 ${14 + 16 * Math.exp(-(t - 16.45) * 5) * (t > 16.45 ? 1 : 0)}px ${col}88, inset 0 0 10px ${col}44` } });
      set(m.scBoxLbl, { text: `Plastic bottle · ${Math.round(conf)}%` });
      set(m.scRow0, { o: 1 - P(t, 14.8, 0.2) });
      set(m.scRow1, { o: P(t, 14.85, 0.25), x: (1 - spring(t - 14.85, 200, 20)) * 60 });
      set(m.scRowPct, { text: `${Math.round(conf)}%`, css: { color: col } });
      const holding = t >= 15.45;
      set(m.scStatus, { text: holding ? "Hold steady…" : "Scanning" });
      set(m.scRing, { o: holding ? 1 : 0 });
      attr(m.scRingArc, "stroke-dashoffset", 1 - P(t, 15.45, 1.0));

      // words and meter
      const exitL = P(t, 17.35, 0.45, E.inC);
      reveal(m.wPoint, t, 12.95, 0.55);
      m.wPoint.style.color = t > 14.45 ? "transparent" : "#fff";
      m.wPoint.style.webkitTextStroke = t > 14.45 ? "2px rgba(191,240,207,.4)" : "0";
      reveal(m.wScan, t, 14.45, 0.55);
      set(m.wPoint.parentNode, { x: -exitL * 700 });
      set(m.wScan.parentNode, { x: -exitL * 700 });
      const mi = spring(t - 14.9, 150, 20);
      set(m.meter, { o: P(t, 14.9, 0.3) * (1 - exitL), x: (1 - mi) * -80 - exitL * 700 });
      set(m.mNum, { text: `${Math.round(conf)}%`, css: { color: col } });
      m.mBar.style.width = conf.toFixed(1) + "%";

      // callouts
      for (let i = 0; i < 4; i++) {
        const t0 = 15.2 + i * 0.5;
        const ln = P(t, t0, 0.3, E.outExpo);
        set(m["col" + i], { sx: ln, o: ln > 0 ? 1 : 0 });
        set(m["cod" + i], { s: spring(t - t0, 300, 18), o: ln > 0 ? 1 : 0 });
        reveal(m["cot" + i], t, t0 + 0.12, 0.5);
        set(m["cos" + i], { o: P(t, t0 + 0.25, 0.35), y: (1 - P(t, t0 + 0.25, 0.4, E.outC)) * 16 });
        const ex = P(t, 17.35 + i * 0.06, 0.4, E.inC);
        set(m["co" + i], { x: ex * 700, o: 1 - ex });
      }

      // the detection box lifts off the phone and becomes the brand bracket
      const lp = P(t, 18.0, 0.55, E.ioC);
      const bx0 = 960 + (SX + (BOT.l + BOT.r) / 2 - 960), by0 = SY + (BOT.t + BOT.b) / 2;
      const w = mix(BOT.r - BOT.l + 20, 440, lp), h = mix(BOT.b - BOT.t + 20, 440, lp);
      U.setBracket(m, "lift", mix(bx0, 600, lp), mix(by0, 540, lp), w, h, mix(34, 104, lp), mix(12, 56, lp), 1);
      set(m.lift, { x: mix(bx0, 600, lp) - w / 2, y: mix(by0, 540, lp) - h / 2, o: t >= 18.0 && t < 18.6 ? 1 : 0 });
    };
  });

  // ------------------------------------------------------------------ seven classes
  A.scene("a3b", 18.5, 22.4, (root) => {
    const CL = ART.CLASSES, N = 26, IH = 420, NH = 150;
    const BX = 600, BY = 540, BS = 440;
    const m = A.build(root, `
      <div class="bg-dark"></div>
      <div class="abs c" data-k="glow" style="left:${BX}px;top:${BY}px;width:1000px;height:1000px;border-radius:50%"></div>
      <div class="abs mask" style="left:110px;top:86px;height:110px"><span class="disp nowrap" data-k="hd" style="font-size:88px;font-weight:800">Seven kinds of everyday waste.</span></div>
      <div class="abs" data-k="hdsub" style="left:114px;top:200px;font:500 36px/1 var(--ui);color:#BFF0CF;letter-spacing:-.01em">One 5 MB model spots them all, on the phone.</div>
      <div class="abs" data-k="win" style="left:${BX - 190}px;top:${BY - 190}px;width:380px;height:380px;overflow:hidden;border-radius:40px">
        <div class="abs full" data-k="reelA" style="filter:url(#vblurA)">
          ${Array.from({ length: N }, (_, n) => `<div class="abs" data-k="it${n}" style="left:40px;top:40px;width:300px;height:300px">${CL[((n % 7) + 7) % 7].draw()}</div>`).join("")}
        </div>
      </div>
      ${U.bracket("br", "#5BD98A", 11)}
      <div class="abs" data-k="names" style="left:930px;top:${BY - 380}px;width:980px;height:760px;overflow:hidden;-webkit-mask:linear-gradient(180deg,transparent,#000 24%,#000 76%,transparent);mask:linear-gradient(180deg,transparent,#000 24%,#000 76%,transparent)">
        <div class="abs full" data-k="reelB" style="filter:url(#vblurB)">
          ${Array.from({ length: N }, (_, n) => { const c = CL[((n % 7) + 7) % 7]; return `<div class="reel-name" data-k="nm${n}" style="top:${380 - 60}px;font-size:120px;color:${c.tint}">${c.name}</div>`; }).join("")}
        </div>
      </div>
      <div class="abs" data-k="dots" style="left:${BX - 190}px;top:${BY + 290}px;display:flex;gap:10px;align-items:center">
        ${CL.map((c, i) => `<i data-k="dt${i}" style="display:block;height:10px;width:30px;border-radius:5px;background:${c.tint}"></i>`).join("")}
      </div>
    `);
    const gA = document.getElementById("vblurA-g"), gB = document.getElementById("vblurB-g");
    const pos = (t) => 21 * E.outQuart(clamp((t - 18.6) / 2.95));
    const lockT = 21.55;

    return (t) => {
      const p = pos(t), v = (pos(t + 1 / 120) - pos(t - 1 / 120)) * 60;
      const idx = ((Math.round(p) % 7) + 7) % 7, c = CL[idx];
      const lockPulse = t > lockT ? Math.exp(-(t - lockT) * 6) : 0;
      const zoom = P(t, 21.95, 0.45, E.inC);

      set(m.glow, { o: 0.9 * (1 - zoom), s: 1 + 0.2 * lockPulse, css: { background: `radial-gradient(closest-side, ${c.tint}40, transparent)` } });
      const bs = BS + 36 * lockPulse + zoom * 500;
      const bcx = mix(BX, 960, zoom), bcy = BY;
      U.setBracket(m, "br", bcx, bcy, bs, bs, bs * 0.236, bs * 0.127, 1, c.tint);
      set(m.br, { x: bcx - bs / 2, y: bcy - bs / 2, o: t < 18.58 ? 0 : 1 - zoom });

      gA.setAttribute("stdDeviation", `0 ${Math.min(26, Math.abs(v) * 1.1).toFixed(2)}`);
      gB.setAttribute("stdDeviation", `0 ${Math.min(22, Math.abs(v) * 0.9).toFixed(2)}`);
      for (let n = 0; n < N; n++) {
        const d = n - p;
        set(m["it" + n], { y: d * IH, o: Math.abs(d) < 1.5 ? 1 : 0, s: 1 + 0.1 * lockPulse * (Math.abs(d) < 0.5 ? 1 : 0) });
        const ad = Math.abs(d);
        set(m["nm" + n], { y: d * NH, s: ad < 1 ? mix(1, 0.52, ad) : Math.max(0.3, 0.52 - (ad - 1) * 0.08), o: ad < 1 ? mix(1, 0.34, ad) : Math.max(0, 0.34 - (ad - 1) * 0.12) });
      }
      set(m.win, { x: (bcx - BX), s: 1 + zoom * 1.2, o: 1 - zoom });
      set(m.names, { o: P(t, 18.55, 0.3) * (1 - P(t, 21.9, 0.3)), x: (1 - P(t, 18.5, 0.6, E.cam)) * 200 });
      reveal(m.hd, t, 18.7, 0.55);
      set(m.hdsub, { o: P(t, 19.0, 0.4) * (1 - P(t, 21.9, 0.3)), y: (1 - P(t, 19.0, 0.5, E.outC)) * 20 });
      set(m.hd.parentNode, { o: 1 - P(t, 21.9, 0.3) });
      for (let i = 0; i < 7; i++) set(m["dt" + i], { css: { width: i === idx ? "70px" : "30px" }, o: (i === idx ? 1 : 0.3) * (1 - P(t, 21.9, 0.3)) });
    };
  });

  // ------------------------------------------------------------------ know
  A.scene("a3c", 21.95, 24.3, (root) => {
    const H = 700, W = H * 200 / 560, BXC = 960, BYC = 540;
    const m = A.build(root, `
      <div class="bg-dark"></div>
      <div class="abs c" data-k="glow" style="left:${BXC}px;top:${BYC}px;width:1300px;height:1300px;border-radius:50%;background:radial-gradient(closest-side,rgba(91,217,138,.3),transparent)"></div>
      <div class="abs c" data-k="floor" style="left:${BXC}px;top:${BYC + H / 2 + 6}px;width:${W * 2}px;height:70px;border-radius:50%;background:radial-gradient(closest-side,rgba(0,0,0,.55),transparent)"></div>
      <svg class="abs" data-k="bottle" viewBox="0 0 200 560" style="left:${BXC - W / 2}px;top:${BYC - H / 2}px;width:${W}px;height:${H}px;overflow:visible">${ART.bottle("kb")}</svg>
      <div class="abs detbox" data-k="box" style="left:${BXC - W / 2 - 34}px;top:${BYC - H / 2 - 34}px;width:${W + 68}px;height:${H + 68}px;border-width:5px;border-radius:30px;--bc:#5BD98A;box-shadow:0 0 40px rgba(91,217,138,.6),inset 0 0 26px rgba(91,217,138,.3)"></div>
      <div class="abs c" data-k="ring0" style="left:${BXC + W / 2 + 34}px;top:${BYC - H / 2 - 34}px;width:170px;height:170px;border-radius:50%;border:4px solid #5BD98A"></div>
      <div class="abs c" data-k="ring1" style="left:${BXC + W / 2 + 34}px;top:${BYC - H / 2 - 34}px;width:170px;height:170px;border-radius:50%;border:3px solid #BFF0CF"></div>
      <div class="abs c" data-k="chk" style="left:${BXC + W / 2 + 34}px;top:${BYC - H / 2 - 34}px;width:150px;height:150px;border-radius:50%;background:#5BD98A;display:grid;place-items:center;box-shadow:0 0 50px rgba(91,217,138,.7)">
        <svg viewBox="0 0 24 24" style="width:84px;height:84px"><path data-k="chkp" d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="#07140D" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1 1"/></svg></div>
      <div class="abs mask" style="left:104px;top:420px;height:210px"><span class="disp nowrap" data-k="wKnow" style="font-size:200px">Know.</span></div>
      <div class="abs" data-k="info" style="left:1300px;top:470px">
        <div style="font:700 64px/1 var(--ui);letter-spacing:-.04em">Plastic bottle</div>
        <div style="display:flex;gap:14px;margin-top:22px">
          <span class="tagpill" style="font-size:30px;color:#5BD98A;background:rgba(91,217,138,.15)">${ART.icon("recycle")} Recyclable</span>
          <span class="tagpill" style="font-size:30px;color:#fff;background:rgba(255,255,255,.12)">92% match</span></div>
      </div>
      <div class="abs full" data-k="wipe" style="pointer-events:none"></div>
    `);
    const sp = U.leafBurst("sp", 14, 5, ["#BFF0CF", "#5BD98A", "#fff"]);
    Object.assign(m, A.build(root, sp.html));
    return (t) => {
      const zin = P(t, 21.95, 0.45, E.outC);
      set(m.bottle, { s: mix(0.6, 1, zin) * (1 + 0.01 * Math.sin(t * 2)), o: zin, y: (1 - zin) * 40 });
      set(m.floor, { o: zin * 0.8 });
      set(m.glow, { o: zin, s: 1 + 0.08 * Math.exp(-(t - 22.02) * 3) });
      const bx = spring(t - 22.02, 260, 19);
      set(m.box, { s: mix(1.25, 1, bx), o: clamp((t - 22.02) * 8) });
      const ck = spring(t - 22.1, 300, 15);
      set(m.chk, { s: ck, o: clamp((t - 22.1) * 10) });
      attr(m.chkp, "stroke-dashoffset", 1 - P(t, 22.2, 0.25, E.outC));
      for (let i = 0; i < 2; i++) {
        const r = P(t, 22.1 + i * 0.12, 0.7, E.outC);
        set(m["ring" + i], { s: 1 + r * (2.4 + i), o: (1 - r) * (r > 0 ? 0.9 : 0) });
      }
      sp.update(m, t, 22.12, 300, 1.0);
      set(m.sp, { x: BXC + W / 2 + 34, y: BYC - H / 2 - 34 });
      reveal(m.wKnow, t, 22.02, 0.55);
      set(m.info, { o: P(t, 22.45, 0.35), x: (1 - P(t, 22.45, 0.6, E.cam)) * 80 });
    };
  });
});
