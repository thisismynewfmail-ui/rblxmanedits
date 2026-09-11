/* BLOCKHAVEN site -- shared page behaviour (posts, comments, friends, follows). */
(function (global) {
  'use strict';

  var Site = {};

  Site.post = function (url, body) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': (window.BH && BH.csrf) || '',
        'X-Requested-With': 'fetch'
      },
      body: JSON.stringify(body || {})
    }).then(function (r) { return r.json(); });
  };

  Site.get = function (url) {
    return fetch(url, { headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { return r.json(); });
  };

  Site.toast = function (message, kind) {
    var wrap = document.getElementById('site-toasts');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.id = 'site-toasts';
      wrap.style.cssText = 'position:fixed;right:14px;bottom:14px;z-index:999;' +
        'display:flex;flex-direction:column;gap:6px;align-items:flex-end';
      document.body.appendChild(wrap);
    }
    var el = document.createElement('div');
    el.className = 'notice ' + (kind === 'bad' ? 'bad' : (kind === 'info' ? 'info' : ''));
    el.style.cssText = 'margin:0;box-shadow:0 4px 14px rgba(20,60,100,.28);' +
      'max-width:320px;animation:none';
    el.textContent = message;
    wrap.appendChild(el);
    setTimeout(function () {
      el.style.transition = 'opacity .4s, transform .4s';
      el.style.opacity = '0';
      el.style.transform = 'translateY(8px)';
      setTimeout(function () { el.remove(); }, 420);
    }, 3200);
  };

  Site.escape = function (text) {
    var div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  };

  Site.ago = function (timestamp) {
    var delta = Math.max(0, Math.floor(Date.now() / 1000) - timestamp);
    if (delta < 60) return delta + ' seconds ago';
    if (delta < 3600) return Math.floor(delta / 60) + ' minutes ago';
    if (delta < 86400) return Math.floor(delta / 3600) + ' hours ago';
    return Math.floor(delta / 86400) + ' days ago';
  };

  // ------------------------------------------------------------------ posts
  function bindPosts() {
    var form = document.getElementById('post-form');
    var body = document.getElementById('post-body');
    var count = document.getElementById('post-count');
    if (body && count) {
      body.addEventListener('input', function () {
        count.textContent = String(400 - body.value.length);
      });
    }
    var submit = document.getElementById('post-submit');
    if (submit) {
      submit.addEventListener('click', function () {
        var text = (body.value || '').trim();
        if (!text) { Site.toast('Write something first.', 'bad'); return; }
        submit.disabled = true;
        Site.post('/api/social/post', { body: text }).then(function (res) {
          submit.disabled = false;
          if (!res.ok) { Site.toast(res.error, 'bad'); return; }
          body.value = '';
          if (count) count.textContent = '400';
          Site.toast('Posted!');
          setTimeout(function () { location.reload(); }, 350);
        });
      });
    }
    if (form) form.addEventListener('submit', function (e) { e.preventDefault(); });
  }

  document.addEventListener('click', function (event) {
    var target = event.target.closest('[data-post-like]');
    if (target) {
      var id = parseInt(target.dataset.postLike, 10);
      Site.post('/api/social/post/like', { id: id }).then(function (res) {
        if (!res.ok) { Site.toast(res.error, 'bad'); return; }
        var counter = target.querySelector('.likecount');
        if (counter) counter.textContent = res.likes;
        target.classList.toggle('liked', res.liked);
        target.style.color = res.liked ? '#c4281c' : '';
      });
      return;
    }
    target = event.target.closest('[data-post-delete]');
    if (target) {
      if (!confirm('Delete this post?')) return;
      Site.post('/api/social/post/delete', { id: parseInt(target.dataset.postDelete, 10) })
        .then(function (res) {
          if (!res.ok) { Site.toast(res.error, 'bad'); return; }
          var post = target.closest('.post');
          if (post) post.remove();
        });
      return;
    }
    target = event.target.closest('[data-post-comments]');
    if (target) {
      var postId = parseInt(target.dataset.postComments, 10);
      var box = document.querySelector('[data-comments-for="' + postId + '"]');
      if (!box) return;
      if (!box.classList.contains('hidden')) { box.classList.add('hidden'); return; }
      box.classList.remove('hidden');
      box.innerHTML = '<div class="muted tiny">loading...</div>';
      Site.get('/api/social/post/comments?id=' + postId).then(function (res) {
        renderComments(box, postId, res.comments || []);
      });
      return;
    }
    target = event.target.closest('[data-wall-delete]');
    if (target) {
      if (!confirm('Remove this comment?')) return;
      Site.post('/api/profile/comment/delete', { id: parseInt(target.dataset.wallDelete, 10) })
        .then(function (res) {
          if (!res.ok) { Site.toast(res.error, 'bad'); return; }
          var node = target.closest('.post');
          if (node) node.remove();
        });
      return;
    }
    target = event.target.closest('[data-friend]');
    if (target) {
      var action = target.dataset.friend;
      var username = target.dataset.username;
      target.disabled = true;
      Site.post('/api/social/friend', { action: action, username: username })
        .then(function (res) {
          target.disabled = false;
          if (!res.ok) { Site.toast(res.error, 'bad'); return; }
          Site.toast(labelFor(res.state, username));
          if (target.id === 'friend-btn') updateFriendButton(target, res.state);
          else setTimeout(function () { location.reload(); }, 400);
        });
      return;
    }
    target = event.target.closest('[data-follow-toggle], #follow-btn');
    if (target) {
      var name = target.dataset.followToggle || target.dataset.username;
      target.disabled = true;
      Site.post('/api/social/follow', { username: name }).then(function (res) {
        target.disabled = false;
        if (!res.ok) { Site.toast(res.error, 'bad'); return; }
        target.textContent = res.following ? 'Unfollow' : 'Follow';
        target.dataset.state = res.following ? '1' : '0';
        Site.toast(res.following ? 'Following ' + name : 'Unfollowed ' + name);
      });
    }
  });

  function labelFor(state, username) {
    if (state === 'friends') return 'You are now friends with ' + username + '!';
    if (state === 'pending_out') return 'Friend request sent to ' + username + '.';
    return 'Updated.';
  }

  function updateFriendButton(button, state) {
    button.dataset.state = state;
    button.classList.remove('go', 'danger');
    if (state === 'friends') {
      button.textContent = 'Remove friend';
      button.dataset.friend = 'remove';
      button.classList.add('danger');
    } else if (state === 'pending_out') {
      button.textContent = 'Request sent';
      button.dataset.friend = 'remove';
    } else {
      button.textContent = 'Add friend';
      button.dataset.friend = 'request';
      button.classList.add('go');
    }
  }

  function renderComments(box, postId, comments) {
    var html = comments.map(function (c) {
      return '<div class="comment"><a href="/profile/' + encodeURIComponent(c.username) +
        '"><b>' + Site.escape(c.username) + '</b></a> <span class="when">' +
        Site.ago(c.created_at) + '</span><div>' + Site.escape(c.body) + '</div></div>';
    }).join('');
    if (window.BH && BH.user) {
      html += '<form class="commentbox" data-comment-form="' + postId + '">' +
        '<input type="text" maxlength="300" placeholder="Write a reply">' +
        '<button class="btn small primary">Reply</button></form>';
    }
    box.innerHTML = html || '<div class="muted tiny">No comments yet.</div>';
  }

  document.addEventListener('submit', function (event) {
    var form = event.target.closest('[data-comment-form]');
    if (form) {
      event.preventDefault();
      var postId = parseInt(form.dataset.commentForm, 10);
      var input = form.querySelector('input');
      var text = (input.value || '').trim();
      if (!text) return;
      Site.post('/api/social/post/comment', { id: postId, body: text })
        .then(function (res) {
          if (!res.ok) { Site.toast(res.error, 'bad'); return; }
          var box = document.querySelector('[data-comments-for="' + postId + '"]');
          renderComments(box, postId, res.comments || []);
        });
      return;
    }
    var wall = event.target.closest('#wall-form');
    if (wall) {
      event.preventDefault();
      var body = document.getElementById('wall-body');
      var value = (body.value || '').trim();
      if (!value) return;
      Site.post('/api/profile/comment', {
        username: wall.dataset.username, body: value
      }).then(function (res) {
        if (!res.ok) { Site.toast(res.error, 'bad'); return; }
        body.value = '';
        renderWall(res.wall || []);
        Site.toast('Comment posted.');
      });
    }
  });

  function renderWall(rows) {
    var list = document.getElementById('wall-list');
    if (!list) return;
    list.innerHTML = rows.map(function (c) {
      return '<div class="post" data-wall="' + c.id + '"><div class="spread"><div>' +
        '<a class="who" href="/profile/' + encodeURIComponent(c.username) + '">' +
        Site.escape(c.username) + '</a> <span class="when">' + Site.ago(c.created_at) +
        '</span></div><a class="tiny muted" data-wall-delete="' + c.id + '">delete</a>' +
        '</div><div class="body">' + Site.escape(c.body) + '</div></div>';
    }).join('');
  }

  // ------------------------------------------------------- live nav counters
  function pollCounts() {
    if (!window.BH || !BH.user) return;
    Site.get('/api/social/counts').then(function (res) {
      if (!res.ok) return;
      updateBadge('/messages', res.unread, 'alert');
      updateBadge('/friends', res.requests, '');
    }).catch(function () {});
  }

  function updateBadge(href, value, cls) {
    var link = document.querySelector('.tabbar a[href="' + href + '"]');
    if (!link) return;
    var badge = link.querySelector('.badge');
    if (!value) { if (badge) badge.remove(); return; }
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'badge ' + cls;
      link.appendChild(document.createTextNode(' '));
      link.appendChild(badge);
    }
    badge.textContent = value;
  }

  document.addEventListener('DOMContentLoaded', function () {
    bindPosts();
    if (window.BH && BH.user) setInterval(pollCounts, 25000);
  });

  global.Site = Site;
})(window);
