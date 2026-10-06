/* Exercise the actual offline viewer script without a browser connection.
 * DOM, WebGL and audio are test doubles: this does not test GPU rendering or
 * audible playback. CAD meshes, application handlers and transforms are real.
 */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'v2/viewer.html'), 'utf8');
assert(!html.includes('__MESH_DATA__') && !html.includes('__DIMENSIONS__'));
const scripts = [...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)];
const source = scripts.find(s => !s[1].includes('application/json'))[2];
new vm.Script(source, {filename: 'viewer.html'});

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
const elements = new Map();
for (const id of [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1])) {
  assert(!elements.has('#' + id), `Duplicate DOM id: ${id}`);
  elements.set('#' + id, new Element());
}
elements.set('.stage', new Element());
for (const script of scripts.filter(s => s[1].includes('application/json'))) {
  elements.get('#' + script[1].match(/id="([^"]+)"/)[1]).textContent = script[2];
}
for (const id of ['sound', 'shell', 'canopy', 'sensors']) elements.get('#' + id).checked = true;
elements.get('#route').value = '0'; elements.get('#explode').value = '0';
const viewButtons = ['assembled', 'internals', 'exploded', 'plan', 'mechanism'].map(view => {
  const button = new Element(); button.dataset.view = view; return button;
});

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
let currentProgram = null, boundBuffer = null, buffers = new Map(), depthWrite = true, cullMode = null;
const uniformMatrices = new Map(), scalarUniforms = new Map(), frameDraws = [], enabled = new Set();
const constants = ['VERTEX_SHADER', 'FRAGMENT_SHADER', 'COMPILE_STATUS', 'LINK_STATUS',
  'ARRAY_BUFFER', 'STATIC_DRAW', 'DEPTH_TEST', 'SRC_ALPHA', 'ONE_MINUS_SRC_ALPHA',
  'TRIANGLES', 'FLOAT', 'BLEND', 'COLOR_BUFFER_BIT', 'DEPTH_BUFFER_BIT', 'LINE_LOOP',
  'TEXTURE_2D', 'TEXTURE0', 'TEXTURE_MIN_FILTER', 'TEXTURE_MAG_FILTER', 'TEXTURE_WRAP_S',
  'TEXTURE_WRAP_T', 'LINEAR', 'CLAMP_TO_EDGE', 'RGBA', 'UNSIGNED_BYTE', 'UNPACK_FLIP_Y_WEBGL',
  'CULL_FACE', 'FRONT', 'BACK'];
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
gl.cullFace = value => { cullMode = value; };
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
gl.uniform3fv = (_location, values) => assert(values.length === 3 && values.every(Number.isFinite));
gl.drawArrays = (primitive, first, count) => {
  assert.equal(first, 0); assert(Number.isInteger(count) && count > 0);
  if (primitive === gl.TRIANGLES) assert.equal(count % 3, 0);
  const screen = currentProgram === evaluate('screenProgram');
  if (screen) { assert.equal(count, 6); screenDraws++; }
  frameDraws.push({screen, primitive, count, buffer: boundBuffer, vertices: buffers.get(boundBuffer),
    depthWrite, blending: enabled.has(gl.BLEND), culling: enabled.has(gl.CULL_FACE), cullMode,
    opacity: screen ? 1 : scalarUniforms.get(currentProgram)?.u_opacity,
    ...uniformMatrices.get(currentProgram)});
  draws++;
};
const canvas = elements.get('#canvas');
canvas.clientWidth = 1200; canvas.clientHeight = 850;
canvas.getContext = type => { assert.equal(type, 'webgl'); return gl; };

