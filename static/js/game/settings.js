/* Game settings and key bindings, stored per browser. */
(function (global) {
  'use strict';

  var KEY = 'blockhaven.settings.v1';

  var DEFAULT_BINDS = {
    forward: 'KeyW', back: 'KeyS', left: 'KeyA', right: 'KeyD',
    jump: 'Space', sprint: 'ShiftLeft', crouch: 'ControlLeft',
    reload: 'KeyR', interact: 'KeyE', camera: 'KeyP',
    chat: 'KeyY', teamchat: 'KeyU', scoreboard: 'Tab', map: 'KeyM',
    slot1: 'Digit1', slot2: 'Digit2', slot3: 'Digit3', slot4: 'Digit4',
    slot5: 'Digit5'
  };

  var BIND_LABELS = {
    forward: 'Move forward', back: 'Move back', left: 'Strafe left',
    right: 'Strafe right', jump: 'Jump', sprint: 'Walk slowly',
    crouch: 'Crouch', reload: 'Reload', interact: 'Interact',
    camera: 'First / third person', chat: 'Chat', teamchat: 'Team chat',
    scoreboard: 'Scoreboard', map: 'Objective info',
    slot1: 'Hotbar 1', slot2: 'Hotbar 2', slot3: 'Hotbar 3',
    slot4: 'Hotbar 4', slot5: 'Hotbar 5'
  };

  var DEFAULTS = {
    sensitivity: 0.16,
    fov: 82,
    invertY: false,
    renderScale: 1,
    viewDistance: 900,
    particles: true,
    showNames: true,
    volume: 0.55,
    binds: DEFAULT_BINDS
  };

  function load() {
    var data = {};
    try { data = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { data = {}; }
    var out = {};
    Object.keys(DEFAULTS).forEach(function (k) {
      out[k] = (data[k] === undefined) ? DEFAULTS[k] : data[k];
    });
    out.binds = Object.assign({}, DEFAULT_BINDS, data.binds || {});
    return out;
  }

  var Settings = load();
  Settings.save = function () {
    try {
      var copy = {};
      Object.keys(DEFAULTS).forEach(function (k) { copy[k] = Settings[k]; });
      localStorage.setItem(KEY, JSON.stringify(copy));
    } catch (e) { /* private browsing */ }
  };
  Settings.reset = function () {
    var fresh = JSON.parse(JSON.stringify(DEFAULTS));
    Object.keys(fresh).forEach(function (k) { Settings[k] = fresh[k]; });
    Settings.save();
  };
  Settings.DEFAULTS = DEFAULTS;
  Settings.BIND_LABELS = BIND_LABELS;
  Settings.DEFAULT_BINDS = DEFAULT_BINDS;

  Settings.actionFor = function (code) {
    var binds = Settings.binds;
    for (var action in binds) {
      if (binds[action] === code) return action;
    }
    return null;
  };

  Settings.keyLabel = function (code) {
    if (!code) return '--';
    return String(code)
      .replace('Key', '').replace('Digit', '')
      .replace('Left', ' L').replace('Right', ' R')
      .replace('Arrow', '');
  };

  global.Settings = Settings;
})(window);
