/* Avatar editor page. */
(function () {
  'use strict';

  var preview = null;
  var selectedHotslot = 0;

  function livePreview() {
    if (preview) return preview;
    var el = document.getElementById('avatar-preview');
    preview = el && el.__preview;
    return preview;
  }

  function applyDescriptor(descriptor) {
    var p = livePreview();
    if (p && p.setDescriptor) p.setDescriptor(descriptor);
    if (window.Thumbs) Thumbs.avatarCache[BH.user.name] = descriptor;
    refreshHotbar(descriptor);
  }

  function refreshHotbar(descriptor) {
    (descriptor.hotbar || []).forEach(function (entry, index) {
      var name = document.querySelector('[data-hot-name="' + index + '"]');
      var canvas = document.querySelector('[data-hot-canvas="' + index + '"]');
      var slot = document.querySelector('[data-hotslot="' + index + '"]');
      if (name) name.textContent = entry ? entry.name : 'empty';
      if (slot) slot.classList.toggle('on', !!entry);
      if (canvas) {
        var ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (entry) { canvas.dataset.item = entry.item_id; Thumbs.renderItem(canvas, entry.item_id, ''); }
        else canvas.dataset.item = '';
      }
    });
    document.querySelectorAll('[data-hotslot]').forEach(function (el) {
      el.style.outline = (parseInt(el.dataset.hotslot, 10) === selectedHotslot)
        ? '2px solid #2c7fc0' : '';
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    // -------------------------------------------------------------- tabs
    document.querySelectorAll('[data-slot-tab]').forEach(function (tab) {
      tab.addEventListener('click', function () {
        var slot = tab.dataset.slotTab;
        document.querySelectorAll('[data-slot-tab]').forEach(function (t) {
          t.classList.toggle('on', t === tab);
        });
        document.querySelectorAll('[data-slot-panel]').forEach(function (panel) {
          panel.classList.toggle('hidden', panel.dataset.slotPanel !== slot);
        });
        if (window.Thumbs) Thumbs.rescan();
      });
    });

    // ------------------------------------------------------------ colours
    document.querySelectorAll('.swatches').forEach(function (group) {
      group.addEventListener('click', function (event) {
        var swatch = event.target.closest('.swatch');
        if (!swatch) return;
        var part = group.dataset.part;
        var colour = swatch.dataset.color;
        setColour(part, colour, group);
      });
    });
    document.querySelectorAll('[data-custom]').forEach(function (input) {
      input.addEventListener('change', function () {
        setColour(input.dataset.custom, input.value, null);
      });
    });

    function setColour(part, colour, group) {
      var payload = { colors: {} };
      payload.colors[part] = colour;
      var status = document.getElementById('color-status');
      if (status) status.textContent = 'Saving...';
      Site.post('/api/avatar/colors', payload).then(function (res) {
        if (!res.ok) { Site.toast(res.error, 'bad'); return; }
        if (status) status.textContent = 'Saved.';
        var hex = document.getElementById('hex-' + part);
        if (hex) hex.textContent = colour;
        var picker = document.querySelector('[data-custom="' + part + '"]');
        if (picker) picker.value = colour;
        if (group) {
          group.querySelectorAll('.swatch').forEach(function (s) {
            s.classList.toggle('on', s.dataset.color === colour);
          });
        }
        applyDescriptor(res.avatar);
      });
    }

    // ------------------------------------------------------------ equipping
    document.querySelectorAll('[data-equip]').forEach(function (pick) {
      pick.addEventListener('click', function () {
        var invId = parseInt(pick.dataset.equip, 10) || 0;
        var slot = pick.dataset.slot;
        Site.post('/api/avatar/equip', { slot: slot, inv_id: invId })
          .then(function (res) {
            if (!res.ok) { Site.toast(res.error, 'bad'); return; }
            document.querySelectorAll('[data-slot="' + slot + '"][data-equip]')
              .forEach(function (other) { other.classList.toggle('on', other === pick); });
            applyDescriptor(res.avatar);
            Site.toast(invId ? 'Equipped.' : 'Removed.');
          });
      });
    });

    // -------------------------------------------------------------- hotbar
    document.querySelectorAll('[data-hotslot]').forEach(function (slot) {
      slot.addEventListener('click', function () {
        selectedHotslot = parseInt(slot.dataset.hotslot, 10);
        document.querySelectorAll('[data-hotslot]').forEach(function (el) {
          el.style.outline = el === slot ? '2px solid #2c7fc0' : '';
        });
        var status = document.getElementById('hotbar-status');
        if (status) status.textContent = 'Slot ' + (selectedHotslot + 1) + ' selected.';
      });
    });
    document.querySelectorAll('[data-usable]').forEach(function (pick) {
      pick.addEventListener('click', function () {
        var invId = parseInt(pick.dataset.usable, 10);
        Site.post('/api/avatar/hotbar', { index: selectedHotslot, inv_id: invId })
          .then(function (res) {
            if (!res.ok) { Site.toast(res.error, 'bad'); return; }
            applyDescriptor(res.avatar);
            Site.toast('Placed in slot ' + (selectedHotslot + 1) + '.');
          });
      });
    });
    var clear = document.getElementById('clear-slot');
    if (clear) {
      clear.addEventListener('click', function () {
        Site.post('/api/avatar/hotbar', { index: selectedHotslot, inv_id: 0 })
          .then(function (res) {
            if (!res.ok) { Site.toast(res.error, 'bad'); return; }
            applyDescriptor(res.avatar);
            Site.toast('Slot ' + (selectedHotslot + 1) + ' cleared.');
          });
      });
    }

    var spin = document.getElementById('spin-toggle');
    if (spin) {
      spin.addEventListener('click', function () {
        var p = livePreview();
        if (!p) return;
        p.spin = !p.spin;
        spin.textContent = p.spin ? 'Pause spin' : 'Resume spin';
      });
    }

    Site.get('/api/avatar').then(function (res) {
      if (res.ok) refreshHotbar(res.avatar);
    });
  });
})();