const audioContexts = [];
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
function assertCanopy(appearance) {
  const buffer = evaluate("meshes.find(m=>m.name==='canopy').buffer");
  const passes = frameDraws.filter(draw => draw.buffer === buffer);
  if (appearance === 'hidden') { assert.equal(passes.length, 0); return; }
  if (appearance === 'opaque') {
    assert.equal(passes.length, 1); assert.equal(passes[0].opacity, 1);
    assert.equal(passes[0].blending, false); assert.equal(passes[0].depthWrite, true);
  } else {
    assert.equal(passes.length, 2, 'Transparent lid uses far/near surface passes');
    assert.deepEqual(passes.map(draw => draw.cullMode), [gl.FRONT, gl.BACK]);
    for (const pass of passes) {
      assert.equal(pass.opacity, .18); assert.equal(pass.blending, true);
      assert.equal(pass.depthWrite, false); assert.equal(pass.culling, true);
    }
  }
  assert.equal(enabled.has(gl.BLEND), false, 'Render state is restored after the lid');
  assert.equal(enabled.has(gl.CULL_FACE), false); assert.equal(depthWrite, true);
}
function screenVisibility() {
  // Project the actual draw buffers and test depth at points across the screen.
  // This catches a panel hidden behind the plate even without a connected GPU.
  const transform = (matrix, p) => [0, 1, 2, 3].map(row =>
    matrix[row] * p[0] + matrix[4 + row] * p[1] + matrix[8 + row] * p[2] + matrix[12 + row] * p[3]);
  const project = (draw, p) => {
    const clip = transform(draw.u_mvp, transform(draw.u_model, [...p, 1]));
    return clip.slice(0, 3).map(v => v / clip[3]);
  };
  const face = frameDraws.find(draw => draw.screen); assert(face);
  const triangles = [];
  for (const draw of frameDraws) {
    if (draw.screen || draw.primitive !== gl.TRIANGLES || (draw.blending && draw.opacity < 1)) continue;
    for (let i = 0; i < draw.count; i += 3) {
      triangles.push([0, 1, 2].map(j => {
        const offset = (i + j) * 6;
        return project(draw, [...draw.vertices.slice(offset, offset + 3)]);
      }));
    }
  }
  let visible = 0, samples = 0;
  for (let row = 1; row <= 8; row++) for (let column = 1; column <= 8; column++) {
    const u = column / 9, v = row / 9, vertices = face.vertices;
    const point = project(face, [vertices[0] + u * (vertices[5] - vertices[0]),
      vertices[1], vertices[2] + v * (vertices[12] - vertices[2])]);
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

(async () => {
  assert.equal(elements.get('#part').children.length, 41);
  assert.deepEqual(JSON.parse(elements.get('#dimensions').textContent).category_labels, ['', '', '', '']);
  frames(1);
  assertCanopy('opaque');
  assert.equal(screenDraws, 0, 'The physical screen is blank outside the demo');
  await click('play'); frames(20); assert.equal(title(), 'Place the bottle');
  assert.equal(elements.get('#canopy').checked, true); assertCanopy('transparent');
  assert.deepEqual(lastScreenText(), ['READY', 'PLACE', 'ONE ITEM', 'LEVEL PLATE']);
  frames(50); assert.equal(title(), 'Scanning…');
  assert.equal(screenState().phase, 'scanning'); assert(lastScreenText().includes('SCANNING'));
  frames(85); assert.equal(title(), 'Water bottle detected');
  assert.deepEqual(lastScreenText(), ['DETECTED', 'WATER', 'BOTTLE', 'TO SUB-BIN 4']);
  const visibility = screenVisibility();
  assert(visibility.ratio >= .95, 'The demo screen must not be hidden behind the plate');
  await click('pause'); const pauseTime = state().time; frames(90);
  assert.equal(state().time, pauseTime); assert.equal(audioContexts[0].state, 'suspended');
  assert.equal(lastScreenText()[0], 'PAUSED');
  assertCanopy('transparent');
  const pausedUploads = textureUploads; frames(10);
  assert.equal(textureUploads, pausedUploads, 'Paused screen progress must freeze');
  elements.get('#canopy').checked = false; frames(1); assertCanopy('hidden');
  elements.get('#canopy').checked = true; frames(1); assertCanopy('transparent');
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
  const validation = JSON.parse(fs.readFileSync(path.join(root, 'v2/validation.json'), 'utf8'));
  for (let bin = 1; bin <= 4; bin++) {
    const actual = JSON.parse(evaluate(`JSON.stringify(tiltAngles(1, ${bin}).map(v=>v*180/Math.PI))`));
    const cad = validation.tilt_pose_checks.find(p => p.destination === bin && p.fraction === 1);
    assert(Math.abs(actual[0] - cad.roll_degrees) < .0001);
    assert(Math.abs(actual[1] - cad.pitch_degrees) < .0001);
    const direction = (45 + (bin - 1) * 90) * Math.PI / 180;
    const normal = JSON.parse(evaluate(`JSON.stringify((()=>{const [a,b]=tiltAngles(1,${bin});return vector(mul(ry(b),rx(a)),[0,0,1])})())`));
    assert(normal[0] * Math.cos(direction) > 0 && normal[1] * Math.sin(direction) > 0);
    evaluate(`player.target=${bin}`);
    const center = JSON.parse(evaluate('JSON.stringify(vector(bottleModel(6.9,demoPose(6.9)),[0,0,dim.demo_bottle_height_mm/2000]))'));
    assert(center[0] * Math.cos(direction) > 0 && center[1] * Math.sin(direction) > 0);
    assert(Math.abs(center[2] - .120) < .000001);
    assert(Math.hypot(center[0], center[1]) < .24, 'Bottle stays within liner perimeter');
  }

  await click('reset'); assert.equal(state().active, false);
  const beforeResetFrames = screenDraws; frames(5);
  assert.equal(screenDraws, beforeResetFrames, 'Reset blanks the physical display');
  assertCanopy('opaque');
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
  await viewButtons[4].fire('click'); frames(1);
  assert.equal(state().active, false); assert.equal(evaluate('mode'), 'mechanism');
  await viewButtons[3].fire('click'); frames(1); assert.equal(evaluate('isPlan'), true);
  console.log(JSON.stringify({
    status: 'passed', parts: 41, demo_duration_seconds: 9,
    checks: ['load/scan/identify/tip/return', 'pause/resume', 'reset cancels sound',
      'six tones + two movement cues', 'muted playback', 'four CAD-aligned destinations',
      'finite draw transforms', 'detail and plan views', '3D screen phase text and destination',
      'paused screen freezes', 'screen blank after reset', 'screen depth/viewport visibility',
      'transparent lid during demo/pause', 'opaque lid after reset', 'manual lid visibility'],
    draw_calls: draws, matrix_checks: matrixChecks, screen_draws: screenDraws,
    texture_uploads: textureUploads,
    detected_screen_visibility: visibility,
    scope: 'Actual viewer logic with mocked DOM/WebGL/Audio; no GPU or audible-browser verification',
  }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
