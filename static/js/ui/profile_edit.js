/* Profile editor: the three pinned slots.
   Selection order is preserved, so slot 1 is the first item clicked. */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var pool = document.getElementById('pin-pool');
    if (!pool) return;
    var slots = document.querySelectorAll('[id^="pin-field-"]').length;
    var status = document.getElementById('pin-status');

    function current() {
      var out = [];
      for (var i = 0; i < slots; i++) {
        var field = document.getElementById('pin-field-' + i);
        var value = parseInt(field && field.value, 10) || 0;
        if (value) out.push(value);
      }
      return out;
    }

    function write(list) {
      for (var i = 0; i < slots; i++) {
        var field = document.getElementById('pin-field-' + i);
        if (field) field.value = list[i] || 0;
      }
      paint(list);
    }

    function paint(list) {
      pool.querySelectorAll('[data-pin]').forEach(function (pick) {
        pick.classList.toggle('on', list.indexOf(parseInt(pick.dataset.pin, 10)) >= 0);
      });
      for (var i = 0; i < slots; i++) {
        var box = document.querySelector('[data-pin-preview="' + i + '"]');
        if (!box) continue;
        var invId = list[i];
        if (!invId) {
          box.className = 'pinslot';
          box.textContent = 'empty';
          continue;
        }
        var pick = pool.querySelector('[data-pin="' + invId + '"]');
        if (!pick) { box.className = 'pinslot'; box.textContent = 'empty'; continue; }
        box.className = 'item tier-' + (pick.dataset.tier || 'normal');
        box.innerHTML = '<div class="thumb-wrap">' +
          '<canvas class="thumb item-thumb" width="160" height="160" data-item="' +
          pick.dataset.item + '" data-effect="' + (pick.dataset.effect || '') +
          '"></canvas></div><div class="meta"><span class="iname">' +
          (pick.dataset.name || '') + '</span></div>';
      }
      if (window.Thumbs) Thumbs.rescan();
      if (status) {
        status.textContent = list.length
          ? list.length + ' of ' + slots + ' slots used.'
          : 'Click an item to pin or unpin it.';
      }
    }

    pool.addEventListener('click', function (event) {
      var pick = event.target.closest('[data-pin]');
      if (!pick) return;
      var invId = parseInt(pick.dataset.pin, 10);
      var list = current();
      var at = list.indexOf(invId);
      if (at >= 0) {
        list.splice(at, 1);
      } else if (list.length >= slots) {
        if (window.Site) Site.toast('You can pin ' + slots + ' items. Unpin one first.', 'bad');
        return;
      } else {
        list.push(invId);
      }
      write(list);
    });

    paint(current());
  });
})();
