/* Inventory page: wear and sell. */
(function () {
  'use strict';
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-equip-inv]').forEach(function (button) {
      button.addEventListener('click', function () {
        Site.post('/api/avatar/equip', {
          slot: button.dataset.slot,
          inv_id: parseInt(button.dataset.equipInv, 10)
        }).then(function (res) {
          if (!res.ok) { Site.toast(res.error, 'bad'); return; }
          Site.toast('Equipped. Check your profile!');
          document.querySelectorAll('.item .owned-flag').forEach(function (flag) {
            if (flag.textContent === 'Worn') flag.remove();
          });
          var card = button.closest('.item');
          if (card && !card.querySelector('.owned-flag')) {
            var flag = document.createElement('span');
            flag.className = 'owned-flag';
            flag.textContent = 'Worn';
            card.querySelector('.thumb-wrap').appendChild(flag);
          }
        });
      });
    });
    document.querySelectorAll('[data-sell]').forEach(function (button) {
      button.addEventListener('click', function () {
        if (!confirm('Sell ' + button.dataset.name + ' back for 40% of its price?')) return;
        Site.post('/api/market/sell', { inv_id: parseInt(button.dataset.sell, 10) })
          .then(function (res) {
            if (!res.ok) { Site.toast(res.error, 'bad'); return; }
            Site.toast('Sold for ' + res.refund.toLocaleString() + ' credits.');
            var card = button.closest('.item');
            if (card) card.remove();
            var wallet = document.getElementById('wallet-amount');
            if (wallet) wallet.textContent = res.balance.toLocaleString();
            var big = document.getElementById('wallet-big');
            if (big) big.textContent = res.balance.toLocaleString();
          });
      });
    });
  });
})();
