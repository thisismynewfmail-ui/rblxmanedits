/* Client-side character physics.
   The server re-validates every position it receives; this exists so movement
   feels immediate instead of waiting a round trip. */
(function (global) {
  'use strict';

  var SIZE = { w: 2.4, h: 5.4, d: 1.8 };
  var STEP_HEIGHT = 2.1;

  function Physics(map, constants) {
    this.map = map;
    this.constants = constants || {};
    this.gravity = this.constants.gravity || 62;
    this.walk = this.constants.walk || 22;
    this.jump = this.constants.jump || 34;
    this.killY = (map && map.kill_y !== undefined) ? map.kill_y : -60;
    this.buildColliders(map ? map.parts || [] : []);
  }

  Physics.SIZE = SIZE;

  Physics.prototype.buildColliders = function (parts) {
    this.boxes = [];
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i];
      if (!part.col) continue;
      var size = part.s.slice();
      if (part.r) {
        var rx = part.r[0], ry = part.r[1], rz = part.r[2];
        if (Math.abs(rx) > 1e-3 || Math.abs(rz) > 1e-3) continue;
        var quarter = Math.abs(ry % (Math.PI / 2));
        if (quarter > 1e-3 && Math.abs(quarter - Math.PI / 2) > 1e-3) continue;
        if (Math.round(ry / (Math.PI / 2)) % 2) size = [size[2], size[1], size[0]];
      }
      var kind = part.t || 'box';
      if (kind === 'sph') size = [size[0] * 0.78, size[1] * 0.78, size[2] * 0.78];
      else if (kind === 'cyl') size = [size[0] * 0.86, size[1], size[2] * 0.86];
      else if (kind === 'cone') size = [size[0] * 0.62, size[1], size[2] * 0.62];
      else if (kind === 'torus') continue;
      this.boxes.push({
        minX: part.p[0] - size[0] / 2, maxX: part.p[0] + size[0] / 2,
        minY: part.p[1] - size[1] / 2, maxY: part.p[1] + size[1] / 2,
        minZ: part.p[2] - size[2] / 2, maxZ: part.p[2] + size[2] / 2
      });
    }
    this.buildGrid();
  };

  Physics.prototype.buildGrid = function () {
    this.cell = 32;
    this.grid = {};
    var self = this;
    this.boxes.forEach(function (box, index) {
      var x0 = Math.floor(box.minX / self.cell), x1 = Math.floor(box.maxX / self.cell);
      var z0 = Math.floor(box.minZ / self.cell), z1 = Math.floor(box.maxZ / self.cell);
      for (var x = x0; x <= x1; x++) {
        for (var z = z0; z <= z1; z++) {
          var key = x + ':' + z;
          (self.grid[key] || (self.grid[key] = [])).push(index);
        }
      }
    });
  };

  Physics.prototype.nearby = function (minX, maxX, minZ, maxZ) {
    var out = [];
    var seen = {};
    var x0 = Math.floor(minX / this.cell), x1 = Math.floor(maxX / this.cell);
    var z0 = Math.floor(minZ / this.cell), z1 = Math.floor(maxZ / this.cell);
    for (var x = x0; x <= x1; x++) {
      for (var z = z0; z <= z1; z++) {
        var list = this.grid[x + ':' + z];
        if (!list) continue;
        for (var i = 0; i < list.length; i++) {
          if (seen[list[i]]) continue;
          seen[list[i]] = 1;
          out.push(this.boxes[list[i]]);
        }
      }
    }
    return out;
  };

  function overlaps(box, minX, maxX, minY, maxY, minZ, maxZ) {
    return box.maxX > minX && box.minX < maxX &&
           box.maxY > minY && box.minY < maxY &&
           box.maxZ > minZ && box.minZ < maxZ;
  }

  /* Move an entity, resolving collisions one axis at a time. */
  Physics.prototype.move = function (state, dt) {
    var hw = SIZE.w / 2, hd = SIZE.d / 2, h = SIZE.h;
    var pos = state.pos, vel = state.vel;
    var result = { grounded: false, hitWall: false, landed: false, headBump: false };
    var candidates = this.nearby(
      pos[0] - hw - Math.abs(vel[0] * dt) - 2, pos[0] + hw + Math.abs(vel[0] * dt) + 2,
      pos[2] - hd - Math.abs(vel[2] * dt) - 2, pos[2] + hd + Math.abs(vel[2] * dt) + 2);

    // ---- X
    var dx = vel[0] * dt;
    if (dx) {
      var nx = pos[0] + dx;
      for (var i = 0; i < candidates.length; i++) {
        var box = candidates[i];
        if (!overlaps(box, nx - hw, nx + hw, pos[1] + 0.05, pos[1] + h,
                      pos[2] - hd, pos[2] + hd)) continue;
        // try stepping up onto low ledges
        if (box.maxY - pos[1] <= STEP_HEIGHT && box.maxY > pos[1]) {
          var lifted = box.maxY + 0.02;
          if (!this.blocked(nx, lifted, pos[2], candidates)) {
            pos[1] = lifted;
            continue;
          }
        }
        nx = dx > 0 ? Math.min(nx, box.minX - hw - 0.001)
                    : Math.max(nx, box.maxX + hw + 0.001);
        vel[0] = 0;
        result.hitWall = true;
      }
      pos[0] = nx;
    }

    // ---- Z
    var dz = vel[2] * dt;
    if (dz) {
      var nz = pos[2] + dz;
      for (i = 0; i < candidates.length; i++) {
        box = candidates[i];
        if (!overlaps(box, pos[0] - hw, pos[0] + hw, pos[1] + 0.05, pos[1] + h,
                      nz - hd, nz + hd)) continue;
        if (box.maxY - pos[1] <= STEP_HEIGHT && box.maxY > pos[1]) {
          var lifted2 = box.maxY + 0.02;
          if (!this.blocked(pos[0], lifted2, nz, candidates)) {
            pos[1] = lifted2;
            continue;
          }
        }
        nz = dz > 0 ? Math.min(nz, box.minZ - hd - 0.001)
                    : Math.max(nz, box.maxZ + hd + 0.001);
        vel[2] = 0;
        result.hitWall = true;
      }
      pos[2] = nz;
    }

    // ---- Y
    var dy = vel[1] * dt;
    var ny = pos[1] + dy;
    for (i = 0; i < candidates.length; i++) {
      box = candidates[i];
      if (!overlaps(box, pos[0] - hw, pos[0] + hw, ny, ny + h,
                    pos[2] - hd, pos[2] + hd)) continue;
      if (dy <= 0) {
        if (box.maxY <= pos[1] + STEP_HEIGHT + 0.5) {
          ny = Math.max(ny, box.maxY);
          if (vel[1] < -12) result.landed = true;
          vel[1] = 0;
          result.grounded = true;
        }
      } else {
        ny = Math.min(ny, box.minY - h - 0.001);
        vel[1] = 0;
        result.headBump = true;
      }
    }
    pos[1] = ny;

    // standing check (a small probe below the feet)
    if (!result.grounded) {
      for (i = 0; i < candidates.length; i++) {
        box = candidates[i];
        if (overlaps(box, pos[0] - hw, pos[0] + hw, pos[1] - 0.22, pos[1] + 0.1,
                     pos[2] - hd, pos[2] + hd)) {
          result.grounded = true;
          break;
        }
      }
    }
    return result;
  };

  Physics.prototype.blocked = function (x, y, z, candidates) {
    var hw = SIZE.w / 2, hd = SIZE.d / 2, h = SIZE.h;
    candidates = candidates || this.nearby(x - hw - 1, x + hw + 1, z - hd - 1, z + hd + 1);
    for (var i = 0; i < candidates.length; i++) {
      if (overlaps(candidates[i], x - hw, x + hw, y + 0.05, y + h, z - hd, z + hd)) {
        return true;
      }
    }
    return false;
  };

  /* Distance along a ray until it hits the world (used by the third person
     camera so it does not clip through walls). */
  Physics.prototype.rayDistance = function (origin, dir, maxDist) {
    var best = maxDist;
    var boxes = this.nearby(
      Math.min(origin[0], origin[0] + dir[0] * maxDist) - 2,
      Math.max(origin[0], origin[0] + dir[0] * maxDist) + 2,
      Math.min(origin[2], origin[2] + dir[2] * maxDist) - 2,
      Math.max(origin[2], origin[2] + dir[2] * maxDist) + 2);
    for (var i = 0; i < boxes.length; i++) {
      var t = raySlab(origin, dir, boxes[i]);
      if (t !== null && t < best) best = t;
    }
    return best;
  };

  function raySlab(origin, dir, box) {
    var tmin = 0, tmax = Infinity;
    var lo = [box.minX, box.minY, box.minZ];
    var hi = [box.maxX, box.maxY, box.maxZ];
    for (var axis = 0; axis < 3; axis++) {
      var o = origin[axis], d = dir[axis];
      if (Math.abs(d) < 1e-8) {
        if (o < lo[axis] || o > hi[axis]) return null;
        continue;
      }
      var inv = 1 / d;
      var t1 = (lo[axis] - o) * inv;
      var t2 = (hi[axis] - o) * inv;
      if (t1 > t2) { var tmp = t1; t1 = t2; t2 = tmp; }
      tmin = Math.max(tmin, t1);
      tmax = Math.min(tmax, t2);
      if (tmin > tmax) return null;
    }
    return tmin >= 0 ? tmin : null;
  }

  Physics.prototype.raycast = function (origin, dir, maxDist) {
    return this.rayDistance(origin, dir, maxDist);
  };

  global.Physics = Physics;
})(window);
