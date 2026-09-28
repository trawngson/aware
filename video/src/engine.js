// Deterministic animation engine: every frame is a pure function of time t
// (seconds). The renderer calls window.seek(t) for each frame and captures it,
// so nothing here may depend on wall-clock time, CSS transitions or randomness.

(function () {
  "use strict";

  const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
  const mix = (a, b, p) => a + (b - a) * p;

  // Cubic-bezier easing, solved with Newton-Raphson and a bisection fallback.
  function bezier(x1, y1, x2, y2) {
    const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
    const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
    const sx = (t) => ((ax * t + bx) * t + cx) * t;
    const sy = (t) => ((ay * t + by) * t + cy) * t;
    const dx = (t) => (3 * ax * t + 2 * bx) * t + cx;
    return (x) => {
      if (x <= 0) return 0;
      if (x >= 1) return 1;
      let t = x;
      for (let i = 0; i < 8; i++) {
        const e = sx(t) - x;
        if (Math.abs(e) < 1e-6) return sy(t);
        const d = dx(t);
        if (Math.abs(d) < 1e-6) break;
        t -= e / d;
      }
      let lo = 0, hi = 1;
      t = x;
      for (let i = 0; i < 40; i++) {
        const v = sx(t);
        if (Math.abs(v - x) < 1e-6) break;
        if (x > v) lo = t; else hi = t;
        t = (lo + hi) / 2;
      }
      return sy(t);
    };
  }

  const back = (s) => (t) => 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2);
  const E = {
    lin: (t) => t,
    inQ: (t) => t * t,
    outQ: (t) => 1 - (1 - t) * (1 - t),
    ioQ: (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
    inC: (t) => t * t * t,
    outC: (t) => 1 - Math.pow(1 - t, 3),
    ioC: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    outQuart: (t) => 1 - Math.pow(1 - t, 4),
    ioQuart: (t) => (t < 0.5 ? 8 * t * t * t * t : 1 - Math.pow(-2 * t + 2, 4) / 2),
    outQuint: (t) => 1 - Math.pow(1 - t, 5),
    ioQuint: (t) => (t < 0.5 ? 16 * Math.pow(t, 5) : 1 - Math.pow(-2 * t + 2, 5) / 2),
    inExpo: (t) => (t <= 0 ? 0 : Math.pow(2, 10 * t - 10)),
    outExpo: (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
    ioExpo: (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2),
    inBack: (t) => 2.70158 * t * t * t - 1.70158 * t * t,
    outBack: back(1.70158),
    outBackS: back(1.1),
    outBackL: back(2.6),
    sine: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
    cam: bezier(0.16, 1, 0.3, 1), // long settle, for camera moves
    snap: bezier(0.7, 0, 0.2, 1), // lands on the beat
    swift: bezier(0.4, 0, 0.2, 1),
    whip: bezier(0.85, 0, 0.15, 1),
    bezier,
  };

  // Damped spring from 0 to 1, t seconds after release. k: stiffness, c: damping.
  function spring(t, k = 170, c = 20, v0 = 0) {
    if (t <= 0) return 0;
    const w0 = Math.sqrt(k), z = c / (2 * Math.sqrt(k)), A = -1;
    if (z < 1) {
      const wd = w0 * Math.sqrt(1 - z * z);
      const B = (v0 + z * w0 * A) / wd;
      return 1 + Math.exp(-z * w0 * t) * (A * Math.cos(wd * t) + B * Math.sin(wd * t));
    }
    return 1 + (A + (v0 + w0 * A) * t) * Math.exp(-w0 * t);
  }

  // Progress 0..1 of a segment starting at t0 lasting d seconds.
  const P = (t, t0, d, ease = E.lin) => ease(clamp((t - t0) / d));
  // Spring progress starting at t0.
  const S = (t, t0, k, c) => spring(t - t0, k, c);
  // Piecewise keyframes: [[time, value], [time, value, ease], ...]
  function K(t, pts) {
    if (t <= pts[0][0]) return pts[0][1];
    for (let i = 1; i < pts.length; i++) {
      const [t1, v1, e] = pts[i];
      if (t <= t1) {
        const [t0, v0] = pts[i - 1];
        const p = (e || E.ioC)((t - t0) / (t1 - t0));
        return mix(v0, v1, p);
      }
    }
    return pts[pts.length - 1][1];
  }

  // Deterministic pseudo-random numbers.
  function rng(seed) {
    let s = seed >>> 0 || 1;
    return () => {
      s ^= s << 13; s >>>= 0;
      s ^= s >> 17;
      s ^= s << 5; s >>>= 0;
      return s / 4294967296;
    };
  }
  const hash = (n) => {
    let x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
    return x - Math.floor(x);
  };

  // Write styles only when they change. Transform order:
  // translate -> rotateX -> rotateY -> rotate -> scale.
  function set(el, p) {
    if (!el) return;
    let tr = "";
    if (p.x !== undefined || p.y !== undefined || p.z !== undefined)
      tr += `translate3d(${(p.x || 0).toFixed(2)}px,${(p.y || 0).toFixed(2)}px,${(p.z || 0).toFixed(2)}px) `;
    if (p.rx) tr += `rotateX(${p.rx.toFixed(3)}deg) `;
    if (p.ry) tr += `rotateY(${p.ry.toFixed(3)}deg) `;
    if (p.r) tr += `rotate(${p.r.toFixed(3)}deg) `;
    if (p.s !== undefined) tr += `scale(${p.s.toFixed(4)}) `;
    if (p.sx !== undefined || p.sy !== undefined) tr += `scale(${(p.sx ?? 1).toFixed(4)},${(p.sy ?? 1).toFixed(4)}) `;
    if (p.skx) tr += `skewX(${p.skx.toFixed(2)}deg) `;
    tr = tr || "none";
    if (tr !== el.__tr) { el.style.transform = tr; el.__tr = tr; }
    if (p.o !== undefined) {
      const o = Math.round(clamp(p.o) * 1000) / 1000;
      if (o !== el.__o) {
        el.style.opacity = o;
        el.style.visibility = o <= 0.001 ? "hidden" : "visible";
        el.__o = o;
      }
    }
    if (p.blur !== undefined) {
      const f = p.blur > 0.05 ? `blur(${p.blur.toFixed(2)}px)` : "none";
      if (f !== el.__f) { el.style.filter = f; el.__f = f; }
    }
    if (p.css) for (const k in p.css) {
      const v = String(p.css[k]);
      const key = "__c_" + k;
      if (el[key] !== v) { el.style.setProperty(k, v); el[key] = v; }
    }
    if (p.text !== undefined && el.__text !== p.text) { el.textContent = p.text; el.__text = p.text; }
  }
  const attr = (el, k, v) => {
    const key = "__a_" + k, s = typeof v === "number" ? v.toFixed(3) : String(v);
    if (el[key] !== s) { el.setAttribute(k, s); el[key] = s; }
  };

  // Build HTML into a parent and return elements keyed by their data-k.
  function build(parent, html) {
    const tpl = document.createElement("template");
    tpl.innerHTML = html.trim();
    const nodes = [...tpl.content.childNodes];
    nodes.forEach((n) => parent.appendChild(n));
    const map = {};
    parent.querySelectorAll("[data-k]").forEach((el) => { map[el.dataset.k] = el; });
    return map;
  }

  // Scenes are active from t0 (inclusive) to t1 (exclusive).
  const scenes = [];
  const globals = [];
  function scene(name, t0, t1, setup) {
    const root = document.createElement("div");
    root.className = "scene " + name;
    document.getElementById("scenes").appendChild(root);
    const s = { name, t0, t1, root, on: false, update: () => {} };
    s.update = setup(root, s) || s.update; // built while visible so layout can be measured
    root.style.display = "none";
    scenes.push(s);
    return s;
  }
  function onFrame(fn) { globals.push(fn); }

  let current = -1;
  function seek(t) {
    current = t;
    for (const s of scenes) {
      const on = t >= s.t0 && t < s.t1;
      if (on !== s.on) { s.root.style.display = on ? "" : "none"; s.on = on; }
      if (on) s.update(t);
    }
    for (const g of globals) g(t);
  }

  const fmt = (n) => Math.round(n).toLocaleString("en-US");

  window.A = { clamp, mix, E, spring, P, S, K, rng, hash, set, attr, build, scene, onFrame, seek, fmt, bezier };
  window.seek = seek;
  window.now = () => current;
})();
