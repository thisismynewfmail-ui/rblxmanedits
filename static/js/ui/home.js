/* Home and welcome pages: the countdown clock and the randomised hero. */
(function () {
  'use strict';

  // ------------------------------------------------------------- countdown
  function bindCountdown() {
    var bar = document.querySelector('[data-countdown]');
    if (!bar) return;
    var remaining = parseInt(bar.dataset.countdown, 10) || 0;
    var fields = {
      d: bar.querySelector('[data-cd="d"]'),
      h: bar.querySelector('[data-cd="h"]'),
      m: bar.querySelector('[data-cd="m"]'),
      s: bar.querySelector('[data-cd="s"]')
    };
    function pad(value) { return value < 10 ? '0' + value : String(value); }
    function tick() {
      var left = Math.max(0, remaining);
      if (fields.d) fields.d.textContent = Math.floor(left / 86400);
      if (fields.h) fields.h.textContent = pad(Math.floor(left / 3600) % 24);
      if (fields.m) fields.m.textContent = pad(Math.floor(left / 60) % 60);
      if (fields.s) fields.s.textContent = pad(left % 60);
      remaining -= 1;
    }
    tick();
    setInterval(tick, 1000);
  }

  // ------------------------------------------------------------------ hero
  var POSE_WORDS = {
    idle: 'standing about', walk: 'on the move', run: 'legging it',
    jump: 'mid-air', sit: 'taking five'
  };

  function describe(hero) {
    var items = hero.items || {};
    var bits = [];
    var build = hero.body_type === 'female' ? 'Female build' : 'Male build';
    bits.push(build);
    var names = [];
    ['hat', 'face', 'shirt', 'pants', 'back'].forEach(function (slot) {
      var entry = items[slot];
      if (!entry) return;
      var meta = (window.Thumbs && Thumbs.catalog && Thumbs.catalog[entry.item_id]) || null;
      if (meta && meta.name) names.push(meta.name);
    });
    if (names.length) bits.push(names.slice(0, 2).join(', '));
    bits.push(POSE_WORDS[hero.pose] || 'standing about');
    var text = bits.join(' · ');
    if (items.hat && items.hat.effect) {
      return text + ' · <span class="uw">UNUSUAL</span>';
    }
    return text;
  }

  function bindHero() {
    var stage = document.getElementById('hero-avatar');
    var button = document.getElementById('hero-reroll');
    var caption = document.getElementById('hero-caption');
    if (!stage) return;

    function paint(hero) {
      if (caption) caption.innerHTML = describe(hero);
      var preview = stage.__preview;
      if (preview && preview.setDescriptor) preview.setDescriptor(hero);
    }

    // the preview is built by the shared thumbnail pass, which may not have
    // run yet when this file executes
    function whenReady(fn) {
      if (stage.__preview) { fn(); return; }
      var tries = 0;
      var poll = setInterval(function () {
        if (stage.__preview || ++tries > 40) { clearInterval(poll); fn(); }
      }, 100);
    }

    whenReady(function () {
      var initial;
      try { initial = JSON.parse(stage.dataset.avatar); } catch (e) { initial = null; }
      if (initial) {
        initial.pose = stage.dataset.heroPose || initial.pose;
        paint(initial);
      }
    });

    if (!button) return;
    var busy = false;
    button.addEventListener('click', function () {
      if (busy) return;
      busy = true;
      button.classList.add('spinning');
      // The roll is done on the server so it draws from the same catalogue
      // the rest of the site does.
      fetch('/api/hero', { headers: { 'Accept': 'application/json' },
                           credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (res && res.ok && res.hero) {
            stage.classList.add('swapping');
            setTimeout(function () {
              paint(res.hero);
              stage.classList.remove('swapping');
            }, 160);
          }
        })
        .catch(function () {})
        .then(function () {
          busy = false;
          button.classList.remove('spinning');
        });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    bindCountdown();
    bindHero();
  });
})();
