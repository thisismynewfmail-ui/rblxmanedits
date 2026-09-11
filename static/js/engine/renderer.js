/* BLOCKHAVEN engine -- instanced primitive renderer.
   Everything in every world is one of six primitives, so the whole scene draws
   in a handful of instanced calls. */
(function (global) {
  'use strict';

  var M = GLX.mat;
  var STRIDE = 28;   // floats per instance: mat4 + colour + params + decal

  var VERT = [
    'precision highp float;',
    'attribute vec3 aPosition;',
    'attribute vec3 aNormal;',
    'attribute vec2 aUV;',
    'attribute vec4 aModel0;',
    'attribute vec4 aModel1;',
    'attribute vec4 aModel2;',
    'attribute vec4 aModel3;',
    'attribute vec4 aColor;',
    'attribute vec4 aParams;',
    'attribute vec4 aDecal;',
    'uniform mat4 uViewProj;',
    'varying vec3 vColor;',
    'varying float vAlpha;',
    'varying vec3 vNormal;',
    'varying vec3 vWorld;',
    'varying vec3 vLocal;',
    'varying vec2 vUV;',
    'varying vec4 vParams;',
    'varying vec4 vDecal;',
    'void main() {',
    '  mat4 model = mat4(aModel0, aModel1, aModel2, aModel3);',
    '  vec3 scale = vec3(length(aModel0.xyz), length(aModel1.xyz), length(aModel2.xyz));',
    '  vec4 world = model * vec4(aPosition, 1.0);',
    '  vWorld = world.xyz;',
    '  vLocal = aPosition * scale;',
    '  mat3 nm = mat3(aModel0.xyz / max(scale.x, 0.0001),',
    '                 aModel1.xyz / max(scale.y, 0.0001),',
    '                 aModel2.xyz / max(scale.z, 0.0001));',
    '  vNormal = normalize(nm * aNormal);',
    '  vColor = aColor.rgb;',
    '  vAlpha = aColor.a;',
    '  vUV = aUV;',
    '  vParams = aParams;',
    '  vDecal = aDecal;',
    '  gl_Position = uViewProj * world;',
    '}'
  ].join('\n');

  var FRAG = [
    'precision highp float;',
    'varying vec3 vColor;',
    'varying float vAlpha;',
    'varying vec3 vNormal;',
    'varying vec3 vWorld;',
    'varying vec3 vLocal;',
    'varying vec2 vUV;',
    'varying vec4 vParams;',
    'varying vec4 vDecal;',
    'uniform vec3 uSunDir;',
    'uniform vec3 uSunColor;',
    'uniform vec3 uSkyColor;',
    'uniform vec3 uGroundColor;',
    'uniform vec3 uFogColor;',
    'uniform vec3 uEye;',
    'uniform float uFogFar;',
    'uniform sampler2D uAtlas;',
    'uniform float uTime;',
    '',
    'float studPattern(vec2 p) {',
    '  vec2 cell = fract(p) - 0.5;',
    '  float d = length(cell);',
    '  float ring = smoothstep(0.30, 0.26, d);',
    '  float lip = smoothstep(0.34, 0.30, d) - smoothstep(0.30, 0.26, d);',
    '  return ring * 0.10 + lip * -0.16;',
    '}',
    '',
    'float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
    '',
    'void main() {',
    '  vec3 normal = normalize(vNormal);',
    '  vec3 base = vColor;',
    '  float material = vParams.y;',
    '  float alpha = vAlpha;',
    '',
    '  // studs on upward faces',
    '  if (vParams.x > 0.5 && normal.y > 0.75) {',
    '    base += studPattern(vLocal.xz + vec2(0.5));',
    '  }',
    '  // grass gets a subtle speckle so big fields do not look flat',
    '  if (material > 3.5 && material < 4.5) {',
    '    float g = hash(floor(vWorld.xz * 0.7));',
    '    base *= 0.93 + g * 0.14;',
    '  }',
    '  // decal on the +Z face',
    '  if (vDecal.z > 0.0 && normal.z > 0.6) {',
    '    vec2 duv = vec2(vUV.x, 1.0 - vUV.y) * vDecal.z + vDecal.xy;',
    '    vec4 tex = texture2D(uAtlas, duv);',
    '    base = mix(base, tex.rgb, tex.a);',
    '  }',
    '',
    '  vec3 lightDir = normalize(uSunDir);',
    // Wrapped diffuse: keeps unlit faces readable the way the old block',
    // renderers did, instead of dropping them to black.',
    '  float ndl = max(dot(normal, lightDir), 0.0);',
    '  float wrapped = ndl * 0.62 + 0.38;',
    '  float hemi = normal.y * 0.5 + 0.5;',
    '  vec3 ambient = mix(uGroundColor, uSkyColor, hemi);',
    '  vec3 lit = base * (ambient + uSunColor * wrapped * 0.60);',
    '',
    '  if (material > 0.5 && material < 1.5) {',        // metal
    '    vec3 viewDir = normalize(uEye - vWorld);',
    '    vec3 h = normalize(viewDir + lightDir);',
    '    float spec = pow(max(dot(normal, h), 0.0), 42.0);',
    '    lit += uSunColor * spec * 0.85;',
    '    lit *= 1.04;',
    '  } else if (material > 1.5 && material < 2.5) {', // neon
    '    lit = base * (1.25 + 0.12 * sin(uTime * 3.0));',
    '  } else if (material > 2.5 && material < 3.5) {', // glass
    '    vec3 viewDir = normalize(uEye - vWorld);',
    '    float fres = pow(1.0 - max(dot(normal, viewDir), 0.0), 3.0);',
    '    lit += vec3(0.35) * fres;',
    '    alpha = min(1.0, alpha + fres * 0.35);',
    '  }',
    '  if (vParams.z > 0.0) { lit = mix(lit, base, vParams.z); }',
    '',
    '  float dist = length(uEye - vWorld);',
    '  float fog = clamp((dist - uFogFar * 0.42) / (uFogFar * 0.72), 0.0, 1.0);',
    '  fog = fog * fog * 0.92;',
    '  vec3 finalColor = mix(lit, uFogColor, fog);',
    '  gl_FragColor = vec4(finalColor, alpha);',
    '}'
  ].join('\n');

  var SKY_VERT = [
    'precision highp float;',
    'attribute vec2 aQuad;',
    'uniform mat4 uInvViewProj;',
    'uniform vec3 uEye;',
    'varying vec3 vRay;',
    'void main() {',
    '  vec4 near = uInvViewProj * vec4(aQuad, -1.0, 1.0);',
    '  vec4 far = uInvViewProj * vec4(aQuad, 1.0, 1.0);',
    '  vRay = (far.xyz / far.w) - (near.xyz / near.w);',
    '  gl_Position = vec4(aQuad, 0.999999, 1.0);',
    '}'
  ].join('\n');

  var SKY_FRAG = [
    'precision highp float;',
    'varying vec3 vRay;',
    'uniform vec3 uTop;',
    'uniform vec3 uHorizon;',
    'uniform vec3 uSunDir;',
    'uniform vec3 uTint;',
    'uniform float uClouds;',
    'uniform float uTime;',
    '',
    'float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }',
    'float noise(vec2 p) {',
    '  vec2 i = floor(p), f = fract(p);',
    '  f = f * f * (3.0 - 2.0 * f);',
    '  float a = hash(i), b = hash(i + vec2(1.0, 0.0));',
    '  float c = hash(i + vec2(0.0, 1.0)), d = hash(i + vec2(1.0, 1.0));',
    '  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);',
    '}',
    'float fbm(vec2 p) {',
    '  float v = 0.0, amp = 0.5;',
    '  for (int i = 0; i < 5; i++) { v += amp * noise(p); p *= 2.03; amp *= 0.5; }',
    '  return v;',
    '}',
    'void main() {',
    '  vec3 dir = normalize(vRay);',
    '  float h = clamp(dir.y * 1.4 + 0.12, 0.0, 1.0);',
    '  vec3 sky = mix(uHorizon, uTop, pow(h, 0.72));',
    '  float sun = max(dot(dir, normalize(uSunDir)), 0.0);',
    '  sky += uTint * pow(sun, 90.0) * 1.4;',
    '  sky += uTint * pow(sun, 6.0) * 0.16;',
    '  if (dir.y > -0.02) {',
    '    vec2 uv = dir.xz / max(dir.y + 0.16, 0.05);',
    '    float t = uTime * 0.004;',
    '    float clouds = fbm(uv * 0.55 + vec2(t, t * 0.4));',
    '    clouds = smoothstep(0.40, 0.80, clouds) * uClouds;',
    '    float shade = 0.55 + 0.45 * smoothstep(0.4, 0.9, fbm(uv * 1.1 - vec2(t)));',
    '    vec3 cloudColor = mix(uTint * 0.72, vec3(1.0), shade);',
    '    clouds *= smoothstep(0.0, 0.22, dir.y);',
    '    sky = mix(sky, cloudColor, clamp(clouds, 0.0, 1.0));',
    '  }',
    '  gl_FragColor = vec4(sky, 1.0);',
    '}'
  ].join('\n');

  var TAG_VERT = [
    'precision highp float;',
    'attribute vec2 aQuad;',
    'uniform mat4 uViewProj;',
    'uniform vec3 uCenter;',
    'uniform vec3 uRight;',
    'uniform vec3 uUp;',
    'uniform vec2 uSize;',
    'varying vec2 vUV;',
    'void main() {',
    '  vUV = aQuad * 0.5 + 0.5;',
    '  vec3 world = uCenter + uRight * (aQuad.x * uSize.x) + uUp * (aQuad.y * uSize.y);',
    '  gl_Position = uViewProj * vec4(world, 1.0);',
    '}'
  ].join('\n');

  var TAG_FRAG = [
    'precision highp float;',
    'varying vec2 vUV;',
    'uniform sampler2D uTex;',
    'uniform float uOpacity;',
    'void main() {',
    '  vec4 c = texture2D(uTex, vUV);',
    '  gl_FragColor = vec4(c.rgb, c.a * uOpacity);',
    '}'
  ].join('\n');

  function Batch(gl, mesh, program) {
    this.gl = gl;
    this.mesh = mesh;
    this.program = program;
    this.data = new Float32Array(STRIDE * 256);
    this.count = 0;
    this.capacity = 256;
    this.buffer = gl.createBuffer();
    this.dirty = true;
    this.uploaded = 0;
    this.setupMesh();
  }

  Batch.prototype.setupMesh = function () {
    var gl = this.gl;
    var m = this.mesh;
    this.vbo = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.vbo);
    var interleaved = new Float32Array(m.positions.length / 3 * 8);
    for (var i = 0; i < m.positions.length / 3; i++) {
      interleaved[i * 8] = m.positions[i * 3];
      interleaved[i * 8 + 1] = m.positions[i * 3 + 1];
      interleaved[i * 8 + 2] = m.positions[i * 3 + 2];
      interleaved[i * 8 + 3] = m.normals[i * 3];
      interleaved[i * 8 + 4] = m.normals[i * 3 + 1];
      interleaved[i * 8 + 5] = m.normals[i * 3 + 2];
      interleaved[i * 8 + 6] = m.uvs[i * 2];
      interleaved[i * 8 + 7] = m.uvs[i * 2 + 1];
    }
    gl.bufferData(gl.ARRAY_BUFFER, interleaved, gl.STATIC_DRAW);
    this.ibo = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.ibo);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, m.indices, gl.STATIC_DRAW);
    this.indexCount = m.indices.length;
    this.indexType = (m.indices instanceof Uint32Array) ? gl.UNSIGNED_INT
                                                        : gl.UNSIGNED_SHORT;
  };

  Batch.prototype.reset = function () { this.count = 0; };

  Batch.prototype.grow = function () {
    var next = new Float32Array(this.data.length * 2);
    next.set(this.data);
    this.data = next;
    this.capacity *= 2;
  };

  Batch.prototype.add = function (px, py, pz, rx, ry, rz, sx, sy, sz,
                                  color, alpha, studs, material, emissive, decal) {
    if (this.count >= this.capacity) this.grow();
    var off = this.count * STRIDE;
    M.compose(this.data, off, px, py, pz, rx, ry, rz, sx, sy, sz);
    this.data[off + 16] = color[0];
    this.data[off + 17] = color[1];
    this.data[off + 18] = color[2];
    this.data[off + 19] = alpha === undefined ? 1 : alpha;
    this.data[off + 20] = studs ? 1 : 0;
    this.data[off + 21] = material || 0;
    this.data[off + 22] = emissive || 0;
    this.data[off + 23] = 0;
    if (decal) {
      this.data[off + 24] = decal.u;
      this.data[off + 25] = decal.v;
      this.data[off + 26] = decal.s;
      this.data[off + 27] = 1;
    } else {
      this.data[off + 24] = 0; this.data[off + 25] = 0;
      this.data[off + 26] = 0; this.data[off + 27] = 0;
    }
    this.count++;
    this.dirty = true;
    return off;
  };

  Batch.prototype.bind = function (staticDraw) {
    var gl = this.gl, p = this.program;
    gl.bindBuffer(gl.ARRAY_BUFFER, this.vbo);
    var stride = 8 * 4;
    gl.enableVertexAttribArray(p.attribs.aPosition);
    gl.vertexAttribPointer(p.attribs.aPosition, 3, gl.FLOAT, false, stride, 0);
    gl.enableVertexAttribArray(p.attribs.aNormal);
    gl.vertexAttribPointer(p.attribs.aNormal, 3, gl.FLOAT, false, stride, 12);
    gl.enableVertexAttribArray(p.attribs.aUV);
    gl.vertexAttribPointer(p.attribs.aUV, 2, gl.FLOAT, false, stride, 24);
    if (p.attribs.aPosition !== undefined) gl.vertexAttribDivisor(p.attribs.aPosition, 0);
    gl.vertexAttribDivisor(p.attribs.aNormal, 0);
    gl.vertexAttribDivisor(p.attribs.aUV, 0);

    gl.bindBuffer(gl.ARRAY_BUFFER, this.buffer);
    if (this.dirty) {
      var view = this.data.subarray(0, this.count * STRIDE);
      gl.bufferData(gl.ARRAY_BUFFER, view,
                    staticDraw ? gl.STATIC_DRAW : gl.DYNAMIC_DRAW);
      this.dirty = false;
    }
    var istride = STRIDE * 4;
    var names = ['aModel0', 'aModel1', 'aModel2', 'aModel3', 'aColor', 'aParams', 'aDecal'];
    for (var i = 0; i < names.length; i++) {
      var loc = p.attribs[names[i]];
      if (loc === undefined || loc < 0) continue;
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, istride, i * 16);
      gl.vertexAttribDivisor(loc, 1);
    }
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.ibo);
  };

  Batch.prototype.draw = function (staticDraw) {
    if (!this.count) return 0;
    this.bind(staticDraw);
    this.gl.drawElementsInstanced(this.gl.TRIANGLES, this.indexCount,
                                  this.indexType, 0, this.count);
    return this.count;
  };

  // ------------------------------------------------------------- Renderer
  function Renderer(canvas, options) {
    options = options || {};
    this.canvas = canvas;
    // A "transparentBackground" renderer skips the sky and clears to alpha 0,
    // which is what the item thumbnails and HUD icons want. (Note: this.transparent
    // is the map of alpha-blended instance batches -- different thing.)
    this.transparentBackground = !!options.transparent;
    if (this.transparentBackground) options.alpha = true;
    var gl = GLX.createContext(canvas, options);
    if (!gl) { this.failed = true; return; }
    this.gl = gl;
    this.program = GLX.compile(gl, VERT, FRAG, 'scene');
    this.skyProgram = GLX.compile(gl, SKY_VERT, SKY_FRAG, 'sky');
    this.tagProgram = GLX.compile(gl, TAG_VERT, TAG_FRAG, 'tag');
    if (!this.program) { this.failed = true; return; }

    Textures.prewarm();
    this.atlas = Textures.uploadAtlas(gl);
    this.atlasVersion = Textures.version;

    this.meshes = Geometry.build();
    this.dynamic = {};
    this.staticBatches = {};
    this.transparent = {};
    var self = this;
    ['box', 'cyl', 'sph', 'cone', 'wedge', 'torus'].forEach(function (name) {
      self.dynamic[name] = new Batch(gl, self.meshes[name], self.program);
      self.staticBatches[name] = new Batch(gl, self.meshes[name], self.program);
      self.transparent[name] = new Batch(gl, self.meshes[name], self.program);
    });

    this.quadBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuffer);
    gl.bufferData(gl.ARRAY_BUFFER,
                  new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    this.tagQuad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.tagQuad);
    gl.bufferData(gl.ARRAY_BUFFER,
                  new Float32Array([-1, -1, 1, -1, 1, 1, -1, -1, 1, 1, -1, 1]),
                  gl.STATIC_DRAW);

    this.view = M.identity();
    this.proj = M.identity();
    this.viewProj = M.identity();
    this.invViewProj = M.identity();
    this.eye = [0, 10, 0];
    this.time = 0;
    this.fov = 75;
    this.near = 0.35;
    this.far = 900;
    this.sky = { top: '#6fa8dc', horizon: '#cfe3f5', sun: [0.4, 0.72, 0.35],
                 clouds: 0.55, tint: '#ffffff' };
    this.fogColor = [0.81, 0.89, 0.96];
    this.sunColor = [1.0, 0.97, 0.88];
    this.skyAmbient = [0.42, 0.47, 0.55];
    this.groundAmbient = [0.17, 0.19, 0.17];
    this.pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    this.renderScale = options.renderScale || 1;
    this.stats = { instances: 0, draws: 0 };
    this.tagCache = {};
    this.resize();
  }

  Renderer.MATERIALS = { plastic: 0, metal: 1, neon: 2, glass: 3, grass: 4, wood: 0 };

  Renderer.prototype.resize = function () {
    var canvas = this.canvas;
    var scale = this.pixelRatio * this.renderScale;
    var width = Math.max(1, Math.floor((canvas.clientWidth || canvas.width) * scale));
    var height = Math.max(1, Math.floor((canvas.clientHeight || canvas.height) * scale));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    this.width = width;
    this.height = height;
    this.aspect = width / Math.max(1, height);
  };

  Renderer.prototype.setSky = function (sky) {
    if (!sky) return;
    this.sky = {
      top: sky.top || '#6fa8dc',
      horizon: sky.horizon || '#cfe3f5',
      sun: sky.sun || [0.4, 0.72, 0.35],
      clouds: sky.clouds === undefined ? 0.55 : sky.clouds,
      tint: sky.tint || '#ffffff'
    };
    this.fogColor = M.hexToRgb(this.sky.horizon);
    var top = M.hexToRgb(this.sky.top);
    this.skyAmbient = [top[0] * 0.40 + 0.16, top[1] * 0.40 + 0.16, top[2] * 0.40 + 0.18];
  };

  Renderer.prototype.setAmbient = function (hex) {
    var c = M.hexToRgb(hex);
    this.groundAmbient = [c[0] * 0.30, c[1] * 0.30, c[2] * 0.30];
  };

  Renderer.prototype.setCamera = function (eye, yaw, pitch, fov) {
    this.eye = eye;
    this.fov = fov || this.fov;
    var cp = Math.cos(pitch);
    var target = [
      eye[0] + Math.sin(yaw) * cp,
      eye[1] + Math.sin(pitch),
      eye[2] + Math.cos(yaw) * cp
    ];
    M.lookAt(this.view, eye, target, [0, 1, 0]);
    M.perspective(this.proj, this.fov * M.toRad, this.aspect, this.near, this.far);
    M.multiply(this.viewProj, this.proj, this.view);
    M.invert(this.invViewProj, this.viewProj);
    // Screen basis: right = normalize(forward x worldUp), up = right x forward.
    this.forward = [target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]];
    this.right = [-Math.cos(yaw), 0, Math.sin(yaw)];
    this.up = [
      this.right[1] * this.forward[2] - this.right[2] * this.forward[1],
      this.right[2] * this.forward[0] - this.right[0] * this.forward[2],
      this.right[0] * this.forward[1] - this.right[1] * this.forward[0]
    ];
    var upLen = Math.hypot(this.up[0], this.up[1], this.up[2]) || 1;
    this.up = [this.up[0] / upLen, this.up[1] / upLen, this.up[2] / upLen];
  };

  Renderer.prototype.setCameraMatrix = function (eye, target, fov) {
    this.eye = eye;
    this.fov = fov || this.fov;
    M.lookAt(this.view, eye, target, [0, 1, 0]);
    M.perspective(this.proj, this.fov * M.toRad, this.aspect, this.near, this.far);
    M.multiply(this.viewProj, this.proj, this.view);
    M.invert(this.invViewProj, this.viewProj);
    // Billboards (particles, name tags) need the screen basis too.
    var fx = target[0] - eye[0], fy = target[1] - eye[1], fz = target[2] - eye[2];
    var flen = Math.hypot(fx, fy, fz) || 1;
    this.forward = [fx / flen, fy / flen, fz / flen];
    var rx = -this.forward[2], rz = this.forward[0];
    var rlen = Math.hypot(rx, rz) || 1;
    this.right = [rx / rlen, 0, rz / rlen];
    this.up = [
      this.right[1] * this.forward[2] - this.right[2] * this.forward[1],
      this.right[2] * this.forward[0] - this.right[0] * this.forward[2],
      this.right[0] * this.forward[1] - this.right[1] * this.forward[0]
    ];
  };

  /* Convert a server "part" dict into an instance in the given batch set. */
  Renderer.prototype.addPart = function (batches, part, offset) {
    var kind = part.t || 'box';
    var batch = batches[kind] || batches.box;
    var p = part.p, s = part.s, r = part.r;
    var ox = offset ? offset[0] : 0, oy = offset ? offset[1] : 0, oz = offset ? offset[2] : 0;
    var decal = part.decSlot || (part.dec ? Textures.decal(part.dec) : null);
    var material = Renderer.MATERIALS[part.m] || 0;
    return batch.add(p[0] + ox, p[1] + oy, p[2] + oz,
                     r ? r[0] : 0, r ? r[1] : 0, r ? r[2] : 0,
                     s[0], s[1], s[2],
                     M.hexToRgb(part.c), part.a === undefined ? 1 : part.a,
                     part.st, material, 0, decal);
  };

  Renderer.prototype.buildStatic = function (parts) {
    var self = this;
    Object.keys(this.staticBatches).forEach(function (k) {
      self.staticBatches[k].reset();
    });
    Object.keys(this.transparent).forEach(function (k) {
      self.transparent[k].reset();
    });
    this.staticParts = parts;
    parts.forEach(function (part) {
      var target = (part.a !== undefined && part.a < 0.999)
        ? self.transparent : self.staticBatches;
      self.addPart(target, part);
    });
    this.refreshAtlas();
  };

  Renderer.prototype.appendStatic = function (parts) {
    var self = this;
    parts.forEach(function (part) {
      var target = (part.a !== undefined && part.a < 0.999)
        ? self.transparent : self.staticBatches;
      self.addPart(target, part);
    });
    this.refreshAtlas();
  };

  Renderer.prototype.refreshAtlas = function () {
    if (Textures.version !== this.atlasVersion) {
      Textures.uploadAtlas(this.gl, this.atlas);
      this.atlasVersion = Textures.version;
    }
  };

  Renderer.prototype.beginFrame = function (dt) {
    this.time += dt || 0;
    var self = this;
    Object.keys(this.dynamic).forEach(function (k) { self.dynamic[k].reset(); });
    this.tagQueue = [];
    this.stats.instances = 0;
    this.stats.draws = 0;
  };

  Renderer.prototype.push = function (part, offset) {
    return this.addPart(this.dynamic, part, offset);
  };

  Renderer.prototype.pushRaw = function (kind, px, py, pz, rx, ry, rz, sx, sy, sz,
                                         color, alpha, studs, material, emissive, decal) {
    var batch = this.dynamic[kind] || this.dynamic.box;
    return batch.add(px, py, pz, rx, ry, rz, sx, sy, sz, color, alpha, studs,
                     material, emissive, decal);
  };

  Renderer.prototype.queueTag = function (key, text, colour, sub, position, scale) {
    var entry = this.tagCache[key];
    if (!entry || entry.text !== text || entry.sub !== sub || entry.colour !== colour) {
      if (entry && entry.tex) this.gl.deleteTexture(entry.tex.texture);
      var tex = Textures.nameTag(this.gl, text, colour, sub);
      entry = { text: text, sub: sub, colour: colour, tex: tex };
      this.tagCache[key] = entry;
    }
    this.tagQueue.push({ tex: entry.tex, p: position, scale: scale || 1 });
  };

  Renderer.prototype.dropTag = function (key) {
    var entry = this.tagCache[key];
    if (entry && entry.tex) {
      this.gl.deleteTexture(entry.tex.texture);
      delete this.tagCache[key];
    }
  };

  Renderer.prototype.drawSky = function () {
    if (!this.skyProgram) return;
    var gl = this.gl, p = this.skyProgram;
    gl.useProgram(p);
    gl.disable(gl.DEPTH_TEST);
    gl.depthMask(false);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.quadBuffer);
    gl.enableVertexAttribArray(p.attribs.aQuad);
    gl.vertexAttribDivisor(p.attribs.aQuad, 0);
    gl.vertexAttribPointer(p.attribs.aQuad, 2, gl.FLOAT, false, 0, 0);
    gl.uniformMatrix4fv(p.uniforms.uInvViewProj, false, this.invViewProj);
    gl.uniform3fv(p.uniforms.uEye, this.eye);
    gl.uniform3fv(p.uniforms.uTop, M.hexToRgb(this.sky.top));
    gl.uniform3fv(p.uniforms.uHorizon, M.hexToRgb(this.sky.horizon));
    gl.uniform3fv(p.uniforms.uSunDir, this.sky.sun);
    gl.uniform3fv(p.uniforms.uTint, M.hexToRgb(this.sky.tint));
    gl.uniform1f(p.uniforms.uClouds, this.sky.clouds);
    gl.uniform1f(p.uniforms.uTime, this.time);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.enable(gl.DEPTH_TEST);
    gl.depthMask(true);
  };

  Renderer.prototype.drawScene = function () {
    var gl = this.gl, p = this.program, self = this;
    gl.useProgram(p);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.atlas);
    gl.uniform1i(p.uniforms.uAtlas, 0);
    gl.uniformMatrix4fv(p.uniforms.uViewProj, false, this.viewProj);
    gl.uniform3fv(p.uniforms.uSunDir, this.sky.sun);
    gl.uniform3fv(p.uniforms.uSunColor, this.sunColor);
    gl.uniform3fv(p.uniforms.uSkyColor, this.skyAmbient);
    gl.uniform3fv(p.uniforms.uGroundColor, this.groundAmbient);
    gl.uniform3fv(p.uniforms.uFogColor, this.fogColor);
    gl.uniform3fv(p.uniforms.uEye, this.eye);
    gl.uniform1f(p.uniforms.uFogFar, this.far);
    gl.uniform1f(p.uniforms.uTime, this.time);

    gl.enable(gl.CULL_FACE);
    gl.cullFace(gl.BACK);
    gl.disable(gl.BLEND);
    Object.keys(this.staticBatches).forEach(function (k) {
      self.stats.instances += self.staticBatches[k].draw(true);
      if (self.staticBatches[k].count) self.stats.draws++;
    });
    Object.keys(this.dynamic).forEach(function (k) {
      self.stats.instances += self.dynamic[k].draw(false);
      if (self.dynamic[k].count) self.stats.draws++;
    });
    // transparent last, no depth write
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.depthMask(false);
    Object.keys(this.transparent).forEach(function (k) {
      self.stats.instances += self.transparent[k].draw(true);
      if (self.transparent[k].count) self.stats.draws++;
    });
    gl.depthMask(true);
  };

  Renderer.prototype.drawTags = function () {
    if (!this.tagQueue || !this.tagQueue.length || !this.tagProgram) return;
    var gl = this.gl, p = this.tagProgram;
    gl.useProgram(p);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.depthMask(false);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.tagQuad);
    gl.enableVertexAttribArray(p.attribs.aQuad);
    gl.vertexAttribDivisor(p.attribs.aQuad, 0);
    gl.vertexAttribPointer(p.attribs.aQuad, 2, gl.FLOAT, false, 0, 0);
    gl.uniformMatrix4fv(p.uniforms.uViewProj, false, this.viewProj);
    var camUp = [0, 1, 0];
    var fwd = this.forward || [0, 0, 1];
    var flen = Math.hypot(fwd[0], fwd[1], fwd[2]) || 1;
    var rx = -fwd[2] / flen, rz = fwd[0] / flen;
    gl.uniform3f(p.uniforms.uRight, rx, 0, rz);
    gl.uniform3fv(p.uniforms.uUp, camUp);
    gl.activeTexture(gl.TEXTURE0);
    for (var i = 0; i < this.tagQueue.length; i++) {
      var tag = this.tagQueue[i];
      gl.bindTexture(gl.TEXTURE_2D, tag.tex.texture);
      gl.uniform1i(p.uniforms.uTex, 0);
      gl.uniform3fv(p.uniforms.uCenter, tag.p);
      var h = tag.scale;
      gl.uniform2f(p.uniforms.uSize, h * tag.tex.aspect, h);
      gl.uniform1f(p.uniforms.uOpacity, tag.opacity === undefined ? 1 : tag.opacity);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    }
    gl.depthMask(true);
  };

  Renderer.prototype.clear = function () {
    var gl = this.gl;
    gl.viewport(0, 0, this.width, this.height);
    if (this.transparentBackground) gl.clearColor(0, 0, 0, 0);
    else gl.clearColor(this.fogColor[0], this.fogColor[1], this.fogColor[2], 1);
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  };

  Renderer.prototype.render = function () {
    this.clear();
    if (!this.transparentBackground) this.drawSky();
    this.drawScene();
    this.drawTags();
  };

  Renderer.STRIDE = STRIDE;
  Renderer.Batch = Batch;
  global.Renderer = Renderer;
})(window);
