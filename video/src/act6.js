// ACT 6 · A second life (0:44–0:54). The Recycling Map, then the Gallery.
(window.BUILD = window.BUILD || []).push(() => {
  const { set, attr, P, K, E, clamp, mix, spring, fmt } = A;
  const reveal = window.reveal;
  const leaf = (c) => `<svg class="ico" viewBox="0 0 24 24" style="color:${c}">${ART.ICON.leaf}</svg>`;
  const PIN = { x: 701, y: 703, r: 70 }; // spiral pin photo centre, shared by both scenes

  // ------------------------------------------------------------------ map
  A.scene("a6a", 43.7, 48.75, (root) => {
    const streets = ["M-20 150C400 128 900 172 1620 116", "M-20 790C500 812 1100 762 1620 796", "M290 -20C320 300 270 600 310 920", "M1270 -20C1240 300 1300 600 1250 920",
      "M-20 470C250 440 480 400 700 360", "M960 330C1180 280 1380 320 1620 260", "M950 640C1200 610 1400 660 1620 610", "M-20 300C220 310 470 280 700 250", "M620 -20C650 200 700 240 730 300", "M880 640C900 760 870 840 900 920"];
    const minor = ["M420 150C440 420 400 620 430 800", "M1100 140C1080 420 1120 560 1100 800", "M310 620C600 600 700 700 880 690", "M1270 460C1400 470 1500 440 1620 450", "M-20 640C120 630 200 650 300 640", "M160 150C180 300 150 420 170 470", "M1400 120C1420 240 1390 400 1410 640", "M560 360C570 480 540 560 560 700", "M980 120C1000 220 960 260 990 330"];
    const LAKE = "M790 250C850 246 876 296 874 362C872 426 892 478 890 536C888 596 866 632 818 628C770 624 748 588 746 532C744 476 726 424 730 360C734 296 748 254 790 250Z";
    const clusters = [[269, 326, 104, 34, 14], [1613, 326, 88, 19, 8], [1248, 365, 77, 12, 5], [1306, 595, 65, 8, 3], [1651, 653, 96, 27, 11], [422, 595, 81, 15, 6], [614, 442, 58, 5, 2]];
    const pins = [["lamp", 787, 307, 100, false], ["turtle", 1152, 768, 100, false], ["spiral", 701, 787, 140, true]];
    const chips = ["All", "Plastic", "Paper", "Glass", "Metal"];
    const m = A.build(root, `
      <div class="abs full" style="background:#E7ECE5"></div>
      <div class="abs" style="left:0;top:0;width:1920px;height:1080px;perspective:1800px">
        <div class="abs" data-k="map" style="left:0;top:0;width:1920px;height:1080px;transform-origin:50% 62%">
          <svg class="abs" viewBox="0 0 1600 900" style="left:-80px;top:-45px;width:2080px;height:1170px">
            <rect x="-100" y="-100" width="1800" height="1100" fill="#E7ECE5"/>
            <g data-k="parks" fill="#D4E5D0"><rect x="120" y="560" width="260" height="170" rx="30"/><rect x="1180" y="120" width="230" height="140" rx="30"/><rect x="1020" y="640" width="200" height="120" rx="26"/><rect x="40" y="40" width="160" height="90" rx="22"/></g>
            <path data-k="lakeRing" d="${LAKE}" fill="#D4E5D0" stroke="#D4E5D0" stroke-width="56" stroke-linejoin="round"/>
            <g fill="none" stroke-linecap="round">
              ${streets.map((d, i) => `<path data-k="sc${i}" d="${d}" stroke="#D5DBD3" stroke-width="24" pathLength="1" stroke-dasharray="1 1"/>`).join("")}
              ${streets.map((d, i) => `<path data-k="sf${i}" d="${d}" stroke="#FAFBF9" stroke-width="16" pathLength="1" stroke-dasharray="1 1"/>`).join("")}
              ${minor.map((d, i) => `<path data-k="sm${i}" d="${d}" stroke="#FAFBF9" stroke-width="8" pathLength="1" stroke-dasharray="1 1"/>`).join("")}
            </g>
            <path data-k="lake" d="${LAKE}" fill="#B9D6E3"/>
            <circle cx="812" cy="520" r="9" fill="#D4E5D0"/>
          </svg>
          <div class="abs c" data-k="me" style="left:868px;top:518px;width:34px;height:34px;border-radius:50%;background:#3E86C9;border:6px solid #fff;box-shadow:0 4px 12px rgba(17,41,28,.3)"></div>
          <div class="abs c" data-k="meR0" style="left:868px;top:518px;width:34px;height:34px;border-radius:50%;background:rgba(62,134,201,.25)"></div>
          <div class="abs c" data-k="meR1" style="left:868px;top:518px;width:34px;height:34px;border-radius:50%;background:rgba(62,134,201,.25)"></div>
          ${clusters.map(([x, y, s, a], i) => `<div class="cluster c tab" data-k="cl${i}" style="left:${x}px;top:${y}px;width:${s}px;height:${s}px;font-size:${Math.round(s * 0.36)}px;box-shadow:0 0 0 ${Math.round(s * 0.14)}px rgba(52,168,98,.2),0 10px 22px rgba(17,41,28,.25)"><span data-k="cn${i}">${a}</span></div>`).join("")}
          ${pins.map(([img, x, y, s, sel]) => `<div class="ppin" data-k="pin_${img}" style="left:${x - s / 2}px;top:${y - s - 14}px;width:${s}px;height:${s + 14}px;transform-origin:50% 100%">
              <div class="ph" style="background-image:url(assets/img/${img}.jpg);${sel ? "border-color:#34A862;box-shadow:0 0 0 12px rgba(52,168,98,.28),0 14px 30px rgba(17,41,28,.35)" : ""}"></div><i class="tip" ${sel ? 'style="border-top-color:#34A862"' : ""}></i></div>`).join("")}
        </div>
      </div>
      <div class="abs full" data-k="topfade" style="background:linear-gradient(180deg,rgba(248,250,247,.85),rgba(248,250,247,0) 22%)"></div>
      <div class="abs" data-k="title" style="left:0;right:0;top:34px;text-align:center;font:650 34px/1 var(--ui);color:var(--ink);letter-spacing:-.02em">Recycling Map</div>
      <div class="abs" data-k="chips" style="left:50%;top:92px;translate:-50% 0;display:flex;gap:14px">
        <i class="abs" data-k="hl" style="left:0;top:0;height:100%;border-radius:999px;background:linear-gradient(180deg,#34A862,#1C7442);box-shadow:0 8px 16px rgba(31,122,70,.3)"></i>
        ${chips.map((c, i) => `<span class="chip" data-k="chip${i}" style="background:${i ? "" : ""}">${c}</span>`).join("")}
      </div>
      <div class="abs g-card" data-k="cap" style="left:80px;top:858px;border-radius:40px;padding:30px 40px">
        <div class="disp nowrap" style="font-size:66px;font-weight:750;color:var(--ink)">See who's recycling near you.</div>
        <div style="display:flex;align-items:center;gap:10px;margin-top:14px;font:600 30px/1 var(--ui);color:#1F7A46">${ART.icon("mappin")}Hoàn Kiếm, Hà Nội</div>
      </div>
      <div class="abs g-card" data-k="sel" style="left:1110px;top:872px;width:740px;border-radius:40px;padding:18px;display:flex;align-items:center;gap:22px;color:var(--ink)">
        <div style="width:124px;height:124px;border-radius:28px;background:url(assets/img/spiral.jpg) center/cover;flex:none"></div>
        <div><div style="font:650 38px/1.1 var(--ui);letter-spacing:-.03em;white-space:nowrap">Bottle flower spiral</div><div style="font:400 28px/1.3 var(--ui);color:rgba(17,41,28,.6);margin-top:6px">Max · 14h</div></div>
        <span class="pill-green" style="margin-left:auto;font-size:30px;padding:14px 20px">+30 ${leaf("#fff")}</span>
      </div>
      <div class="abs c" data-k="ring" style="left:${PIN.x}px;top:${PIN.y}px;width:140px;height:140px;border-radius:50%;border:10px solid #fff;opacity:0"></div>
    `);
    const chipBox = chips.map((_, i) => ({ x: m["chip" + i].offsetLeft, w: m["chip" + i].offsetWidth, h: m["chip" + i].offsetHeight }));

    return (t) => {
      const land = P(t, 43.72, 1.25, E.cam);
      set(m.map, { rx: mix(62, 0, land), s: mix(1.9, 1, land), y: mix(-120, 0, land), o: P(t, 43.72, 0.3) });
      streets.forEach((_, i) => {
        const d = P(t, 43.85 + i * 0.05, 0.7, E.outC);
        attr(m["sc" + i], "stroke-dashoffset", 1 - d); attr(m["sf" + i], "stroke-dashoffset", 1 - d);
      });
      minor.forEach((_, i) => attr(m["sm" + i], "stroke-dashoffset", 1 - P(t, 44.2 + i * 0.04, 0.6, E.outC)));
      set(m.parks, { o: P(t, 44.1, 0.4) });
      const lk = P(t, 44.15, 0.6, E.outBack);
      set(m.lake, { o: P(t, 44.15, 0.2), s: mix(0.6, 1, lk), css: { "transform-origin": "810px 440px", "transform-box": "view-box" } });
      set(m.lakeRing, { o: P(t, 44.25, 0.3) });
      set(m.me, { s: spring(t - 44.6, 300, 15) });
      for (let i = 0; i < 2; i++) {
        const ph = ((t - 44.6 + i * 0.6) % 1.2) / 1.2;
        set(m["meR" + i], { s: 1 + ph * 5, o: t > 44.6 ? (1 - ph) * 0.9 : 0 });
      }
      const filt = P(t, 46.45, 0.35, E.ioC);
      clusters.forEach(([, , s, all, pl], i) => {
        const t0 = 44.75 + i * 0.08;
        const sc = spring(t - t0, 260, 14) * mix(1, 0.72 + 0.28 * Math.sqrt(pl / all), filt);
        set(m["cl" + i], { s: sc, o: clamp((t - t0) * 6) });
        const n = t < 46.45 ? all * E.outC(clamp((t - t0) / 0.7)) : mix(all, pl, filt);
        set(m["cn" + i], { text: String(Math.round(n)) });
      });
      pins.forEach(([img, , , , sel], i) => {
        const t0 = 44.62 + i * 0.14;
        const drop = t > t0 ? 1 - Math.abs(Math.cos((t - t0) * 9)) * Math.exp(-(t - t0) * 6) : 0;
        const y = t > t0 ? -(1 - E.outC(clamp((t - t0) / 0.25))) * 300 : -300;
        const out = sel ? 0 : P(t, 46.5, 0.3, E.inBack);
        const selPulse = sel && t > 46.9 ? 1 + 0.08 * Math.exp(-(t - 46.9) * 5) : 1;
        set(m["pin_" + img], { y, s: (1 - out) * selPulse * (0.85 + 0.15 * drop), o: clamp((t - t0) * 8) * (1 - out) });
      });
      const ui = P(t, 44.55, 0.4);
      set(m.title, { o: ui }); set(m.topfade, { o: ui });
      set(m.chips, { o: ui, y: (1 - P(t, 44.55, 0.6, E.cam)) * -30 });
      const hx = mix(chipBox[0].x, chipBox[1].x, filt), hw = mix(chipBox[0].w, chipBox[1].w, filt);
      set(m.hl, { x: hx, css: { width: hw + "px" } });
      for (let i = 0; i < 5; i++) m["chip" + i].style.color = (i === 0 && filt < 0.5) || (i === 1 && filt >= 0.5) ? "#fff" : "#11291C";
      for (let i = 0; i < 5; i++) m["chip" + i].style.background = "transparent";
      const cp = spring(t - 45.2, 130, 17);
      set(m.cap, { y: (1 - cp) * 260, o: clamp((t - 45.2) * 5) });
      const sl = spring(t - 46.9, 140, 16);
      set(m.sel, { y: (1 - sl) * 260, o: clamp((t - 46.9) * 5) });
      // portal into the Gallery through the spiral pin
      const r = mix(PIN.r, 2400, P(t, 47.95, 0.7, E.ioExpo));
      set(m.ring, { o: t > 47.95 ? 1 - P(t, 48.35, 0.3) : 0, css: { width: `${r * 2 + 20}px`, height: `${r * 2 + 20}px` } });
    };
  });

  // ------------------------------------------------------------------ gallery
  A.scene("a6b", 47.95, 54.45, (root) => {
    const avatar = (bg, txt, s = 60) => `<div class="avatar" style="width:${s}px;height:${s}px;font-size:${s * 0.36}px;${bg};border:2.5px solid rgba(255,255,255,.85)">${txt}</div>`;
    const actions = (likes, likedK, comments, saved, shares) => `<div class="acts">
      <span data-k="${likedK}" style="position:relative"><span data-k="${likedK}Ico" style="display:flex;position:relative">${ART.icon("heartO")}<span data-k="${likedK}Fill" class="abs" style="left:0;top:0;color:#C7433A;display:flex;opacity:0">${ART.icon("heart")}</span></span><span data-k="${likedK}N">${likes}</span></span>
      <span>${ART.icon("bubble")}${comments}</span><span>${ART.icon("bookmark")}${saved}</span><span>${ART.icon("share")}${shares}</span></div>`;
    const posts = [
      ["pA", avatar("background-image:url(assets/img/avatar.png);background-color:#1C3B28", ""), "Truong Son Nguyen", "Just now", "", "I just scanned and sorted: Plastic bottle 🌱♻️", `<div class="img" style="height:330px">${window.heroPhoto("gh", 736, 330, 280)}</div>`, actions("0", "lkA", 0, 0, 0)],
      ["pB", avatar("background:linear-gradient(#3FB3BE,#0E7C86)", "M"), "Max", "14h", "Plastic", "I just followed one of @Anthony's tutorial and ended up with this cute-looking flower spiral, it's so adorable that I think I might keep it on my bedside from now on!", `<div class="img" style="height:430px;background-image:url(assets/img/spiral.jpg)"></div>`, actions("30", "lkB", 2, 289, 27)],
      ["pC", avatar("background:linear-gradient(#34A862,#1C7442)", "DL"), "Dieu Linh Do", "2d", "", "I just recycled my mom's old fabric into this beautiful lamp for my room's decor! I think this is by far my most beautiful project.", `<div class="img" style="height:430px;background-image:url(assets/img/lamp.jpg)"></div>`, actions("2.0K", "lkC", 2, 2, 2)],
      ["pD", avatar("background:linear-gradient(#E0A23A,#B56E12)", "A"), "Anthony", "1d", "Paper", "Yo, I'm so excited to share with you guys what I've been working on for the last few days: it's a DIY little turtle made from used egg carton.", `<div class="img" style="height:430px;background-image:url(assets/img/turtle.jpg)"></div>`, actions("7", "lkD", 1, 0, 0)],
    ];
    const m = A.build(root, `
      <div class="abs full" data-k="bg"><div class="bg-forest"></div><div class="bg-forest-blur" style="-webkit-mask:linear-gradient(180deg,transparent 10%,#000 34%);mask:linear-gradient(180deg,transparent 10%,#000 34%)"></div><div class="scrim-side"></div></div>
      <div class="abs mask" style="left:106px;top:250px;height:170px"><span class="disp nowrap" data-k="g1" style="font-size:160px">Give it a</span></div>
      <div class="abs mask" style="left:106px;top:415px;height:175px"><span class="disp nowrap" data-k="g2" style="font-size:160px">second life.</span></div>
      <div class="abs" data-k="g3" style="left:110px;top:640px;font:300 66px/1.1 var(--display);color:#BFF0CF;letter-spacing:-.03em">Share what you made.</div>
      <div class="abs" data-k="feed" style="left:1060px;top:0;width:780px">
        <div class="abs g-frost" data-k="comp" style="left:0;top:0;width:780px;height:96px;border-radius:34px;display:flex;align-items:center;gap:18px;padding:0 18px">
          ${avatar("background-image:url(assets/img/avatar.png);background-color:#1C3B28", "", 60)}
          <span style="font:400 26px/1 var(--ui);color:rgba(255,255,255,.8)">Share what you made…</span>
          <span class="pill-green" style="margin-left:auto;font-size:24px;padding:14px 24px">Post</span></div>
        ${posts.map(([k, av, name, time, tagTxt, text, img, acts]) => `
          <div class="post g-card" data-k="${k}" style="left:0;top:0;width:780px">
            <div class="ph">${av}<div><b>${name}</b><small>${time}</small></div>${tagTxt ? `<span class="tagpill" style="margin-left:auto;font-size:18px;color:${tagTxt === "Plastic" ? "#1F7A46" : "#3E86C9"};background:${tagTxt === "Plastic" ? "rgba(31,122,70,.12)" : "rgba(62,134,201,.12)"}">${tagTxt}</span>` : ""}</div>
            <p>${text}</p>${img}${acts}</div>`).join("")}
        <div class="abs full" data-k="hearts"></div>
      </div>
    `);
    const hr = A.rng(4);
    const hearts = Array.from({ length: 9 }, (_, i) => ({ dx: (hr() - 0.5) * 120, h: 260 + hr() * 260, t0: 50.98 + i * 0.09, sz: 30 + hr() * 30, w: hr() * 6 }));
    Object.assign(m, A.build(m.hearts, hearts.map((h, i) => `<span class="abs" data-k="ht${i}" style="left:0;top:0;width:${h.sz}px;height:${h.sz}px;color:#C7433A;display:flex">${ART.icon("heart", "", `style="width:100%;height:100%"`)}</span>`).join("")));
    const H = ["pA", "pB", "pC", "pD"].map((k) => m[k].offsetHeight);
    const GAP = 28, TOP0 = 120;
    const heartPos = () => { const a = m.lkB.getBoundingClientRect(), f = m.feed.getBoundingClientRect(); return { x: a.left - f.left + 12, y: a.top - f.top }; };

    return (t) => {
      root.style.clipPath = t < 48.7 ? `circle(${mix(PIN.r, 2400, P(t, 47.95, 0.7, E.ioExpo))}px at ${PIN.x}px ${PIN.y}px)` : "none";
      reveal(m.g1, t, 48.55, 0.55); reveal(m.g2, t, 48.7, 0.55);
      set(m.g3, { o: P(t, 49.05, 0.4), y: (1 - P(t, 49.05, 0.5, E.outC)) * 20 });
      const out = P(t, 53.55, 0.6, E.inC);
      for (const k of ["g1", "g2"]) set(m[k].parentNode, { o: 1 - out, y: -out * 60 });
      set(m.g3, { o: P(t, 49.05, 0.4) * (1 - out) });

      // new post slides in at the top, then the feed scrolls to Max's spiral
      const ins = spring(t - 48.75, 150, 18);
      const scroll = K(t, [[49.75, 0], [50.6, -(H[0] + GAP) + 10, E.ioC], [51.6, -(H[0] + GAP) + 10], [53.9, -(H[0] + H[1] + GAP * 2) - 260, E.ioQ]]);
      let y = TOP0 + scroll;
      set(m.comp, { y, o: P(t, 48.3, 0.3) });
      y += 96 + GAP;
      set(m.pA, { y: y - (1 - ins) * 60, s: mix(0.92, 1, ins), o: clamp((t - 48.75) * 5) });
      y += (H[0] + GAP) * ins;
      set(m.pB, { y }); y += H[1] + GAP;
      set(m.pC, { y }); y += H[2] + GAP;
      set(m.pD, { y });
      set(m.feed, { o: 1 - out * 0.9, y: -out * 120 });

      // like Max's post
      const liked = t >= 50.95;
      set(m.lkBFill, { o: liked ? 1 : 0 });
      set(m.lkBIco, { s: liked ? 1 + 0.5 * Math.exp(-(t - 50.95) * 9) * Math.abs(Math.cos((t - 50.95) * 20)) : 1 });
      set(m.lkBN, { text: liked ? "31" : "30", css: { color: liked ? "#C7433A" : "" } });
      const hp = heartPos();
      hearts.forEach((h, i) => {
        const u = clamp((t - h.t0) / 1.2);
        set(m["ht" + i], { x: hp.x + h.dx * u + Math.sin(u * 8 + h.w) * 16, y: hp.y - h.h * E.outC(u), s: 0.6 + 0.6 * Math.sin(Math.min(u * 4, 1) * Math.PI / 2), o: u > 0 && u < 1 ? 1 - u * u : 0 });
      });
    };
  });
});
