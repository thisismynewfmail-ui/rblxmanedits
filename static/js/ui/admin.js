/* Admin dashboard: live stats, credit adjustments and item grants. */
(function () {
  'use strict';

  function refresh() {
    Site.get('/api/admin/live').then(function (res) {
      if (!res.ok) return;
      setText('s-users', res.site.users.toLocaleString());
      setText('s-online', res.online_users);
      setText('s-ingame', res.in_game);
      setText('s-visits', res.site.visits.toLocaleString());
      setText('s-credits', res.money.circulating.toLocaleString());
      setText('s-unusuals', res.item_stats.unusuals.toLocaleString());
      res.worlds.forEach(function (world) {
        var row = document.querySelector('[data-world-row="' + world.id + '"]');
        if (!row) return;
        row.querySelector('.p').textContent = world.players;
        row.querySelector('.i').textContent = world.instances;
        row.querySelector('.v').textContent = world.visits.toLocaleString();
        row.querySelector('.t').textContent = world.tick_ms + ' ms';
        row.querySelector('.s').innerHTML = world.online
          ? '<span class="pill green">running</span>'
          : '<span class="pill red">offline</span>';
      });
      var hosts = document.getElementById('admin-hosts');
      if (hosts && res.hosts.length) {
        var head = hosts.rows[0];
        var html = res.hosts.map(function (h) {
          return '<tr><td>' + esc(h.world) + '</td><td>' + esc(h.pid) + '</td><td>' + esc(h.port) +
            '</td><td>' + Math.floor(h.uptime) + 's</td><td>' + h.restarts +
            '</td><td>' + (h.alive ? '<span class="pill green">yes</span>'
                                   : '<span class="pill red">no</span>') + '</td></tr>';
        }).join('');
        hosts.innerHTML = '';
        hosts.appendChild(head);
        hosts.insertAdjacentHTML('beforeend', html);
      }
    }).catch(function () {});
  }

  function esc(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function openUser(username) {
    Site.get('/api/admin/user?username=' + encodeURIComponent(username))
      .then(function (res) {
        if (!res.ok) { Site.toast(res.error, 'bad'); return; }
        document.getElementById('am-title').textContent = username;
        var inv = res.inventory.map(function (item) {
          return '<tr><td>' + esc(item.name) + '</td><td>' + esc(item.slot_label) +
            '</td><td>' + (item.tier === 'unusual'
              ? '<span class="pill purple">Unusual: ' + esc(item.effect_name) + '</span>'
              : '<span class="pill">Normal</span>') +
            '</td><td class="right"><button class="btn small danger" data-revoke="' +
            item.inv_id + '" data-user="' + username + '">Remove</button></td></tr>';
        }).join('');
        var ledger = res.ledger.map(function (row) {
          return '<tr><td>' + esc(row.reason) + '</td><td class="right">' +
            (row.delta > 0 ? '+' : '') + row.delta.toLocaleString() +
            '</td><td class="right">' + row.balance_after.toLocaleString() + '</td></tr>';
        }).join('');
        document.getElementById('am-body').innerHTML =
          '<dl class="stats"><div><dt>Credits</dt><dd>' + res.credits.toLocaleString() +
          '</dd></div><div><dt>Kills</dt><dd>' + res.stats.total.kills +
          '</dd></div><div><dt>Deaths</dt><dd>' + res.stats.total.deaths +
          '</dd></div></dl>' +
          '<div class="inline-form" style="margin:10px 0">' +
          '<button class="btn small danger" data-ban="' + esc(username) +
          '">Toggle suspension</button>' +
          '<a class="btn small" href="/profile/' + encodeURIComponent(username) +
          '" target="_blank">Open profile</a>' +
          '</div>' +
          '<h3>Inventory (' + res.inventory.length + ')</h3>' +
          '<table class="grid">' + inv + '</table>' +
          '<h3 style="margin-top:10px">Credit ledger</h3>' +
          '<table class="grid">' + ledger + '</table>';
        document.getElementById('admin-modal').classList.remove('hidden');
      });
  }

  document.addEventListener('click', function (event) {
    var target = event.target.closest('[data-admin-open]');
    if (target) { openUser(target.dataset.adminOpen); return; }
    target = event.target.closest('#am-close');
    if (target) { document.getElementById('admin-modal').classList.add('hidden'); return; }
    target = event.target.closest('[data-revoke]');
    if (target) {
      Site.post('/api/admin/revoke', {
        username: target.dataset.user, inv_id: parseInt(target.dataset.revoke, 10)
      }).then(function (res) {
        if (!res.ok) { Site.toast(res.error, 'bad'); return; }
        Site.toast('Item removed.');
        openUser(target.dataset.user);
      });
      return;
    }
    target = event.target.closest('[data-ban]');
    if (target) {
      Site.post('/api/admin/ban', { username: target.dataset.ban }).then(function (res) {
        if (!res.ok) { Site.toast(res.error, 'bad'); return; }
        Site.toast(res.banned ? 'Account suspended.' : 'Account restored.');
      });
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    setInterval(refresh, 3000);

    document.getElementById('cr-go').addEventListener('click', function () {
      var payload = {
        username: document.getElementById('cr-user').value.trim(),
        amount: parseInt(document.getElementById('cr-amount').value, 10) || 0,
        mode: document.getElementById('cr-mode').value,
        reason: document.getElementById('cr-reason').value
      };
      Site.post('/api/admin/credits', payload).then(function (res) {
        var out = document.getElementById('cr-result');
        if (!res.ok) {
          out.innerHTML = '<div class="notice bad">' + esc(res.error) + '</div>';
          return;
        }
        out.innerHTML = '<div class="notice">' + esc(res.username) + ' now has ' +
          res.balance.toLocaleString() + ' credits.</div>';
        var row = document.querySelector('[data-user-row="' + res.username + '"] .credits');
        if (row) row.textContent = res.balance.toLocaleString();
      });
    });

    document.getElementById('gr-go').addEventListener('click', function () {
      var payload = {
        username: document.getElementById('gr-user').value.trim(),
        item_id: document.getElementById('gr-item').value,
        tier: document.getElementById('gr-tier').value,
        effect: document.getElementById('gr-effect').value
      };
      Site.post('/api/admin/grant', payload).then(function (res) {
        var out = document.getElementById('gr-result');
        if (!res.ok) {
          out.innerHTML = '<div class="notice bad">' + esc(res.error) + '</div>';
          return;
        }
        out.innerHTML = '<div class="notice">Granted ' + esc(res.item.item_id) +
          (res.item.tier === 'unusual' ? ' (UNUSUAL: ' + esc(res.item.effect) + ')' : '') +
          '.</div>';
      });
    });
  });
})();
