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
      if (res.graph) paintGraph(res.graph);
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

  // ------------------------------------------------------------ social graph
  var graph = null;
  var graphFitted = false;

  function paintGraph(data) {
    var canvas = document.getElementById('graph-canvas');
    if (!canvas || typeof SocialGraph === 'undefined') return;
    var empty = document.getElementById('graph-empty');
    if (empty) empty.classList.toggle('hidden', !!(data.nodes || []).length);
    if (!graph) {
      graph = new SocialGraph(canvas, {
        onSelect: showGraphCard,
        onStats: writeGraphStats
      });
      // handy from the console when tuning the layout
      window.__graph = graph;
    }
    graph.setData(data);
    /* Fit twice and then never again.  The first fit is early so the mesh is
       not off screen while it is still spreading out; the second is once the
       layout has cooled and the final extents are known.  Re-fitting on every
       three-second refresh would yank the view about while it is being read. */
    if (!graphFitted && (data.nodes || []).length) {
      graphFitted = true;
      setTimeout(function () { graph.fit(); }, 500);
      setTimeout(function () { graph.fit(); }, 3200);
    }
  }

  function writeGraphStats(stats) {
    setText('graph-count', stats.nodes + ' accounts, ' + stats.edges + ' friendships');
    var bits = [
      stats.components + ' cluster' + (stats.components === 1 ? '' : 's'),
      stats.online + ' online',
      stats.admins + ' admin' + (stats.admins === 1 ? '' : 's')
    ];
    if (stats.pending) bits.push(stats.pending + ' request' + (stats.pending === 1 ? '' : 's') + ' pending');
    if (stats.isolated) bits.push(stats.isolated + ' with no friends');
    setText('graph-stats', bits.join('  \u00b7  '));
  }

  function showGraphCard(node) {
    var card = document.getElementById('graph-card');
    if (!card) return;
    if (!node) { card.classList.add('hidden'); return; }
    var seen = node.lastSeen
      ? new Date(node.lastSeen * 1000).toLocaleString()
      : 'never';
    var online = (Date.now() / 1000 - node.lastSeen) < 300;
    card.innerHTML =
      '<b>' + escapeHtml(node.name) + '</b>' +
      (node.admin ? ' <span class="pill red">admin</span>' : '') +
      (online ? ' <span class="pill green">online</span>' : '') +
      '<div class="tiny">' + node.friends + ' friend' +
      (node.friends === 1 ? '' : 's') + '</div>' +
      '<div class="tiny muted">last seen ' + escapeHtml(seen) + '</div>' +
      '<div style="margin-top:6px;display:flex;gap:5px;flex-wrap:wrap">' +
      '<a class="btn small" href="/profile/' + encodeURIComponent(node.name) + '">Profile</a>' +
      '<button class="btn small primary" data-user-open="' +
      escapeHtml(node.name) + '">Manage</button></div>';
    card.classList.remove('hidden');
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;',
                '"': '&quot;', "'": '&#39;' })[ch];
    });
  }

  function bindGraphControls() {
    var key = document.getElementById('graph-key');
    var keyToggle = document.getElementById('graph-key-toggle');
    if (keyToggle && key) {
      keyToggle.addEventListener('click', function (event) {
        event.preventDefault();
        var hidden = key.classList.toggle('hidden');
        keyToggle.textContent = hidden ? 'show key' : 'hide key';
      });
    }
    var freeze = document.getElementById('graph-freeze');
    if (freeze) {
      freeze.addEventListener('click', function (event) {
        event.preventDefault();
        if (!graph) return;
        graph.frozen = !graph.frozen;
        freeze.textContent = graph.frozen ? 'resume' : 'freeze';
      });
    }
    // the card's Manage button opens the same player modal the table does
    document.addEventListener('click', function (event) {
      var button = event.target.closest('[data-user-open]');
      if (button) openUser(button.dataset.userOpen);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    bindGraphControls();
    refresh();
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
