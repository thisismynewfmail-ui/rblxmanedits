/* Market page: the themed buy confirmation and the unbox reveal. */
(function () {
  'use strict';

  function coin() {
    return '<span class="coin" style="vertical-align:-1px"></span> ';
  }

  /* Confirmation and reveal are both Site.dialog panels, so a purchase never
     leaves the site's own chrome for a browser alert. */
  function confirmBuy(button) {
    var price = parseInt(button.dataset.price, 10) || 0;
    var name = button.dataset.name || 'this item';
    if (price <= 0) return Promise.resolve(true);
    var body =
      '<div class="spread" style="gap:12px;align-items:flex-start">' +
      '<canvas class="item-thumb" width="180" height="180" data-item="' +
      button.dataset.buy + '" style="width:90px;height:90px;flex:0 0 90px;' +
      'background:var(--tile-normal);border:1px solid var(--line-soft);border-radius:4px"></canvas>' +
      '<div style="min-width:0"><b style="font-size:13px">' + Site.escape(name) + '</b>' +
      '<div class="muted tiny" style="margin-top:2px;text-transform:uppercase">' +
      Site.escape(button.dataset.slot || '') + '</div>' +
      '<p style="margin:8px 0 0">Buy for ' + coin() + '<b>' + price.toLocaleString() +
      '</b> credits?</p>' +
      (button.dataset.unusual === '1'
        ? '<p class="tiny" style="color:var(--unusual-ink);margin:6px 0 0">' +
          'Hats roll for Unusual at 0.5% on purchase.</p>' : '') +
      '</div></div>';
    return Site.dialog({
      title: 'Confirm purchase',
      tone: 'gold',
      bodyHtml: body,
      confirm: 'Buy it',
      cancel: 'Not now'
    });
  }

  function showUnbox(result) {
    var unusual = result.tier === 'unusual';
    var body =
      '<div class="center">' +
      '<canvas id="unbox-canvas" width="320" height="320" style="width:200px;height:200px;' +
      'max-width:100%;background:' + (unusual ? 'var(--tile-unusual)' : 'var(--tile-normal)') +
      ';border:1px solid var(--line-soft);border-radius:6px"></canvas>' +
      '<h2 style="margin-top:10px;color:' + (unusual ? 'var(--unusual-ink)' : 'var(--ink-strong)') +
      '">' + Site.escape(result.name) + '</h2>' +
      '<p class="muted">' + (unusual
        ? 'Effect: <b>' + Site.escape(result.effect_name) + '</b> &mdash; serial #' +
          Site.escape(String(result.serial))
        : 'Serial #' + Site.escape(String(result.serial)) + ' &bull; ' +
          (result.price || 0).toLocaleString() + ' credits') + '</p>' +
      '<p class="tiny muted">New balance: ' + coin() +
      (result.balance || 0).toLocaleString() + '</p></div>';
    Site.dialog({
      title: unusual ? 'UNUSUAL UNBOXED!' : 'Purchase complete',
      tone: unusual ? 'purple' : 'green',
      bodyHtml: body,
      confirm: 'Nice',
      cancel: null
    });
    // the canvas only exists once the dialog is in the document
    setTimeout(function () {
      var canvas = document.getElementById('unbox-canvas');
      if (canvas && window.Thumbs) {
        Thumbs.renderItem(canvas, result.item_id, result.effect || '');
      }
    }, 30);
  }

  function bumpOwned(card, itemId, count) {
    if (!card) return;
    var flag = card.querySelector('[data-owned="' + itemId + '"]');
    if (!flag) {
      flag = document.createElement('span');
      flag.className = 'owned-flag';
      flag.dataset.owned = itemId;
      card.querySelector('.thumb-wrap').appendChild(flag);
    }
    flag.classList.remove('hidden');
    flag.dataset.count = String(count);
    flag.textContent = 'Owned x' + count;
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-buy]').forEach(function (button) {
      button.addEventListener('click', function () {
        confirmBuy(button).then(function (yes) {
          if (!yes) return;
          var label = button.textContent;
          button.disabled = true;
          button.textContent = '...';
          Site.post('/api/market/buy', { item_id: button.dataset.buy })
            .then(function (res) {
              button.disabled = false;
              button.textContent = label;
              if (!res.ok) { Site.toast(res.error, 'bad'); return; }
              var wallet = document.getElementById('wallet-amount');
              if (wallet) wallet.textContent = (res.balance || 0).toLocaleString();
              // the server reports how many copies are owned now, so the count
              // is right even if another tab bought one a second ago
              bumpOwned(button.closest('.item'), button.dataset.buy, res.owned);
              showUnbox(res);
            });
        });
      });
    });
  });
})();
