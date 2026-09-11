/* BLOCKHAVEN engine -- particles.
   Drives the Unusual hat effects (which follow a player everywhere) plus all
   the combat feedback: muzzle flashes, impacts, explosions and pickups. */
(function (global) {
  'use strict';

  var M = GLX.mat;
  var MAX = 2600;

  var VERT = [
    'precision highp float;',
    'attribute vec2 aQuad;',
    'attribute vec3 aPos;',
    'attribute vec4 aColor;',
    'attribute vec3 aMeta;',   // size, rotation, shape index
    'uniform mat4 uViewProj;',
    'uniform vec3 uRight;',
    'uniform vec3 uUp;',
    'varying vec4 vColor;',
    'varying vec2 vUV;',
    'varying float vShape;',
    'void main() {',
    '  float c = cos(aMeta.y), s = sin(aMeta.y);',
    '  vec2 q = vec2(aQuad.x * c - aQuad.y * s, aQuad.x * s + aQuad.y * c);',
    '  vec3 world = aPos + uRight * (q.x * aMeta.x) + uUp * (q.y * aMeta.x);',
    '  vUV = aQuad * 0.5 + 0.5;',
    '  vColor = aColor;',
    '  vShape = aMeta.z;',
    '  gl_Position = uViewProj * vec4(world, 1.0);',
    '}'
  ].join('\n');

  var FRAG = [
    'precision highp float;',
    'varying vec4 vColor;',
    'varying vec2 vUV;',
    'varying float vShape;',
    'uniform sampler2D uTex;',
    'void main() {',
    '  float col = mod(vShape, 4.0);',
    '  float row = floor(vShape / 4.0);',
    '  vec2 uv = vec2((col + vUV.x) * 0.25, (row + vUV.y) * 0.5);',
    '  vec4 tex = texture2D(uTex, uv);',
    '  gl_FragColor = vec4(vColor.rgb * tex.rgb, tex.a * vColor.a);',
    '}'
  ].join('\n');

  var SHAPES = { puff: 0, flame: 1, star: 2, flake: 3, spark: 4, bubble: 5,
                 ray: 6, ring: 7 };

  function buildAtlas() {
    var CELL = 128;
    var canvas = document.createElement('canvas');
    canvas.width = CELL * 4;
    canvas.height = CELL * 2;
    var ctx = canvas.getContext('2d');
    function cell(index) {
      ctx.save();
      ctx.translate((index % 4) * CELL, Math.floor(index / 4) * CELL);
      return ctx;
    }
    // puff -- soft radial
    var c = cell(0);
    var g = c.createRadialGradient(64, 64, 2, 64, 64, 62);
    g.addColorStop(0, 'rgba(255,255,255,1)');
    g.addColorStop(0.45, 'rgba(255,255,255,0.55)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    c.fillStyle = g; c.fillRect(0, 0, CELL, CELL); c.restore();
    // flame -- teardrop
    c = cell(1);
    var fg = c.createRadialGradient(64, 78, 4, 64, 70, 56);
    fg.addColorStop(0, 'rgba(255,255,255,1)');
    fg.addColorStop(0.5, 'rgba(255,255,255,0.7)');
    fg.addColorStop(1, 'rgba(255,255,255,0)');
    c.fillStyle = fg;
    c.beginPath();
    c.moveTo(64, 8);
    c.bezierCurveTo(104, 58, 100, 112, 64, 118);
    c.bezierCurveTo(28, 112, 24, 58, 64, 8);
    c.fill(); c.restore();
    // star
    c = cell(2);
    c.fillStyle = '#ffffff';
    c.beginPath();
    for (var i = 0; i < 10; i++) {
      var ang = -Math.PI / 2 + i * Math.PI / 5;
      var rad = (i % 2 === 0) ? 58 : 22;
      var x = 64 + Math.cos(ang) * rad, y = 64 + Math.sin(ang) * rad;
      if (i === 0) c.moveTo(x, y); else c.lineTo(x, y);
    }
    c.closePath(); c.fill(); c.restore();
    // snowflake
    c = cell(3);
    c.strokeStyle = '#ffffff'; c.lineWidth = 8; c.lineCap = 'round';
    for (i = 0; i < 6; i++) {
      var a = (i / 6) * Math.PI * 2;
      c.beginPath();
      c.moveTo(64, 64);
      c.lineTo(64 + Math.cos(a) * 52, 64 + Math.sin(a) * 52);
      c.stroke();
      c.beginPath();
      c.moveTo(64 + Math.cos(a) * 30, 64 + Math.sin(a) * 30);
      c.lineTo(64 + Math.cos(a) * 42 + Math.cos(a + 1.2) * 16,
               64 + Math.sin(a) * 42 + Math.sin(a + 1.2) * 16);
      c.stroke();
    }
    c.restore();
    // spark -- short streak
    c = cell(4);
    var sg = c.createLinearGradient(64, 10, 64, 118);
    sg.addColorStop(0, 'rgba(255,255,255,0)');
    sg.addColorStop(0.5, 'rgba(255,255,255,1)');
    sg.addColorStop(1, 'rgba(255,255,255,0)');
    c.fillStyle = sg; c.fillRect(52, 8, 24, 112); c.restore();
    // bubble
    c = cell(5);
    c.strokeStyle = 'rgba(255,255,255,0.95)'; c.lineWidth = 7;
    c.beginPath(); c.arc(64, 64, 50, 0, Math.PI * 2); c.stroke();
    c.fillStyle = 'rgba(255,255,255,0.55)';
    c.beginPath(); c.arc(46, 44, 12, 0, Math.PI * 2); c.fill();
    c.restore();
    // ray
    c = cell(6);
    var rg = c.createLinearGradient(0, 64, 128, 64);
    rg.addColorStop(0, 'rgba(255,255,255,0)');
    rg.addColorStop(0.5, 'rgba(255,255,255,1)');
    rg.addColorStop(1, 'rgba(255,255,255,0)');
    c.fillStyle = rg; c.fillRect(0, 50, 128, 28); c.restore();
    // ring
    c = cell(7);
    c.strokeStyle = '#ffffff'; c.lineWidth = 14;
    c.beginPath(); c.arc(64, 64, 46, 0, Math.PI * 2); c.stroke(); c.restore();
    return canvas;
  }

  function Particles(gl) {
    this.gl = gl;
    this.program = GLX.compile(gl, VERT, FRAG, 'particles');
    this.enabled = true;
    this.count = 0;
    this.pos = new Float32Array(MAX * 3);
    this.vel = new Float32Array(MAX * 3);
    this.col = new Float32Array(MAX * 4);
    this.meta = new Float32Array(MAX * 3);      // size, rotation, shape
    this.life = new Float32Array(MAX);
    this.maxLife = new Float32Array(MAX);
    this.grow = new Float32Array(MAX);
    this.grav = new Float32Array(MAX);
    this.spin = new Float32Array(MAX);
    this.blend = new Uint8Array(MAX);
    this.ramp = new Float32Array(MAX * 12);     // up to 4 colours per particle
    this.rampLen = new Uint8Array(MAX);
    this.orbit = new Float32Array(MAX * 3);     // speed, radius, phase
    this.origin = new Float32Array(MAX * 3);
    this.emitters = {};

    this.atlas = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, this.atlas);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, buildAtlas());
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

    this.quad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
    gl.bufferData(gl.ARRAY_BUFFER,
                  new Float32Array([-1, -1, 1, -1, 1, 1, -1, -1, 1, 1, -1, 1]),
                  gl.STATIC_DRAW);
    this.instanceBuffer = gl.createBuffer();
    this.instanceData = new Float32Array(MAX * 10);
  }

  Particles.prototype.spawn = function (opts) {
    if (!this.enabled) return;
    if (this.count >= MAX) return;
    var i = this.count++;
    this.pos[i * 3] = opts.p[0];
    this.pos[i * 3 + 1] = opts.p[1];
    this.pos[i * 3 + 2] = opts.p[2];
    this.vel[i * 3] = opts.v[0];
    this.vel[i * 3 + 1] = opts.v[1];
    this.vel[i * 3 + 2] = opts.v[2];
    this.origin[i * 3] = opts.origin ? opts.origin[0] : opts.p[0];
    this.origin[i * 3 + 1] = opts.origin ? opts.origin[1] : opts.p[1];
    this.origin[i * 3 + 2] = opts.origin ? opts.origin[2] : opts.p[2];
    this.life[i] = opts.life;
    this.maxLife[i] = opts.life;
    this.meta[i * 3] = opts.size;
    this.meta[i * 3 + 1] = Math.random() * Math.PI * 2;
    this.meta[i * 3 + 2] = SHAPES[opts.shape] === undefined ? 0 : SHAPES[opts.shape];
    this.grow[i] = opts.grow || 0;
    this.grav[i] = opts.gravity || 0;
    this.spin[i] = opts.spin || 0;
    this.blend[i] = opts.blend === 'add' ? 1 : 0;
    var colours = opts.colors || ['#ffffff'];
    this.rampLen[i] = Math.min(4, colours.length);
    for (var k = 0; k < this.rampLen[i]; k++) {
      var rgb = M.hexToRgb(colours[k]);
      this.ramp[i * 12 + k * 3] = rgb[0];
      this.ramp[i * 12 + k * 3 + 1] = rgb[1];
      this.ramp[i * 12 + k * 3 + 2] = rgb[2];
    }
    this.orbit[i * 3] = opts.orbit || 0;
    this.orbit[i * 3 + 1] = opts.orbitRadius || 0;
    this.orbit[i * 3 + 2] = Math.random() * Math.PI * 2;
    this.col[i * 4 + 3] = 1;
  };

  Particles.prototype.remove = function (i) {
    var last = --this.count;
    if (i === last) return;
    var arrays3 = ['pos', 'vel', 'meta', 'orbit', 'origin'];
    for (var a = 0; a < arrays3.length; a++) {
      var arr = this[arrays3[a]];
      arr[i * 3] = arr[last * 3];
      arr[i * 3 + 1] = arr[last * 3 + 1];
      arr[i * 3 + 2] = arr[last * 3 + 2];
    }
    for (var k = 0; k < 12; k++) this.ramp[i * 12 + k] = this.ramp[last * 12 + k];
    for (k = 0; k < 4; k++) this.col[i * 4 + k] = this.col[last * 4 + k];
    this.life[i] = this.life[last];
    this.maxLife[i] = this.maxLife[last];
    this.grow[i] = this.grow[last];
    this.grav[i] = this.grav[last];
    this.spin[i] = this.spin[last];
    this.blend[i] = this.blend[last];
    this.rampLen[i] = this.rampLen[last];
  };

  /* Attach a persistent effect (an Unusual hat) to a key. */
  Particles.prototype.setEmitter = function (key, effect, position) {
    if (!effect) { delete this.emitters[key]; return; }
    var emitter = this.emitters[key];
    if (!emitter || emitter.effect !== effect) {
      emitter = { effect: effect, acc: 0, p: position.slice(), active: true };
      this.emitters[key] = emitter;
    }
    emitter.p[0] = position[0];
    emitter.p[1] = position[1];
    emitter.p[2] = position[2];
    emitter.active = true;
  };

  Particles.prototype.clearEmitter = function (key) { delete this.emitters[key]; };

  Particles.prototype.updateEmitters = function (dt) {
    var keys = Object.keys(this.emitters);
    for (var k = 0; k < keys.length; k++) {
      var emitter = this.emitters[keys[k]];
      if (!emitter.active) continue;
      var e = emitter.effect;
      emitter.acc += (e.rate || 12) * dt;
      var spawnCount = Math.floor(emitter.acc);
      emitter.acc -= spawnCount;
      spawnCount = Math.min(spawnCount, 6);
      for (var n = 0; n < spawnCount; n++) {
        var radius = e.radius === undefined ? 0.5 : e.radius;
        var ang = Math.random() * Math.PI * 2;
        var rr = Math.sqrt(Math.random()) * radius;
        var spread = e.spread || 0.4;
        var rise = e.rise || [0.5, 1.2];
        this.spawn({
          p: [emitter.p[0] + Math.cos(ang) * rr,
              emitter.p[1] + (Math.random() - 0.2) * 0.25,
              emitter.p[2] + Math.sin(ang) * rr],
          origin: emitter.p,
          v: [(Math.random() - 0.5) * spread * 2,
              rise[0] + Math.random() * (rise[1] - rise[0]),
              (Math.random() - 0.5) * spread * 2],
          life: (e.life ? e.life[0] + Math.random() * (e.life[1] - e.life[0]) : 1),
          size: (e.size ? e.size[0] + Math.random() * (e.size[1] - e.size[0]) : 0.4),
          grow: e.grow || 0,
          gravity: e.gravity || 0,
          spin: (Math.random() - 0.5) * (e.spin || 0),
          blend: e.blend || 'normal',
          colors: e.colors,
          shape: e.shape || 'puff',
          orbit: e.orbit || 0,
          orbitRadius: rr
        });
      }
      emitter.active = false;   // must be refreshed every frame to keep going
    }
  };

  Particles.prototype.update = function (dt) {
    if (!this.enabled) { this.count = 0; return; }
    this.updateEmitters(dt);
    for (var i = 0; i < this.count; i++) {
      this.life[i] -= dt;
      if (this.life[i] <= 0) { this.remove(i); i--; continue; }
      var orbitSpeed = this.orbit[i * 3];
      if (orbitSpeed) {
        this.orbit[i * 3 + 2] += orbitSpeed * dt;
        var radius = this.orbit[i * 3 + 1];
        var phase = this.orbit[i * 3 + 2];
        this.pos[i * 3] = this.origin[i * 3] + Math.cos(phase) * radius;
        this.pos[i * 3 + 2] = this.origin[i * 3 + 2] + Math.sin(phase) * radius;
        this.pos[i * 3 + 1] += this.vel[i * 3 + 1] * dt;
      } else {
        this.vel[i * 3 + 1] += this.grav[i] * dt;
        this.pos[i * 3] += this.vel[i * 3] * dt;
        this.pos[i * 3 + 1] += this.vel[i * 3 + 1] * dt;
        this.pos[i * 3 + 2] += this.vel[i * 3 + 2] * dt;
      }
      this.meta[i * 3] = Math.max(0.01, this.meta[i * 3] + this.grow[i] * dt);
      this.meta[i * 3 + 1] += this.spin[i] * dt;
      // colour ramp across the lifetime
      var t = 1 - (this.life[i] / this.maxLife[i]);
      var n = this.rampLen[i] || 1;
      var f = t * (n - 1);
      var idx = Math.min(n - 2, Math.floor(f));
      if (n === 1) idx = 0;
      var frac = n === 1 ? 0 : f - idx;
      var base = i * 12 + idx * 3;
      var next = n === 1 ? base : base + 3;
      this.col[i * 4] = this.ramp[base] + (this.ramp[next] - this.ramp[base]) * frac;
      this.col[i * 4 + 1] = this.ramp[base + 1] +
        (this.ramp[next + 1] - this.ramp[base + 1]) * frac;
      this.col[i * 4 + 2] = this.ramp[base + 2] +
        (this.ramp[next + 2] - this.ramp[base + 2]) * frac;
      var fade = Math.min(1, this.life[i] / (this.maxLife[i] * 0.45));
      var fadeIn = Math.min(1, t / 0.12);
      this.col[i * 4 + 3] = fade * fadeIn;
    }
  };

  Particles.prototype.draw = function (renderer) {
    if (!this.count || !this.program) return;
    var gl = this.gl, p = this.program;
    var fwd = renderer.forward || [0, 0, 1];
    var flen = Math.hypot(fwd[0], fwd[1], fwd[2]) || 1;
    var right = [-fwd[2] / flen, 0, fwd[0] / flen];
    var rlen = Math.hypot(right[0], right[1], right[2]) || 1;
    right = [right[0] / rlen, 0, right[2] / rlen];
    var up = [
      right[1] * fwd[2] / flen - right[2] * fwd[1] / flen,
      right[2] * fwd[0] / flen - right[0] * fwd[2] / flen,
      right[0] * fwd[1] / flen - right[1] * fwd[0] / flen
    ];

    gl.useProgram(p);
    gl.uniformMatrix4fv(p.uniforms.uViewProj, false, renderer.viewProj);
    gl.uniform3fv(p.uniforms.uRight, right);
    gl.uniform3fv(p.uniforms.uUp, up);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.atlas);
    gl.uniform1i(p.uniforms.uTex, 0);
    gl.enable(gl.BLEND);
    gl.depthMask(false);

    for (var pass = 0; pass < 2; pass++) {
      var written = 0;
      for (var i = 0; i < this.count; i++) {
        if (this.blend[i] !== pass) continue;
        var o = written * 10;
        this.instanceData[o] = this.pos[i * 3];
        this.instanceData[o + 1] = this.pos[i * 3 + 1];
        this.instanceData[o + 2] = this.pos[i * 3 + 2];
        this.instanceData[o + 3] = this.col[i * 4];
        this.instanceData[o + 4] = this.col[i * 4 + 1];
        this.instanceData[o + 5] = this.col[i * 4 + 2];
        this.instanceData[o + 6] = this.col[i * 4 + 3];
        this.instanceData[o + 7] = this.meta[i * 3];
        this.instanceData[o + 8] = this.meta[i * 3 + 1];
        this.instanceData[o + 9] = this.meta[i * 3 + 2];
        written++;
      }
      if (!written) continue;
      if (pass === 1) gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
      else gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

      gl.bindBuffer(gl.ARRAY_BUFFER, this.quad);
      gl.enableVertexAttribArray(p.attribs.aQuad);
      gl.vertexAttribPointer(p.attribs.aQuad, 2, gl.FLOAT, false, 0, 0);
      gl.vertexAttribDivisor(p.attribs.aQuad, 0);

      gl.bindBuffer(gl.ARRAY_BUFFER, this.instanceBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, this.instanceData.subarray(0, written * 10),
                    gl.DYNAMIC_DRAW);
      var stride = 10 * 4;
      gl.enableVertexAttribArray(p.attribs.aPos);
      gl.vertexAttribPointer(p.attribs.aPos, 3, gl.FLOAT, false, stride, 0);
      gl.vertexAttribDivisor(p.attribs.aPos, 1);
      gl.enableVertexAttribArray(p.attribs.aColor);
      gl.vertexAttribPointer(p.attribs.aColor, 4, gl.FLOAT, false, stride, 12);
      gl.vertexAttribDivisor(p.attribs.aColor, 1);
      gl.enableVertexAttribArray(p.attribs.aMeta);
      gl.vertexAttribPointer(p.attribs.aMeta, 3, gl.FLOAT, false, stride, 28);
      gl.vertexAttribDivisor(p.attribs.aMeta, 1);
      gl.drawArraysInstanced ? gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, written)
        : null;
      if (!gl.drawArraysInstanced) {
        // WebGL1 fallback through the ANGLE extension
        gl.drawArraysInstancedANGLE(gl.TRIANGLES, 0, 6, written);
      }
    }
    gl.depthMask(true);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  };

  // ------------------------------------------------------------- one-shots
  Particles.prototype.burst = function (kind, position, options) {
    options = options || {};
    var n, i, ang, speed;
    if (kind === 'muzzle') {
      for (i = 0; i < 5; i++) {
        this.spawn({ p: position, v: [(Math.random() - 0.5) * 3,
                                      (Math.random() - 0.3) * 2,
                                      (Math.random() - 0.5) * 3],
          life: 0.09 + Math.random() * 0.07, size: 0.5 + Math.random() * 0.4,
          grow: -1.4, gravity: 0, spin: 6, blend: 'add', shape: 'flame',
          colors: ['#fff3b0', '#ffb347', '#ff6b1a'] });
      }
    } else if (kind === 'impact') {
      var colour = options.color || '#c8cbcd';
      for (i = 0; i < 8; i++) {
        this.spawn({ p: position, v: [(Math.random() - 0.5) * 9,
                                      Math.random() * 7,
                                      (Math.random() - 0.5) * 9],
          life: 0.28 + Math.random() * 0.3, size: 0.14 + Math.random() * 0.18,
          grow: -0.2, gravity: -20, spin: 8, blend: 'normal', shape: 'spark',
          colors: [colour, '#8a8f94'] });
      }
      this.spawn({ p: position, v: [0, 0.6, 0], life: 0.5, size: 0.7, grow: 1.4,
        gravity: 0.4, blend: 'normal', shape: 'puff', colors: ['#e8e8e8', '#b9c3cc'] });
    } else if (kind === 'blood') {
      for (i = 0; i < 10; i++) {
        this.spawn({ p: position, v: [(Math.random() - 0.5) * 7,
                                      Math.random() * 5 + 1,
                                      (Math.random() - 0.5) * 7],
          life: 0.32 + Math.random() * 0.25, size: 0.22 + Math.random() * 0.2,
          grow: -0.25, gravity: -22, spin: 4, blend: 'normal', shape: 'puff',
          colors: [options.color || '#d8412f', '#7c1a12'] });
      }
    } else if (kind === 'explosion') {
      var radius = options.radius || 8;
      for (i = 0; i < 34; i++) {
        ang = Math.random() * Math.PI * 2;
        speed = radius * (0.5 + Math.random());
        this.spawn({ p: position,
          v: [Math.cos(ang) * speed, Math.random() * radius * 1.1,
              Math.sin(ang) * speed],
          life: 0.5 + Math.random() * 0.7, size: 1.1 + Math.random() * 1.6,
          grow: 1.6, gravity: -3, spin: 3, blend: 'add', shape: 'flame',
          colors: ['#ffffff', '#ffd24a', '#ff6b1a', '#5a1a04'] });
      }
      for (i = 0; i < 14; i++) {
        ang = Math.random() * Math.PI * 2;
        this.spawn({ p: position,
          v: [Math.cos(ang) * radius * 1.4, Math.random() * 4,
              Math.sin(ang) * radius * 1.4],
          life: 1.1 + Math.random(), size: 1.6, grow: 2.4, gravity: 0.6,
          blend: 'normal', shape: 'puff', colors: ['#4a4a4a', '#2a2a2a'] });
      }
      this.spawn({ p: position, v: [0, 0, 0], life: 0.35, size: radius * 0.8,
        grow: radius * 2.4, gravity: 0, blend: 'add', shape: 'ring',
        colors: ['#fff3b0', '#ff8c1a'] });
    } else if (kind === 'heal') {
      for (i = 0; i < 8; i++) {
        this.spawn({ p: [position[0] + (Math.random() - 0.5) * 2, position[1],
                         position[2] + (Math.random() - 0.5) * 2],
          v: [0, 2.2 + Math.random(), 0], life: 0.8, size: 0.4, grow: -0.2,
          gravity: 0.4, spin: 2, blend: 'add', shape: 'star',
          colors: ['#ffffff', '#8ef2a0', '#2f9d4a'] });
      }
    } else if (kind === 'pickup') {
      for (i = 0; i < 12; i++) {
        ang = (i / 12) * Math.PI * 2;
        this.spawn({ p: position, v: [Math.cos(ang) * 3, 3, Math.sin(ang) * 3],
          life: 0.7, size: 0.4, grow: -0.3, gravity: -3, spin: 5, blend: 'add',
          shape: 'star', colors: ['#ffffff', '#ffd95e', '#e0a615'] });
      }
    } else if (kind === 'dust') {
      for (i = 0; i < 4; i++) {
        this.spawn({ p: position, v: [(Math.random() - 0.5) * 2, Math.random(),
                                      (Math.random() - 0.5) * 2],
          life: 0.45, size: 0.4, grow: 0.8, gravity: 0.2, blend: 'normal',
          shape: 'puff', colors: [options.color || '#cfcfcf', '#ffffff'] });
      }
    } else if (kind === 'coin') {
      for (i = 0; i < 10; i++) {
        ang = Math.random() * Math.PI * 2;
        this.spawn({ p: position, v: [Math.cos(ang) * 2.4, 5 + Math.random() * 3,
                                      Math.sin(ang) * 2.4],
          life: 0.9, size: 0.45, grow: -0.15, gravity: -12, spin: 9,
          blend: 'add', shape: 'star', colors: ['#fff3b0', '#f5c518', '#a97a06'] });
      }
    }
    n = 0; return n;
  };

  Particles.SHAPES = SHAPES;
  global.Particles = Particles;
})(window);
