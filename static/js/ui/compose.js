/* BLOCKHAVEN -- the message composer's "To" combo box.

   A player-name autocomplete rather than a spelling test.  It opens on focus
   with your friends already listed (that is who you write to), narrows as you
   type, and is driven with the keyboard as well as the pointer, because a
   list you can only reach with a mouse is not much of an improvement.

   Everything degrades: the markup is a plain text input with a list beside
   it, so if this file never loads the form still posts a username. */
(function (global) {
  'use strict';

  var MIN_GAP_MS = 140;   // keystroke debounce

  function ready(fn) {
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  ready(function () {
    var combo = document.getElementById('to-combo');
    var input = document.getElementById('compose-to');
    var list = document.getElementById('to-list');
    var clear = document.getElementById('to-clear');
    if (!combo || !input || !list) return;

    var open = false;
    var rows = [];
    var active = -1;
    var timer = null;
    var lastTerm = null;
    var cache = {};

    function setOpen(value) {
      open = value && rows.length > 0;
      list.hidden = !open;
      combo.classList.toggle('on', open);
      input.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (!open) setActive(-1);
    }

    function setActive(index) {
      active = index;
      var items = list.querySelectorAll('.combo-opt');
      for (var i = 0; i < items.length; i++) {
        var on = i === index;
        items[i].classList.toggle('on', on);
        items[i].setAttribute('aria-selected', on ? 'true' : 'false');
        // keep the highlighted row in view when driving with the keyboard
        if (on && items[i].scrollIntoView) {
          items[i].scrollIntoView({ block: 'nearest' });
        }
      }
      input.setAttribute('aria-activedescendant',
                         index >= 0 ? 'to-opt-' + index : '');
    }

    function highlight(name, term) {
      if (!term) return escapeHtml(name);
      var at = name.toLowerCase().indexOf(term.toLowerCase());
      if (at < 0) return escapeHtml(name);
      return escapeHtml(name.slice(0, at)) + '<b>' +
             escapeHtml(name.slice(at, at + term.length)) + '</b>' +
             escapeHtml(name.slice(at + term.length));
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, function (ch) {
        return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;',
                  '"': '&quot;', "'": '&#39;' })[ch];
      });
    }

    function render(term) {
      list.innerHTML = '';
      rows.forEach(function (row, index) {
        var li = document.createElement('li');
        li.className = 'combo-opt';
        li.id = 'to-opt-' + index;
        li.setAttribute('role', 'option');
        li.setAttribute('aria-selected', 'false');
        li.dataset.name = row.username;

        var art = document.createElement('canvas');
        art.className = 'thumb avatar-thumb';
        art.width = 96; art.height = 96;
        art.dataset.user = row.username;
        li.appendChild(art);

        var name = document.createElement('span');
        name.className = 'combo-name';
        name.innerHTML = highlight(row.username, term);
        li.appendChild(name);

        var tag = document.createElement('span');
        tag.className = 'combo-tag';
        if (row.friend) { tag.textContent = 'friend'; tag.classList.add('friend'); }
        else if (row.online) { tag.textContent = 'online'; tag.classList.add('online'); }
        li.appendChild(tag);

        list.appendChild(li);
      });
      // the avatar heads are drawn by the shared thumbnail pass
      if (global.Thumbs && Thumbs.scan) Thumbs.scan(list);
      setActive(-1);
    }

    function choose(name) {
      input.value = name;
      setOpen(false);
      var next = document.getElementById('compose-subject');
      if (next && !next.value) next.focus();
    }

    function fetchSuggestions(term) {
      var key = term.toLowerCase();
      if (cache[key]) { rows = cache[key]; render(term); setOpen(true); return; }
      var url = '/api/users/suggest' + (term ? '?q=' + encodeURIComponent(term) : '');
      fetch(url, { headers: { 'Accept': 'application/json' },
                   credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (!res || !res.ok) return;
          // a slow reply for a term the writer has already moved past is
          // stale; dropping it stops the list flickering backwards
          if ((res.term || '') !== term.toLowerCase()) return;
          cache[key] = res.users || [];
          rows = cache[key];
          render(term);
          setOpen(document.activeElement === input);
        })
        .catch(function () {});
    }

    function schedule() {
      var term = input.value.trim();
      if (term === lastTerm) return;
      lastTerm = term;
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () { fetchSuggestions(term); }, MIN_GAP_MS);
    }

    input.addEventListener('focus', function () {
      lastTerm = null;
      schedule();
    });
    input.addEventListener('input', schedule);

    input.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        if (!open) { schedule(); return; }
        event.preventDefault();
        var step = event.key === 'ArrowDown' ? 1 : -1;
        var next = active + step;
        if (next < 0) next = rows.length - 1;
        if (next >= rows.length) next = 0;
        setActive(next);
        return;
      }
      if (event.key === 'Enter' && open && active >= 0) {
        event.preventDefault();
        choose(rows[active].username);
        return;
      }
      if (event.key === 'Escape' && open) {
        event.preventDefault();
        setOpen(false);
      }
      if (event.key === 'Tab' && open && active >= 0) {
        choose(rows[active].username);
      }
    });

    // mousedown rather than click: blur would have closed the list first
    list.addEventListener('mousedown', function (event) {
      var opt = event.target.closest('.combo-opt');
      if (!opt) return;
      event.preventDefault();
      choose(opt.dataset.name);
    });

    input.addEventListener('blur', function () {
      // let a tap on an option land before the list goes away
      setTimeout(function () { setOpen(false); }, 120);
    });

    if (clear) {
      clear.addEventListener('click', function () {
        input.value = '';
        lastTerm = null;
        input.focus();
        schedule();
      });
    }

    document.addEventListener('click', function (event) {
      if (!combo.contains(event.target)) setOpen(false);
    });
  });
})(window);
