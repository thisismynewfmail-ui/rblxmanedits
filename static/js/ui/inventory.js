/* Inventory page: wear and sell, both through the site's own dialogs. */
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
          // one slot holds one item, so clear the old "Worn" marker first
          document.querySelectorAll('[data-slot="' + button.dataset.slot +
                                    '"][data-equip-inv]').forEach(function (other) {
            var card = other.closest('.item');
            var flag = card && card.querySelector('.owned-flag');
            if (flag && flag.textContent === 'Worn') flag.remove();
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
        var refund = parseInt(button.dataset.refund, 10) || 0;
        Site.dialog({
          title: 'Sell this item?',
          tone: 'red',
          danger: true,
          confirm: 'Sell it',
          cancel: 'Keep it',
          bodyHtml: '<div class="spread" style="gap:12px;align-items:flex-start">' +
            '<canvas class="item-thumb" width="180" height="180" data-item="' +
            button.dataset.item + '" style="width:80px;height:80px;flex:0 0 80px;' +
            'background:var(--tile-normal);border:1px solid var(--line-soft);border-radius:4px"></canvas>' +
            '<div><b>' + Site.escape(button.dataset.name) + '</b>' +
            '<p style="margin:6px 0 0">Selling returns 40% of the catalogue price: ' +
            '<span class="coin" style="vertical-align:-1px"></span> <b>' +
            refund.toLocaleString() + '</b>.</p>' +
            '<p class="tiny muted" style="margin:6px 0 0">This copy, serial and any ' +
            'Unusual effect on it are gone for good.</p></div></div>'
        }).then(function (yes) {
          if (!yes) return;
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
  });
})();
