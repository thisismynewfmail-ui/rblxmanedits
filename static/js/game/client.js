/* The Game View client: input, prediction, rendering and message handling. */
(function (global) {
  'use strict';

  var M = GLX.mat;
  var SEND_RATE = 1 / 20;

  function Client() {
    this.world = BH.world;
    this.avatar = BH.avatar;
    this.settings = Settings;
    this.canvas = document.getElementById('view');
    this.renderer = new Renderer(this.canvas, { antialias: true });
    if (this.renderer.failed) {
      document.getElementById('load-msg').innerHTML =
        'This browser could not start WebGL, so the game view cannot run.<br>' +
        '<a href="/worlds" style="color:#ffd95e">Back to the world browser</a>';
      return;
    }
    this.particles = new Particles(this.renderer.gl);
    this.audio = new GameAudio();
    this.audio.setVolume(Settings.volume);
    this.hud = new HUD(this);
    this.net = new Net(this.world.id, BH.instance);
    this.players = {};
    this.projectiles = {};
    this.tracers = [];
    this.state = {};
    this.local = {
      pos: [0, 20, 0], vel: [0, 0, 0], yaw: 0, pitch: 0, grounded: false,
      health: 100, alive: true, anim: 'idle'
    };
    this.myId = 0;
    this.myTeam = '';
    this.myPlot = null;
    this.coins = 0;
    this.slot = 0;
    this.ammo = [0, 0, 0, 0, 0];
    this.reserve = [0, 0, 0, 0, 0];
    this.reloadUntil = 0;
    this.nextFire = 0;
    this.firing = false;
    this.thirdPerson = false;
    this.paused = false;
    this.keys = {};
    this.time = 0;
    this.accumulator = 0;
    this.sendTimer = 0;
    this.recoil = 0;
    this.bob = 0;
    this.respawnAt = 0;
    this.deadBy = '';
    this.extras = null;
    this.fps = 60;
    this.lastFrame = performance.now();
    this.applySettings();
    this.bindInput();
    this.bindNet();
    this.hud.setLoading(15, 'Requesting a slot on the game host...');
    var self = this;
    this.net.connect().then(function () {
      self.hud.setLoading(45, 'Connected -- waiting for the world...');
    }).catch(function (err) {
      document.getElementById('load-msg').innerHTML =
        (err && err.message ? err.message : 'Could not connect.') +
        '<br><a href="/worlds" style="color:#ffd95e">Back to the world browser</a>';
    });
    this.loop = this.loop.bind(this);
    requestAnimationFrame(this.loop);
  }

  // -------------------------------------------------------------- settings
  Client.prototype.applySettings = function () {
    this.renderer.renderScale = Settings.renderScale;
    this.renderer.far = Settings.viewDistance;
    this.renderer.resize();
    if (this.particles) this.particles.enabled = Settings.particles;
    if (this.audio) this.audio.setVolume(Settings.volume);
  };

  // ----------------------------------------------------------------- input
  Client.prototype.bindInput = function () {
    var self = this;
    var canvas = this.canvas;

    canvas.addEventListener('click', function () {
      if (self.paused || self.hud.chatOpen) return;
      if (!document.pointerLockElement) canvas.requestPointerLock();
      self.audio.resume();
    });

    document.addEventListener('pointerlockchange', function () {
      var locked = document.pointerLockElement === canvas;
      canvas.classList.toggle('freelook', !locked);
      if (!locked && !self.hud.chatOpen && !self.paused) self.setPaused(true);
    });

    document.addEventListener('mousemove', function (event) {
      if (document.pointerLockElement !== canvas) return;
      var sens = Settings.sensitivity * 0.006;
      self.local.yaw -= event.movementX * sens;
      var dy = event.movementY * sens * (Settings.invertY ? -1 : 1);
      self.local.pitch = Math.max(-1.5, Math.min(1.5, self.local.pitch - dy));
    });

    document.addEventListener('mousedown', function (event) {
      if (self.paused || self.hud.chatOpen) return;
      if (document.pointerLockElement !== canvas) return;
      if (event.button === 0) { self.firing = true; self.tryFire(); }
      if (event.button === 2) self.toggleCamera();
    });
    document.addEventListener('mouseup', function (event) {
      if (event.button === 0) self.firing = false;
    });
    canvas.addEventListener('contextmenu', function (e) { e.preventDefault(); });

    document.addEventListener('keydown', function (event) {
      if (self.hud.captureBind && self.hud.awaitingBind) {
        event.preventDefault();
        self.hud.captureBind(event.code);
        return;
      }
      // While the chat box is open every game binding is ignored so the
      // player can type freely.
      if (self.hud.chatOpen) {
        if (event.code === 'Escape') { self.hud.closeChat(); event.preventDefault(); }
        else if (event.code === 'Enter') { self.sendChat(); event.preventDefault(); }
        return;
      }
      var action = Settings.actionFor(event.code);
      if (event.code === 'Escape') {
        event.preventDefault();
        self.setPaused(!self.paused);
        return;
      }
      if (self.paused) return;
      if (action === 'scoreboard') { event.preventDefault(); self.hud.toggleScoreboard(true); return; }
      if (action === 'chat') { event.preventDefault(); self.hud.openChat(false); return; }
      if (action === 'teamchat') { event.preventDefault(); self.hud.openChat(true); return; }
      if (action === 'camera') { event.preventDefault(); self.toggleCamera(); return; }
      if (action === 'reload') { self.net.send({ t: 'reload' }); return; }
      if (action === 'interact') { self.interact(); return; }
      if (action && action.indexOf('slot') === 0) {
        self.selectSlot(parseInt(action.slice(4), 10) - 1);
        return;
      }
      if (action) { self.keys[action] = true; event.preventDefault(); }
      if (event.code === 'Enter' && !self.local.alive) self.net.send({ t: 'respawn' });
    });

    document.addEventListener('keyup', function (event) {
      var action = Settings.actionFor(event.code);
      if (action === 'scoreboard') { self.hud.toggleScoreboard(false); return; }
      if (action) self.keys[action] = false;
    });

    window.addEventListener('blur', function () { self.keys = {}; self.firing = false; });
    window.addEventListener('resize', function () { self.renderer.resize(); });

    var chatInput = document.getElementById('chat-input');
    if (chatInput) {
      chatInput.addEventListener('keydown', function (event) {
        event.stopPropagation();
        if (event.code === 'Enter') { self.sendChat(); event.preventDefault(); }
        if (event.code === 'Escape') { self.hud.closeChat(); event.preventDefault(); }
      });
    }
  };

  Client.prototype.sendChat = function () {
    var input = document.getElementById('chat-input');
    var text = (input.value || '').trim();
    if (text) this.net.send({ t: 'chat', m: text, team: this.hud.chatTeam });
    input.value = '';
    this.hud.closeChat();
    if (!this.paused) this.canvas.requestPointerLock();
  };

  Client.prototype.setPaused = function (value) {
    this.paused = value;
    this.hud.show('pause', value);
    if (!value) {
      this.hud.show('settings', false);
      this.hud.show('helpbox', false);
      if (!this.hud.chatOpen) this.canvas.requestPointerLock();
    } else if (document.pointerLockElement) {
      document.exitPointerLock();
    }
  };

  Client.prototype.toggleCamera = function () {
    this.thirdPerson = !this.thirdPerson;
    var badge = document.getElementById('view-badge');
    if (badge) badge.textContent = this.thirdPerson ? '3rd person' : '1st person';
    this.hud.toast(this.thirdPerson ? 'Third person' : 'First person');
  };

  Client.prototype.selectSlot = function (index) {
    if (index < 0 || index > 4) return;
    if (!this.avatar.hotbar[index]) return;
    this.slot = index;
    this.hud.setSlot(index);
    this.net.send({ t: 'slot', i: index });
    this.updateAmmoHud();
    this.audio.play('ui', { volume: 0.4 });
  };

  Client.prototype.interact = function () {
    if (this.extras) this.extras.interact();
  };

  Client.prototype.quit = function () {
    this.net.close();
    window.location.href = '/profile/' + encodeURIComponent(BH.user.name);
  };

  // ------------------------------------------------------------------- net
  Client.prototype.bindNet = function () {
    var self = this;
    var net = this.net;

    net.on('welcome', function (msg) { self.onWelcome(msg); });
    net.on('join', function (msg) {
      self.addPlayer(msg.player);
      self.hud.toast(msg.player.name + ' joined');
    });
    net.on('leave', function (msg) {
      var player = self.players[msg.id];
      if (player) {
        self.renderer.dropTag('p' + msg.id);
        self.particles.clearEmitter('hat' + msg.id);
        delete self.players[msg.id];
      }
    });
    net.on('snap', function (msg) { self.onSnapshot(msg); });
    net.on('state', function (msg) { self.onState(msg.s); });
    net.on('chat', function (msg) {
      self.hud.addChat(msg);
      if (msg.kind !== 'system') self.audio.play('chat', { volume: 0.3 });
    });
    net.on('kill', function (msg) { self.onKill(msg); });
    net.on('dmg', function (msg) { self.onDamage(msg); });
    net.on('dealt', function (msg) {
      self.hud.hitmarker();
      self.audio.play('hit', { volume: 0.5 });
    });
    net.on('hit', function () { self.hud.hitmarker(); });
    net.on('heal', function (msg) {
      self.local.health = msg.hp;
      self.hud.setHealth(msg.hp);
      self.particles.burst('heal', [self.local.pos[0], self.local.pos[1] + 3, self.local.pos[2]]);
      self.audio.play('heal', { volume: 0.5 });
    });
    net.on('died', function (msg) {
      self.local.alive = false;
      self.respawnAt = performance.now() / 1000 + msg.in;
      self.deadBy = msg.by;
      self.audio.play('die');
      self.hud.setHealth(0);
    });
    net.on('spawn', function (msg) {
      self.local.pos = msg.p.slice();
      self.local.vel = [0, 0, 0];
      self.local.yaw = msg.yaw;
      self.local.pitch = 0;
      self.local.alive = true;
      self.local.health = msg.hp;
      self.hud.setHealth(msg.hp);
      self.hud.setRespawn(null);
      self.respawnAt = 0;
    });
    net.on('you', function (msg) {
      if (msg.slot !== undefined) {
        self.slot = msg.slot;
        self.hud.setSlot(msg.slot);
      }
      if (msg.ammo !== undefined) self.ammo[msg.slot !== undefined ? msg.slot : self.slot] = msg.ammo;
      if (msg.reserve !== undefined) self.reserve[msg.slot !== undefined ? msg.slot : self.slot] = msg.reserve;
      self.updateAmmoHud();
    });
    net.on('reloading', function (msg) {
      self.reloadUntil = performance.now() / 1000 + msg.time;
      self.audio.play('reload', { volume: 0.6 });
      self.updateAmmoHud();
    });
    net.on('correct', function (msg) {
      self.local.pos = msg.p.slice();
      self.local.vel = [0, 0, 0];
    });
    net.on('knock', function (msg) {
      self.local.vel[0] += msg.v[0];
      self.local.vel[1] += msg.v[1];
      self.local.vel[2] += msg.v[2];
    });
    net.on('team', function (msg) {
      self.myTeam = msg.team;
      if (msg.plot !== undefined) self.myPlot = msg.plot;
      self.hud.toast('You are on ' + msg.team.toUpperCase());
    });
    net.on('teams', function (msg) {
      Object.keys(msg.map || {}).forEach(function (id) {
        var player = self.players[id];
        if (player) player.team = msg.map[id];
        if (parseInt(id, 10) === self.myId) self.myTeam = msg.map[id];
      });
    });
    net.on('slot', function (msg) {
      var player = self.players[msg.id];
      if (player) player.slot = msg.i;
    });
    net.on('fx', function (msg) { self.onEffect(msg); });
    net.on('proj', function (msg) {
      self.projectiles[msg.id] = { p: msg.p.slice(), v: msg.v.slice() };
      self.audio.play('rocket', { volume: self.volumeAt(msg.p) });
    });
    net.on('vote', function (msg) { self.hud.updateVote(msg); });
    net.on('round_end', function (msg) {
      self.hud.showEndCard(msg);
      self.audio.play('capture');
    });
    net.on('round_start', function (msg) {
      self.hud.show('endcard', false);
      self.hud.toast('Round ' + msg.round + ' -- go!', 'good', true);
      if (msg.state) self.onState(msg.state);
    });
    net.on('respawned', function (msg) {
      var player = self.players[msg.id];
      if (player) { player.alive = true; player.health = msg.hp; }
    });
    net.on('flags', function (msg) {
      if (self.extras) self.extras.setFlags(msg.f);
    });
    net.on('evt', function (msg) { self.onEvent(msg); });
    net.on('notice', function (msg) {
      self.hud.toast(msg.m, msg.bad ? 'bad' : '');
    });
    net.on('coins', function (msg) {
      if (msg.gained) {
        self.hud.toast('+' + msg.gained.toLocaleString() + ' coins', 'good');
        self.particles.burst('coin', [self.local.pos[0], self.local.pos[1] + 3,
                                      self.local.pos[2]]);
        self.audio.play('coin');
      }
      self.coins = msg.c;
      self.hud.setCoins(msg.c);
    });
    net.on('tycoon_init', function (msg) {
      if (!self.extras) { self.pendingTycoonInit = msg; return; }
      self.applyTycoonInit(msg);
    });
    net.on('tycoon_state', function (msg) {
      if (self.extras) self.extras.setPlots(msg.plots);
    });
    net.on('tycoon_plot', function (msg) {
      if (!self.extras) return;
      var plots = self.extras.plots.slice();
      var found = false;
      for (var i = 0; i < plots.length; i++) {
        if (plots[i].index === msg.plot.index) { plots[i] = msg.plot; found = true; }
      }
      if (!found) plots.push(msg.plot);
      self.extras.setPlots(plots);
      if (msg.plot.geometry) {
        msg.plot.geometry.forEach(function (geo) {
          self.extras.builtGeometry[msg.plot.index + ':' + geo.id] = geo.parts || [];
        });
        self.rebuildStatic();
      }
    });
    net.on('tycoon_build', function (msg) {
      if (self.extras) self.extras.addBuilt(msg.plot, msg.upgrade, msg.geometry);
    });
    net.on('tycoon_reset', function (msg) {
      if (self.extras) self.extras.resetPlot(msg.plot);
    });
    net.on('tycoon_active', function (msg) {
      if (msg.by === BH.user.name) self.audio.play('coin', { volume: 0.6 });
    });
    net.on('tycoon_collect', function (msg) {});
    net.on('ping', function (ms) {
      var badge = document.getElementById('ping-badge');
      if (badge) badge.textContent = ms + ' ms';
    });
    net.on('close', function (info) {
      if (info && info.byUs) return;
      document.getElementById('loading').classList.remove('hide');
      document.getElementById('load-msg').innerHTML =
        'Disconnected from the game host.<br>' +
        '<a href="/' + self.world.id + '" style="color:#ffd95e">Rejoin</a> &bull; ' +
        '<a href="/worlds" style="color:#ffd95e">World browser</a>';
    });
  };

  Client.prototype.onWelcome = function (msg) {
    this.hud.setLoading(70, 'Building ' + msg.map.name + '...');
    this.map = msg.map;
    this.constants = msg.constants;
    this.myId = msg.you.id;
    this.myTeam = msg.you.team;
    this.myPlot = msg.you.plot;
    this.physics = new Physics(msg.map, msg.constants);
    this.renderer.setSky(msg.map.sky);
    this.renderer.setAmbient(msg.map.ambient);
    this.extras = new WorldExtras(this);
    this.staticParts = msg.map.parts;
    this.renderer.buildStatic(msg.map.parts);
    this.local.pos = msg.you.pos ? msg.you.pos.slice() : [0, 20, 0];
    this.state = msg.state || {};
    var self = this;
    (msg.players || []).forEach(function (player) {
      if (player.id !== self.myId) self.addPlayer(player);
    });
    (msg.chat || []).forEach(function (entry) { self.hud.addChat(entry); });
    this.hud.buildHotbar(this.avatar.hotbar || [], 0);
    for (var i = 0; i < 5; i++) {
      var item = (this.avatar.hotbar || [])[i];
      var stats = item && item.data && item.data.stats;
      this.ammo[i] = stats && stats.mag ? stats.mag : 0;
      this.reserve[i] = stats && stats.reserve ? stats.reserve : 0;
    }
    this.updateAmmoHud();
    if (this.state.flags && this.extras) this.extras.setFlags(this.state.flags);
    if (this.state.plots && this.extras) this.extras.setPlots(this.state.plots);
    this.onState(this.state);
    var badge = document.getElementById('instance-badge');
    if (badge) badge.textContent = 'instance #' + msg.world.instance;
    if (this.pendingTycoonInit) {
      this.applyTycoonInit(this.pendingTycoonInit);
      this.pendingTycoonInit = null;
    }
    this.hud.setLoading(100, 'Ready. Click to play.');
    this.hud.toast('Click the screen to lock the mouse. Press <b>Y</b> to chat.', '', true);
  };

  Client.prototype.applyTycoonInit = function (msg) {
    this.myPlot = msg.your_plot;
    this.coins = msg.coins;
    this.hud.setCoins(msg.coins);
    if (!this.extras) return;
    this.extras.setPlots(msg.plots);
    var self = this;
    (msg.plots || []).forEach(function (plot) {
      (plot.geometry || []).forEach(function (geo) {
        self.extras.builtGeometry[plot.index + ':' + geo.id] = geo.parts || [];
      });
    });
    this.rebuildStatic();
  };

  Client.prototype.addPlayer = function (data) {
    if (data.id === this.myId) return;
    this.players[data.id] = {
      id: data.id, name: data.name, team: data.team, avatar: data.avatar,
      pos: (data.pos || [0, 0, 0]).slice(), target: (data.pos || [0, 0, 0]).slice(),
      yaw: 0, pitch: 0, anim: 'idle', health: data.hp, alive: data.alive,
      slot: data.slot || 0, uid: data.uid, admin: data.admin
    };
  };

  Client.prototype.onSnapshot = function (msg) {
    var rows = msg.ps || [];
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var id = row[0];
      if (id === this.myId) {
        this.serverHealth = row[7];
        continue;
      }
      var player = this.players[id];
      if (!player) continue;
      player.target = [row[1], row[2], row[3]];
      player.yaw = row[4];
      player.pitch = row[5];
      player.anim = row[6];
      player.health = row[7];
      player.slot = row[8];
      player.alive = !!row[9];
    }
    var live = {};
    (msg.pr || []).forEach(function (row) {
      live[row[0]] = true;
      this.projectiles[row[0]] = this.projectiles[row[0]] || {};
      this.projectiles[row[0]].p = [row[1], row[2], row[3]];
    }, this);
    Object.keys(this.projectiles).forEach(function (id) {
      if (!live[id]) delete this.projectiles[id];
    }, this);
  };

  Client.prototype.onState = function (state) {
    if (!state) return;
    this.state = state;
    this.hud.updateObjective(state);
    if (this.hud.scoreboardOpen) this.hud.renderScoreboard(state.scoreboard);
    if (state.flags && this.extras) this.extras.setFlags(state.flags);
    if (state.plots && this.extras && this.world.mode === 'endless') {
      // the endless world sends a lighter summary here; the full plot payload
      // arrives on tycoon_state
    }
  };

  Client.prototype.onKill = function (msg) {
    this.hud.addKill(msg, BH.user.name);
    if (msg.kid === this.myId) {
      this.audio.play('kill');
      if (msg.streak >= 3) {
        this.hud.toast(msg.streak + ' kill streak!', 'good');
      }
    }
    var victim = this.players[msg.vid];
    if (victim) {
      victim.alive = false;
      this.particles.burst('blood', [victim.pos[0], victim.pos[1] + 3, victim.pos[2]]);
    }
  };

  Client.prototype.onDamage = function (msg) {
    this.local.health = msg.hp;
    this.hud.setHealth(msg.hp);
    this.hud.flashDamage();
    this.audio.play('hurt', { volume: 0.6 });
    if (msg.from) {
      var dx = msg.from[0] - this.local.pos[0];
      var dz = msg.from[2] - this.local.pos[2];
      var angle = Math.atan2(dx, dz) - this.local.yaw;
      this.hud.hurtArrow(-angle);
    }
  };

  Client.prototype.onEffect = function (msg) {
    if (msg.k === 'shot') {
      var shooter = this.players[msg.id];
      var origin = msg.o || (shooter ? [shooter.pos[0], shooter.pos[1] + 4.85, shooter.pos[2]] : null);
      if (!origin) return;
      this.spawnTracer(origin, msg.d, 400);
      this.particles.burst('muzzle', [origin[0] + msg.d[0] * 1.6,
                                      origin[1] + msg.d[1] * 1.6,
                                      origin[2] + msg.d[2] * 1.6]);
      var weapon = msg.w || '';
      var sound = weapon.indexOf('shotgun') >= 0 ? 'shotgun'
        : weapon.indexOf('sniper') >= 0 ? 'sniper'
        : weapon.indexOf('smg') >= 0 ? 'smg'
        : weapon.indexOf('rifle') >= 0 ? 'rifle' : 'pistol';
      this.audio.play(sound, { volume: this.volumeAt(origin) });
    } else if (msg.k === 'explode') {
      this.particles.burst('explosion', msg.p, { radius: msg.r || 8 });
      this.audio.play('explode', { volume: this.volumeAt(msg.p) });
      delete this.projectiles[msg.id];
    } else if (msg.k === 'swing') {
      var player = this.players[msg.id];
      if (player) this.audio.play('swing', { volume: this.volumeAt(player.pos) });
    }
  };

  Client.prototype.onEvent = function (msg) {
    if (msg.k === 'flag_take') {
      this.hud.toast('<b>' + msg.by + '</b> took the ' + msg.team.toUpperCase() + ' flag!',
                     msg.team === this.myTeam ? 'bad' : 'good');
      this.audio.play('alarm', { volume: 0.5 });
    } else if (msg.k === 'flag_capture') {
      this.hud.toast('<b>' + msg.by + '</b> captured for ' + msg.team.toUpperCase() + '!',
                     msg.team === this.myTeam ? 'good' : 'bad', true);
      this.audio.play('capture');
    } else if (msg.k === 'flag_return') {
      this.hud.toast('The ' + msg.team.toUpperCase() + ' flag was returned.');
    } else if (msg.k === 'checkpoint') {
      this.hud.toast('Checkpoint ' + msg.n + ' captured!', 'good', true);
      this.audio.play('capture');
    } else if (msg.k === 'setup_end') {
      this.hud.toast('The gates are open!', 'good', true);
      this.audio.play('alarm');
    }
  };

  Client.prototype.volumeAt = function (position) {
    var d = Math.hypot(position[0] - this.local.pos[0],
                       position[1] - this.local.pos[1],
                       position[2] - this.local.pos[2]);
    return Math.max(0.05, Math.min(1, 1 - d / 220));
  };

  // -------------------------------------------------------------- shooting
  Client.prototype.currentWeapon = function () {
    return (this.avatar.hotbar || [])[this.slot] || null;
  };

  Client.prototype.weaponStats = function () {
    var item = this.currentWeapon();
    if (!item || !item.data || !item.data.stats) {
      return { kind: 'hitscan', rpm: 240, mag: 12, auto: false, recoil: 1 };
    }
    return item.data.stats;
  };

  Client.prototype.tryFire = function () {
    if (!this.local.alive || this.paused || this.hud.chatOpen) return;
    var now = performance.now() / 1000;
    if (now < this.nextFire || now < this.reloadUntil) return;
    var stats = this.weaponStats();
    var melee = stats.kind === 'melee';
    if (!melee && stats.kind !== 'support' && this.ammo[this.slot] <= 0) {
      this.net.send({ t: 'reload' });
      return;
    }
    this.nextFire = now + 60 / Math.max(1, stats.rpm || 240);
    var dir = this.lookDirection();
    var origin = [this.local.pos[0], this.local.pos[1] + 4.85, this.local.pos[2]];
    this.net.send({ t: 'fire', d: dir, o: origin });
    if (!melee && stats.kind !== 'support') {
      this.ammo[this.slot] = Math.max(0, this.ammo[this.slot] - 1);
      this.updateAmmoHud();
      this.recoil = Math.min(1.4, this.recoil + (stats.recoil || 1) * 0.16);
      this.local.pitch = Math.min(1.5, this.local.pitch + (stats.recoil || 1) * 0.006);
      this.particles.burst('muzzle', [origin[0] + dir[0] * 1.8,
                                      origin[1] + dir[1] * 1.8,
                                      origin[2] + dir[2] * 1.8]);
      this.spawnTracer(origin, dir, stats.range || 200);
      var sound = stats.sound || 'pistol';
      this.audio.play(sound, { volume: 0.85 });
    } else if (melee) {
      this.audio.play(stats.sound || 'swing', { volume: 0.8 });
      this.recoil = Math.min(1.4, this.recoil + 0.5);
    } else {
      this.audio.play('heal', { volume: 0.7 });
    }
  };

  Client.prototype.lookDirection = function () {
    var cp = Math.cos(this.local.pitch);
    return [Math.sin(this.local.yaw) * cp, Math.sin(this.local.pitch),
            Math.cos(this.local.yaw) * cp];
  };

  Client.prototype.spawnTracer = function (origin, dir, maxRange) {
    var distance = this.physics
      ? this.physics.rayDistance(origin, dir, maxRange) : maxRange;
    // stop the tracer at the first player it would pass through
    var self = this;
    Object.keys(this.players).forEach(function (id) {
      var player = self.players[id];
      if (!player.alive) return;
      var hit = rayBox(origin, dir,
                       [player.pos[0] - 1.6, player.pos[1], player.pos[2] - 1.0],
                       [player.pos[0] + 1.6, player.pos[1] + 5.4, player.pos[2] + 1.0]);
      if (hit !== null && hit < distance) distance = hit;
    });
    var end = [origin[0] + dir[0] * distance, origin[1] + dir[1] * distance,
               origin[2] + dir[2] * distance];
    this.tracers.push({ a: origin.slice(), b: end, t: 0 });
    if (distance < maxRange - 0.5) {
      this.particles.burst('impact', end);
    }
  };

  function rayBox(origin, dir, lo, hi) {
    var tmin = 0, tmax = Infinity;
    for (var axis = 0; axis < 3; axis++) {
      var o = origin[axis], d = dir[axis];
      if (Math.abs(d) < 1e-8) {
        if (o < lo[axis] || o > hi[axis]) return null;
        continue;
      }
      var inv = 1 / d;
      var t1 = (lo[axis] - o) * inv, t2 = (hi[axis] - o) * inv;
      if (t1 > t2) { var tmp = t1; t1 = t2; t2 = tmp; }
      tmin = Math.max(tmin, t1); tmax = Math.min(tmax, t2);
      if (tmin > tmax) return null;
    }
    return tmin >= 0 ? tmin : null;
  }

  Client.prototype.updateAmmoHud = function () {
    var item = this.currentWeapon();
    var stats = this.weaponStats();
    var reloading = performance.now() / 1000 < this.reloadUntil;
    if (stats.kind === 'melee') {
      this.hud.setAmmo(null, null, item ? item.name : '', false);
    } else {
      this.hud.setAmmo(this.ammo[this.slot], this.reserve[this.slot],
                       item ? item.name : '', reloading);
    }
  };

  // ------------------------------------------------------------ simulation
  Client.prototype.step = function (dt) {
    var local = this.local;
    if (!this.physics) return;
    if (!local.alive) {
      var remaining = this.respawnAt - performance.now() / 1000;
      this.hud.setRespawn(Math.max(0, remaining), this.deadBy);
      if (remaining <= 0) this.hud.setRespawn(0, this.deadBy);
      return;
    }
    var speed = this.constants.walk || 22;
    if (this.keys.sprint) speed *= 0.45;
    var forward = (this.keys.forward ? 1 : 0) - (this.keys.back ? 1 : 0);
    var strafe = (this.keys.right ? 1 : 0) - (this.keys.left ? 1 : 0);
    var sin = Math.sin(local.yaw), cos = Math.cos(local.yaw);
    var wishX = sin * forward + cos * strafe;
    var wishZ = cos * forward - sin * strafe;
    var length = Math.hypot(wishX, wishZ);
    if (length > 0.001) { wishX /= length; wishZ /= length; }

    var accel = local.grounded ? 90 : 26;
    var targetX = wishX * speed, targetZ = wishZ * speed;
    local.vel[0] += (targetX - local.vel[0]) * Math.min(1, accel * dt / speed);
    local.vel[2] += (targetZ - local.vel[2]) * Math.min(1, accel * dt / speed);
    if (length < 0.001 && local.grounded) {
      var friction = Math.max(0, 1 - 12 * dt);
      local.vel[0] *= friction;
      local.vel[2] *= friction;
    }
    if (this.keys.jump && local.grounded) {
      local.vel[1] = this.constants.jump || 34;
      local.grounded = false;
      this.audio.play('jump', { volume: 0.35 });
    }
    local.vel[1] -= (this.constants.gravity || 62) * dt;
    if (local.vel[1] < -140) local.vel[1] = -140;

    var result = this.physics.move(local, dt);
    if (result.landed) {
      this.audio.play('land', { volume: 0.4 });
      this.particles.burst('dust', [local.pos[0], local.pos[1], local.pos[2]]);
    }
    local.grounded = result.grounded;

    var horizontal = Math.hypot(local.vel[0], local.vel[2]);
    if (!local.grounded) local.anim = local.vel[1] > 1 ? 'jump' : 'fall';
    else if (horizontal > speed * 0.65) local.anim = 'run';
    else if (horizontal > 1.5) local.anim = 'walk';
    else local.anim = 'idle';
    this.bob += horizontal * dt * 0.6;

    if (local.pos[1] < (this.map.kill_y || -60) + 2) {
      // the server will confirm the death; stop falling forever
      local.vel[1] = Math.max(local.vel[1], -40);
    }
    this.recoil *= Math.max(0, 1 - dt * 7);
  };

  Client.prototype.sendInput = function () {
    this.net.send({
      t: 'in',
      p: [round2(this.local.pos[0]), round2(this.local.pos[1]), round2(this.local.pos[2])],
      v: [round2(this.local.vel[0]), round2(this.local.vel[1]), round2(this.local.vel[2])],
      y: round3(this.local.yaw), pi: round3(this.local.pitch),
      a: this.local.anim, g: this.local.grounded ? 1 : 0
    });
  };

  function round2(v) { return Math.round(v * 100) / 100; }
  function round3(v) { return Math.round(v * 1000) / 1000; }

  // ------------------------------------------------------------- rendering
  Client.prototype.rebuildStatic = function () {
    if (!this.staticParts) return;
    var parts = this.staticParts;
    if (this.extras) parts = parts.concat(this.extras.staticExtras());
    this.renderer.buildStatic(parts);
  };

  Client.prototype.cameraPosition = function () {
    var eye = [this.local.pos[0], this.local.pos[1] + 4.85, this.local.pos[2]];
    if (!this.thirdPerson) {
      var sway = Math.sin(this.bob * 2) * 0.06;
      eye[1] += sway;
      return { eye: eye, yaw: this.local.yaw, pitch: this.local.pitch };
    }
    // Classic over-the-shoulder chase camera, pulled in when a wall is close
    // but never so close that it ends up inside the character.
    var dir = this.lookDirection();
    var back = [-dir[0], -dir[1], -dir[2]];
    var wanted = 17;
    var minimum = 5.0;
    var side = [Math.cos(this.local.yaw), 0, -Math.sin(this.local.yaw)];
    var pivot = [eye[0] + side[0] * 1.2, eye[1] + 1.3, eye[2] + side[2] * 1.2];
    var distance = wanted;
    if (this.physics) {
      var clear = this.physics.rayDistance(pivot, back, wanted + 2) - 1.6;
      distance = Math.min(wanted, Math.max(minimum, clear));
    }
    return {
      eye: [pivot[0] + back[0] * distance, pivot[1] + back[1] * distance,
            pivot[2] + back[2] * distance],
      yaw: this.local.yaw, pitch: this.local.pitch
    };
  };

  Client.prototype.render = function (dt) {
    var renderer = this.renderer;
    renderer.resize();
    renderer.beginFrame(dt);
    var camera = this.cameraPosition();
    renderer.setCamera(camera.eye, camera.yaw, camera.pitch, Settings.fov);

    var time = this.time;
    var self = this;

    // ---- remote players
    Object.keys(this.players).forEach(function (id) {
      var player = self.players[id];
      var lerp = Math.min(1, dt * 16);
      player.pos[0] += (player.target[0] - player.pos[0]) * lerp;
      player.pos[1] += (player.target[1] - player.pos[1]) * lerp;
      player.pos[2] += (player.target[2] - player.pos[2]) * lerp;
      if (!player.alive) {
        self.renderer.dropTag('p' + player.id);
        self.particles.clearEmitter('hat' + player.id);
        return;
      }
      var holding = (player.avatar.hotbar || [])[player.slot] || null;
      var parts = Avatar.build(player.avatar, {
        position: player.pos, yaw: player.yaw, pitch: player.pitch,
        time: time, holding: holding,
        pose: Avatar.pose(player.anim, time + player.id, 0)
      });
      parts.forEach(function (part) { renderer.push(part); });
      self.drawShadow(player.pos);
      var hat = (player.avatar.items || {}).hat;
      if (hat && hat.tier === 'unusual' && hat.effect_def && Settings.particles) {
        self.particles.setEmitter('hat' + player.id, hat.effect_def,
                                  Avatar.hatAnchor(player.pos, player.yaw, hat));
      }
      if (Settings.showNames) {
        var distance = Math.hypot(player.pos[0] - camera.eye[0],
                                  player.pos[1] - camera.eye[1],
                                  player.pos[2] - camera.eye[2]);
        if (distance < 320) {
          var scale = Math.max(0.85, Math.min(3.4, 0.85 + distance * 0.011));
          var colour = player.team === 'red' ? '#ff9a90'
            : (player.team === 'blue' ? '#9ecbff' : '#ffe08a');
          var sub = (player.team && player.team !== self.myTeam &&
                     self.world.mode !== 'endless')
            ? Math.max(0, Math.round(player.health)) + ' hp' : '';
          renderer.queueTag('p' + player.id, player.name, colour, sub,
                            [player.pos[0], player.pos[1] + 7.6, player.pos[2]],
                            scale);
        }
      }
    });

    // ---- own avatar
    var holdingSelf = this.currentWeapon();
    if (this.local.alive) {
      if (this.thirdPerson) {
        var parts = Avatar.build(this.avatar, {
          position: this.local.pos, yaw: this.local.yaw, pitch: this.local.pitch,
          time: time, holding: holdingSelf,
          pose: Avatar.pose(this.local.anim, time, 0)
        });
        parts.forEach(function (part) { renderer.push(part); });
      } else {
        var viewParts = Avatar.viewModel(this.avatar, holdingSelf, {
          eye: camera.eye, forward: renderer.forward, right: renderer.right,
          up: renderer.up
        }, { x: Math.sin(this.bob) * 0.03, y: Math.abs(Math.cos(this.bob)) * 0.02,
             recoil: this.recoil });
        viewParts.forEach(function (part) { renderer.push(part); });
      }
      this.drawShadow(this.local.pos);
      var myHat = (this.avatar.items || {}).hat;
      if (myHat && myHat.tier === 'unusual' && myHat.effect_def && Settings.particles
          && this.thirdPerson) {
        this.particles.setEmitter('hatme', myHat.effect_def,
                                  Avatar.hatAnchor(this.local.pos, this.local.yaw, myHat));
      }
    }

    // ---- projectiles
    Object.keys(this.projectiles).forEach(function (id) {
      var proj = self.projectiles[id];
      if (!proj.p) return;
      renderer.pushRaw('cyl', proj.p[0], proj.p[1], proj.p[2], 0, 0, 0,
                       0.8, 2.2, 0.8, [0.25, 0.25, 0.28], 1, 0, 1, 0, null);
      renderer.pushRaw('sph', proj.p[0], proj.p[1], proj.p[2], 0, 0, 0,
                       1.6, 1.6, 1.6, [1, 0.7, 0.2], 0.6, 0, 2, 0.5, null);
      if (Settings.particles && Math.random() < 0.8) {
        self.particles.spawn({
          p: proj.p, v: [0, 0.4, 0], life: 0.45, size: 0.9, grow: 1.4,
          gravity: 0.6, blend: 'normal', shape: 'puff',
          colors: ['#f2f2f2', '#9a9a9a'] });
      }
    });

    // ---- tracers
    for (var i = 0; i < this.tracers.length; i++) {
      var tracer = this.tracers[i];
      tracer.t += dt;
      if (tracer.t > 0.09) { this.tracers.splice(i, 1); i--; continue; }
      var dx = tracer.b[0] - tracer.a[0];
      var dy = tracer.b[1] - tracer.a[1];
      var dz = tracer.b[2] - tracer.a[2];
      var length = Math.hypot(dx, dy, dz);
      if (length < 0.5) continue;
      var yaw = Math.atan2(dx, dz);
      var pitch = -Math.asin(dy / length);
      renderer.pushRaw('box',
        tracer.a[0] + dx * 0.5, tracer.a[1] + dy * 0.5, tracer.a[2] + dz * 0.5,
        pitch, yaw, 0, 0.09, 0.09, length,
        [1, 0.93, 0.6], 0.7 * (1 - tracer.t / 0.09), 0, 2, 0.9, null);
    }

    if (this.extras) this.extras.draw(renderer, this.state, time, dt);
    this.particles.update(dt);
    renderer.render();
    this.particles.draw(renderer);
  };

  Client.prototype.drawShadow = function (position) {
    if (!this.physics) return;
    var drop = this.physics.rayDistance([position[0], position[1] + 0.4, position[2]],
                                        [0, -1, 0], 40);
    if (drop >= 40) return;
    var y = position[1] + 0.4 - drop + 0.06;
    var fade = Math.max(0.06, 0.34 - drop * 0.012);
    this.renderer.pushRaw('cyl', position[0], y, position[2], 0, 0, 0,
                          4.6, 0.06, 3.6, [0.1, 0.12, 0.14], fade, 0, 0, 0.9, null);
  };

  // ------------------------------------------------------------------ loop
  Client.prototype.loop = function (now) {
    requestAnimationFrame(this.loop);
    var dt = Math.min(0.1, (now - this.lastFrame) / 1000);
    this.lastFrame = now;
    this.time += dt;
    this.fps += ((1 / Math.max(0.0001, dt)) - this.fps) * 0.08;

    if (this.physics && !this.paused) {
      this.accumulator += dt;
      var steps = 0;
      while (this.accumulator >= 1 / 120 && steps < 8) {
        this.step(1 / 120);
        this.accumulator -= 1 / 120;
        steps++;
      }
      this.sendTimer += dt;
      if (this.sendTimer >= SEND_RATE) {
        this.sendTimer = 0;
        if (this.net.connected) this.sendInput();
      }
      if (this.firing) {
        var stats = this.weaponStats();
        if (stats.auto || stats.kind === 'melee') this.tryFire();
      }
      if (performance.now() / 1000 >= this.reloadUntil && this.wasReloading) {
        this.wasReloading = false;
        this.updateAmmoHud();
      } else if (performance.now() / 1000 < this.reloadUntil) {
        this.wasReloading = true;
      }
    }
    if (this.renderer && !this.renderer.failed && this.map) this.render(dt);
    var perf = document.getElementById('perf');
    if (perf && this.renderer && this.renderer.stats) {
      perf.textContent = Math.round(this.fps) + ' fps  ' +
        this.renderer.stats.instances + ' parts';
    }
  };

  document.addEventListener('DOMContentLoaded', function () {
    if (!window.BH || !BH.world) return;
    window.gameClient = new Client();
  });

  global.GameClient = Client;
})(window);
