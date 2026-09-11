/* The in-game HUD: health, ammo, hotbar, kill feed, chat, scoreboard,
   objective banner, vote panel, pause and settings menus. */
(function (global) {
  'use strict';

  function el(id) { return document.getElementById(id); }

  function HUD(client) {
    this.client = client;
    this.chatOpen = false;
    this.chatTeam = false;
    this.scoreboardOpen = false;
    this.killFeed = [];
    this.chatLines = [];
    this.toasts = [];
    this.bindMenus();
    this.buildKeybinds();
    this.syncSettings();
  }

  HUD.prototype.escape = function (text) {
    var div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  };

  // ------------------------------------------------------------- health/ammo
  HUD.prototype.setHealth = function (hp) {
    hp = Math.max(0, Math.min(100, Math.round(hp)));
    var fill = el('health-fill');
    if (fill) {
      fill.style.width = hp + '%';
      fill.classList.toggle('low', hp <= 30);
    }
    var text = el('health-text');
    if (text) text.textContent = hp;
  };

  HUD.prototype.setAmmo = function (mag, reserve, name, reloading) {
    var wrap = el('ammo');
    if (!wrap) return;
    wrap.classList.toggle('reloading', !!reloading);
    wrap.querySelector('.mag').textContent = (mag === null || mag === undefined)
      ? '--' : mag;
    wrap.querySelector('.res').textContent = (reserve === null || reserve === undefined)
      ? '' : '/ ' + reserve;
    wrap.querySelector('.wname').textContent = name || '';
  };

  HUD.prototype.buildHotbar = function (hotbar, activeIndex) {
    var wrap = el('hotbar-hud');
    if (!wrap) return;
    wrap.innerHTML = '';
    for (var i = 0; i < 5; i++) {
      var item = hotbar[i];
      var slot = document.createElement('div');
      slot.className = 'slot' + (item ? '' : ' empty') + (i === activeIndex ? ' on' : '');
      slot.dataset.slot = i;
      slot.innerHTML = '<span class="k">' + (i + 1) + '</span>' +
        '<span class="n">' + (item ? this.escape(item.name) : '') + '</span>';
      if (item) {
        var canvas = document.createElement('canvas');
        canvas.width = 128; canvas.height = 128;
        slot.insertBefore(canvas, slot.querySelector('.n'));
        if (window.Thumbs) Thumbs.renderItem(canvas, item.item_id, '');
      }
      wrap.appendChild(slot);
    }
  };

  HUD.prototype.setSlot = function (index) {
    var wrap = el('hotbar-hud');
    if (!wrap) return;
    Array.prototype.forEach.call(wrap.children, function (slot, i) {
      slot.classList.toggle('on', i === index);
    });
  };

  // ---------------------------------------------------------------- killfeed
  HUD.prototype.addKill = function (data, myName) {
    var feed = el('killfeed');
    if (!feed) return;
    var mine = data.k === myName || data.v === myName;
    var line = document.createElement('div');
    line.className = 'kf' + (mine ? ' mine' : '');
    var killer = data.k
      ? '<span class="n-' + (data.kteam || 'red') + '">' + this.escape(data.k) + '</span>'
      : '<span class="w">the world</span>';
    var victim = '<span class="n-' + (data.vteam || 'blue') + '">' +
      this.escape(data.v) + '</span>';
    var weapon = '<span class="w">' + this.escape(data.w || '') + '</span>';
    line.innerHTML = killer + ' ' + weapon + (data.hs ? ' <span class="hs">&#9733;</span>' : '') +
      ' &rarr; ' + victim;
    feed.appendChild(line);
    while (feed.children.length > 6) feed.removeChild(feed.firstChild);
    setTimeout(function () {
      line.style.transition = 'opacity .6s';
      line.style.opacity = '0';
      setTimeout(function () { line.remove(); }, 620);
    }, 7000);
  };

  // -------------------------------------------------------------------- chat
  HUD.prototype.addChat = function (entry) {
    var log = el('chat-log');
    if (!log) return;
    var line = document.createElement('div');
    var kind = entry.kind || 'all';
    line.className = 'chat-line ' + (kind === 'system' ? 'system' : (kind === 'team' ? 'team' : ''));
    if (kind === 'system') {
      line.innerHTML = this.escape(entry.m);
    } else {
      var teamClass = entry.team === 'red' ? 'red'
        : (entry.team === 'blue' ? 'blue' : 'plot');
      line.innerHTML = '<span class="name ' + teamClass + (entry.admin ? ' admin' : '') +
        '" data-username="' + this.escape(entry.from) + '" title="Double click to open profile">' +
        this.escape(entry.from) + '</span>' +
        (kind === 'team' ? ' <span style="opacity:.7">(team)</span>' : '') +
        ': ' + this.escape(entry.m);
    }
    log.appendChild(line);
    while (log.children.length > 12) log.removeChild(log.firstChild);
    var self = this;
    setTimeout(function () {
      if (self.chatOpen || log.classList.contains('expanded')) return;
      line.classList.add('fading');
      setTimeout(function () {
        if (line.parentNode && !self.chatOpen) line.remove();
      }, 1100);
    }, 18000);
  };

  HUD.prototype.openChat = function (team) {
    this.chatOpen = true;
    this.chatTeam = !!team;
    var wrap = el('chat-input-wrap');
    var input = el('chat-input');
    var scope = el('chat-scope');
    if (scope) {
      scope.textContent = team ? 'TEAM' : 'ALL';
      scope.style.color = team ? '#9ade8f' : '#ffe08a';
    }
    if (wrap) wrap.classList.add('on');
    el('chat-log').classList.add('expanded');
    if (input) { input.value = ''; input.focus(); }
    if (document.pointerLockElement) document.exitPointerLock();
  };

  HUD.prototype.closeChat = function () {
    this.chatOpen = false;
    var wrap = el('chat-input-wrap');
    if (wrap) wrap.classList.remove('on');
    var input = el('chat-input');
    if (input) input.blur();
    el('chat-log').classList.remove('expanded');
  };

  // -------------------------------------------------------------- scoreboard
  HUD.prototype.toggleScoreboard = function (open) {
    this.scoreboardOpen = open === undefined ? !this.scoreboardOpen : open;
    var board = el('scoreboard');
    if (board) board.classList.toggle('on', this.scoreboardOpen);
    if (this.scoreboardOpen) this.renderScoreboard();
  };

  HUD.prototype.renderScoreboard = function (rows) {
    var board = el('sb-body');
    if (!board) return;
    rows = rows || this.client.state.scoreboard || [];
    var myId = this.client.myId;
    var tycoon = this.client.world.mode === 'endless';
    var html = rows.map(function (row) {
      var team = row.team === 'red' ? 'red' : (row.team === 'blue' ? 'blue' : '');
      return '<tr class="' + team + (row.id === myId ? ' me' : '') + '">' +
        '<td class="who" data-username="' + row.name + '">' + row.name + '</td>' +
        '<td>' + (row.team || '-') + '</td>' +
        '<td>' + row.kills + '</td><td>' + row.deaths + '</td>' +
        '<td>' + (tycoon ? row.coins : row.score) + '</td></tr>';
    }).join('');
    board.innerHTML = html;
    var title = el('sb-title');
    if (title) {
      title.textContent = this.client.world.name + ' -- instance #' +
        (this.client.state.instance || '?') + ' (' + rows.length + ' players)';
    }
  };

  // --------------------------------------------------------------- objective
  HUD.prototype.updateObjective = function (state) {
    if (!state) return;
    var mode = this.client.world.mode;
    var red = el('score-red'), blue = el('score-blue');
    var timer = el('obj-timer'), sub = el('obj-sub');
    var bar = el('cartbar');
    if (mode === 'captures') {
      var captures = state.captures || { red: 0, blue: 0 };
      if (red) red.textContent = captures.red;
      if (blue) blue.textContent = captures.blue;
      if (timer) timer.textContent = formatTime(state.time_left || 0);
      if (sub) {
        var flags = state.flags || {};
        sub.innerHTML = 'first to ' + (state.target || 3) + ' captures &bull; ' +
          flagLabel('RED', flags.red) + ' &bull; ' + flagLabel('BLU', flags.blue);
      }
      if (bar) bar.style.display = 'none';
    } else if (mode === 'payload') {
      var wins = state.round_wins || { red: 0, blue: 0 };
      if (red) red.textContent = wins.red;
      if (blue) blue.textContent = wins.blue;
      if (timer) {
        timer.textContent = state.setup_left
          ? 'SETUP ' + formatTime(state.setup_left)
          : formatTime(state.time_left || 0);
      }
      if (sub) {
        var cart = state.cart || {};
        sub.innerHTML = (state.attackers || 'blue').toUpperCase() + ' attacking &bull; ' +
          Math.round((cart.progress || 0) * 100) + '% &bull; ' +
          (cart.blocked ? '<b style="color:#ff7a6e">BLOCKED</b>'
            : (cart.pushers ? cart.pushers + ' pushing' : 'cart idle'));
      }
      if (bar) {
        bar.style.display = 'block';
        var progress = (state.cart && state.cart.progress) || 0;
        bar.querySelector('.fill').style.width = (progress * 100) + '%';
        bar.querySelector('.cart').style.left = (progress * 100) + '%';
        if (!bar.dataset.built) {
          (state.checkpoints || []).forEach(function (fraction) {
            var mark = document.createElement('div');
            mark.className = 'cp';
            mark.style.left = (fraction * 100) + '%';
            bar.appendChild(mark);
          });
          bar.dataset.built = '1';
        }
      }
    } else {
      var plots = state.plots || [];
      var mine = null;
      plots.forEach(function (plot) {
        if (plot.index === this.client.myPlot) mine = plot;
      }, this);
      if (red) red.textContent = '';
      if (blue) blue.textContent = '';
      var mode2 = el('score-mode');
      if (mode2) {
        mode2.textContent = mine
          ? mine.name + ' -- ' + mine.built + '/' + mine.total + ' built'
          : 'Claim a plot to begin';
        mode2.style.fontSize = '15px';
      }
      if (timer) {
        timer.textContent = mine ? Math.round(mine.income) + ' coins/sec' : '';
      }
      if (sub) {
        sub.textContent = plots.filter(function (p) { return p.owner; }).length +
          ' of ' + plots.length + ' plots claimed';
      }
      if (bar) bar.style.display = 'none';
    }
  };

  function flagLabel(name, flag) {
    if (!flag) return name;
    if (flag.state === 'home') return name + ' flag: home';
    if (flag.state === 'carried') return name + ' flag: <b>TAKEN</b>';
    return name + ' flag: dropped';
  }

  function formatTime(seconds) {
    seconds = Math.max(0, Math.floor(seconds));
    var m = Math.floor(seconds / 60), s = seconds % 60;
    return m + ':' + (s < 10 ? '0' : '') + s;
  }
  HUD.prototype.formatTime = formatTime;

  // -------------------------------------------------------------------- vote
  HUD.prototype.updateVote = function (data) {
    var panel = el('vote');
    if (!panel) return;
    if (!data.open) {
      panel.classList.remove('on');
      if (data.result !== undefined) {
        this.toast(data.result ? 'Teams shuffled!' : 'Teams stay as they are.',
                   data.result ? 'good' : '');
      }
      return;
    }
    panel.classList.add('on');
    el('vote-yes').textContent = data.yes;
    el('vote-need').textContent = data.needed;
    el('vote-bar').style.width =
      Math.min(100, (data.yes / Math.max(1, data.needed)) * 100) + '%';
    el('vote-timer').textContent = Math.ceil(data.ends_in || 0);
  };

  // ------------------------------------------------------------------ toasts
  HUD.prototype.toast = function (text, kind, big) {
    var wrap = el('toast-wrap');
    if (!wrap) return;
    var node = document.createElement('div');
    node.className = 'toast ' + (kind || '') + (big ? ' big' : '');
    node.innerHTML = text;
    wrap.appendChild(node);
    setTimeout(function () {
      node.style.transition = 'opacity .5s, transform .5s';
      node.style.opacity = '0';
      node.style.transform = 'translateY(-8px)';
      setTimeout(function () { node.remove(); }, 520);
    }, big ? 4200 : 2600);
  };

  HUD.prototype.flashDamage = function () {
    var flash = el('damage-flash');
    if (!flash) return;
    flash.classList.add('on');
    setTimeout(function () { flash.classList.remove('on'); }, 60);
  };

  HUD.prototype.hurtArrow = function (angle) {
    var wrap = el('hurt-arrows');
    if (!wrap) return;
    var node = document.createElement('div');
    node.className = 'hurt-arrow';
    node.style.transform = 'rotate(' + angle + 'rad)';
    node.innerHTML = '<i></i>';
    wrap.appendChild(node);
    setTimeout(function () { node.remove(); }, 1300);
  };

  HUD.prototype.hitmarker = function () {
    var marker = el('hitmarker');
    if (!marker) return;
    marker.classList.add('show');
    clearTimeout(this._hitTimer);
    this._hitTimer = setTimeout(function () { marker.classList.remove('show'); }, 140);
  };

  HUD.prototype.setRespawn = function (seconds, by) {
    var wrap = el('respawn');
    if (!wrap) return;
    if (seconds === null) { wrap.classList.remove('on'); return; }
    wrap.classList.add('on');
    el('respawn-count').textContent = Math.max(0, Math.ceil(seconds));
    el('respawn-by').textContent = by ? 'Killed by ' + by : '';
  };

  HUD.prototype.setPrompt = function (text) {
    var node = el('prompt');
    if (!node) return;
    if (!text) { node.classList.remove('on'); return; }
    node.classList.add('on');
    node.innerHTML = text;
  };

  HUD.prototype.setCoins = function (value) {
    var wrap = el('coins');
    if (!wrap) return;
    wrap.classList.add('on');
    el('coin-amount').textContent = Math.floor(value).toLocaleString();
  };

  // ------------------------------------------------------------------ menus
  HUD.prototype.bindMenus = function () {
    var self = this;
    var client = this.client;
    function show(id, on) {
      var node = el(id);
      if (node) node.classList.toggle('on', on);
    }
    this.show = show;

    el('btn-resume').addEventListener('click', function () { client.setPaused(false); });
    el('btn-settings').addEventListener('click', function () {
      show('pause', false); show('settings', true);
    });
    el('btn-settings-close').addEventListener('click', function () {
      show('settings', false); show('pause', true);
    });
    el('btn-help').addEventListener('click', function () {
      show('pause', false); show('helpbox', true);
      el('help-body').innerHTML = self.helpHTML();
    });
    el('helpbox').addEventListener('click', function (event) {
      if (event.target === el('helpbox')) { show('helpbox', false); show('pause', true); }
    });
    el('btn-thirdperson').addEventListener('click', function () {
      client.toggleCamera();
    });
    el('btn-quit').addEventListener('click', function () {
      client.quit();
    });
    el('btn-defaults').addEventListener('click', function () {
      Settings.reset();
      self.syncSettings();
      self.buildKeybinds();
      client.applySettings();
    });

    bindRange('set-sens', 'val-sens', 'sensitivity', function (v) { return v.toFixed(2); });
    bindRange('set-fov', 'val-fov', 'fov', function (v) { return Math.round(v) + '&deg;'; });
    bindRange('set-scale', 'val-scale', 'renderScale', function (v) { return Math.round(v * 100) + '%'; });
    bindRange('set-far', 'val-far', 'viewDistance', function (v) { return Math.round(v); });
    bindRange('set-vol', 'val-vol', 'volume', function (v) { return Math.round(v * 100) + '%'; });
    bindCheck('set-invert', 'invertY');
    bindCheck('set-particles', 'particles');
    bindCheck('set-names', 'showNames');

    function bindRange(inputId, labelId, key, format) {
      var input = el(inputId);
      if (!input) return;
      input.addEventListener('input', function () {
        Settings[key] = parseFloat(input.value);
        var label = el(labelId);
        if (label) label.innerHTML = format(Settings[key]);
        Settings.save();
        client.applySettings();
      });
    }
    function bindCheck(inputId, key) {
      var input = el(inputId);
      if (!input) return;
      input.addEventListener('change', function () {
        Settings[key] = input.checked;
        Settings.save();
        client.applySettings();
      });
    }

    el('vote-yes-btn').addEventListener('click', function () {
      client.net.send({ t: 'vote', v: true });
    });
    el('vote-no-btn').addEventListener('click', function () {
      client.net.send({ t: 'vote', v: false });
    });

    // double click a name (chat or scoreboard) opens that profile
    document.addEventListener('dblclick', function (event) {
      var node = event.target.closest('[data-username]');
      if (!node) return;
      var name = node.dataset.username;
      if (!name) return;
      window.open('/profile/' + encodeURIComponent(name), '_blank');
    });
  };

  HUD.prototype.helpHTML = function () {
    var binds = Settings.binds;
    var rows = Object.keys(Settings.BIND_LABELS).map(function (action) {
      return '<div class="keyrow"><span>' + Settings.BIND_LABELS[action] +
        '</span><b>' + Settings.keyLabel(binds[action]) + '</b></div>';
    }).join('');
    return rows +
      '<div class="keyrow"><span>Fire</span><b>Left mouse</b></div>' +
      '<div class="keyrow"><span>Pause</span><b>Esc</b></div>' +
      '<p style="margin-top:10px;font-size:11px">Double click a name in chat or on the ' +
      'scoreboard to open that player\'s profile in a new tab.</p>' +
      '<button class="primary" onclick="document.getElementById(\'helpbox\')' +
      '.classList.remove(\'on\');document.getElementById(\'pause\').classList.add(\'on\')">Back</button>';
  };

  HUD.prototype.syncSettings = function () {
    setValue('set-sens', Settings.sensitivity, 'val-sens', Settings.sensitivity.toFixed(2));
    setValue('set-fov', Settings.fov, 'val-fov', Math.round(Settings.fov) + '&deg;');
    setValue('set-scale', Settings.renderScale, 'val-scale',
             Math.round(Settings.renderScale * 100) + '%');
    setValue('set-far', Settings.viewDistance, 'val-far', Math.round(Settings.viewDistance));
    setValue('set-vol', Settings.volume, 'val-vol', Math.round(Settings.volume * 100) + '%');
    check('set-invert', Settings.invertY);
    check('set-particles', Settings.particles);
    check('set-names', Settings.showNames);

    function setValue(id, value, labelId, label) {
      var input = el(id);
      if (input) input.value = value;
      var node = el(labelId);
      if (node) node.innerHTML = label;
    }
    function check(id, value) {
      var input = el(id);
      if (input) input.checked = !!value;
    }
  };

  HUD.prototype.buildKeybinds = function () {
    var wrap = el('keybinds');
    if (!wrap) return;
    var self = this;
    wrap.innerHTML = '';
    Object.keys(Settings.BIND_LABELS).forEach(function (action) {
      var row = document.createElement('div');
      row.className = 'keyrow';
      row.innerHTML = '<span>' + Settings.BIND_LABELS[action] + '</span>';
      var button = document.createElement('button');
      button.textContent = Settings.keyLabel(Settings.binds[action]);
      button.addEventListener('click', function () {
        button.classList.add('binding');
        button.textContent = 'press a key...';
        self.awaitingBind = { action: action, button: button };
      });
      row.appendChild(button);
      wrap.appendChild(row);
    });
  };

  HUD.prototype.captureBind = function (code) {
    if (!this.awaitingBind) return false;
    var action = this.awaitingBind.action;
    var button = this.awaitingBind.button;
    if (code !== 'Escape') {
      Object.keys(Settings.binds).forEach(function (other) {
        if (other !== action && Settings.binds[other] === code) Settings.binds[other] = '';
      });
      Settings.binds[action] = code;
      Settings.save();
    }
    button.classList.remove('binding');
    button.textContent = Settings.keyLabel(Settings.binds[action]);
    this.awaitingBind = null;
    this.buildKeybinds();
    return true;
  };

  HUD.prototype.setLoading = function (percent, message) {
    var bar = el('load-bar');
    if (bar) bar.style.width = Math.max(4, Math.min(100, percent)) + '%';
    var msg = el('load-msg');
    if (msg && message) msg.textContent = message;
    if (percent >= 100) {
      setTimeout(function () {
        var loading = el('loading');
        if (loading) loading.classList.add('hide');
      }, 260);
    }
  };

  HUD.prototype.showEndCard = function (data) {
    var body = el('end-body');
    var title = el('end-title');
    if (!body || !title) return;
    var winner = data.winner ? data.winner.toUpperCase() : 'NOBODY';
    title.textContent = data.match_over === false ? 'Round over' : 'Match over';
    var colour = data.winner === 'red' ? '#b8383b'
      : (data.winner === 'blue' ? '#2f6f9f' : '#6f8095');
    body.innerHTML = '<h2 style="font-size:26px;color:' + colour + '">' + winner +
      ' WINS</h2><p>' + this.escape(data.reason || '') + '</p>' +
      '<div style="max-height:220px;overflow:auto"><table style="width:100%;font-size:12px">' +
      (data.scores || []).slice(0, 12).map(function (row) {
        return '<tr><td style="text-align:left">' + row.name + '</td><td>' +
          row.kills + ' / ' + row.deaths + '</td><td style="text-align:right">' +
          row.score + '</td></tr>';
      }).join('') + '</table></div>';
    this.show('endcard', true);
    var self = this;
    clearTimeout(this._endTimer);
    this._endTimer = setTimeout(function () { self.show('endcard', false); }, 7000);
  };

  global.HUD = HUD;
})(window);
