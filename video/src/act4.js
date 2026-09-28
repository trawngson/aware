// ACT 4 · Guidance (0:23–0:34). The results screen in layers, points and CO2e,
// then the recycling steps acted out by the bottle itself.
(window.BUILD = window.BUILD || []).push(() => {
  const { set, attr, P, K, E, clamp, mix, spring } = A;
  const reveal = window.reveal;

  // A "photo" of the bottle, used as the results hero and in the Gallery.
  window.heroPhoto = (k, w, h, bottleH) => {
    const bw = bottleH * 200 / 560;
    return `<div class="hero-photo" data-k="${k}" style="left:0;top:0;width:${w}px;height:${h}px">
      <div class="abs" style="left:-10%;right:-10%;bottom:0;height:${h * 0.3}px;background:linear-gradient(180deg,#7d6d58,#3c3226)"></div>
      <div class="bokeh" style="left:${w * 0.1}px;top:${h * 0.12}px;width:${w * 0.3}px;height:${w * 0.3}px;background:radial-gradient(closest-side,rgba(191,240,207,.22),transparent)"></div>
      <div class="bokeh" style="left:${w * 0.7}px;top:${h * 0.05}px;width:${w * 0.24}px;height:${w * 0.24}px;background:radial-gradient(closest-side,rgba(242,201,76,.18),transparent)"></div>
      <div class="contact" style="left:${w / 2 - bw * 0.8}px;top:${h * 0.7 + bottleH * 0.02 - bw * 0.14}px;width:${bw * 1.6}px;height:${bw * 0.34}px"></div>
      <svg class="abs" viewBox="0 0 200 560" style="left:${w / 2 - bw / 2}px;top:${h * 0.7 - bottleH}px;width:${bw}px;height:${bottleH}px;overflow:visible">${ART.bottle(k + "B")}</svg>
    </div>`;
  };

  const leafIco = (c = "#fff") => `<svg class="ico" viewBox="0 0 24 24" style="color:${c}">${ART.ICON.leaf}</svg>`;
  const tag = (txt, ico, fg, bg, fs) => `<span class="tagpill" style="font-size:${fs}px;color:${fg};background:${bg}">${ico ? ART.icon(ico) : ""}${txt}</span>`;

  // ------------------------------------------------------------------ exploded view
  A.scene("a4a", 23.35, 26.5, (root) => {
    const L = (z, top, h, inner, cls = "g-card") => `<div class="abs ${cls}" data-k="ly${z}" style="left:16px;top:${top}px;width:361px;height:${h}px;border-radius:26px;padding:20px">${inner}</div>`;
    const m = A.build(root, `
      <div class="bg-light"></div>
      <div class="blob" style="left:-200px;top:-260px;width:900px;height:900px;background:radial-gradient(closest-side,rgba(91,217,138,.22),transparent)"></div>
      <div class="blob" style="left:1300px;top:500px;width:900px;height:900px;background:radial-gradient(closest-side,rgba(76,191,208,.16),transparent)"></div>
      <div class="abs" style="left:0;top:0;width:1920px;height:1080px;perspective:3200px">
        <div class="abs" data-k="iso" style="left:${470 - 196}px;top:${600 - 426}px;width:393px;height:852px;transform-style:preserve-3d;transform-origin:50% 50%">
          <div class="abs" data-k="ly0" style="left:0;top:0;width:393px;height:852px;border-radius:55px;background:#EDF1EA;overflow:hidden;box-shadow:0 0 0 10px #101412,-40px 50px 80px rgba(17,41,28,.3)">
            ${window.heroPhoto("xh", 393, 400, 300)}
            <div class="abs" style="left:0;right:0;top:300px;height:110px;background:linear-gradient(180deg,rgba(237,241,234,0),#EDF1EA)"></div>
            ${[250, 416, 622].map((y, i) => `<div class="abs" style="left:16px;top:${y}px;width:361px;height:${[150, 190, 200][i]}px;border-radius:26px;border:2px dashed rgba(17,41,28,.14)"></div>`).join("")}
          </div>
          ${L(1, 250, 150, `<div style="display:flex;justify-content:space-between;align-items:center"><div class="card-title">Plastic bottle</div><span class="pill-green" style="font-size:15px;padding:7px 12px">+20 ${leafIco()}</span></div>
            <div style="display:flex;gap:8px;margin-top:14px">${tag("Plastic", "tag", "#1F7A46", "rgba(31,122,70,.13)", 13)}${tag("Recyclable", "recycle", "#1F7A46", "rgba(31,122,70,.1)", 13)}${tag("92% match", "", "rgba(17,41,28,.7)", "rgba(17,41,28,.06)", 13)}</div>
            <div style="font:400 15px/1.4 var(--ui);color:rgba(17,41,28,.78);margin-top:14px">Plastic bottles are recyclable.</div>`, "g-strong")}
          ${L(2, 416, 190, `<div class="cardhead"><span class="itile" style="background:rgba(31,122,70,.13);color:#1F7A46">${ART.icon("cloud")}</span>Estimated CO₂e avoided</div>
            <div style="display:flex;align-items:baseline;gap:6px;margin-top:12px"><span class="bigval">12</span><span style="font:600 20px/1 var(--ui);color:rgba(17,41,28,.6)">g</span></div>
            <div style="display:grid;gap:7px;margin-top:12px">
              <div class="cmpbar"><span>Bag</span><span class="trk"><i class="fil" style="width:5%"></i></span><em>7 g</em></div>
              <div class="cmpbar me"><span>This item</span><span class="trk"><i class="fil" style="width:9%"></i></span><em>12 g</em></div>
              <div class="cmpbar"><span>Alu can</span><span class="trk"><i class="fil" style="width:100%"></i></span><em>131 g</em></div></div>`)}
          ${L(3, 622, 200, `<div class="cardhead">How to recycle this bottle</div>
            ${["Pour out any liquid left inside.", "Take off the cap. Keep it.", "Squash the bottle flat."].map((s, i) => `<div style="display:flex;gap:10px;align-items:center;margin-top:14px;font:400 14px/1.3 var(--ui);color:rgba(17,41,28,.8)"><span style="width:24px;height:24px;border-radius:50%;background:linear-gradient(#2E9E5B,#1F7A46);color:#fff;display:grid;place-items:center;font:700 12px/1 var(--ui)">${i + 1}</span>${s}</div>`).join("")}`)}
        </div>
      </div>
      <svg class="abs" style="left:0;top:0;width:1920px;height:1080px;overflow:visible;pointer-events:none">
        ${[0, 1, 2, 3].map((i) => `<path data-k="lk${i}" fill="none" stroke="rgba(17,41,28,.35)" stroke-width="2.5"/><circle data-k="lkd${i}" r="8" fill="#1F7A46"/>`).join("")}
      </svg>
      ${[["The photo you took", "It never leaves the phone"], ["What it is", "Name, material and your leaves"], ["What it saves", "CO₂e avoided by recycling it"], ["What to do", "Steps for Hanoi's sorting rules"]].map(([a, b], i) => `
        <div class="abs" data-k="lb${i}" style="left:1210px;top:${760 - i * 196}px">
          <div style="font:700 56px/1.05 var(--ui);letter-spacing:-.035em;color:var(--ink);white-space:nowrap">${a}</div>
          <div style="font:500 32px/1.3 var(--ui);color:#1F7A46;margin-top:8px;white-space:nowrap">${b}</div></div>`).join("")}
    `);
    return (t) => {
      // reveal: a circle wipe out of the check mark in the previous shot
      const r = mix(0, 2400, P(t, 23.35, 0.85, E.ioExpo));
      root.style.clipPath = t < 24.25 ? `circle(${r}px at 1119px 156px)` : "none";

      const iso = 1 - P(t, 25.55, 0.8, E.ioC);
      const zoom = P(t, 25.85, 0.65, E.inC);
      const sc = 1.08 * (1 + zoom * 1.4);
      set(m.iso, { x: mix(0, 400, zoom), y: mix(0, 380, zoom), rx: 52 * iso, r: -30 * iso, s: sc * (1 + 0.02 * Math.sin(t * 1.5)), o: 1 - P(t, 26.2, 0.25) });
      for (let i = 0; i < 4; i++) {
        const sep = spring(t - (24.0 + i * 0.1), 120, 16) * (1 - P(t, 25.5, 0.5, E.ioC));
        set(m["ly" + i], { z: sep * i * 90, x: sep * i * 190, y: sep * i * 30 });
      }
      const sr = document.getElementById("stage").getBoundingClientRect();
      for (let i = 0; i < 4; i++) {
        const t0 = 24.35 + i * 0.13;
        const ln = P(t, t0, 0.45, E.outExpo);
        const vis = P(t, t0, 0.3) * (1 - P(t, 25.45, 0.3));
        set(m["lb" + i], { o: vis, x: (1 - P(t, t0, 0.5, E.cam)) * 60 });
        const r = m["ly" + i].getBoundingClientRect();
        const ax = (i === 0 ? r.left + r.width * 0.62 : r.right - r.width * 0.12) - sr.left, ay = (i === 0 ? r.top + r.height * 0.28 : r.top + r.height * 0.5) - sr.top;
        const bx = 1190, by = 760 - i * 196 + 32;
        const ex = mix(ax, bx, ln), ey = mix(ay, by, ln);
        attr(m["lk" + i], "d", `M${ax.toFixed(1)} ${ay.toFixed(1)}C${(ax + 120).toFixed(1)} ${ay.toFixed(1)} ${(ex - 120).toFixed(1)} ${ey.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`);
        set(m["lk" + i], { o: vis }); set(m["lkd" + i], { o: vis });
        attr(m["lkd" + i], "cx", ax.toFixed(1)); attr(m["lkd" + i], "cy", ay.toFixed(1));
      }
    };
  });

  // ------------------------------------------------------------------ points and CO2e
  A.scene("a4b", 26.05, 30.5, (root) => {
    const m = A.build(root, `
      <div class="bg-light"></div>
      <div class="abs" style="left:0;right:0;top:0;height:420px;background:linear-gradient(180deg,#143424 0%,#244a34 35%,rgba(237,241,234,0) 100%)"></div>
      <div class="blob" style="left:1300px;top:600px;width:900px;height:900px;background:radial-gradient(closest-side,rgba(76,191,208,.14),transparent)"></div>
      <div class="abs g-strong" data-k="c1" style="left:100px;top:150px;width:830px;border-radius:52px;padding:52px">
        <div style="display:flex;align-items:flex-start;justify-content:space-between">
          <div style="font:700 92px/1 var(--ui);letter-spacing:-.05em">Plastic bottle</div>
          <span class="pill-green" data-k="pill" style="font-size:42px;padding:16px 26px;margin-top:6px">+20 ${leafIco()}</span></div>
        <div style="display:flex;gap:14px;margin-top:34px">
          <span data-k="tg0">${tag("Plastic", "tag", "#1F7A46", "rgba(31,122,70,.13)", 32)}</span>
          <span data-k="tg1">${tag("Recyclable", "recycle", "#1F7A46", "rgba(31,122,70,.1)", 32)}</span>
          <span data-k="tg2">${tag("92% match", "", "rgba(17,41,28,.7)", "rgba(17,41,28,.06)", 32)}</span></div>
        <div style="font:400 36px/1.4 var(--ui);color:rgba(17,41,28,.78);margin-top:30px">Plastic bottles are recyclable.</div>
      </div>
      <div class="abs g-card" data-k="fb" style="left:100px;top:655px;width:830px;height:124px;border-radius:40px;padding:0 34px;font:600 36px/1 var(--ui);color:var(--ink)">
        <div class="abs full" data-k="fbA" style="display:flex;align-items:center;gap:16px;padding:0 34px"><span style="margin-right:auto;letter-spacing:-.02em">Was this detection correct?</span>
          <span data-k="yes" style="position:relative;font-size:32px;padding:18px 34px;border-radius:999px;color:#1F7A46;background:rgba(31,122,70,.1);border:1.5px solid rgba(31,122,70,.2)">Yes<i data-k="rip" class="abs c" style="left:50%;top:50%;width:90px;height:90px;border-radius:50%;background:rgba(31,122,70,.25)"></i></span>
          <span style="font-size:32px;padding:18px 34px;border-radius:999px;color:rgba(17,41,28,.7);background:rgba(17,41,28,.06)">No</span></div>
        <div class="abs full" data-k="fbB" style="display:flex;align-items:center;gap:16px;padding:0 34px;opacity:0"><span style="color:#1F7A46;font-size:44px;display:flex">${ART.icon("checkc")}</span>Thanks for the feedback!</div>
      </div>
      <div class="abs g-card" data-k="c2" style="left:990px;top:150px;width:830px;border-radius:52px;padding:52px">
        <div class="cardhead" style="font-size:40px;gap:18px"><span class="itile" style="width:64px;height:64px;border-radius:20px;font-size:32px;background:rgba(31,122,70,.13);color:#1F7A46">${ART.icon("cloud")}</span>Estimated CO₂e avoided</div>
        <div style="display:flex;align-items:baseline;gap:12px;margin-top:26px"><span class="tab" data-k="co2" style="font:700 190px/1 var(--ui);letter-spacing:-.06em">12</span><span style="font:600 64px/1 var(--ui);color:rgba(17,41,28,.6)">g</span>
          <span style="margin-left:auto;font:600 30px/1 var(--ui);color:rgba(17,41,28,.55);background:rgba(17,41,28,.06);padding:14px 22px;border-radius:999px">range 12–15 g</span></div>
        <div style="display:grid;gap:22px;margin-top:40px">
          ${[["Bag", 7, ""], ["This item", 12, "me"], ["Alu can", 131, ""]].map(([n, g, c], i) => `<div class="cmpbar ${c}" style="grid-template-columns:170px 1fr 110px;gap:22px;font-size:${c ? 34 : 32}px"><span>${n}</span><span class="trk" style="height:20px;border-radius:10px"><i class="fil" data-k="bar${i}" style="width:${(g / 131) * 100}%;border-radius:10px"></i></span><em>${g} g</em></div>`).join("")}
        </div>
        <div style="font:500 26px/1.4 var(--ui);color:rgba(17,41,28,.5);margin-top:34px">Factors from the US EPA Waste Reduction Model</div>
      </div>
    `);
    const burst = U.leafBurst("pb", 16, 33);
    Object.assign(m, A.build(root, burst.html));
    return (t) => {
      const e1 = P(t, 26.05, 0.45, E.cam);
      set(m.c1, { s: mix(1.08, 1, e1), o: P(t, 26.05, 0.2) * (1 - P(t, 29.95, 0.4)), blur: (1 - e1) * 6, y: -P(t, 29.95, 0.45, E.inC) * 120 });
      const e2 = spring(t - 26.45, 140, 18);
      set(m.c2, { x: (1 - e2) * 500, o: P(t, 26.45, 0.2) * (1 - P(t, 30.02, 0.4)), y: -P(t, 30.02, 0.45, E.inC) * 120 });
      const e3 = spring(t - 26.75, 140, 18);
      set(m.fb, { y: (1 - e3) * 120 - P(t, 30.08, 0.45, E.inC) * 120, o: P(t, 26.75, 0.2) * (1 - P(t, 30.08, 0.4)) });
      set(m.pill, { s: spring(t - 26.6, 320, 12) });
      burst.update(m, t, 26.66, 500, 1.1);
      set(m.pb, { x: 830, y: 245 });
      for (let i = 0; i < 3; i++) set(m["tg" + i], { s: spring(t - (26.85 + i * 0.125), 330, 16), css: { display: "inline-block" } });
      const n = 12 * E.outC(clamp((t - 27.0) / 0.8));
      set(m.co2, { text: String(Math.round(n)) });
      for (let i = 0; i < 3; i++) set(m["bar" + i], { sx: spring(t - (27.25 + i * 0.13), 110, 13), css: { "transform-origin": "0 50%" } });
      const tap = t - 28.85;
      set(m.rip, { s: tap > 0 ? 0.3 + P(tap, 0, 0.45, E.outC) * 2.4 : 0, o: tap > 0 ? 1 - P(tap, 0, 0.45) : 0 });
      set(m.yes, { s: tap > 0 && tap < 0.2 ? 0.94 : 1 });
      set(m.fbA, { o: 1 - P(t, 29.05, 0.2) });
      set(m.fbB, { o: P(t, 29.12, 0.25), x: (1 - P(t, 29.12, 0.4, E.cam)) * 30 });
    };
  });

  // ------------------------------------------------------------------ how to recycle it
  window.FLASHES = window.FLASHES.concat([[34.14, 0.22, 0.2]]);
  A.scene("a4c", 29.95, 34.62, (root) => {
    const BX = 460, BY = 340; // bottle svg top-left; the bottle is 200x560 px
    const steps = [
      ["Pour it out", "Empty any liquid left inside.", 30.35],
      ["Take the cap off", "Keep it: caps are plastic too.", 31.75],
      ["Squash it flat", "It saves space in the bag.", 32.75],
      ["Give it to a scrap collector", "ve chai, đồng nát", 33.5],
    ];
    const m = A.build(root, `
      <div class="bg-light"></div>
      <div class="blob" style="left:-300px;top:300px;width:1100px;height:1100px;background:radial-gradient(closest-side,rgba(91,217,138,.2),transparent)"></div>
      <div class="abs" data-k="hdr" style="left:110px;top:84px">
        <span class="tagpill" style="font:650 38px/1 var(--ui);padding:16px 28px;color:#1F7A46;background:rgba(31,122,70,.12);border:1.5px solid rgba(31,122,70,.22)">${ART.icon("mappin")}&nbsp;Based on Hanoi's waste-sorting regulations</span>
      </div>
      <div class="abs mask" style="left:108px;top:170px;height:120px"><span class="disp nowrap" data-k="ttl" style="font-size:104px;color:var(--ink);font-weight:750">How to recycle this bottle</span></div>
      <div class="abs c" data-k="shadow" style="left:${BX + 100}px;top:${BY + 562}px;width:300px;height:44px;border-radius:50%;background:radial-gradient(closest-side,rgba(17,41,28,.28),transparent)"></div>
      <div class="abs c" data-k="puddle" style="left:300px;top:902px;width:240px;height:44px;border-radius:50%;background:radial-gradient(closest-side,rgba(76,160,220,.55),rgba(76,160,220,.15) 80%,transparent)"></div>
      <svg class="abs" viewBox="0 0 1920 1080" style="left:0;top:0;width:1920px;height:1080px;overflow:visible">
        <path data-k="stream" fill="none" stroke="#6CB8E8" stroke-opacity=".75" stroke-width="18" stroke-linecap="round"/>
        <path data-k="stream2" fill="none" stroke="#fff" stroke-opacity=".6" stroke-width="5" stroke-linecap="round"/>
        ${Array.from({ length: 7 }, (_, i) => `<circle data-k="drop${i}" r="${6 - (i % 3)}" fill="#6CB8E8"/>`).join("")}
        <g data-k="puffs" stroke="#9FB7A8" stroke-width="6" stroke-linecap="round">
          <path d="M540 600l-18-40"/><path d="M560 590v-50"/><path d="M580 600l18-40"/></g>
      </svg>
      <svg class="abs" data-k="bsvg" viewBox="0 0 200 560" style="left:${BX}px;top:${BY}px;width:200px;height:560px;overflow:visible"><g data-k="tilt">${ART.bottle("sb", { level: 0.58, crinkle: true })}</g></svg>
      <svg class="abs" data-k="cap" viewBox="0 0 200 560" style="left:${BX}px;top:${BY}px;width:200px;height:560px;overflow:visible;opacity:0">
        <g data-k="capg"><rect x="66" y="20" width="68" height="47" rx="7" fill="#D22A3B"/><rect x="66" y="20" width="68" height="7" rx="3.5" fill="#fff" fill-opacity=".3"/>
        ${Array.from({ length: 12 }, (_, i) => `<rect x="${70 + i * 5.3}" y="27" width="1.8" height="40" fill="#000" fill-opacity=".2"/>`).join("")}</g></svg>
      <div class="abs" data-k="list" style="left:1010px;top:330px;width:840px">
        <i class="abs" data-k="track" style="left:39px;top:60px;width:4px;height:450px;border-radius:2px;background:rgba(17,41,28,.1)"></i>
        <i class="abs" data-k="rail" style="left:39px;top:60px;width:4px;height:450px;border-radius:2px;background:#1F7A46;transform-origin:50% 0"></i>
        ${steps.map(([a, b], i) => `
          <div class="abs" data-k="st${i}" style="left:0;top:${i * 150}px;display:flex;gap:28px;align-items:flex-start;width:840px">
            <div data-k="stb${i}" style="flex:none;width:82px;height:82px;border-radius:50%;display:grid;place-items:center;font:700 38px/1 var(--ui);color:#fff;background:linear-gradient(#2E9E5B,#1F7A46);box-shadow:0 8px 18px rgba(31,122,70,.3)"><span data-k="stn${i}">${i + 1}</span><span data-k="stc${i}" class="abs" style="font-size:44px;opacity:0;display:flex">${ART.icon("check")}</span></div>
            <div><div style="font:700 54px/1.1 var(--ui);letter-spacing:-.035em;color:var(--ink);white-space:nowrap">${a}</div>
            <div style="font:400 34px/1.3 var(--ui);color:rgba(17,41,28,.65);margin-top:8px;white-space:nowrap">${b}</div></div></div>`).join("")}
      </div>
      <div class="abs" data-k="foot" style="left:1010px;top:960px;font:500 26px/1.3 var(--ui);color:rgba(17,41,28,.5)">Hanoi People's Committee Decision No. 87, in force from 8 January 2026</div>
    `);

    return (t) => {
      const inn = P(t, 29.95, 0.45);
      set(m.hdr, { o: inn * (1 - P(t, 33.95, 0.3)), y: (1 - P(t, 30.0, 0.6, E.cam)) * -30 });
      reveal(m.ttl, t, 30.05, 0.6);
      set(m.ttl.parentNode, { o: 1 - P(t, 33.95, 0.3) });
      set(m.foot, { o: P(t, 30.6, 0.4) * (1 - P(t, 33.95, 0.3)) });

      // bottle enters
      const bin = spring(t - 30.0, 150, 16);
      // step 1: pour
      const a = K(t, [[30.4, 0], [30.85, -118, E.ioC], [31.42, -118], [31.72, 0, E.outBackS]]);
      attr(m.tilt, "transform", `rotate(${a.toFixed(2)} 100 280)`);
      attr(m.sbLevel, "transform", `rotate(${(-a).toFixed(2)} 100 280)`);
      const lvl = t < 30.6 ? 10.6 : t < 31.5 ? K(t, [[30.6, 10.6], [30.85, 58], [31.42, 150, E.inQ]]) : 999;
      attr(m.sbLiquid, "y", 280 + lvl); attr(m.sbSurface, "y", 280 + lvl - 1.5);
      const pouring = t > 30.84 && t < 31.5;
      const mx = BX + 100 - 229.6 * Math.min(1, Math.abs(a) / 118), my = BY + 280 + 122 * Math.min(1, Math.abs(a) / 118);
      const flow = P(t, 30.84, 0.12) * (1 - P(t, 31.3, 0.2));
      const endY = mix(my, 900, flow);
      attr(m.stream, "d", `M${mx} ${my} Q${mx - 18} ${(my + endY) / 2} ${mx - 26} ${endY}`);
      attr(m.stream2, "d", `M${mx - 3} ${my + 6} Q${mx - 20} ${(my + endY) / 2} ${mx - 27} ${endY}`);
      set(m.stream, { o: pouring ? 1 : 0 }); set(m.stream2, { o: pouring ? 1 : 0 });
      for (let i = 0; i < 7; i++) {
        const ph = ((t - 30.9) * 1.6 + i / 7) % 1;
        attr(m["drop" + i], "cx", mx - 30 + Math.sin(i * 3) * 14);
        attr(m["drop" + i], "cy", mix(my + 20, 900, ph));
        set(m["drop" + i], { o: t > 30.95 && t < 31.55 ? 0.9 : 0 });
      }
      set(m.puddle, { s: P(t, 30.9, 0.6, E.outC), o: P(t, 30.9, 0.2) * (1 - P(t, 32.2, 0.6)) });

      // step 2: unscrew and pop the cap
      const tw = P(t, 31.82, 0.42);
      attr(m.sbCapRidges, "x", (40 - ((t - 31.82) * 90) % 5.3 * (tw > 0 && tw < 1 ? 1 : 0)).toFixed(2));
      attr(m.sbCap, "transform", `translate(0 ${(-tw * 12 - Math.abs(Math.sin(tw * 9)) * 2).toFixed(2)})`);
      set(m.sbCap, { o: t < 32.24 ? 1 : 0 });
      const fly = P(t, 32.24, 0.4, E.lin);
      const bounce = t > 32.64 ? Math.abs(Math.sin((t - 32.64) * 16)) * 26 * Math.exp(-(t - 32.64) * 9) : 0;
      const cxp = mix(0, 205, fly), cyp = -12 + (493 + 12) * fly * fly - 95 * Math.sin(fly * Math.PI) * (1 - fly * 0.2) - bounce;
      attr(m.capg, "transform", `translate(${cxp.toFixed(1)} ${cyp.toFixed(1)}) rotate(${(fly * 540).toFixed(1)} 100 43)`);
      set(m.cap, { o: t >= 32.24 ? 1 - P(t, 33.95, 0.3) : 0 });

      // step 3: squash with anticipation and settle
      let sy = 1, sx = 1;
      if (t > 32.8) {
        const ant = P(t, 32.8, 0.15, E.outQ);
        sy = mix(1, 1.06, ant); sx = mix(1, 0.97, ant);
        const sq = P(t, 32.95, 0.16, E.outExpo);
        sy = mix(sy, 0.4, sq); sx = mix(sx, 1.32, sq);
        const st = spring(t - 33.11, 260, 9);
        sy = mix(sy, 0.46, st); sx = mix(sx, 1.26, st);
      }
      // the bottle pops into leaves at 34.14
      const popS = t > 34.08 ? (t < 34.16 ? 1 + P(t, 34.08, 0.08) * 0.18 : Math.max(0, 1.18 - P(t, 34.16, 0.07) * 1.18)) : 1;
      attr(m.sbSquash, "transform", `translate(100 540) scale(${(sx * popS).toFixed(4)} ${(sy * popS).toFixed(4)}) translate(-100 -540)`);
      set(m.sbCrinkle, { o: P(t, 32.98, 0.12) });
      set(m.bsvg, { y: (1 - bin) * 300, o: P(t, 29.95, 0.25) });
      set(m.shadow, { sx: sx * popS * (1 + 0.1 * Math.abs(Math.sin(a * Math.PI / 180))), o: P(t, 29.95, 0.4) * (popS > 0 ? 1 : 0) });
      const pf = P(t, 32.98, 0.35, E.outC);
      set(m.puffs, { y: -pf * 60 + (1 - sy) * 250, o: pf > 0 ? 1 - pf : 0 });

      // steps list
      let active = -1;
      steps.forEach((s, i) => { if (t >= s[2]) active = i; });
      steps.forEach(([, , t0], i) => {
        const e = P(t, t0, 0.55, E.cam);
        const on = i === active;
        set(m["st" + i], { x: (1 - e) * 120, o: P(t, t0, 0.25) * (on ? 1 : 0.42) * (1 - P(t, 33.95, 0.3)) });
        set(m["stb" + i], { s: on ? 1 + 0.12 * Math.exp(-(t - t0) * 8) : 0.86 });
        set(m["stn" + i], { o: i < active ? 0 : 1 });
        set(m["stc" + i], { o: i < active ? 1 : 0 });
      });
      set(m.track, { o: P(t, 30.35, 0.3) * (1 - P(t, 33.95, 0.3)) });
      set(m.rail, { sy: K(t, [[30.35, 0], [31.75, 0.33], [32.75, 0.66], [33.5, 1]]) , o: 1 - P(t, 33.95, 0.3) });
    };
  });
});
