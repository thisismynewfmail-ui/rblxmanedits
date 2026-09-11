/* Home page: the spotlight countdown. */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
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
  });
})();
