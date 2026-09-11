/* Market page: buying, and the unbox reveal for Unusual rolls. */
(function () {
  'use strict';

  function showUnbox(result) {
    var modal = document.getElementById('unbox-modal');
    if (!modal) return;
    var unusual = result.tier === 'unusual';
    modal.classList.remove('hidden');
    document.getElementById('unbox-title').textContent =
      unusual ? 'UNUSUAL UNBOXED!' : 'Purchase complete';
    document.getElementById('unbox-title').className =
      'panel-head ' + (unusual ? 'purple' : 'green');
    document.getElementById('unbox-name').textContent = result.name;
    document.getElementById('unbox-name').style.color = unusual ? '#5d1f9c' : '#1b3d5f';
    document.getElementById('unbox-sub').innerHTML = unusual
      ? 'Effect: <b>' + Site.escape(result.effect_name) + '</b> &mdash; serial #' +
        Site.escape(result.serial)
      : 'Serial #' + result.serial + ' &bull; ' + result.price.toLocaleString() + ' credits';
    var canvas = document.getElementById('unbox-canvas');
    if (canvas) {
      canvas.dataset.item = result.item_id;
      canvas.dataset.effect = result.effect || '';
      Thumbs.renderItem(canvas, result.item_id, result.effect || '');
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var close = document.getElementById('unbox-close');
    if (close) {
      close.addEventListener('click', function () {
        document.getElementById('unbox-modal').classList.add('hidden');
      });
    }
    document.querySelectorAll('[data-buy]').forEach(function (button) {
      button.addEventListener('click', function () {
        var itemId = button.dataset.buy;
        var price = parseInt(button.dataset.price, 10) || 0;
        if (price > 0 && !confirm('Buy ' + button.dataset.name + ' for ' +
                                  price.toLocaleString() + ' credits?')) return;
        button.disabled = true;
        button.textContent = '...';
        Site.post('/api/market/buy', { item_id: itemId }).then(function (res) {
          button.disabled = false;
          button.textContent = 'Buy';
          if (!res.ok) { Site.toast(res.error, 'bad'); return; }
          var wallet = document.getElementById('wallet-amount');
          if (wallet) wallet.textContent = res.balance.toLocaleString();
          var card = button.closest('.item');
          if (card) {
            var owned = card.querySelector('.owned-flag');
            if (!owned) {
              owned = document.createElement('span');
              owned.className = 'owned-flag';
              card.querySelector('.thumb-wrap').appendChild(owned);
              owned.dataset.count = '0';
            }
            var count = (parseInt(owned.dataset.count || '0', 10) || 0) + 1;
            owned.dataset.count = String(count);
            owned.textContent = 'Owned x' + count;
          }
          showUnbox(res);
        });
      });
    });
  });
})();
