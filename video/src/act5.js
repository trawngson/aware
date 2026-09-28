// ACT 5 · Rewards (0:34–0:44). The bottle becomes leaves, the leaves land on
// Home, the dashboard fans out in space, then the leaderboard.
(window.BUILD = window.BUILD || []).push(() => {
  const { set, attr, P, K, E, clamp, mix, spring, fmt } = A;
  const reveal = window.reveal;
  window.FLASHES = window.FLASHES.concat([[41.6, 0.12, 0.16]]);
  const leaf = (c) => `<svg class="ico" viewBox="0 0 24 24" style="color:${c}">${ART.ICON.leaf}</svg>`;
  const tile = (ico, c, bg) => `<span class="itile" style="background:${bg || c + "22"};color:${c}">${ART.icon(ico)}</span>`;

  A.scene("a5", 34.0, 44.5, (root) => {
    const cards = {
      goal: [580, 0, 360, `<div class="hd">${tile("flag", "#1F7A46")}September Goal<em>70%</em></div>
        <div class="num"><b class="tab" data-k="vGoal">2,000</b>${leaf("#1F7A46")}<span>&nbsp;to go</span></div>
        <div class="progress"><i data-k="goalBar" style="width:70%;transform-origin:0 50%"></i></div>`],
      waste: [0, 0, 175, `<div class="hd" style="color:#1F7A46;font-size:13px">${ART.icon("trash")}Waste Saved</div>
        <div class="num"><b class="tab" data-k="vWaste" style="font-size:27px">6,700</b><span style="font-weight:600;font-size:16px">g</span></div>
        <span class="trend" style="color:#1F7A46;background:rgba(31,122,70,.12)">↑ 12% today</span>`],
      co2: [275, 0, 175, `<div class="hd" style="color:#0E7C86;font-size:13px">${ART.icon("cloud")}CO₂ Saved</div>
        <div class="num"><b class="tab" data-k="vCo2" style="font-size:27px">1,250</b><span style="font-weight:600;font-size:16px">kg</span></div>
        <span class="trend" style="color:#0E7C86;background:rgba(14,124,134,.12)">↓ 9% today</span>`],
      streak: [1160, 0, 330, `<div class="hd">${tile("flame", "#A66A00")}Recycling Streak<em>This Week</em></div>
        <div style="display:flex;align-items:flex-end;gap:6px;margin-top:10px"><b class="tab" data-k="vStreak" style="font:700 40px/1 var(--ui);letter-spacing:-1.4px">3</b><span style="font:400 17px/1 var(--ui);color:rgba(17,41,28,.55);padding-bottom:4px">days</span>
          <span style="margin-left:auto;text-align:right;font:400 11px/1.3 var(--ui);color:rgba(17,41,28,.5)">Best<br><b style="font:600 14px/1 var(--ui);color:#A66A00">18 days</b></span></div>
        <div class="days">${["M", "T", "W", "T", "F", "S", "S"].map((d, i) => `<span><i>${i === 3 ? "" : `<b data-k="day${i}" style="transform-origin:50% 100%"></b>`}</i>${d}</span>`).join("")}</div>`],
      items: [0, 190, 360, `<div class="hd">${tile("scan", "#1F7A46")}Items Scanned<em>This Month</em></div>
        <div style="display:flex;align-items:flex-end;gap:6px;margin-top:10px"><b class="tab" data-k="vItems" style="font:700 40px/1 var(--ui);letter-spacing:-1.4px">47</b><span style="font:400 17px/1 var(--ui);color:rgba(17,41,28,.55);padding-bottom:4px">items</span>
          <span class="trend" style="margin-left:auto;color:#1F7A46;background:rgba(31,122,70,.12)">↑ +12 this week</span></div>
        <div class="segbar" data-k="seg" style="transform-origin:0 50%"><i style="flex:18;background:#1F7A46"></i><i style="flex:14;background:#4FA878"></i><i style="flex:9;background:#8FBFA4"></i><i style="flex:6;background:#C3DBCC"></i></div>
        <div class="legend"><span><i style="background:#1F7A46"></i>Plastic 18</span><span><i style="background:#4FA878"></i>Paper 14</span><span><i style="background:#8FBFA4"></i>Metal 9</span><span><i style="background:#C3DBCC"></i>Glass 6</span></div>`],
      weekly: [580, 200, 360, `<div class="hd">${tile("barsx", "#1F7A46")}Weekly Comparison</div>
        <div class="legend"><span><i style="background:#1F7A46"></i>This week</span><span><i style="background:rgba(17,41,28,.15)"></i>Last week</span></div>
        <div class="wkbars">${[[18, 26], [26, 34], [32, 20], [23, 46], [37, 31], [29, 40], [20, 23]].map(([a, b], i) => `<div><span class="pair"><i data-k="wa${i}" style="height:${a}px;background:rgba(17,41,28,.13);transform-origin:50% 100%"></i><i data-k="wb${i}" style="height:${b}px;background:linear-gradient(#2E9E5B,#1F7A46);transform-origin:50% 100%"></i></span>${"MTWTFSS"[i]}</div>`).join("")}</div>`],
      recent: [1160, 240, 330, `<div class="hd">${tile("clock", "#1F7A46")}Recent Activity<em>Today</em></div>
        ${[["Plastic Bottle", "Recycled · just now", 20, "#1F7A46", "recycle"], ["Cardboard Box", "Recycled · 1h ago", 20, "#A66A00", "tag"], ["Weekly Goal", "Achieved · 3h ago", 100, "#0E7C86", "trophy"]].map(([a, b, p, c, ic], i) => `
          <div data-k="ra${i}" style="display:flex;align-items:center;gap:12px;margin-top:14px">${`<span class="itile" style="width:38px;height:38px;border-radius:13px;font-size:17px;background:${c}22;color:${c}">${ART.icon(ic)}</span>`}
            <div><div style="font:600 15px/1.2 var(--ui)">${a}</div><div style="font:400 12px/1.2 var(--ui);color:rgba(17,41,28,.55)">${b}</div></div>
            <span style="margin-left:auto;font:600 14px/1 var(--ui);color:#1F7A46;display:flex;gap:3px;align-items:center">+${p}${leaf("#1F7A46")}</span></div>`).join("")}`],
      impact: [0, 400, 360, `<div class="hd" style="color:#fff">${tile("globe", "#BFF0CF", "rgba(255,255,255,.18)")}Your Impact<em style="color:rgba(255,255,255,.7)">All Time</em></div>
        <div style="display:flex;align-items:baseline;gap:6px;margin-top:12px"><b class="tab" data-k="vTrees" style="font:700 46px/1 var(--ui);color:#fff">3</b><span style="font:500 19px/1 var(--ui);color:rgba(255,255,255,.8)">trees saved</span></div>
        <div style="margin-top:12px;padding:10px 12px;border-radius:16px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.22);font:400 13px/1 var(--ui);color:rgba(255,255,255,.88);display:flex;justify-content:space-between">1,247 recyclers · 2.4 tons together<b style="color:#fff">#1</b></div>`],
    };
    const order = ["goal", "waste", "co2", "streak", "items", "weekly", "recent", "impact"];
    const Z = 1.5;
    const lb = [["Truong Son", 24120, true], ["Dieu Linh", 20000], ["Ha Chi", 15000], ["Anthony", 9400], ["Max", 8100], ["Minh Khoi", 7650]];

    const m = A.build(root, `
      <div class="abs full" data-k="bg">
        <div class="bg-forest" data-k="forest"></div>
        <div class="bg-forest-blur" data-k="forestB" style="-webkit-mask:linear-gradient(180deg,transparent 24%,#000 46%);mask:linear-gradient(180deg,transparent 24%,#000 46%)"></div>
        <div class="scrim-home"></div>
      </div>
      <div class="abs" style="left:0;top:0;width:1920px;height:1080px;perspective:2400px">
        <div class="abs" data-k="plane" style="left:132px;top:262px;width:1656px;height:680px;transform-style:preserve-3d">
          ${order.map((k) => { const [x, y, w, html] = cards[k]; return `<div class="abs" data-k="w_${k}" style="left:${x}px;top:${y}px"><div class="hcard ${k === "impact" ? "" : "g-card"}" style="position:relative;zoom:${Z};width:${w}px;${k === "impact" ? "background:linear-gradient(180deg,rgba(9,28,17,.55),rgba(9,28,17,.8)),url(assets/img/forest.jpg) center/cover;box-shadow:0 14px 16px rgba(12,38,22,.28);color:#fff" : ""}">${html}</div></div>`; }).join("")}
        </div>
      </div>
      <div class="abs full" data-k="dim" style="background:radial-gradient(120% 100% at 30% 50%,rgba(4,12,7,.94),rgba(5,15,9,.8))"></div>
      <div class="abs g-frost" data-k="hdr" style="left:500px;top:62px;width:920px;height:142px;border-radius:50px;display:flex;align-items:center;gap:24px;padding:0 26px">
        <div class="avatar" style="width:98px;height:98px;background-image:url(assets/img/avatar.png);background-color:#1C3B28;border:3px solid rgba(255,255,255,.7)"></div>
        <div><div style="font:500 25px/1 var(--ui);color:rgba(255,255,255,.85)">Welcome back</div><div style="font:700 54px/1.1 var(--ui);letter-spacing:-.035em;margin-top:6px">Truong Son</div></div>
        <div data-k="pts" style="margin-left:auto;display:flex;align-items:center;gap:10px;font:600 40px/1 var(--ui);padding:16px 24px;border-radius:999px;background:rgba(255,255,255,.2);border:1.5px solid rgba(255,255,255,.32)" class="tab"><span style="display:inline-flex">${U.odo("od", 5)}</span><span style="color:#BFF0CF;display:flex">${leaf("#BFF0CF")}</span></div>
      </div>
      <div class="abs full" data-k="flyers"></div>
      <span class="abs c pill-green" data-k="plus" style="left:560px;top:690px;font-size:54px;padding:18px 32px">+20 ${leaf("#fff")}</span>
      <div class="abs mask" style="right:110px;top:640px;height:150px;text-align:right"><span class="disp nowrap" data-k="t1" style="font-size:140px;color:var(--ink)">Sort it right.</span></div>
      <div class="abs mask" style="right:110px;top:790px;height:150px;text-align:right"><span class="disp nowrap" data-k="t2" style="font-size:140px;color:#1F7A46">Earn leaves.</span></div>
      <div class="abs mask" style="left:106px;top:300px;height:175px"><span class="disp nowrap" data-k="c1" style="font-size:170px">Climb the</span></div>
      <div class="abs mask" style="left:106px;top:470px;height:175px"><span class="disp nowrap" data-k="c2" style="font-size:170px">board.</span></div>
      <div class="abs" data-k="c3" style="left:112px;top:690px;font:500 42px/1 var(--ui);color:#BFF0CF">Monthly leaderboard</div>
      <div class="abs" data-k="lbw" style="left:940px;top:140px">
        <div class="g-card" style="zoom:2;width:430px;border-radius:26px;padding:20px 20px 22px">
          <div class="cardhead" style="font-size:16px">${tile("bars", "#1F7A46")}Recycle Leaderboard<em style="margin-left:auto;font:400 13px/1 var(--ui);font-style:normal;color:rgba(17,41,28,.55)">This Month</em></div>
          <div style="display:grid;gap:12px;margin-top:16px">
            ${lb.map(([n, p, me], i) => `<div class="lbrow ${me ? "me" : ""}" data-k="r${i}" style="${me ? "margin:0 -8px;padding:8px;border-radius:14px;background:rgba(31,122,70,.1);overflow:hidden" : ""}">
              <span class="n" ${me ? 'style="background:#1F7A46;color:#fff"' : ""}>${i + 1}</span>${n}${me ? '<span class="you">You</span>' : ""}
              <span class="p"><span data-k="rp${i}">${fmt(p)}</span>${leaf("#1F7A46")}</span>
              ${me ? '<i data-k="glint" class="abs" style="top:-20px;bottom:-20px;left:0;width:60px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.9),transparent);transform:rotate(20deg)"></i>' : ""}</div>`).join("")}
          </div>
        </div>
      </div>
      <div class="abs c" data-k="badge" style="left:1828px;top:128px;width:150px;height:150px;border-radius:50%;background:radial-gradient(circle at 35% 30%,#FFE08A,#F2C94C 45%,#C8901F);display:grid;place-items:center;font:800 58px/1 var(--display);color:#3B2A05;box-shadow:0 0 0 14px rgba(242,201,76,.25),0 18px 36px rgba(0,0,0,.3)">#1</div>
    `);
    const conf = U.leafBurst("cf", 18, 77, ["#F2C94C", "#FFE08A", "#5BD98A", "#BFF0CF"]);
    Object.assign(m, A.build(root, conf.html));

    // points pill target (measured) and the twenty flying leaves
    const pr = m.pts.getBoundingClientRect(), sr = document.getElementById("stage").getBoundingClientRect();
    const TX = pr.left - sr.left + pr.width * 0.42, TY = pr.top - sr.top + pr.height / 2;
    const rr = A.rng(99);
    const leaves = Array.from({ length: 20 }, (_, i) => {
      const a = -Math.PI / 2 + (rr() - 0.5) * 2.6;
      const R = 180 + rr() * 260;
      return { a, R, t0: 34.16 + i * 0.022, d: 0.8 + rr() * 0.3, spin: (rr() - 0.5) * 720, sz: 30 + rr() * 16, c: ["#34A862", "#5BD98A", "#BFF0CF", "#2E9E5B"][i % 4], ox: (rr() - 0.5) * 360 };
    });
    Object.assign(m, A.build(m.flyers, leaves.map((l, i) => `<i data-k="lf${i}" class="abs" style="left:${-l.sz / 2}px;top:${-l.sz / 2}px;width:${l.sz}px;height:${l.sz}px;border-radius:50% 0 50% 50%;background:${l.c};box-shadow:0 0 16px ${l.c}"></i>`).join("")));
    const SX0 = 560, SY0 = 790;
    const bez = (p0, p1, p2, p3, u) => { const v = 1 - u; return v * v * v * p0 + 3 * v * v * u * p1 + 3 * v * u * u * p2 + u * u * u * p3; };

    return (t) => {
      set(m.bg, { o: P(t, 34.12, 0.45) });
      set(m.forest, { s: 1.05 + 0.02 * P(t, 34, 10), y: -P(t, 34, 10) * 20 });
      set(m.forestB, { s: 1.05 + 0.02 * P(t, 34, 10), y: -P(t, 34, 10) * 20 });

      // header drops in; points roll as each leaf lands
      const hdIn = spring(t - 34.25, 140, 16), hdOut = P(t, 39.8, 0.45, E.inC);
      set(m.hdr, { y: (1 - hdIn) * -240 - hdOut * 260, o: P(t, 34.25, 0.2) });
      let val = 24100, pulse = 0;
      leaves.forEach((l, i) => {
        const u = clamp((t - l.t0) / l.d);
        const e = E.ioC(u);
        const x = bez(SX0, SX0 + Math.cos(l.a) * l.R, TX - 380 + l.ox, TX, e);
        const y = bez(SY0, SY0 + Math.sin(l.a) * l.R, TY + 320, TY, e);
        set(m["lf" + i], { x, y, r: l.spin * u + 45, s: mix(1, 0.45, e), o: u > 0 && u < 1 ? 1 : 0 });
        const arrive = l.t0 + l.d;
        val += E.outC(clamp((t - arrive) / 0.1));
        if (t > arrive) pulse += Math.exp(-(t - arrive) * 14);
      });
      U.setOdo(m, "od", 5, val);
      set(m.pts, { s: 1 + 0.035 * Math.min(pulse, 2.5), css: { "box-shadow": `0 0 ${Math.min(60, pulse * 30)}px rgba(191,240,207,.55)` } });
      set(m.plus, { s: spring(t - 34.15, 300, 13), y: -P(t, 34.5, 0.6, E.outC) * 90, o: clamp((t - 34.15) * 10) * (1 - P(t, 34.7, 0.35)) });

      reveal(m.t1, t, 34.6, 0.55); reveal(m.t2, t, 34.78, 0.55);
      const tOut = P(t, 35.85, 0.35, E.inC);
      set(m.t1.parentNode, { o: 1 - tOut, y: -tOut * 40 }); set(m.t2.parentNode, { o: 1 - tOut, y: -tOut * 40 });

      // dashboard in space
      const drift = P(t, 36.0, 4.5, E.lin);
      const back = P(t, 39.75, 0.6, E.ioC);
      set(m.plane, { rx: mix(12, 6, drift), ry: mix(-16, -8, drift), x: mix(-30, 30, drift), z: -back * 900, o: 1 - back * 0.55 });
      order.forEach((k, i) => {
        const t0 = 36.02 + i * 0.1;
        const s = spring(t - t0, 110, 17);
        set(m["w_" + k], { z: (1 - s) * -1500, y: (1 - s) * 220, rx: (1 - s) * 35, o: clamp((t - t0) * 5) });
      });
      const roll = (k, t0, v, dec = 0) => set(m[k], { text: fmt(v * E.outC(clamp((t - t0) / 0.9))) });
      roll("vGoal", 36.3, 2000); roll("vWaste", 36.4, 6700); roll("vCo2", 36.5, 1250);
      roll("vItems", 36.7, 47); roll("vTrees", 37.0, 3);
      set(m.vStreak, { text: String(Math.round(3 * clamp((t - 36.9) / 0.6))) });
      set(m.goalBar, { sx: E.outC(clamp((t - 36.6) / 1.0)) });
      [0, 1, 2, 4, 5, 6].forEach((d, j) => set(m["day" + d], { sy: spring(t - (37.0 + j * 0.25), 260, 16) }));
      set(m.seg, { sx: E.outC(clamp((t - 36.9) / 0.8)) });
      for (let i = 0; i < 7; i++) {
        set(m["wa" + i], { sy: spring(t - (37.0 + i * 0.07), 180, 15) });
        set(m["wb" + i], { sy: spring(t - (37.1 + i * 0.07), 180, 13) });
      }
      for (let i = 0; i < 3; i++) set(m["ra" + i], { x: (1 - spring(t - (37.1 + i * 0.12), 200, 18)) * 60, o: clamp((t - 37.1 - i * 0.12) * 5) });

      // leaderboard
      set(m.dim, { o: back * 0.9 * (1 - P(t, 43.7, 0.6)) });
      const cIn = spring(t - 40.0, 110, 16), cOut = P(t, 43.55, 0.8, E.inC);
      set(m.lbw, { x: (1 - cIn) * 420, y: (1 - cIn) * 380, r: (1 - cIn) * 10, s: 1 + cOut * 0.5, o: clamp((t - 40.0) * 5) * (1 - cOut) });
      lb.forEach(([, p], i) => {
        const t0 = 40.3 + i * 0.08;
        set(m["r" + i], { x: (1 - spring(t - t0, 200, 18)) * 240, o: clamp((t - t0) * 6) });
        set(m["rp" + i], { text: fmt(p * E.outC(clamp((t - t0) / 0.9))) });
      });
      set(m.glint, { x: mix(-120, 900, P(t, 41.25, 0.55, E.ioC)) });
      const bd = t > 41.6 ? E.outBack(clamp((t - 41.6) / 0.35)) : 0;
      set(m.badge, { s: t > 41.6 ? mix(2.4, 1, bd) : 0, r: mix(-40, -10, bd) + 6 * Math.sin((t - 41.6) * 30) * Math.exp(-(t - 41.6) * 6) * (t > 41.6 ? 1 : 0), o: clamp((t - 41.6) * 8) * (1 - cOut) });
      conf.update(m, t, 41.66, 600, 1.2);
      set(m.cf, { x: 1828, y: 128 });
      reveal(m.c1, t, 40.2, 0.55); reveal(m.c2, t, 40.35, 0.55);
      set(m.c3, { o: P(t, 40.7, 0.4) * (1 - cOut), y: (1 - P(t, 40.7, 0.5, E.outC)) * 20 });
      set(m.c1.parentNode, { o: 1 - cOut, x: -cOut * 200 }); set(m.c2.parentNode, { o: 1 - cOut, x: -cOut * 200 });
    };
  });
});
