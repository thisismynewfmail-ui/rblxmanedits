/* BLOCKHAVEN site -- 3D previews.
   One hidden WebGL canvas renders every item icon, avatar thumbnail and world
   preview on the page, then blits the result into the visible 2D canvases. */
(function (global) {
  'use strict';

  var Thumbs = {
    ready: false,
    catalog: null,
    avatarCache: {},
    imageCache: {},
    queue: [],
    working: false
  };

  var OFFSCREEN = 256;

  function ensureRenderer() {
    if (Thumbs.renderer || Thumbs.failed) return Thumbs.renderer;
    var canvas = document.createElement('canvas');
    canvas.width = OFFSCREEN;
    canvas.height = OFFSCREEN;
    canvas.style.position = 'absolute';
    canvas.style.left = '-10000px';
    document.body.appendChild(canvas);
    var renderer = new Renderer(canvas, { preserveDrawingBuffer: true,
                                          antialias: true, transparent: true });
    if (renderer.failed) { Thumbs.failed = true; return null; }
    renderer.renderScale = 1;
    renderer.pixelRatio = 1;
    renderer.resize();
    renderer.far = 400;
    renderer.setSky({ top: '#a8cdea', horizon: '#f0f6fb', sun: [0.4, 0.8, 0.4],
                      clouds: 0.0, tint: '#ffffff' });
    renderer.fogColor = [0.94, 0.96, 0.98];
    Thumbs.renderer = renderer;
    Thumbs.particles = new Particles(renderer.gl);
    return renderer;
  }

  function fetchJSON(url) {
    return fetch(url, { headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.json(); });
  }

  Thumbs.loadCatalog = function () {
    if (Thumbs.catalogPromise) return Thumbs.catalogPromise;
    Thumbs.catalogPromise = fetchJSON('/api/catalog').then(function (data) {
      Thumbs.catalog = {};
      (data.items || []).forEach(function (item) { Thumbs.catalog[item.id] = item; });
      Thumbs.tiers = data.tiers || {};
      Thumbs.effects = data.effects || {};
      Thumbs.palette = data.palette || [];
      return Thumbs.catalog;
    }).catch(function () { Thumbs.catalog = {}; return {}; });
    return Thumbs.catalogPromise;
  };

  Thumbs.loadAvatar = function (username) {
    if (Thumbs.avatarCache[username]) return Promise.resolve(Thumbs.avatarCache[username]);
    return fetchJSON('/api/avatar/' + encodeURIComponent(username))
      .then(function (data) {
        Thumbs.avatarCache[username] = data.avatar || null;
        return data.avatar;
      }).catch(function () { return null; });
  };

  function frameCamera(renderer, parts, padding, angle, tilt) {
    var min = [1e9, 1e9, 1e9], max = [-1e9, -1e9, -1e9];
    parts.forEach(function (part) {
      for (var i = 0; i < 3; i++) {
        min[i] = Math.min(min[i], part.p[i] - part.s[i] * 0.75);
        max[i] = Math.max(max[i], part.p[i] + part.s[i] * 0.75);
      }
    });
    if (min[0] > max[0]) { min = [-1, -1, -1]; max = [1, 1, 1]; }
    var centre = [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2];
    var radius = Math.max(
      max[0] - min[0], Math.max(max[1] - min[1], max[2] - min[2])) * 0.5;
    radius = Math.max(radius, 0.6) * (padding || 1.9);
    angle = angle === undefined ? -0.55 : angle;
    tilt = tilt === undefined ? 0.28 : tilt;
    var eye = [
      centre[0] + Math.sin(angle) * radius * 1.6,
      centre[1] + Math.sin(tilt) * radius * 1.6,
      centre[2] + Math.cos(angle) * radius * 1.6
    ];
    renderer.setCameraMatrix(eye, centre, 40);
    return { centre: centre, radius: radius };
  }

  function renderParts(parts, options) {
    var renderer = ensureRenderer();
    if (!renderer) return null;
    options = options || {};
    renderer.setSky(options.sky || { top: '#bcdcf5', horizon: '#f4f9fc',
                                     sun: [0.45, 0.8, 0.35], clouds: 0, tint: '#ffffff' });
    renderer.buildStatic([]);
    renderer.beginFrame(0.016);
    parts.forEach(function (part) { renderer.push(part); });
    frameCamera(renderer, parts, options.padding, options.angle, options.tilt);
    if (options.effect && Thumbs.particles && Thumbs.effects) {
      var def = Thumbs.effects[options.effect];
      if (def) {
        Thumbs.particles.count = 0;
        Thumbs.particles.emitters = {};
        var anchor = options.anchor || [0, 0, 0];
        for (var step = 0; step < 90; step++) {
          Thumbs.particles.setEmitter('thumb', def, anchor);
          Thumbs.particles.update(1 / 60);
        }
      }
    }
    renderer.render();
    if (options.effect && Thumbs.particles) Thumbs.particles.draw(renderer);
    return renderer.canvas;
  }

  function blit(target, source) {
    var ctx = target.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, target.width, target.height);
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(source, 0, 0, target.width, target.height);
  }

  // ------------------------------------------------------------ item icons
  Thumbs.itemParts = function (item, effect) {
    var slot = item.slot;
    var data = item.data || {};
    if (slot === 'hat' || slot === 'back') {
      var parts = (data.parts || []).map(function (piece) {
        return { t: piece.t || 'box', p: piece.p.slice(), s: piece.s.slice(),
                 c: piece.c, r: piece.r, m: piece.m, a: piece.a,
                 decSlot: piece.decal ? Textures.decal(piece.decal) : null };
      });
      if (!parts.length) parts.push({ t: 'box', p: [0, 0, 0], s: [1, 1, 1], c: '#c8cbcd' });
      return { parts: parts, angle: -0.62, tilt: 0.15, padding: 1.55,
               anchor: [0, 0.35, 0] };
    }
    if (slot === 'usable') {
      var weaponParts = (data.parts || []).map(function (piece) {
        return { t: piece.t || 'box', p: piece.p.slice(), s: piece.s.slice(),
                 c: piece.c, r: piece.r, m: piece.m };
      });
      return { parts: weaponParts, angle: -1.15, tilt: 0.42, padding: 1.5 };
    }
    // wearable clothing/faces are shown on a mannequin
    var descriptor = {
      colors: { head: '#f5cd30', torso: '#c8cbcd', left_arm: '#f5cd30',
                right_arm: '#f5cd30', left_leg: '#a3a2a5', right_leg: '#a3a2a5' },
      items: {}
    };
    descriptor.items[slot] = { item_id: item.id, slot: slot, data: data,
                               tier: 'normal' };
    if (slot !== 'face') {
      descriptor.items.face = { item_id: 'face_smile', slot: 'face',
                                data: (Thumbs.catalog.face_smile || {}).data };
    }
    var faceOn = slot === 'face';
    var body = Avatar.build(descriptor, { position: [0, 0, 0],
                                          yaw: faceOn ? 0 : 0.4,
                                          pose: Avatar.pose('idle', 0, 0) });
    if (faceOn) {
      return { parts: body.filter(function (p) { return p.p[1] > 3.9; }),
               angle: 0.0, tilt: 0.04, padding: 1.35 };
    }
    return { parts: body, angle: -0.45, tilt: 0.18, padding: 1.35 };
  };

  Thumbs.renderItem = function (canvas, itemId, effect) {
    Thumbs.loadCatalog().then(function (catalog) {
      var item = catalog[itemId];
      if (!item) return;
      var key = 'item:' + itemId + ':' + (effect || '');
      if (Thumbs.imageCache[key]) { blit(canvas, Thumbs.imageCache[key]); return; }
      var spec = Thumbs.itemParts(item, effect);
      var source = renderParts(spec.parts, {
        angle: spec.angle, tilt: spec.tilt, padding: spec.padding,
        effect: effect, anchor: spec.anchor
      });
      if (!source) return;
      var copy = document.createElement('canvas');
      copy.width = OFFSCREEN; copy.height = OFFSCREEN;
      copy.getContext('2d').drawImage(source, 0, 0);
      Thumbs.imageCache[key] = copy;
      blit(canvas, copy);
    });
  };

  Thumbs.renderAvatarFor = function (canvas, username) {
    var key = 'avatar:' + username;
    if (Thumbs.imageCache[key]) { blit(canvas, Thumbs.imageCache[key]); return; }
    Promise.all([Thumbs.loadCatalog(), Thumbs.loadAvatar(username)])
      .then(function (results) {
        var descriptor = results[1];
        if (!descriptor) return;
        var parts = Avatar.build(descriptor, {
          position: [0, 0, 0], yaw: 0.35, pose: Avatar.pose('idle', 0, 0)
        });
        var hat = (descriptor.items || {}).hat;
        var source = renderParts(parts, {
          angle: -0.35, tilt: 0.12, padding: 1.28,
          effect: hat && hat.tier === 'unusual' ? hat.effect : '',
          anchor: hat ? Avatar.hatAnchor([0, 0, 0], 0, hat) : null
        });
        if (!source) return;
        var copy = document.createElement('canvas');
        copy.width = OFFSCREEN; copy.height = OFFSCREEN;
        copy.getContext('2d').drawImage(source, 0, 0);
        Thumbs.imageCache[key] = copy;
        blit(canvas, copy);
      });
  };

  // --------------------------------------------------------- world previews
  function worldScene(kind, colors) {
    var parts = [];
    function box(p, s, c, extra) {
      var part = { t: 'box', p: p, s: s, c: c };
      if (extra) { for (var k in extra) part[k] = extra[k]; }
      parts.push(part);
    }
    function tree(x, z, scale, leaf) {
      parts.push({ t: 'cyl', p: [x, 2.4 * scale, z], s: [1.2 * scale, 5 * scale, 1.2 * scale], c: '#7c503a' });
      parts.push({ t: 'sph', p: [x, 6.6 * scale, z], s: [6 * scale, 5.4 * scale, 6 * scale], c: leaf || '#287f47' });
    }
    box([0, -1, 0], [90, 2, 60], colors && colors[0] ? '#5aa84f' : '#5aa84f', { st: 1 });
    if (kind === 'ctf') {
      box([-26, 5, -8], [26, 10, 22], '#c8cbcd', { st: 1 });
      box([-26, 11, -8], [28, 2, 24], '#a3a2a5');
      box([-26, 13.5, -8], [6, 3, 6], '#c4281c');
      box([26, 5, -8], [26, 10, 22], '#c8cbcd', { st: 1 });
      box([26, 11, -8], [28, 2, 24], '#a3a2a5');
      box([26, 13.5, -8], [6, 3, 6], '#0d69ac');
      box([0, 0.2, 0], [12, 0.4, 60], '#d8d8d0');
      box([0, 3, 14], [22, 6, 22], '#a3a2a5', { st: 1 });
      box([-6, 8, 14], [2.4, 10, 2.4], '#c8cbcd');
      box([6, 8, 14], [2.4, 10, 2.4], '#c8cbcd');
      box([0, 13.5, 14], [16, 2, 3], '#c8cbcd');
      tree(-38, 18, 1.1); tree(36, 20, 0.9); tree(-14, 24, 0.8);
    } else if (kind === 'payload') {
      parts[0].c = '#c9b48b';
      box([0, 0.3, 0], [80, 0.6, 8], '#b09a72');
      for (var i = -34; i <= 34; i += 6) {
        box([i, 0.8, 0], [4.4, 0.6, 9], '#5f3d1e');
        box([i, 1.3, -3], [4.4, 0.5, 1], '#8f9296', { m: 'metal' });
        box([i, 1.3, 3], [4.4, 0.5, 1], '#8f9296', { m: 'metal' });
      }
      box([-4, 3.4, 0], [10, 5, 6], '#4a4a4a', { m: 'metal' });
      box([-4, 6.6, 0], [7, 2.4, 5], '#b8383b');
      box([-8.5, 1.6, 3.2], [2.6, 2.6, 1.2], '#22262b', { m: 'metal' });
      box([-8.5, 1.6, -3.2], [2.6, 2.6, 1.2], '#22262b', { m: 'metal' });
      box([28, 6, -16], [26, 12, 18], '#b8383b', { st: 1 });
      box([28, 12.6, -16], [28, 1.6, 20], '#8f2b2e');
      box([-30, 6, 16], [24, 12, 16], '#5885a2', { st: 1 });
      box([-30, 12.6, 16], [26, 1.6, 18], '#3f6580');
      box([12, 4, 18], [12, 8, 12], '#8a5a2b', { st: 1 });
    } else {
      box([-24, 1.2, 4], [40, 2.4, 34], '#cdd0d3', { st: 1 });
      box([-24, 8, -6], [30, 12, 16], '#c98b5e');
      box([-24, 14.6, -6], [33, 2, 19], '#c4281c', { st: 1 });
      box([-24, 18, 2], [18, 5, 1.4], '#f2b01e', { m: 'neon', dec: 'burger' });
      box([-24, 4, 10], [22, 3.4, 3], '#8a5a2b');
      box([-4, 4, 12], [6, 4, 5], '#a8adb2', { m: 'metal' });
      box([24, 1.2, 4], [36, 2.4, 30], '#cdd0d3', { st: 1 });
      box([24, 4, -2], [16, 6, 10], '#8f9296', { m: 'metal' });
      box([0, 0.4, -22], [90, 0.8, 14], '#b9b9b1');
      tree(38, 22, 1.0); tree(-44, 20, 0.9);
      box([6, 2.2, 22], [10, 4.4, 10], '#e2e2da', { st: 1 });
      box([6, 5, 22], [7, 1.6, 7], '#9fd8e8', { m: 'glass', a: 0.8 });
    }
    return parts;
  }

  var WORLD_SKIES = {
    ctf: { top: '#7fb2e5', horizon: '#e8f0f8', sun: [0.35, 0.7, -0.25], clouds: 0.5, tint: '#ffffff' },
    payload: { top: '#e8b46a', horizon: '#f7e4bd', sun: [0.5, 0.55, 0.2], clouds: 0.7, tint: '#ffe9c4' },
    burger: { top: '#8fc4ef', horizon: '#ffeec4', sun: [0.3, 0.75, 0.4], clouds: 0.42, tint: '#fff6e0' }
  };

  Thumbs.renderWorld = function (canvas, kind, colors) {
    var key = 'world:' + kind + ':' + canvas.width;
    if (Thumbs.imageCache[key]) { blit(canvas, Thumbs.imageCache[key]); return; }
    var renderer = ensureRenderer();
    if (!renderer) return;
    var parts = worldScene(kind, colors);
    renderer.transparentBackground = false;
    var previous = { w: renderer.canvas.width, h: renderer.canvas.height };
    renderer.canvas.width = 512;
    renderer.canvas.height = 288;
    renderer.width = 512; renderer.height = 288; renderer.aspect = 512 / 288;
    renderer.setSky(WORLD_SKIES[kind] || WORLD_SKIES.ctf);
    renderer.buildStatic([]);
    renderer.beginFrame(0.016);
    parts.forEach(function (part) { renderer.push(part); });
    renderer.setCameraMatrix([44, 34, 62], [0, 5, -2], 42);
    renderer.render();
    var copy = document.createElement('canvas');
    copy.width = 512; copy.height = 288;
    copy.getContext('2d').drawImage(renderer.canvas, 0, 0);
    Thumbs.imageCache[key] = copy;
    blit(canvas, copy);
    renderer.transparentBackground = true;
    renderer.canvas.width = previous.w;
    renderer.canvas.height = previous.h;
    renderer.width = previous.w; renderer.height = previous.h;
    renderer.aspect = previous.w / previous.h;
  };

  // ------------------------------------------------------- live 3D preview
  function LivePreview(container, descriptor) {
    this.container = container;
    this.descriptor = descriptor;
    this.canvas = document.createElement('canvas');
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    container.insertBefore(this.canvas, container.firstChild);
    this.renderer = new Renderer(this.canvas, { antialias: true });
    if (this.renderer.failed) {
      container.innerHTML = '<div style="padding:20px;text-align:center;color:#6f8095">' +
        'Your browser could not start WebGL, so the 3D preview is unavailable.</div>';
      this.failed = true;
      return;
    }
    this.particles = new Particles(this.renderer.gl);
    this.renderer.setSky({ top: '#bcdcf5', horizon: '#f4f9fc', sun: [0.4, 0.8, 0.35],
                           clouds: 0.18, tint: '#ffffff' });
    this.renderer.far = 200;
    this.angle = -0.45;
    this.tilt = 0.2;
    this.distance = 12.5;
    this.spin = true;
    this.time = 0;
    this.bindInput();
    this.loop = this.loop.bind(this);
    requestAnimationFrame(this.loop);
  }

  LivePreview.prototype.bindInput = function () {
    var self = this;
    var dragging = false, lastX = 0, lastY = 0;
    this.canvas.addEventListener('pointerdown', function (e) {
      dragging = true; lastX = e.clientX; lastY = e.clientY;
      self.spin = false;
      self.canvas.setPointerCapture(e.pointerId);
    });
    this.canvas.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      self.angle -= (e.clientX - lastX) * 0.011;
      self.tilt = Math.max(-0.7, Math.min(0.95, self.tilt + (e.clientY - lastY) * 0.008));
      lastX = e.clientX; lastY = e.clientY;
    });
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(function (name) {
      self.canvas.addEventListener(name, function () { dragging = false; });
    });
    this.canvas.addEventListener('wheel', function (e) {
      e.preventDefault();
      self.distance = Math.max(6, Math.min(26, self.distance + e.deltaY * 0.012));
    }, { passive: false });
  };

  LivePreview.prototype.setDescriptor = function (descriptor) {
    this.descriptor = descriptor;
  };

  LivePreview.prototype.loop = function (now) {
    if (this.failed) return;
    requestAnimationFrame(this.loop);
    if (!this.container.offsetParent && this.container.offsetWidth === 0) return;
    var dt = Math.min(0.05, (now - (this.last || now)) / 1000);
    this.last = now;
    this.time += dt;
    if (this.spin) this.angle += dt * 0.32;
    this.renderer.resize();
    var parts = Avatar.build(this.descriptor, {
      position: [0, 0, 0], yaw: 0, time: this.time,
      pose: Avatar.pose('idle', this.time, 0)
    });
    this.renderer.beginFrame(dt);
    parts.forEach(function (part) { this.renderer.push(part); }, this);
    // simple ground shadow
    this.renderer.pushRaw('cyl', 0, 0.02, 0, 0, 0, 0, 5.2, 0.04, 4.0,
                          [0.35, 0.42, 0.5], 0.32, 0, 0, 0.8, null);
    var centre = [0, 2.9, 0];
    var eye = [
      centre[0] + Math.sin(this.angle) * this.distance,
      centre[1] + Math.sin(this.tilt) * this.distance * 0.85 + 0.6,
      centre[2] + Math.cos(this.angle) * this.distance
    ];
    this.renderer.setCameraMatrix(eye, centre, 42);
    var hat = (this.descriptor.items || {}).hat;
    if (hat && hat.tier === 'unusual' && hat.effect_def) {
      this.particles.setEmitter('hat', hat.effect_def,
                                Avatar.hatAnchor([0, 0, 0], 0, hat));
    } else {
      this.particles.clearEmitter('hat');
    }
    this.particles.update(dt);
    this.renderer.render();
    this.particles.draw(this.renderer);
  };

  Thumbs.LivePreview = LivePreview;

  // ---------------------------------------------------------------- boot
  function observe() {
    var observer = null;
    if (window.IntersectionObserver) {
      observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          observer.unobserve(entry.target);
          paint(entry.target);
        });
      }, { rootMargin: '160px' });
    }
    function schedule(el) {
      if (observer) observer.observe(el);
      else paint(el);
    }
    document.querySelectorAll('canvas.item-thumb[data-item]').forEach(schedule);
    document.querySelectorAll('canvas.avatar-thumb[data-user]').forEach(schedule);
    document.querySelectorAll('canvas.world-shot[data-world]').forEach(schedule);
  }

  function paint(el) {
    if (el.dataset.item !== undefined && el.classList.contains('item-thumb')) {
      if (el.dataset.item) Thumbs.renderItem(el, el.dataset.item, el.dataset.effect);
    } else if (el.dataset.user) {
      Thumbs.renderAvatarFor(el, el.dataset.user);
    } else if (el.dataset.world) {
      Thumbs.renderWorld(el, el.dataset.world, null);
    }
  }

  Thumbs.paint = paint;
  Thumbs.rescan = observe;

  document.addEventListener('DOMContentLoaded', function () {
    if (typeof Renderer === 'undefined') return;
    Thumbs.loadCatalog().then(function () {
      observe();
      document.querySelectorAll('.avatar-view[data-avatar]').forEach(function (el) {
        var descriptor;
        try { descriptor = JSON.parse(el.dataset.avatar); } catch (e) { return; }
        el.__preview = new LivePreview(el, descriptor);
      });
      document.querySelectorAll('.avatar-view[data-avatar-demo]').forEach(function (el) {
        el.__preview = new LivePreview(el, {
          colors: { head: '#f5cd30', torso: '#c4281c', left_arm: '#f5cd30',
                    right_arm: '#f5cd30', left_leg: '#1b2a35', right_leg: '#1b2a35' },
          items: {
            face: { item_id: 'face_smile', slot: 'face',
                    data: (Thumbs.catalog.face_smile || {}).data },
            hat: { item_id: 'hat_red_cap', slot: 'hat', tier: 'unusual',
                   effect: 'burning',
                   effect_def: (Thumbs.effects || {}).burning,
                   data: (Thumbs.catalog.hat_red_cap || {}).data }
          }
        });
      });
    });
  });

  global.Thumbs = Thumbs;
})(window);
