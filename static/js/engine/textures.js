/* BLOCKHAVEN engine -- every texture in the project is drawn at runtime on a
   2D canvas, so the whole platform ships without a single image asset. */
(function (global) {
  'use strict';

  var CELL = 128;
  var GRID = 8;                 // 8x8 cells -> 1024x1024 atlas
  var SIZE = CELL * GRID;

  var Textures = {
    atlasCanvas: null,
    slots: {},                  // name -> {u, v, s}
    nextSlot: 1,                // slot 0 is a plain white square
    version: 0
  };

  function ensureCanvas() {
    if (Textures.atlasCanvas) return Textures.atlasCanvas;
    var canvas = document.createElement('canvas');
    canvas.width = SIZE;
    canvas.height = SIZE;
    var ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, SIZE, SIZE);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, CELL, CELL);
    Textures.atlasCanvas = canvas;
    Textures.ctx = ctx;
    return canvas;
  }

  function allocate(name) {
    if (Textures.slots[name]) return Textures.slots[name];
    var index = Textures.nextSlot++;
    if (index >= GRID * GRID) { index = 0; }
    var cx = (index % GRID), cy = Math.floor(index / GRID);
    var slot = { u: cx / GRID, v: cy / GRID, s: 1 / GRID, x: cx * CELL, y: cy * CELL,
                 index: index };
    Textures.slots[name] = slot;
    return slot;
  }

  function cellContext(slot, background) {
    ensureCanvas();
    var ctx = Textures.ctx;
    ctx.save();
    ctx.beginPath();
    ctx.rect(slot.x, slot.y, CELL, CELL);
    ctx.clip();
    ctx.clearRect(slot.x, slot.y, CELL, CELL);
    if (background) {
      ctx.fillStyle = background;
      ctx.fillRect(slot.x, slot.y, CELL, CELL);
    }
    ctx.translate(slot.x, slot.y);
    return ctx;
  }

  // --------------------------------------------------------------- faces
  Textures.drawFace = function (name, shapes) {
    var key = 'face:' + name;
    if (Textures.slots[key]) return Textures.slots[key];
    var slot = allocate(key);
    var ctx = cellContext(slot, null);
    var cx = CELL / 2, cy = CELL / 2, S = CELL;
    (shapes || []).forEach(function (shape) {
      ctx.save();
      ctx.fillStyle = shape.c || '#1a1a1a';
      ctx.strokeStyle = shape.c || '#1a1a1a';
      var x = cx + (shape.x || 0) * S;
      var y = cy + (shape.y || 0) * S;
      if (shape.k === 'ellipse') {
        ctx.beginPath();
        ctx.ellipse(x, y, (shape.w || 0.1) * S / 2, (shape.h || 0.1) * S / 2, 0, 0, Math.PI * 2);
        ctx.fill();
      } else if (shape.k === 'rect') {
        ctx.translate(x, y);
        if (shape.rot) ctx.rotate(shape.rot);
        ctx.fillRect(-(shape.w || 0.1) * S / 2, -(shape.h || 0.1) * S / 2,
                     (shape.w || 0.1) * S, (shape.h || 0.1) * S);
      } else if (shape.k === 'arc') {
        ctx.beginPath();
        ctx.lineWidth = (shape.w || 0.05) * S;
        ctx.lineCap = 'round';
        ctx.arc(x, y, (shape.r || 0.2) * S,
                (shape.a0 || 0) * Math.PI * 2, (shape.a1 || 1) * Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
    });
    ctx.restore();
    Textures.version++;
    return slot;
  };

  // -------------------------------------------------------------- decals
  var decalPainters = {};

  function painter(name, fn) { decalPainters[name] = fn; }

  painter('letter_R', function (ctx) {
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, CELL, CELL);
    ctx.fillStyle = '#c4281c';
    ctx.font = 'bold 104px Verdana, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('R', CELL / 2, CELL / 2 + 4);
  });

  painter('skull', function (ctx) {
    ctx.fillStyle = '#1b1b1b'; ctx.fillRect(0, 0, CELL, CELL);
    ctx.fillStyle = '#f2f3f3';
    ctx.beginPath(); ctx.ellipse(64, 54, 34, 30, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillRect(48, 76, 32, 18);
    ctx.fillStyle = '#1b1b1b';
    ctx.beginPath(); ctx.ellipse(52, 50, 9, 11, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(76, 50, 9, 11, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillRect(58, 66, 12, 10);
    ctx.fillStyle = '#f2f3f3';
    for (var i = 0; i < 3; i++) ctx.fillRect(50 + i * 12, 86, 8, 12);
  });

  function banner(colour, dark) {
    return function (ctx) {
      ctx.fillStyle = colour; ctx.fillRect(0, 0, CELL, CELL);
      ctx.fillStyle = dark;
      ctx.beginPath();
      ctx.moveTo(0, 0); ctx.lineTo(CELL, 0); ctx.lineTo(CELL, 96);
      ctx.lineTo(64, 120); ctx.lineTo(0, 96); ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#f7e9c0';
      ctx.beginPath();
      ctx.moveTo(64, 24); ctx.lineTo(92, 46); ctx.lineTo(82, 84);
      ctx.lineTo(46, 84); ctx.lineTo(36, 46); ctx.closePath(); ctx.fill();
      ctx.fillStyle = colour;
      ctx.beginPath(); ctx.arc(64, 60, 15, 0, Math.PI * 2); ctx.fill();
    };
  }
  painter('banner_red', banner('#c4281c', '#8c1c15'));
  painter('banner_blue', banner('#0d69ac', '#0a3c69'));

  painter('burger', function (ctx) {
    ctx.clearRect(0, 0, CELL, CELL);
    ctx.fillStyle = '#e0a94e';
    ctx.beginPath(); ctx.ellipse(64, 44, 46, 26, 0, Math.PI, 0); ctx.fill();
    ctx.fillStyle = '#f2e2b0';
    for (var i = 0; i < 7; i++) {
      ctx.beginPath();
      ctx.ellipse(30 + i * 11, 32 + (i % 2) * 5, 3, 2, 0, 0, Math.PI * 2); ctx.fill();
    }
    ctx.fillStyle = '#5aa84f'; ctx.fillRect(16, 52, 96, 9);
    ctx.fillStyle = '#7c4a2a'; ctx.fillRect(18, 61, 92, 16);
    ctx.fillStyle = '#f5c518'; ctx.fillRect(20, 77, 88, 8);
    ctx.fillStyle = '#e0a94e';
    ctx.beginPath(); ctx.ellipse(64, 88, 46, 18, 0, 0, Math.PI); ctx.fill();
  });

  painter('logo_block', function (ctx) {
    ctx.clearRect(0, 0, CELL, CELL);
    ctx.fillStyle = '#f2f3f3'; ctx.fillRect(40, 40, 48, 48);
    ctx.fillStyle = '#b8b8b8'; ctx.fillRect(48, 48, 32, 32);
    ctx.fillStyle = '#8f9296'; ctx.fillRect(56, 56, 16, 16);
  });

  painter('tux', function (ctx) {
    ctx.clearRect(0, 0, CELL, CELL);
    ctx.fillStyle = '#f2f3f3';
    ctx.beginPath(); ctx.moveTo(46, 0); ctx.lineTo(82, 0); ctx.lineTo(64, 40);
    ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#1b2a35';
    ctx.beginPath(); ctx.moveTo(64, 34); ctx.lineTo(50, 46); ctx.lineTo(64, 54);
    ctx.lineTo(78, 46); ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#c4281c';
    ctx.beginPath(); ctx.moveTo(52, 28); ctx.lineTo(76, 28); ctx.lineTo(64, 42);
    ctx.closePath(); ctx.fill();
    ctx.fillStyle = '#dcdcdc';
    ctx.fillRect(60, 60, 8, 8); ctx.fillRect(60, 84, 8, 8);
  });

  painter('chevron', function (ctx) {
    ctx.clearRect(0, 0, CELL, CELL);
    ctx.strokeStyle = '#e0c060'; ctx.lineWidth = 10;
    for (var i = 0; i < 3; i++) {
      ctx.beginPath();
      ctx.moveTo(30, 40 + i * 22); ctx.lineTo(64, 62 + i * 22); ctx.lineTo(98, 40 + i * 22);
      ctx.stroke();
    }
  });

  painter('flowers', function (ctx) {
    ctx.clearRect(0, 0, CELL, CELL);
    var colours = ['#ffd166', '#ef476f', '#06d6a0', '#f7f7f7'];
    for (var i = 0; i < 12; i++) {
      var x = 14 + (i * 37) % 104, y = 16 + ((i * 53) % 96);
      ctx.fillStyle = colours[i % colours.length];
      for (var k = 0; k < 5; k++) {
        var a = (k / 5) * Math.PI * 2;
        ctx.beginPath();
        ctx.ellipse(x + Math.cos(a) * 6, y + Math.sin(a) * 6, 4, 4, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = '#ffe066';
      ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fill();
    }
  });

  painter('sigil', function (ctx) {
    ctx.clearRect(0, 0, CELL, CELL);
    ctx.strokeStyle = '#c78bff'; ctx.lineWidth = 4;
    ctx.beginPath(); ctx.arc(64, 64, 40, 0, Math.PI * 2); ctx.stroke();
    ctx.beginPath();
    for (var i = 0; i < 5; i++) {
      var a = -Math.PI / 2 + (i * 4 * Math.PI * 2) / 5;
      var x = 64 + Math.cos(a) * 36, y = 64 + Math.sin(a) * 36;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath(); ctx.stroke();
  });

  painter('hazard', function (ctx) {
    ctx.fillStyle = '#f2b01e'; ctx.fillRect(0, 0, CELL, CELL);
    ctx.fillStyle = '#1b1b1b';
    for (var i = -CELL; i < CELL * 2; i += 32) {
      ctx.beginPath();
      ctx.moveTo(i, 0); ctx.lineTo(i + 16, 0); ctx.lineTo(i + 16 - CELL, CELL);
      ctx.lineTo(i - CELL, CELL); ctx.closePath(); ctx.fill();
    }
  });

  function teamSign(label, colour) {
    return function (ctx) {
      ctx.fillStyle = '#f2f3f3'; ctx.fillRect(0, 0, CELL, CELL);
      ctx.fillStyle = colour; ctx.fillRect(0, 34, CELL, 60);
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 34px Verdana, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(label, CELL / 2, 64);
      ctx.fillStyle = '#1b2a35';
      ctx.font = 'bold 14px Verdana, sans-serif';
      ctx.fillText('SPAWN', CELL / 2, 108);
    };
  }
  painter('sign_red', teamSign('RED', '#b8383b'));
  painter('sign_blue', teamSign('BLU', '#5885a2'));

  painter('sign_tycoon', function (ctx) {
    ctx.fillStyle = '#f2b01e'; ctx.fillRect(0, 0, CELL, CELL);
    ctx.fillStyle = '#8c1c15';
    ctx.font = 'bold 22px Verdana, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('PATTY', CELL / 2, 48);
    ctx.fillText('PLAINS', CELL / 2, 78);
  });

  Textures.drawText = function (key, text, background, colour, fontSize) {
    if (Textures.slots['text:' + key]) return Textures.slots['text:' + key];
    var slot = allocate('text:' + key);
    var ctx = cellContext(slot, background || '#f2f3f3');
    ctx.fillStyle = colour || '#1b2a35';
    ctx.font = 'bold ' + (fontSize || 20) + 'px Verdana, sans-serif';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    var words = String(text).split(' ');
    var lines = [];
    var line = '';
    words.forEach(function (w) {
      var test = line ? line + ' ' + w : w;
      if (ctx.measureText(test).width > CELL - 10 && line) { lines.push(line); line = w; }
      else line = test;
    });
    if (line) lines.push(line);
    var startY = CELL / 2 - ((lines.length - 1) * (fontSize || 20)) / 2;
    lines.forEach(function (l, i) {
      ctx.fillText(l, CELL / 2, startY + i * (fontSize || 20) * 1.05);
    });
    ctx.restore();
    Textures.version++;
    return slot;
  };

  Textures.decal = function (name) {
    if (!name) return null;
    var key = 'decal:' + name;
    if (Textures.slots[key]) return Textures.slots[key];
    var fn = decalPainters[name];
    if (!fn) {
      if (/^plot_\d+$/.test(name)) {
        return Textures.drawText(name, 'PLOT ' + (parseInt(name.slice(5), 10) + 1),
                                 '#ffffff', '#1b2a35', 26);
      }
      return null;
    }
    var slot = allocate(key);
    var ctx = cellContext(slot, null);
    fn(ctx);
    ctx.restore();
    Textures.version++;
    return slot;
  };

  Textures.faceSlot = function (itemId, data) {
    if (!itemId) return null;
    if (Textures.slots['face:' + itemId]) return Textures.slots['face:' + itemId];
    if (!data || !data.shapes) return null;
    return Textures.drawFace(itemId, data.shapes);
  };

  Textures.prewarm = function () {
    ensureCanvas();
    Object.keys(decalPainters).forEach(function (name) { Textures.decal(name); });
  };

  /* Name tags are their own little textures (one per player) rather than
     atlas cells, so long names stay sharp. */
  Textures.nameTag = function (gl, text, colour, sub) {
    var pad = 10;
    var canvas = document.createElement('canvas');
    var ctx = canvas.getContext('2d');
    ctx.font = 'bold 34px Verdana, sans-serif';
    var width = Math.ceil(ctx.measureText(text).width) + pad * 2;
    canvas.width = Math.max(64, width);
    canvas.height = sub ? 74 : 52;
    ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'rgba(10,16,24,0.55)';
    var r = 8;
    ctx.beginPath();
    ctx.moveTo(r, 0); ctx.lineTo(canvas.width - r, 0);
    ctx.quadraticCurveTo(canvas.width, 0, canvas.width, r);
    ctx.lineTo(canvas.width, canvas.height - r);
    ctx.quadraticCurveTo(canvas.width, canvas.height, canvas.width - r, canvas.height);
    ctx.lineTo(r, canvas.height); ctx.quadraticCurveTo(0, canvas.height, 0, canvas.height - r);
    ctx.lineTo(0, r); ctx.quadraticCurveTo(0, 0, r, 0);
    ctx.fill();
    ctx.font = 'bold 34px Verdana, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineWidth = 5;
    ctx.strokeStyle = 'rgba(0,0,0,0.85)';
    ctx.strokeText(text, canvas.width / 2, 26);
    ctx.fillStyle = colour || '#ffffff';
    ctx.fillText(text, canvas.width / 2, 26);
    if (sub) {
      ctx.font = 'bold 18px Verdana, sans-serif';
      ctx.fillStyle = '#e8f4ff';
      ctx.strokeText(sub, canvas.width / 2, 58);
      ctx.fillText(sub, canvas.width / 2, 58);
    }
    var texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, canvas);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    return { texture: texture, width: canvas.width, height: canvas.height,
             aspect: canvas.width / canvas.height };
  };

  Textures.uploadAtlas = function (gl, existing) {
    ensureCanvas();
    var texture = existing || gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE,
                  Textures.atlasCanvas);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.generateMipmap(gl.TEXTURE_2D);
    return texture;
  };

  Textures.CELL = CELL;
  Textures.GRID = GRID;
  global.Textures = Textures;
})(window);
