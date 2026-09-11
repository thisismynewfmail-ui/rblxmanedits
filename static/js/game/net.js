/* Websocket transport for the game view.
   The join ticket is minted by the website (signed, short lived); the socket
   itself is proxied through the same port into the world's host process. */
(function (global) {
  'use strict';

  function Net(worldId, instance) {
    this.worldId = worldId;
    this.instance = instance || '';
    this.handlers = {};
    this.socket = null;
    this.connected = false;
    this.queue = [];
    this.pingSent = 0;
    this.ping = 0;
    this.closedByUs = false;
    this.retries = 0;
  }

  Net.prototype.on = function (kind, fn) {
    (this.handlers[kind] || (this.handlers[kind] = [])).push(fn);
    return this;
  };

  Net.prototype.emit = function (kind, payload) {
    var list = this.handlers[kind];
    if (list) for (var i = 0; i < list.length; i++) list[i](payload);
    var any = this.handlers['*'];
    if (any) for (i = 0; i < any.length; i++) any[i](kind, payload);
  };

  Net.prototype.connect = function () {
    var self = this;
    return fetch('/api/game/join', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': (window.BH && BH.csrf) || '',
        'X-Requested-With': 'fetch'
      },
      body: JSON.stringify({ world_id: this.worldId, instance: this.instance })
    }).then(function (r) { return r.json(); }).then(function (res) {
      if (!res.ok) throw new Error(res.error || 'Could not join.');
      var proto = location.protocol === 'https:' ? 'wss://' : 'ws://';
      var url = proto + location.host + res.ws;
      self.open(url);
      return res;
    });
  };

  Net.prototype.open = function (url) {
    var self = this;
    var socket = new WebSocket(url);
    this.socket = socket;
    socket.onopen = function () {
      self.connected = true;
      self.retries = 0;
      self.emit('open');
      while (self.queue.length) socket.send(self.queue.shift());
      self.pingTimer = setInterval(function () { self.sendPing(); }, 2500);
    };
    socket.onmessage = function (event) {
      var message;
      try { message = JSON.parse(event.data); } catch (e) { return; }
      if (message.t === 'pong') {
        self.ping = Math.max(0, Math.round(performance.now() - self.pingSent));
        self.emit('ping', self.ping);
        return;
      }
      self.emit(message.t, message);
    };
    socket.onclose = function () {
      self.connected = false;
      clearInterval(self.pingTimer);
      self.emit('close', { byUs: self.closedByUs });
    };
    socket.onerror = function () { self.emit('error'); };
  };

  Net.prototype.send = function (payload) {
    var text = JSON.stringify(payload);
    if (this.socket && this.socket.readyState === 1) this.socket.send(text);
    else if (this.queue.length < 40) this.queue.push(text);
  };

  Net.prototype.sendPing = function () {
    this.pingSent = performance.now();
    this.send({ t: 'ping', c: this.pingSent | 0 });
  };

  Net.prototype.close = function () {
    this.closedByUs = true;
    clearInterval(this.pingTimer);
    if (this.socket) { try { this.socket.close(); } catch (e) {} }
  };

  global.Net = Net;
})(window);
