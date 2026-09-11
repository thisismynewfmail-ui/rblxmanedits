/* BLOCKHAVEN admin -- the social graph.

   A force-directed drawing of every accepted friendship, on a 2D canvas.
   Three forces, integrated with simple Verlet-ish damping:

     * repulsion   every node pushes every other away (Coulomb), which is what
                   stops the mesh collapsing into a dot;
     * springs     every edge pulls its two ends toward a rest length, which
                   is what makes friends sit near each other;
     * gravity     a weak pull toward the middle, so disconnected components
                   do not drift off the canvas for ever.

   Repulsion is O(n^2).  That is fine here and nowhere near the bottleneck at
   the few hundred accounts an admin view deals with; if this ever needs
   thousands it wants a quadtree, not a rewrite.

   The layout is *warm*: when the data refreshes, nodes that were already on
   screen keep their positions and only new ones are seeded.  Re-running the
   layout from scratch every three seconds would make the whole mesh jump
   about and be unreadable. */
(function (global) {
  'use strict';

  var REPULSION = 5200;      // how hard nodes push each other apart
  var SPRING = 0.0145;       // how hard an edge pulls its ends together
  var REST = 92;             // the length an edge would like to be
  var GRAVITY = 0.0022;      // pull toward the centre
  var DAMPING = 0.86;        // velocity retained per frame
  var MAX_STEP = 14;         // px per frame, so nothing ever teleports
  var ONLINE_WINDOW = 300;   // seconds; matches the site's "online" rule

  function Graph(canvas, options) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.options = options || {};
    this.nodes = [];
    this.byId = {};
    this.edges = [];
    this.view = { x: 0, y: 0, zoom: 1 };
    this.frozen = false;
    this.hover = null;
    this.selected = null;
    this.alpha = 1;          // simulated annealing: cools as it settles
    this.dpr = Math.min(global.devicePixelRatio || 1, 2);
    this.bind();
    this.frame = this.frame.bind(this);
    requestAnimationFrame(this.frame);
  }

  // ------------------------------------------------------------------ data
  Graph.prototype.setData = function (data) {
    var self = this;
    var seen = {};
    var width = this.canvas.clientWidth || 600;
    var height = this.canvas.clientHeight || 380;
    var fresh = 0;

    (data.nodes || []).forEach(function (row) {
      var node = self.byId[row.id];
      if (!node) {
        // New nodes are seeded on a ring rather than at the centre: dropping
        // everything on one point gives the repulsion nothing to work with
        // and the first second of layout is an explosion.
        var angle = Math.random() * Math.PI * 2;
        var radius = 60 + Math.random() * Math.min(width, height) * 0.3;
        node = {
          id: row.id,
          x: width / 2 + Math.cos(angle) * radius,
          y: height / 2 + Math.sin(angle) * radius,
          vx: 0, vy: 0
        };
        self.byId[row.id] = node;
        self.nodes.push(node);
        fresh++;
      }
      node.name = row.name;
      node.admin = !!row.admin;
      node.friends = row.friends || 0;
      node.lastSeen = row.last_seen || 0;
      seen[row.id] = true;
    });

    // drop anybody who is no longer in the payload
    this.nodes = this.nodes.filter(function (node) {
      if (seen[node.id]) return true;
      delete self.byId[node.id];
      if (self.selected && self.selected.id === node.id) self.selected = null;
      return false;
    });

    this.edges = (data.edges || []).map(function (row) {
      return { a: self.byId[row.a], b: self.byId[row.b], pending: !!row.pending };
    }).filter(function (edge) { return edge.a && edge.b; });

    // only reheat the layout when the shape actually changed
    if (fresh) this.alpha = Math.max(this.alpha, 0.9);
    else this.alpha = Math.max(this.alpha, 0.12);
    if (this.options.onStats) this.options.onStats(this.stats());
  };

  Graph.prototype.stats = function () {
    var online = 0, admins = 0, isolated = 0, pending = 0;
    var now = Date.now() / 1000;
    this.nodes.forEach(function (node) {
      if (now - node.lastSeen < ONLINE_WINDOW) online++;
      if (node.admin) admins++;
      if (!node.friends) isolated++;
    });
    this.edges.forEach(function (e) { if (e.pending) pending++; });
    return {
      nodes: this.nodes.length,
      edges: this.edges.length - pending,
      pending: pending,
      online: online,
      admins: admins,
      isolated: isolated,
      components: this.componentCount()
    };
  };

  /* How many separate islands the mesh is in.  A flood fill over the
     accepted edges only -- a pending request is not a connection yet. */
  Graph.prototype.componentCount = function () {
    var adjacency = {};
    this.nodes.forEach(function (n) { adjacency[n.id] = []; });
    this.edges.forEach(function (e) {
      if (e.pending) return;
      adjacency[e.a.id].push(e.b.id);
      adjacency[e.b.id].push(e.a.id);
    });
    var seen = {}, count = 0;
    this.nodes.forEach(function (node) {
      if (seen[node.id]) return;
      count++;
      var stack = [node.id];
      while (stack.length) {
        var id = stack.pop();
        if (seen[id]) continue;
        seen[id] = true;
        (adjacency[id] || []).forEach(function (next) {
          if (!seen[next]) stack.push(next);
        });
      }
    });
    return count;
  };

  // ----------------------------------------------------------------- layout
  Graph.prototype.step = function () {
    var nodes = this.nodes;
    var count = nodes.length;
    if (!count) return;
    var width = this.canvas.clientWidth || 600;
    var height = this.canvas.clientHeight || 380;
    var cx = width / 2, cy = height / 2;
    var alpha = this.alpha;

    for (var i = 0; i < count; i++) {
      var a = nodes[i];
      for (var j = i + 1; j < count; j++) {
        var b = nodes[j];
        var dx = b.x - a.x, dy = b.y - a.y;
        var distSq = dx * dx + dy * dy;
        if (distSq < 0.01) {
          // exactly coincident: nudge them apart deterministically enough
          dx = (i % 2 ? 1 : -1) * 0.5; dy = 0.5; distSq = 0.5;
        }
        if (distSq > 360000) continue;   // far enough away to ignore
        var dist = Math.sqrt(distSq);
        var force = REPULSION / distSq;
        var fx = (dx / dist) * force, fy = (dy / dist) * force;
        a.vx -= fx; a.vy -= fy;
        b.vx += fx; b.vy += fy;
      }
    }

    this.edges.forEach(function (edge) {
      var dx = edge.b.x - edge.a.x, dy = edge.b.y - edge.a.y;
      var dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
      // a pending request is a weaker tie than a friendship
      var k = SPRING * (edge.pending ? 0.45 : 1);
      var force = (dist - REST) * k;
      var fx = (dx / dist) * force, fy = (dy / dist) * force;
      edge.a.vx += fx; edge.a.vy += fy;
      edge.b.vx -= fx; edge.b.vy -= fy;
    });

    for (i = 0; i < count; i++) {
      var node = nodes[i];
      if (node === this.dragging) { node.vx = node.vy = 0; continue; }
      node.vx += (cx - node.x) * GRAVITY;
      node.vy += (cy - node.y) * GRAVITY;
      node.vx *= DAMPING;
      node.vy *= DAMPING;
      var step = Math.hypot(node.vx, node.vy) * alpha;
      if (step > MAX_STEP) {
        var scale = MAX_STEP / step;
        node.vx *= scale; node.vy *= scale;
      }
      node.x += node.vx * alpha;
      node.y += node.vy * alpha;
    }
    // cool off, so a settled graph stops jittering and stops burning CPU
    this.alpha = Math.max(0.02, this.alpha * 0.992);
  };

  // ---------------------------------------------------------------- drawing
  Graph.prototype.palette = function () {
    var dark = global.Site ? Site.isDark() : false;
    return dark
      ? { edge: 'rgba(150,180,215,.22)', pending: 'rgba(210,160,90,.30)',
          node: '#6f9fd0', hub: '#4fc3a1', admin: '#e0574f',
          online: '#7ede7a', ring: '#0d1722', label: '#c6d7e8',
          glow: 'rgba(120,190,255,.35)' }
      : { edge: 'rgba(60,100,140,.26)', pending: 'rgba(190,130,40,.34)',
          node: '#2f6f9f', hub: '#1f8f70', admin: '#c4281c',
          online: '#3f9f45', ring: '#ffffff', label: '#31465c',
          glow: 'rgba(40,110,180,.30)' };
  };

  Graph.prototype.colourFor = function (node, colours) {
    if (node.admin) return colours.admin;
    if (Date.now() / 1000 - node.lastSeen < ONLINE_WINDOW) return colours.online;
    if (node.friends >= 5) return colours.hub;
    return colours.node;
  };

  Graph.prototype.radiusFor = function (node) {
    // area grows with the friend count, so a hub reads as bigger without a
    // single account swallowing the canvas
    return 4.5 + Math.sqrt(node.friends) * 2.6;
  };

  Graph.prototype.resize = function () {
    var css = this.canvas.getBoundingClientRect();
    var w = Math.max(1, Math.round(css.width * this.dpr));
    var h = Math.max(1, Math.round(css.height * this.dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
  };

  Graph.prototype.draw = function () {
    var ctx = this.ctx;
    var colours = this.palette();
    var view = this.view;
    ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.save();
    ctx.translate(view.x, view.y);
    ctx.scale(view.zoom, view.zoom);

    var focus = this.selected || this.hover;
    var near = {};
    if (focus) {
      near[focus.id] = true;
      this.edges.forEach(function (e) {
        if (e.a === focus) near[e.b.id] = true;
        if (e.b === focus) near[e.a.id] = true;
      });
    }

    this.edges.forEach(function (edge) {
      var lit = focus && (edge.a === focus || edge.b === focus);
      ctx.beginPath();
      ctx.moveTo(edge.a.x, edge.a.y);
      ctx.lineTo(edge.b.x, edge.b.y);
      ctx.strokeStyle = lit ? colours.glow
                            : (edge.pending ? colours.pending : colours.edge);
      ctx.lineWidth = lit ? 2.2 : 1;
      if (edge.pending) { ctx.setLineDash([4, 3]); } else { ctx.setLineDash([]); }
      ctx.stroke();
    });
    ctx.setLineDash([]);

    var self = this;
    this.nodes.forEach(function (node) {
      var r = self.radiusFor(node);
      var dim = focus && !near[node.id];
      ctx.globalAlpha = dim ? 0.28 : 1;
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
      ctx.fillStyle = self.colourFor(node, colours);
      ctx.fill();
      ctx.lineWidth = node === self.selected ? 2.4 : 1.2;
      ctx.strokeStyle = node === self.selected ? colours.glow : colours.ring;
      ctx.stroke();
      // A label on everything at once is unreadable; they appear when the
      // view is zoomed in, on hubs, and on whatever is being looked at.
      if (!dim && (view.zoom > 1.15 || node.friends >= 5 || node === focus)) {
        ctx.globalAlpha = dim ? 0.3 : 0.92;
        ctx.font = '600 10px system-ui, sans-serif';
        ctx.fillStyle = colours.label;
        ctx.textAlign = 'center';
        ctx.fillText(node.name, node.x, node.y - r - 4);
      }
      ctx.globalAlpha = 1;
    });
    ctx.restore();
  };

  Graph.prototype.frame = function () {
    requestAnimationFrame(this.frame);
    if (!this.canvas.isConnected) return;
    var box = this.canvas.getBoundingClientRect();
    if (!box.width || !box.height) return;    // hidden: nothing to do
    this.resize();
    if (!this.frozen) this.step();
    this.draw();
  };

  // ------------------------------------------------------------ interaction
  Graph.prototype.toLocal = function (clientX, clientY) {
    var box = this.canvas.getBoundingClientRect();
    return {
      x: (clientX - box.left - this.view.x) / this.view.zoom,
      y: (clientY - box.top - this.view.y) / this.view.zoom
    };
  };

  Graph.prototype.nodeAt = function (clientX, clientY) {
    var point = this.toLocal(clientX, clientY);
    var best = null, bestDist = Infinity;
    var self = this;
    this.nodes.forEach(function (node) {
      var r = self.radiusFor(node) + 5;
      var d = Math.hypot(node.x - point.x, node.y - point.y);
      if (d < r && d < bestDist) { best = node; bestDist = d; }
    });
    return best;
  };

  Graph.prototype.bind = function () {
    var self = this;
    var canvas = this.canvas;
    var panning = null;

    canvas.addEventListener('pointerdown', function (event) {
      canvas.setPointerCapture(event.pointerId);
      var node = self.nodeAt(event.clientX, event.clientY);
      if (node) {
        self.dragging = node;
        self.dragMoved = false;
      } else {
        panning = { x: event.clientX - self.view.x, y: event.clientY - self.view.y };
      }
    });

    canvas.addEventListener('pointermove', function (event) {
      if (self.dragging) {
        var point = self.toLocal(event.clientX, event.clientY);
        self.dragging.x = point.x;
        self.dragging.y = point.y;
        self.dragMoved = true;
        self.alpha = Math.max(self.alpha, 0.5);   // let the mesh react
        return;
      }
      if (panning) {
        self.view.x = event.clientX - panning.x;
        self.view.y = event.clientY - panning.y;
        return;
      }
      var over = self.nodeAt(event.clientX, event.clientY);
      canvas.style.cursor = over ? 'pointer' : 'grab';
      self.hover = over;
    });

    function release(event) {
      if (self.dragging && !self.dragMoved) {
        self.selected = self.selected === self.dragging ? null : self.dragging;
        if (self.options.onSelect) self.options.onSelect(self.selected);
      } else if (!self.dragging && panning && self.options.onSelect) {
        // a click on empty space clears the selection
        var moved = Math.abs(event.clientX - panning.x - self.view.x) +
                    Math.abs(event.clientY - panning.y - self.view.y);
        if (moved < 3 && self.selected) {
          self.selected = null;
          self.options.onSelect(null);
        }
      }
      self.dragging = null;
      panning = null;
    }
    canvas.addEventListener('pointerup', release);
    canvas.addEventListener('pointercancel', function () {
      self.dragging = null; panning = null;
    });

    canvas.addEventListener('wheel', function (event) {
      event.preventDefault();
      var box = canvas.getBoundingClientRect();
      var mx = event.clientX - box.left, my = event.clientY - box.top;
      var before = self.view.zoom;
      var next = before * (event.deltaY < 0 ? 1.12 : 0.89);
      next = Math.max(0.35, Math.min(3.2, next));
      // zoom about the pointer rather than the origin, so the thing under
      // the cursor stays under the cursor
      self.view.x = mx - (mx - self.view.x) * (next / before);
      self.view.y = my - (my - self.view.y) * (next / before);
      self.view.zoom = next;
    }, { passive: false });
  };

  /* Fit every node into view.  Called on first data and on demand, never on
     every refresh -- a view that re-centres itself while you are reading it
     is worse than one that drifts. */
  Graph.prototype.fit = function () {
    if (!this.nodes.length) return;
    var minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    this.nodes.forEach(function (n) {
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    });
    var pad = 40;
    var w = Math.max(1, maxX - minX) + pad * 2;
    var h = Math.max(1, maxY - minY) + pad * 2;
    var box = this.canvas.getBoundingClientRect();
    if (!box.width || !box.height) return;
    var zoom = Math.max(0.35, Math.min(2.2, Math.min(box.width / w, box.height / h)));
    this.view.zoom = zoom;
    this.view.x = box.width / 2 - ((minX + maxX) / 2) * zoom;
    this.view.y = box.height / 2 - ((minY + maxY) / 2) * zoom;
  };

  global.SocialGraph = Graph;
})(window);
