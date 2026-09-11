/* World browser: live player counts, ratings and favourites. */
(function () {
  'use strict';

  function refresh() {
    Site.get('/api/worlds/status').then(function (res) {
      if (!res.ok) return;
      Object.keys(res.worlds).forEach(function (id) {
        var info = res.worlds[id];
        document.querySelectorAll('[data-live-players="' + id + '"]').forEach(function (el) {
          el.textContent = info.players;
        });
        document.querySelectorAll('[data-live-instances="' + id + '"]').forEach(function (el) {
          el.textContent = info.instances;
        });
        var table = document.querySelector('table[data-instances="' + id + '"]');
        if (table) renderInstances(table, id, info);
      });
      var total = document.getElementById('global-players');
      if (total) total.textContent = res.total;
    }).catch(function () {});
  }

  function renderInstances(table, id, info) {
    var wide = table.querySelector('tr th:nth-child(5)') !== null;
    var head = table.rows[0];
    var html = '';
    if (!info.instance_list.length) {
      html = '<tr><td colspan="' + (wide ? 5 : 4) + '" class="muted">' +
        'No instance running yet &mdash; pressing Load starts one.</td></tr>';
    } else {
      info.instance_list.forEach(function (inst) {
        html += '<tr><td>#' + inst.id + '</td><td>' + inst.count + '/' + inst.max +
          '</td><td>' + inst.phase + '</td>' +
          (wide ? '<td>' + inst.round + '</td>' : '') +
          '<td class="right"><a class="btn small go" href="/' + id +
          '?instance=' + inst.id + '">Join</a></td></tr>';
      });
    }
    table.innerHTML = '';
    table.appendChild(head);
    table.insertAdjacentHTML('beforeend', html);
  }

  document.addEventListener('DOMContentLoaded', function () {
    setInterval(refresh, 5000);
    setTimeout(refresh, 800);

    document.querySelectorAll('[data-vote]').forEach(function (button) {
      button.addEventListener('click', function () {
        Site.post('/api/worlds/vote', {
          world_id: button.dataset.world, vote: button.dataset.vote
        }).then(function (res) {
          if (!res.ok) { Site.toast(res.error, 'bad'); return; }
          document.getElementById('rating-value').textContent = res.stats.rating;
          document.getElementById('rating-votes').textContent = res.stats.rating_votes;
          document.querySelectorAll('[data-vote]').forEach(function (b) {
            b.classList.remove('go', 'danger');
          });
          if (res.vote === 1) button.classList.add('go');
          if (res.vote === -1) button.classList.add('danger');
        });
      });
    });

    document.querySelectorAll('[data-fav]').forEach(function (button) {
      button.addEventListener('click', function () {
        Site.post('/api/worlds/favourite', { world_id: button.dataset.fav })
          .then(function (res) {
            if (!res.ok) { Site.toast(res.error, 'bad'); return; }
            button.innerHTML = res.favourite ? '&#9733; Favourited' : '&#9734; Favourite';
            button.classList.toggle('primary', res.favourite);
          });
      });
    });
  });
})();
