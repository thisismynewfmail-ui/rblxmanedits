/* Profile editor: the three pinned slots, arranged by dragging.

   Pinning used to be click-to-append and click-to-remove, which meant you
   could not say *where* something went -- the order was whatever order you
   happened to click in, and changing your mind about slot 1 meant unpinning
   everything after it.  Here a slot is a place you drop something:

     * drag from the inventory below into a slot to pin it there,
     * drag a slot onto another slot to swap the two,
     * drag a pinned item back to the inventory (or off the row) to unpin it,
     * drop onto a slot that is already full and the two trade places.

   HTML5 drag and drop has no touch support at all, so the pointer events
   path below is the real implementation and the native one is only wired up
   as a courtesy for people who expect a drag image.  Click still works as a
   fallback: it fills the first empty slot, or clears a filled one. */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var pool = document.getElementById('pin-pool');
    var row = document.getElementById('pin-preview');
    if (!pool || !row) return;
    var slots = document.querySelectorAll('[id^="pin-field-"]').length;
    var status = document.getElementById('pin-status');

    // ------------------------------------------------------------- state
    function current() {
      var out = [];
      for (var i = 0; i < slots; i++) {
        var field = document.getElementById('pin-field-' + i);
        out.push(parseInt(field && field.value, 10) || 0);
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

    function filled(list) {
      return list.filter(function (v) { return v; }).length;
    }

    // ------------------------------------------------------------ painting
    function pickFor(invId) {
      return pool.querySelector('[data-pin="' + invId + '"]');
    }

    function paint(list) {
      pool.querySelectorAll('[data-pin]').forEach(function (pick) {
        pick.classList.toggle('on',
          list.indexOf(parseInt(pick.dataset.pin, 10)) >= 0);
      });
      for (var i = 0; i < slots; i++) {
        var box = row.querySelector('[data-pin-preview="' + i + '"]');
        if (!box) continue;
        var invId = list[i];
        var pick = invId ? pickFor(invId) : null;
        if (!pick) {
          box.className = 'pinslot';
          box.removeAttribute('data-holds');
          box.innerHTML = '<span class="slot-n">' + (i + 1) + '</span>' +
                          '<span class="slot-hint">drop an item here</span>';
          continue;
        }
        box.className = 'pinslot filled item tier-' + (pick.dataset.tier || 'normal');
        box.dataset.holds = String(invId);
        box.innerHTML =
          '<span class="slot-n">' + (i + 1) + '</span>' +
          '<button type="button" class="slot-clear" data-clear="' + i +
          '" title="Unpin">&times;</button>' +
          '<div class="thumb-wrap">' +
          '<canvas class="thumb item-thumb" width="160" height="160" data-item="' +
          pick.dataset.item + '" data-effect="' + (pick.dataset.effect || '') +
          '"></canvas></div><div class="meta"><span class="iname">' +
          escapeHtml(pick.dataset.name || '') + '</span></div>';
      }
      if (window.Thumbs && Thumbs.scan) Thumbs.scan(row);
      else if (window.Thumbs) Thumbs.rescan();
      if (status) {
        var used = filled(list);
        status.textContent = used
          ? used + ' of ' + slots + ' pinned. Drag between the slots to reorder.'
          : 'Drag an item up into a slot to pin it.';
      }
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, function (ch) {
        return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;',
                  '"': '&quot;', "'": '&#39;' })[ch];
      });
    }

    // ------------------------------------------------------------- moves
    /* Put invId into a slot.  If that slot already holds something the two
       trade places when the item came from another slot, and the displaced
       item simply goes back to the pool when it came from the pool. */
    function drop(invId, toSlot, fromSlot) {
      var list = current();
      var displaced = list[toSlot] || 0;
      if (fromSlot !== null && fromSlot !== undefined && fromSlot >= 0) {
        list[fromSlot] = displaced;
      } else {
        // an item can only be pinned once
        var already = list.indexOf(invId);
        if (already >= 0) list[already] = displaced;
      }
      list[toSlot] = invId;
      write(list);
    }

    function unpin(slot) {
      var list = current();
      list[slot] = 0;
      write(list);
    }

    function firstEmpty(list) {
      for (var i = 0; i < slots; i++) if (!list[i]) return i;
      return -1;
    }

    // --------------------------------------------------------- dragging
    // One implementation for mouse, pen and touch, because HTML5 drag and
    // drop does not fire at all on a touch screen.
    var drag = null;
    /* A completed drag is followed by a click on whatever the pointer was
       captured to, and the click fallbacks below would read that as "toggle
       this item" -- so a successful drop was instantly undone.  This swallows
       exactly that one click. */
    var swallowClick = false;

    function slotIndexAt(x, y) {
      var found = -1;
      row.querySelectorAll('[data-pin-preview]').forEach(function (box) {
        var r = box.getBoundingClientRect();
        if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) {
          found = parseInt(box.dataset.pinPreview, 10);
        }
      });
      return found;
    }

    function overPool(x, y) {
      var r = pool.getBoundingClientRect();
      return x >= r.left && x <= r.right && y >= r.top && y <= r.bottom;
    }

    function startDrag(event, invId, fromSlot, sourceEl) {
      drag = {
        invId: invId, fromSlot: fromSlot, source: sourceEl,
        pointerId: event.pointerId, moved: false,
        startX: event.clientX, startY: event.clientY, ghost: null
      };
      sourceEl.setPointerCapture(event.pointerId);
    }

    function makeGhost(source) {
      var ghost = source.cloneNode(true);
      ghost.className = 'pin-ghost';
      var r = source.getBoundingClientRect();
      ghost.style.width = r.width + 'px';
      ghost.style.height = r.height + 'px';
      document.body.appendChild(ghost);
      // the clone's canvas is blank, so copy the pixels across
      var from = source.querySelector('canvas');
      var to = ghost.querySelector('canvas');
      if (from && to) {
        try { to.getContext('2d').drawImage(from, 0, 0); } catch (e) {}
      }
      return ghost;
    }

    function moveGhost(x, y) {
      if (!drag || !drag.ghost) return;
      drag.ghost.style.left = x + 'px';
      drag.ghost.style.top = y + 'px';
    }

    function highlight(x, y) {
      var index = slotIndexAt(x, y);
      row.querySelectorAll('[data-pin-preview]').forEach(function (box) {
        box.classList.toggle('over',
          parseInt(box.dataset.pinPreview, 10) === index);
      });
      pool.classList.toggle('over',
        drag && drag.fromSlot >= 0 && overPool(x, y));
    }

    function endDrag(x, y) {
      if (!drag) return;
      var d = drag;
      drag = null;
      if (d.ghost) d.ghost.remove();
      row.querySelectorAll('[data-pin-preview]').forEach(function (box) {
        box.classList.remove('over');
      });
      pool.classList.remove('over');
      document.body.classList.remove('pin-dragging');
      if (!d.moved) return;          // a click, handled elsewhere
      swallowClick = true;
      setTimeout(function () { swallowClick = false; }, 0);

      var target = slotIndexAt(x, y);
      if (target >= 0) { drop(d.invId, target, d.fromSlot); return; }
      // dropped outside the slot row: pulling a pinned item out unpins it
      if (d.fromSlot >= 0) unpin(d.fromSlot);
    }

    function bindDragSource(root) {
      root.addEventListener('pointerdown', function (event) {
        if (event.button !== undefined && event.button !== 0) return;
        var fromPool = event.target.closest('[data-pin]');
        var fromSlot = event.target.closest('[data-pin-preview]');
        if (event.target.closest('[data-clear]')) return;
        if (fromPool) {
          startDrag(event, parseInt(fromPool.dataset.pin, 10), -1, fromPool);
        } else if (fromSlot && fromSlot.dataset.holds) {
          startDrag(event, parseInt(fromSlot.dataset.holds, 10),
                    parseInt(fromSlot.dataset.pinPreview, 10), fromSlot);
        }
      });
    }

    document.addEventListener('pointermove', function (event) {
      if (!drag || event.pointerId !== drag.pointerId) return;
      if (!drag.moved) {
        var dx = event.clientX - drag.startX;
        var dy = event.clientY - drag.startY;
        // a few pixels of slop, so a tap is still a tap
        if (Math.abs(dx) + Math.abs(dy) < 6) return;
        drag.moved = true;
        drag.ghost = makeGhost(drag.source);
        document.body.classList.add('pin-dragging');
      }
      event.preventDefault();
      moveGhost(event.clientX, event.clientY);
      highlight(event.clientX, event.clientY);
    }, { passive: false });

    document.addEventListener('pointerup', function (event) {
      if (!drag || event.pointerId !== drag.pointerId) return;
      endDrag(event.clientX, event.clientY);
    });
    document.addEventListener('pointercancel', function () {
      if (drag) endDrag(-1, -1);
    });

    bindDragSource(pool);
    bindDragSource(row);

    // --------------------------------------------------------- clicking
    // Still supported, because dragging is a poor fit for a keyboard and an
    // awkward one on a small screen.
    pool.addEventListener('click', function (event) {
      if (swallowClick) return;
      var pick = event.target.closest('[data-pin]');
      if (!pick) return;
      var invId = parseInt(pick.dataset.pin, 10);
      var list = current();
      var at = list.indexOf(invId);
      if (at >= 0) { unpin(at); return; }
      var empty = firstEmpty(list);
      if (empty < 0) {
        if (window.Site) {
          Site.toast('All ' + slots + ' slots are full. Drag onto one to swap.', 'bad');
        }
        return;
      }
      drop(invId, empty, -1);
    });

    row.addEventListener('click', function (event) {
      if (swallowClick) return;
      var clear = event.target.closest('[data-clear]');
      if (clear) { unpin(parseInt(clear.dataset.clear, 10)); }
    });

    paint(current());
  });
})();
