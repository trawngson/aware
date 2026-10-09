/* Exercise the offline v3 viewer without a browser connection.
 * DOM, WebGL and audio are test doubles: this does not test GPU rendering or
 * audible playback. CAD meshes, application handlers and transforms are real.
 * Usage: node cad/verify_viewer_v3.cjs [v3]
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');

class Element {
  constructor() {
    this.listeners = new Map(); this.style = {}; this.dataset = {};
    this.classList = {toggle() {}}; this.children = [];
    this.value = ''; this.checked = false; this.hidden = false;
    this.disabled = false; this.textContent = ''; this.innerHTML = '';
  }
  addEventListener(event, fn) { this.listeners.set(event, fn); }
  appendChild(child) { this.children.push(child); }
  setPointerCapture() {}
  async fire(event) { await this.listeners.get(event)?.({preventDefault() {}}); }
}
class AudioParam {
  setValueAtTime() {} linearRampToValueAtTime() {}
  exponentialRampToValueAtTime() {} setTargetAtTime() {}
}
class AudioNode {
  constructor(context, kind) {
    this.context = context; this.kind = kind; this.gain = new AudioParam();
    this.frequency = new AudioParam(); this.started = false; this.ended = false;
    this.endTime = Infinity;
  }
  connect() {}
  start() { this.started = true; this.context.started.push(this); }
  stop(time = this.context.currentTime) {
    this.endTime = time;
    if (time <= this.context.currentTime && !this.ended) {
      this.ended = true; this.onended?.();
    }
  }
}

async function verify(folder) {
  const html = fs.readFileSync(path.join(folder, 'viewer.html'), 'utf8');
  const dim = JSON.parse(fs.readFileSync(path.join(folder, 'dimensions.json'), 'utf8'));
  const validation = JSON.parse(fs.readFileSync(path.join(folder, 'validation.json'), 'utf8'));
  assert.equal(dim.revision, 'v3');
  assert(!html.includes('__MESH_DATA__') && !html.includes('__DIMENSIONS__'));
  const scripts = [...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)];
  const source = scripts.find(s => !s[1].includes('application/json'))[2];
  new vm.Script(source, {filename: 'viewer.html'});

  const elements = new Map();
  for (const id of [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1])) {
    assert(!elements.has('#' + id), `Duplicate DOM id: ${id}`);
    elements.set('#' + id, new Element());
  }
  elements.set('.stage', new Element());
  for (const script of scripts.filter(s => s[1].includes('application/json'))) {
    elements.get('#' + script[1].match(/id="([^"]+)"/)[1]).textContent = script[2];
  }
  for (const id of ['sound', 'shell', 'funnel', 'sensors']) elements.get('#' + id).checked = true;
  elements.get('#route').value = '0'; elements.get('#explode').value = '0';
  const views = ['assembled', 'cutaway', 'internals', 'exploded', 'plan', 'mechanism'];
  const viewButtons = views.map(view => {
    const button = new Element(); button.dataset.view = view; return button;
  });
  const view = name => viewButtons[views.indexOf(name)].fire('click');

  let draws = 0, matrixChecks = 0, screenDraws = 0, textureUploads = 0;
  const screenCanvasCommands = [];
  const context2d = {
    fillRect(x, y, width, height) {
      assert([x, y, width, height].every(Number.isFinite));
      screenCanvasCommands.push({type: 'rect', x, y, width, height, color: this.fillStyle});
    },
    fillText(text, x, y, maxWidth) {
      assert.equal(typeof text, 'string'); assert([x, y, maxWidth].every(Number.isFinite));
      screenCanvasCommands.push({type: 'text', text, x, y, font: this.font});
    },
  };
  let currentProgram = null, boundBuffer = null, depthWrite = true, currentCut = [0, 0, 0];
  const buffers = new Map(), uniformMatrices = new Map(), scalarUniforms = new Map();
  const frameDraws = [], enabled = new Set();
  const constants = ['VERTEX_SHADER', 'FRAGMENT_SHADER', 'COMPILE_STATUS', 'LINK_STATUS',
    'ARRAY_BUFFER', 'STATIC_DRAW', 'DEPTH_TEST', 'SRC_ALPHA', 'ONE_MINUS_SRC_ALPHA',
    'TRIANGLES', 'FLOAT', 'BLEND', 'COLOR_BUFFER_BIT', 'DEPTH_BUFFER_BIT', 'LINE_LOOP',
    'TEXTURE_2D', 'TEXTURE0', 'TEXTURE_MIN_FILTER', 'TEXTURE_MAG_FILTER', 'TEXTURE_WRAP_S',
    'TEXTURE_WRAP_T', 'LINEAR', 'CLAMP_TO_EDGE', 'RGBA', 'UNSIGNED_BYTE', 'UNPACK_FLIP_Y_WEBGL'];
  const gl = Object.fromEntries(constants.map((name, i) => [name, i + 1]));
  for (const name of ['shaderSource', 'compileShader', 'attachShader', 'linkProgram',
    'enableVertexAttribArray', 'disableVertexAttribArray', 'blendFunc',
    'vertexAttribPointer', 'uniform1i', 'viewport', 'clearColor',
    'bindTexture', 'activeTexture', 'texParameteri', 'pixelStorei']) gl[name] = () => {};
  for (const name of ['createShader', 'createProgram', 'createBuffer', 'createTexture']) gl[name] = () => ({});
  gl.useProgram = program => { currentProgram = program; };
  gl.enable = capability => enabled.add(capability);
  gl.disable = capability => enabled.delete(capability);
  gl.depthMask = value => { depthWrite = value; };
  gl.uniform1f = (location, value) => {
    assert(Number.isFinite(value));
    if (!scalarUniforms.has(currentProgram)) scalarUniforms.set(currentProgram, {});
    scalarUniforms.get(currentProgram)[location] = value;
  };
  gl.bindBuffer = (_target, buffer) => { boundBuffer = buffer; };
  gl.clear = () => { frameDraws.length = 0; };
  gl.texImage2D = (_target, _level, _internal, _format, _type, textureCanvas) => {
    assert.equal(textureCanvas.width, 1024); assert.equal(textureCanvas.height, 512);
    textureUploads++;
  };
  gl.getShaderParameter = gl.getProgramParameter = () => true;
  gl.getAttribLocation = (_program, name) => name === 'a_pos' ? 0 : 1;
  gl.getUniformLocation = (_program, name) => name;
  gl.bufferData = (_target, values) => {
    assert(values.length > 0 && (values.length % 6 === 0 || values.length % 5 === 0));
    assert(values.every(Number.isFinite), 'Mesh buffer has non-finite vertices');
    buffers.set(boundBuffer, values);
  };
  gl.uniformMatrix4fv = (location, transpose, values) => {
    assert.equal(transpose, false); assert.equal(values.length, 16);
    assert(values.every(Number.isFinite), 'Non-finite animation/camera transform');
    if (!uniformMatrices.has(currentProgram)) uniformMatrices.set(currentProgram, {});
    uniformMatrices.get(currentProgram)[location] = values;
    matrixChecks++;
  };
  gl.uniform3fv = (location, values) => {
    assert(values.length === 3 && values.every(Number.isFinite));
    if (location === 'u_cut') currentCut = [...values];
  };
  gl.drawArrays = (primitive, first, count) => {
    assert.equal(first, 0); assert(Number.isInteger(count) && count > 0);
    if (primitive === gl.TRIANGLES) assert.equal(count % 3, 0);
    const screen = currentProgram === evaluate('screenProgram');
    if (screen) { assert.equal(count, 6); screenDraws++; }
    frameDraws.push({screen, primitive, count, buffer: boundBuffer, vertices: buffers.get(boundBuffer),
      depthWrite, blending: enabled.has(gl.BLEND),
      opacity: screen ? 1 : scalarUniforms.get(currentProgram)?.u_opacity,
      cut: screen ? [0, 0, 0] : currentCut, ...uniformMatrices.get(currentProgram)});
    draws++;
  };
  const canvas = elements.get('#canvas');
  canvas.clientWidth = 1200; canvas.clientHeight = 850;
  canvas.getContext = type => { assert.equal(type, 'webgl'); return gl; };

  const audioContexts = [];
  class AudioContext {
    constructor() {
      this.state = 'suspended'; this.currentTime = 0; this.sampleRate = 48000;
      this.destination = {}; this.started = []; audioContexts.push(this);
    }
    async resume() { this.state = 'running'; }
    async suspend() { this.state = 'suspended'; }
    createGain() { return new AudioNode(this, 'gain'); }
    createOscillator() { return new AudioNode(this, 'tone'); }
    createBufferSource() { return new AudioNode(this, 'movement'); }
    createBiquadFilter() { return new AudioNode(this, 'filter'); }
    createBuffer(_channels, size) { return {getChannelData: () => new Float32Array(size)}; }
    advance(dt) {
      if (this.state !== 'running') return;
      this.currentTime += dt;
      for (const node of this.started) if (!node.ended && node.endTime <= this.currentTime) {
        node.ended = true; node.onended?.();
      }
    }
  }
  let nextFrame, now = 0;
  const context = vm.createContext({
    document: {
      querySelector(selector) { assert(elements.has(selector), `Missing DOM node: ${selector}`); return elements.get(selector); },
      querySelectorAll(selector) { assert.equal(selector, '[data-view]'); return viewButtons; },
      createElement(tag) {
        const element = new Element();
        if (tag === 'canvas') element.getContext = type => { assert.equal(type, '2d'); return context2d; };
        return element;
      },
    },
    window: {AudioContext}, devicePixelRatio: 1,
    requestAnimationFrame(fn) { nextFrame = fn; },
  });
  vm.runInContext(source, context, {filename: 'viewer.html'});
  const evaluate = code => vm.runInContext(code, context);
  function frames(count) {
    for (let i = 0; i < count; i++) {
      now += 1000 / 60; audioContexts.forEach(audio => audio.advance(1 / 60));
      const fn = nextFrame; nextFrame = null; assert(fn); fn(now);
    }
  }
  const click = id => elements.get('#' + id).fire('click');
  const title = () => elements.get('#demo-title').textContent;
  const state = () => JSON.parse(evaluate('JSON.stringify(player)'));
  const screenState = () => JSON.parse(evaluate('JSON.stringify(screenState(player.time,player.target,player.paused))'));
  const lastScreenText = () => screenCanvasCommands.filter(c => c.type === 'text').slice(-4).map(c => c.text);
  const meshCount = evaluate('meshes.length');
  const cutBuffers = new Set(evaluate('meshes.filter(m=>cutGroups.includes(m.group)).map(m=>m.buffer)'));

  function assertCut(on) {
    // Only shell, funnel and sensor pods open up, and always on the camera side.
    const theta = evaluate('theta');
    assert(frameDraws.some(draw => cutBuffers.has(draw.buffer)) || !on);
    for (const draw of frameDraws.filter(d => !d.screen)) {
      const expected = on && cutBuffers.has(draw.buffer);
      assert.equal(draw.cut[2], expected ? 1 : 0);
      if (expected) {
        assert(Math.abs(draw.cut[0] - Math.cos(theta)) < 1e-9);
        assert(Math.abs(draw.cut[1] - Math.sin(theta)) < 1e-9);
      }
    }
  }
  const transform = (matrix, p) => [0, 1, 2, 3].map(row =>
    matrix[row] * p[0] + matrix[4 + row] * p[1] + matrix[8 + row] * p[2] + matrix[12 + row] * p[3]);
  function screenVisibility() {
    // Project the actual draw buffers and test depth at points across the screen.
    // Triangles removed by the cutaway are skipped, as the fragment shader would.
    const project = (draw, world) => {
      const clip = transform(draw.u_mvp, world);
      return clip.slice(0, 3).map(v => v / clip[3]);
    };
    const face = frameDraws.find(draw => draw.screen); assert(face);
    const triangles = [];
    for (const draw of frameDraws) {
      if (draw.screen || draw.primitive !== gl.TRIANGLES || (draw.blending && draw.opacity < 1)) continue;
      for (let i = 0; i < draw.count; i += 3) {
        const world = [0, 1, 2].map(j => {
          const offset = (i + j) * 6;
          return transform(draw.u_model, [...draw.vertices.slice(offset, offset + 3), 1]);
        });
        if (draw.cut[2] > .5 && world.every(p => p[0] * draw.cut[0] + p[1] * draw.cut[1] > 0)) continue;
        triangles.push(world.map(p => project(draw, p)));
      }
    }
    const corner = i => [...face.vertices.slice(i * 5, i * 5 + 3)];
    const bottomLeft = corner(0), bottomRight = corner(1), topLeft = corner(5);
    let visible = 0, samples = 0;
    for (let row = 1; row <= 8; row++) for (let column = 1; column <= 8; column++) {
      const u = column / 9, v = row / 9;
      const local = bottomLeft.map((value, axis) =>
        value + u * (bottomRight[axis] - value) + v * (topLeft[axis] - value));
      const point = project(face, transform(face.u_model, [...local, 1]));
      assert(Math.abs(point[0]) < 1 && Math.abs(point[1]) < 1, 'Screen is inside the viewport');
      const blocked = triangles.some(([a, b, c]) => {
        const determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1]);
        if (Math.abs(determinant) < 1e-12) return false;
        const wa = ((b[1] - c[1]) * (point[0] - c[0]) + (c[0] - b[0]) * (point[1] - c[1])) / determinant;
        const wb = ((c[1] - a[1]) * (point[0] - c[0]) + (a[0] - c[0]) * (point[1] - c[1])) / determinant;
        const wc = 1 - wa - wb;
        return wa >= 0 && wb >= 0 && wc >= 0 && wa * a[2] + wb * b[2] + wc * c[2] < point[2] - 1e-6;
      });
      samples++; if (!blocked) visible++;
    }
    return {visible, samples, ratio: visible / samples};
  }

  // Bottle geometry against the CAD funnel: a horizontal cylinder, axis across the slope.
  const bottleRadius = dim.demo_bottle_diameter_mm / 2000, halfLength = dim.demo_bottle_height_mm / 2000;
  const mouthR = dim.funnel_mouth_diameter_mm / 2000, throatR = dim.throat_diameter_mm / 2000;
  const rimZ = dim.rim_height_mm / 1000, plateTop = dim.plate_level_top_height_mm / 1000;
  const funnelSlope = Math.tan(dim.funnel_slope_degrees * Math.PI / 180);
  const lipEdgeZ = dim.throat_lip_bottom_height_mm / 1000, skirtEdgeZ = dim.skirt_bottom_height_mm / 1000;
  const bottleCenter = t => JSON.parse(evaluate(
    `JSON.stringify(vector(bottleModel(${t},demoPose(${t})),[0,0,dim.demo_bottle_height_mm/2000]))`));
  function throwClearance() {
    let minimum = Infinity;
    for (let step = 0; step <= 70; step++) {
      const center = bottleCenter(step / 100), reach = Math.hypot(center[0], center[1]);
      const inner = Math.max(0, reach - bottleRadius), outer = Math.hypot(reach, halfLength) + bottleRadius;
      // Highest part of rim, funnel or plate anywhere under the bottle.
      let surface = -Infinity;
      if (inner < dim.body_diameter_mm / 2000) surface = outer >= mouthR ? rimZ
        : outer > throatR ? rimZ - (mouthR - outer) * funnelSlope : plateTop;
      minimum = Math.min(minimum, center[2] - bottleRadius - surface);
    }
    return minimum;
  }
  function exitClearance(edgeZ) {
    let minimum = Infinity;
    for (let step = 0; step <= 110; step++) {
      const center = bottleCenter(4.9 + step / 100), reach = Math.hypot(center[0], center[1]);
      for (let along = -halfLength; along <= halfLength + 1e-9; along += halfLength / 8) {
        minimum = Math.min(minimum, Math.hypot(Math.hypot(reach, along) - throatR, center[2] - edgeZ) - bottleRadius);
      }
    }
    return minimum;
  }

  assert.equal(elements.get('#part').children.length, meshCount);
  assert.equal(validation.roundtrip_solid_count, meshCount);
  assert.deepEqual(dim.category_labels, ['', '', '', '']);
  frames(1);
  assertCut(false);
  assert.equal(screenDraws, 0, 'The physical screen is blank outside the demo');
  const start = bottleCenter(0);
  assert(start[1] < -dim.body_diameter_mm / 2000 && start[2] > rimZ, 'Bottle starts in front of and above the rim');
  const thrown = throwClearance();
  // Viewer matrices are single precision, hence the micrometre tolerance.
  assert(thrown > -1e-6, 'Thrown bottle must clear the rim and funnel wall');
  assert(Math.abs(bottleCenter(.7)[2] - bottleRadius - plateTop) < 1e-6, 'Bottle comes to rest on the plate');

  await click('play'); frames(20); assert.equal(title(), 'Throw it in');
  assert.equal(elements.get('#cutaway').checked, true); assertCut(true);
  assert.deepEqual(lastScreenText(), ['READY', 'DROP', 'ITEM IN', 'ONE AT A TIME']);
  frames(50); assert.equal(title(), 'Scanning…');
  assert.equal(screenState().phase, 'scanning'); assert(lastScreenText().includes('SCANNING'));
  frames(85); assert.equal(title(), 'Water bottle detected');
  assert.deepEqual(lastScreenText(), ['DETECTED', 'WATER', 'BOTTLE', 'TO SUB-BIN 4']);
  const visibility = screenVisibility();
  assert(visibility.ratio >= .95, 'The demo screen must not be hidden');
  await click('pause'); const pauseTime = state().time; frames(90);
  assert.equal(state().time, pauseTime); assert.equal(audioContexts[0].state, 'suspended');
  assert.equal(lastScreenText()[0], 'PAUSED');
  assertCut(true);
  const pausedUploads = textureUploads; frames(10);
  assert.equal(textureUploads, pausedUploads, 'Paused screen progress must freeze');
  evaluate('theta=1.2'); frames(1); assertCut(true); evaluate('theta=-.9');
  await click('pause'); frames(80); assert.equal(title(), 'Tipping into the bin');
  assert.equal(screenState().phase, 'delivery'); assert(lastScreenText().includes('SUB-BIN 4'));
  frames(210); assert.equal(title(), 'Returning to level');
  assert.equal(screenState().phase, 'return');
  frames(110); assert.equal(title(), 'Ready for the next item');
  assert.deepEqual(lastScreenText(), ['READY', 'THANK YOU', 'READY', 'NEXT ITEM']);
  assert.equal(state().time, 9); assert.equal(state().running, false);
  assert.equal(evaluate('demoPose(player.time).tilt'), 0);
  assert.equal(elements.get('#progress').style.width, '100%');
  assert.equal(audioContexts.length, 1, 'Replay must reuse one audio context');
  assert.equal(audioContexts[0].started.filter(n => n.kind === 'tone').length, 6);
  assert.equal(audioContexts[0].started.filter(n => n.kind === 'movement').length, 2);

  // Final tilt matrices agree with CAD exports and descend into the right sector.
  let exit = Infinity, underSkirt = Infinity;
  for (let bin = 1; bin <= 4; bin++) {
    const actual = JSON.parse(evaluate(`JSON.stringify(tiltAngles(1, ${bin}).map(v=>v*180/Math.PI))`));
    const cad = validation.tilt_pose_checks.find(p => p.destination === bin && p.fraction === 1);
    assert(Math.abs(actual[0] - cad.roll_degrees) < .0001);
    assert(Math.abs(actual[1] - cad.pitch_degrees) < .0001);
    const direction = (45 + (bin - 1) * 90) * Math.PI / 180;
    const normal = JSON.parse(evaluate(`JSON.stringify((()=>{const [a,b]=tiltAngles(1,${bin});return vector(mul(ry(b),rx(a)),[0,0,1])})())`));
    assert(normal[0] * Math.cos(direction) > 0 && normal[1] * Math.sin(direction) > 0);
    evaluate(`player.target=${bin}`);
    const center = bottleCenter(6.9);
    assert(center[0] * Math.cos(direction) > 0 && center[1] * Math.sin(direction) > 0);
    assert(Math.abs(center[2] - dim.demo_landing_height_mm / 1000) < .000001);
    assert(Math.hypot(center[0], center[1]) < .24, 'Bottle stays within liner perimeter');
    exit = Math.min(exit, exitClearance(lipEdgeZ));
    underSkirt = Math.min(underSkirt, exitClearance(skirtEdgeZ));
  }
  assert(exit > .005, 'Sliding bottle must pass under the throat lip');
  if (dim.skirt_strip_count) assert(underSkirt > 0, 'Demo bottle should pass without bending the skirt');

  await click('reset'); assert.equal(state().active, false);
  const beforeResetFrames = screenDraws; frames(5);
  assert.equal(screenDraws, beforeResetFrames, 'Reset blanks the physical display');
  assertCut(false);
  assert.equal(elements.get('#cutaway').checked, false);
  assert.equal(evaluate('activeSounds.size'), 0); assert.equal(audioContexts[0].state, 'suspended');
  elements.get('#route').value = '2'; await click('play');
  assert.equal(state().target, 2); frames(148);
  assert.deepEqual(lastScreenText(), ['DETECTED', 'WATER', 'BOTTLE', 'TO SUB-BIN 2']);
  assert(screenVisibility().ratio >= .95);
  assert(evaluate('activeSounds.size') > 0, 'Detection chime should still be scheduled');
  await click('reset'); assert.equal(evaluate('activeSounds.size'), 0);
  assert(audioContexts[0].started.every(n => n.ended), 'Reset must cancel pending audio');

  elements.get('#sound').checked = false; await elements.get('#sound').fire('change');
  const beforeMuted = audioContexts[0].started.length;
  await click('play'); frames(550);
  assert.equal(state().time, 9); assert.equal(audioContexts[0].started.length, beforeMuted);
  await view('mechanism'); frames(1);
  assert.equal(state().active, false); assert.equal(evaluate('mode'), 'mechanism');
  assert(!frameDraws.some(draw => cutBuffers.has(draw.buffer)), 'Joint detail hides shell, funnel and pods');
  await view('cutaway'); frames(1); assertCut(true);
  evaluate('theta=2.1'); frames(1); assertCut(true);
  await view('plan'); frames(1); assert.equal(evaluate('isPlan'), true); assertCut(false);
  await view('assembled'); frames(1); assertCut(false);
  return {
    status: 'passed', parts: meshCount, demo_duration_seconds: 9,
    checks: ['throw/scan/identify/tip/return', 'thrown bottle clears rim and funnel',
      'sliding bottle clears throat lip', 'pause/resume', 'reset cancels sound',
      'six tones + two movement cues', 'muted playback', 'four CAD-aligned destinations',
      'finite draw transforms', 'camera-facing cutaway in demo and cutaway view',
      'no cutaway in plan/assembled', '3D screen phase text and destination',
      'paused screen freezes', 'screen blank after reset', 'screen depth/viewport visibility'],
    draw_calls: draws, matrix_checks: matrixChecks, screen_draws: screenDraws,
    texture_uploads: textureUploads, detected_screen_visibility: visibility,
    thrown_bottle_min_clearance_mm: Math.round(thrown * 1e4) / 10,
    exit_min_clearance_mm: Math.round(exit * 1e4) / 10,
    exit_min_clearance_under_skirt_mm: Math.round(underSkirt * 1e4) / 10,
    scope: 'Actual viewer logic with mocked DOM/WebGL/Audio; no GPU or audible-browser verification',
  };
}

(async () => {
  const folders = process.argv.slice(2);
  for (const folder of folders.length ? folders : ['v3']) {
    console.log(JSON.stringify(await verify(path.resolve(root, folder)), null, 2));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
