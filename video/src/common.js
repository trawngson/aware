// Shared building blocks for the scenes.
(function () {
  "use strict";
  const { set, attr, clamp, mix, E, spring } = A;

  // ---- Brand bracket: viewfinder corners, rounded except the logo's sharp corner.
  function bracket(k, color = "#BFF0CF", width = 8) {
    return `<svg data-k="${k}" class="abs" style="overflow:visible;left:0;top:0" width="10" height="10">
      ${[0, 1, 2, 3].map((i) => `<path data-k="${k}${i}" fill="none" stroke="${color}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round" pathLength="1"/>`).join("")}
    </svg>`;
  }
  // Place a bracket box centered at (cx, cy) with size w x h, arm length L,
  // corner radius R; draw is 0..1 (stroke reveal from the arm tips).
  function setBracket(m, k, cx, cy, w, h, L, R, draw = 1, color) {
    const svg = m[k];
    set(svg, { x: cx - w / 2, y: cy - h / 2 });
    L = Math.min(L, w / 2, h / 2); R = Math.min(R, L);
    const d = [
      `M0 ${L}V${R}A${R} ${R} 0 0 1 ${R} 0H${L}`,
      `M${w - L} 0H${w}V${L}`,
      `M${w} ${h - L}V${h - R}A${R} ${R} 0 0 1 ${w - R} ${h}H${w - L}`,
      `M${L} ${h}H${R}A${R} ${R} 0 0 1 0 ${h - R}V${h - L}`,
    ];
    for (let i = 0; i < 4; i++) {
      const p = m[k + i];
      attr(p, "d", d[i]);
      attr(p, "stroke-dasharray", "1 1");
      attr(p, "stroke-dashoffset", 1 - clamp(draw));
      if (color) attr(p, "stroke", color);
    }
  }

  // ---- Split text into per-letter spans (keys k0..kn).
  function letters(text, k, style = "") {
    return [...text].map((ch, i) => `<span data-k="${k}${i}" style="display:inline-block;${style}">${ch === " " ? "&nbsp;" : ch}</span>`).join("");
  }
  function animLetters(m, k, n, t, t0, stagger, fn) {
    for (let i = 0; i < n; i++) fn(m[k + i], t - t0 - i * stagger, i);
  }

  // ---- Camera shake: decaying noise.
  function shake(t, t0, amp = 14, dur = 0.5) {
    const lt = t - t0;
    if (lt < 0 || lt > dur) return { x: 0, y: 0, r: 0 };
    const d = Math.pow(1 - lt / dur, 2);
    return { x: Math.sin(lt * 83) * amp * d, y: Math.cos(lt * 71) * amp * 0.7 * d, r: Math.sin(lt * 57) * 0.4 * d };
  }

  // ---- Odometer: digits roll like a mechanical counter.
  function odo(k, digits, group = true) {
    let html = "";
    for (let i = digits - 1; i >= 0; i--) {
      html += `<span class="odo" style="display:inline-block;height:1em;overflow:hidden;vertical-align:top;line-height:1em"><span data-k="${k}d${i}" style="display:block">${"0123456789012".split("").map((d) => `<span style="display:block;height:1em">${d}</span>`).join("")}</span></span>`;
      if (group && i % 3 === 0 && i > 0) html += `<span style="display:inline-block">,</span>`;
    }
    return html;
  }
  function setOdo(m, k, digits, value) {
    for (let i = 0; i < digits; i++) {
      const p = Math.pow(10, i);
      const base = Math.floor(value / p);
      const lower = value - base * p;
      const frac = i === 0 ? value - Math.floor(value) : lower > p - 1 ? lower - (p - 1) : 0;
      const pos = (base % 10) + frac;
      const el = m[k + "d" + i], tr = `translateY(${(-pos).toFixed(3)}em)`;
      if (el.__tr !== tr) { el.style.transform = tr; el.__tr = tr; }
    }
  }

  // ---- Leaf particle burst (DOM), deterministic from a seed.
  function leafBurst(k, n, seed, colors = ["#34A862", "#5BD98A", "#BFF0CF", "#2E9E5B"]) {
    const r = A.rng(seed);
    const parts = [];
    let html = `<div data-k="${k}" class="abs" style="left:0;top:0;width:0;height:0">`;
    for (let i = 0; i < n; i++) {
      const a = r() * Math.PI * 2, sp = 260 + r() * 520, sz = 10 + r() * 18, spin = (r() - 0.5) * 900, c = colors[i % colors.length];
      parts.push({ a, sp, sz, spin, delay: r() * 0.06 });
      html += `<i data-k="${k}p${i}" class="abs" style="left:${-sz / 2}px;top:${-sz / 2}px;width:${sz}px;height:${sz}px;border-radius:50% 0 50% 50%;background:${c}"></i>`;
    }
    html += `</div>`;
    return {
      html,
      update(m, t, t0, gravity = 900, life = 1.0) {
        parts.forEach((p, i) => {
          const lt = t - t0 - p.delay;
          const el = m[k + "p" + i];
          if (lt <= 0 || lt > life) { set(el, { o: 0 }); return; }
          const drag = (1 - Math.exp(-3 * lt)) / 3;
          const x = Math.cos(p.a) * p.sp * drag;
          const y = Math.sin(p.a) * p.sp * drag + 0.5 * gravity * lt * lt * 0.35;
          set(el, { x, y, r: p.spin * lt, s: 1 - 0.4 * (lt / life), o: 1 - Math.pow(lt / life, 2) });
        });
      },
    };
  }

  // ---- Phone and scan screen.
  function phone(k, inner, style = "") {
    return `<div data-k="${k}" class="phone" style="${style}"><div class="screen" data-k="${k}Screen">${inner}
      <div class="island"></div>
      <div class="sbar"><span>9:41</span><span style="display:flex;gap:6px;align-items:center"><i style="width:18px;height:11px;background:linear-gradient(90deg,#fff 0 3px,transparent 3px 5px,#fff 5px 8px,transparent 8px 10px,#fff 10px 13px,transparent 13px 15px,#fff 15px);clip-path:polygon(0 100%,100% 0,100% 100%)"></i><i class="bat"></i></span></div>
    </div></div>`;
  }

  // Illustrated camera view: a room, a table and the hero bottle.
  function room(k, w, h, bottleH, bottleX, bottleBottom) {
    const bw = bottleH * (200 / 560);
    const bok = [
      [0.12, 0.18, 0.2, "rgba(191,240,207,.20)"], [0.78, 0.12, 0.16, "rgba(242,201,76,.16)"],
      [0.88, 0.42, 0.24, "rgba(191,240,207,.12)"], [0.3, 0.36, 0.1, "rgba(255,255,255,.12)"],
      [0.6, 0.26, 0.08, "rgba(242,201,76,.14)"], [0.05, 0.48, 0.14, "rgba(91,217,138,.12)"],
    ];
    return `<div class="room" data-k="${k}Room">
      ${bok.map(([x, y, s, c], i) => `<div class="bokeh" data-k="${k}Bok${i}" style="left:${x * w}px;top:${y * h}px;width:${s * w}px;height:${s * w}px;margin:${-s * w / 2}px 0 0 ${-s * w / 2}px;background:radial-gradient(closest-side,${c},${c.replace(/[\d.]+\)$/, "0)")} )"></div>`).join("")}
      <div class="table" style="height:${h - bottleBottom + bottleH * 0.09}px"></div>
      <div class="edge" style="top:${bottleBottom - bottleH * 0.09}px"></div>
      <div class="contact" style="left:${bottleX - bw * 0.75}px;top:${bottleBottom - bw * 0.16}px;width:${bw * 1.5}px;height:${bw * 0.34}px"></div>
      <svg class="hero-bottle" data-k="${k}Bottle" viewBox="0 0 200 560" style="left:${bottleX - bw / 2}px;top:${bottleBottom - bottleH}px;width:${bw}px;height:${bottleH}px">${ART.bottle(k + "B", { vision: true })}</svg>
      <div class="abs" data-k="${k}Sweep" style="left:0;right:0;height:${h * 0.28}px;top:0;background:linear-gradient(180deg,rgba(91,217,138,0),rgba(91,217,138,.28) 80%,rgba(191,240,207,.9) 99%,rgba(191,240,207,0));opacity:0"></div>
    </div>`;
  }

  // The scan tab (ScanTabView) at 1pt = 1px inside a 393x852 screen.
  function scanScreen(k) {
    const camH = 545;
    return `
      <div class="camview" data-k="${k}Cam" style="left:0;top:0;width:393px;height:${camH}px">${room(k, 393, camH, 360, 196, 440)}
        <div class="camshade" style="background:linear-gradient(180deg,rgba(6,18,11,.45) 0%,rgba(6,18,11,.05) 28%,rgba(6,18,11,.15) 62%,rgba(11,26,17,.9) 96%,#0B1A11 100%)"></div>
        <div class="detbox" data-k="${k}Box" style="left:0;top:0;width:10px;height:10px;opacity:0"><span class="lbl" data-k="${k}BoxLbl">Plastic bottle · 58%</span></div>
      </div>
      <div class="navrow" data-k="${k}Nav"><div class="statuspill g-dark"><i class="dot"></i><span data-k="${k}Status">Scanning</span>
        <svg data-k="${k}Ring" viewBox="0 0 20 20" style="width:18px;height:18px;opacity:0"><circle cx="10" cy="10" r="8" fill="none" stroke="rgba(255,255,255,.2)" stroke-width="2.6"/><circle data-k="${k}RingArc" cx="10" cy="10" r="8" fill="none" stroke="#5BD98A" stroke-width="2.6" stroke-linecap="round" pathLength="1" stroke-dasharray="1 1" stroke-dashoffset="1" transform="rotate(-90 10 10)"/></svg></div>
        <div class="navbtns g-dark">${ART.icon("bolt")}${ART.icon("sliders")}</div></div>
      <div data-k="${k}Vf" class="abs" style="left:0;top:0">
        ${bracket(k + "VfB", "rgba(255,255,255,.85)", 3)}
        <div class="vfpill g-dark" data-k="${k}VfPill" style="left:196px;top:392px;translate:-50% 0">Point at an object</div>
      </div>
      <div class="detsec" data-k="${k}Det" style="top:476px">
        <h5>Detected Items <small data-k="${k}DetCount">1 item</small></h5>
        <div class="drow g-dark" data-k="${k}Row0"><div class="t itile" style="background:rgba(255,255,255,.12);color:#fff;font-size:18px">${ART.icon("magnify")}</div>
          <div><b>No items detected</b><small>Pinch to zoom in or adjust lighting</small></div></div>
        <div class="drow g-dark" data-k="${k}Row1" style="position:absolute;left:0;right:0;top:29px;opacity:0"><div class="t itile" style="background:rgba(91,217,138,.2);color:#5BD98A;font-size:20px">${ART.icon("recycle")}</div>
          <div><b>Plastic bottle</b><small>Recyclable</small></div><span class="pct tab" data-k="${k}RowPct" style="color:#F2C94C">58%</span></div>
      </div>
      <div class="tabbar"><div>${ART.icon("house")}Home</div><div class="on">${ART.icon("camera")}Scan</div><div>${ART.icon("photo")}Gallery</div></div>`;
  }

  // Directional (vertical) blur filter shared by the reels.
  function ensureFilters() {
    if (document.getElementById("fx-defs")) return;
    const d = document.createElement("div");
    d.innerHTML = `<svg id="fx-defs" width="0" height="0" style="position:absolute"><defs>
      <filter id="vblurA" x="-5%" y="-50%" width="110%" height="200%"><feGaussianBlur id="vblurA-g" stdDeviation="0 0"/></filter>
      <filter id="vblurB" x="-5%" y="-50%" width="110%" height="200%"><feGaussianBlur id="vblurB-g" stdDeviation="0 0"/></filter>
    </defs></svg>`;
    document.body.appendChild(d.firstChild);
  }

  window.U = { bracket, setBracket, letters, animLetters, shake, odo, setOdo, leafBurst, phone, room, scanScreen, ensureFilters };
})();
