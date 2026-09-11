/* BLOCKHAVEN engine -- procedural meshes.
   Every primitive is unit sized and centred on the origin so an instance's
   model matrix carries all of the position/rotation/scale information. */
(function (global) {
  'use strict';

  var Geometry = {};

  /* Make every triangle wind counter-clockwise when seen from outside.

     The scene is drawn with back-face culling on, so a triangle whose index
     order disagrees with its own vertex normals gets culled and the solid
     reads as a hollow, see-through shell.  Rather than hand-checking each
     primitive below (and every one added later) the winding is measured
     against the authored normals here and flipped when it disagrees. */
  function fixWinding(positions, normals, indices) {
    for (var t = 0; t < indices.length; t += 3) {
      var a = indices[t] * 3, b = indices[t + 1] * 3, c = indices[t + 2] * 3;
      var e1x = positions[b] - positions[a];
      var e1y = positions[b + 1] - positions[a + 1];
      var e1z = positions[b + 2] - positions[a + 2];
      var e2x = positions[c] - positions[a];
      var e2y = positions[c + 1] - positions[a + 1];
      var e2z = positions[c + 2] - positions[a + 2];
      var fx = e1y * e2z - e1z * e2y;
      var fy = e1z * e2x - e1x * e2z;
      var fz = e1x * e2y - e1y * e2x;
      var nx = normals[a] + normals[b] + normals[c];
      var ny = normals[a + 1] + normals[b + 1] + normals[c + 1];
      var nz = normals[a + 2] + normals[b + 2] + normals[c + 2];
      if (fx * nx + fy * ny + fz * nz < 0) {
        var swap = indices[t + 1];
        indices[t + 1] = indices[t + 2];
        indices[t + 2] = swap;
      }
    }
    return indices;
  }

  function mesh(positions, normals, uvs, indices) {
    fixWinding(positions, normals, indices);
    return {
      positions: new Float32Array(positions),
      normals: new Float32Array(normals),
      uvs: new Float32Array(uvs),
      indices: (positions.length / 3 > 65535)
        ? new Uint32Array(indices) : new Uint16Array(indices)
    };
  }

  Geometry.box = function () {
    var p = [], n = [], u = [], i = [];
    var faces = [
      { nrm: [0, 0, 1], v: [[-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5]] },
      { nrm: [0, 0, -1], v: [[0.5, -0.5, -0.5], [-0.5, -0.5, -0.5], [-0.5, 0.5, -0.5], [0.5, 0.5, -0.5]] },
      { nrm: [1, 0, 0], v: [[0.5, -0.5, 0.5], [0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [0.5, 0.5, 0.5]] },
      { nrm: [-1, 0, 0], v: [[-0.5, -0.5, -0.5], [-0.5, -0.5, 0.5], [-0.5, 0.5, 0.5], [-0.5, 0.5, -0.5]] },
      { nrm: [0, 1, 0], v: [[-0.5, 0.5, 0.5], [0.5, 0.5, 0.5], [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5]] },
      { nrm: [0, -1, 0], v: [[-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5], [-0.5, -0.5, 0.5]] }
    ];
    var uvq = [[0, 0], [1, 0], [1, 1], [0, 1]];
    for (var f = 0; f < faces.length; f++) {
      var base = p.length / 3;
      for (var k = 0; k < 4; k++) {
        p.push(faces[f].v[k][0], faces[f].v[k][1], faces[f].v[k][2]);
        n.push(faces[f].nrm[0], faces[f].nrm[1], faces[f].nrm[2]);
        u.push(uvq[k][0], uvq[k][1]);
      }
      i.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }
    return mesh(p, n, u, i);
  };

  Geometry.cylinder = function (segments) {
    segments = segments || 18;
    var p = [], n = [], u = [], i = [];
    var s, ang, cx, sz;
    for (s = 0; s <= segments; s++) {
      ang = (s / segments) * Math.PI * 2;
      cx = Math.cos(ang) * 0.5; sz = Math.sin(ang) * 0.5;
      var nx = Math.cos(ang), nz = Math.sin(ang);
      p.push(cx, -0.5, sz); n.push(nx, 0, nz); u.push(s / segments, 0);
      p.push(cx, 0.5, sz); n.push(nx, 0, nz); u.push(s / segments, 1);
    }
    for (s = 0; s < segments; s++) {
      var a = s * 2;
      i.push(a, a + 2, a + 3, a, a + 3, a + 1);
    }
    // caps
    for (var side = 0; side < 2; side++) {
      var y = side ? 0.5 : -0.5;
      var ny = side ? 1 : -1;
      var centre = p.length / 3;
      p.push(0, y, 0); n.push(0, ny, 0); u.push(0.5, 0.5);
      for (s = 0; s <= segments; s++) {
        ang = (s / segments) * Math.PI * 2;
        p.push(Math.cos(ang) * 0.5, y, Math.sin(ang) * 0.5);
        n.push(0, ny, 0);
        u.push(0.5 + Math.cos(ang) * 0.5, 0.5 + Math.sin(ang) * 0.5);
      }
      for (s = 0; s < segments; s++) {
        if (side) i.push(centre, centre + 1 + s, centre + 2 + s);
        else i.push(centre, centre + 2 + s, centre + 1 + s);
      }
    }
    return mesh(p, n, u, i);
  };

  Geometry.sphere = function (rings, segments) {
    rings = rings || 12; segments = segments || 18;
    var p = [], n = [], u = [], i = [];
    for (var r = 0; r <= rings; r++) {
      var phi = (r / rings) * Math.PI;
      var y = Math.cos(phi) * 0.5, rad = Math.sin(phi) * 0.5;
      for (var s = 0; s <= segments; s++) {
        var theta = (s / segments) * Math.PI * 2;
        var x = Math.cos(theta) * rad, z = Math.sin(theta) * rad;
        p.push(x, y, z);
        var len = Math.sqrt(x * x + y * y + z * z) || 1;
        n.push(x / len, y / len, z / len);
        u.push(s / segments, 1 - r / rings);
      }
    }
    for (r = 0; r < rings; r++) {
      for (s = 0; s < segments; s++) {
        var a = r * (segments + 1) + s;
        var b = a + segments + 1;
        i.push(a, b, a + 1, a + 1, b, b + 1);
      }
    }
    return mesh(p, n, u, i);
  };

  Geometry.cone = function (segments) {
    segments = segments || 16;
    var p = [], n = [], u = [], i = [], s, ang;
    for (s = 0; s < segments; s++) {
      var a0 = (s / segments) * Math.PI * 2;
      var a1 = ((s + 1) / segments) * Math.PI * 2;
      var x0 = Math.cos(a0) * 0.5, z0 = Math.sin(a0) * 0.5;
      var x1 = Math.cos(a1) * 0.5, z1 = Math.sin(a1) * 0.5;
      var mx = (Math.cos(a0) + Math.cos(a1)) * 0.5;
      var mz = (Math.sin(a0) + Math.sin(a1)) * 0.5;
      var ny = 0.45;
      var len = Math.sqrt(mx * mx + mz * mz + ny * ny) || 1;
      var base = p.length / 3;
      p.push(x0, -0.5, z0, x1, -0.5, z1, 0, 0.5, 0);
      for (var k = 0; k < 3; k++) n.push(mx / len, ny / len, mz / len);
      u.push(s / segments, 0, (s + 1) / segments, 0, (s + 0.5) / segments, 1);
      i.push(base, base + 1, base + 2);
    }
    var centre = p.length / 3;
    p.push(0, -0.5, 0); n.push(0, -1, 0); u.push(0.5, 0.5);
    for (s = 0; s <= segments; s++) {
      ang = (s / segments) * Math.PI * 2;
      p.push(Math.cos(ang) * 0.5, -0.5, Math.sin(ang) * 0.5);
      n.push(0, -1, 0);
      u.push(0.5 + Math.cos(ang) * 0.5, 0.5 + Math.sin(ang) * 0.5);
    }
    for (s = 0; s < segments; s++) i.push(centre, centre + 2 + s, centre + 1 + s);
    return mesh(p, n, u, i);
  };

  /* A right-triangle prism: full height at -Z, zero height at +Z. */
  Geometry.wedge = function () {
    var p = [], n = [], u = [], i = [];
    function quad(v0, v1, v2, v3, nrm) {
      var base = p.length / 3;
      var vs = [v0, v1, v2, v3];
      var uvq = [[0, 0], [1, 0], [1, 1], [0, 1]];
      for (var k = 0; k < 4; k++) {
        p.push(vs[k][0], vs[k][1], vs[k][2]);
        n.push(nrm[0], nrm[1], nrm[2]);
        u.push(uvq[k][0], uvq[k][1]);
      }
      i.push(base, base + 1, base + 2, base, base + 2, base + 3);
    }
    function tri(v0, v1, v2, nrm) {
      var base = p.length / 3;
      var vs = [v0, v1, v2];
      var uvq = [[0, 0], [1, 0], [0.5, 1]];
      for (var k = 0; k < 3; k++) {
        p.push(vs[k][0], vs[k][1], vs[k][2]);
        n.push(nrm[0], nrm[1], nrm[2]);
        u.push(uvq[k][0], uvq[k][1]);
      }
      i.push(base, base + 1, base + 2);
    }
    quad([-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5], [-0.5, -0.5, 0.5], [0, -1, 0]);
    quad([0.5, -0.5, -0.5], [-0.5, -0.5, -0.5], [-0.5, 0.5, -0.5], [0.5, 0.5, -0.5], [0, 0, -1]);
    var sy = 1 / Math.sqrt(2);
    quad([-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5], [0, sy, sy]);
    tri([0.5, -0.5, -0.5], [0.5, -0.5, 0.5], [0.5, 0.5, -0.5], [1, 0, 0]);
    tri([-0.5, -0.5, 0.5], [-0.5, -0.5, -0.5], [-0.5, 0.5, -0.5], [-1, 0, 0]);
    return mesh(p, n, u, i);
  };

  Geometry.torus = function (major, minor) {
    major = major || 20; minor = minor || 9;
    var p = [], n = [], u = [], i = [];
    var R = 0.4, r = 0.1;   // relative to a unit bounding box
    for (var a = 0; a <= major; a++) {
      var theta = (a / major) * Math.PI * 2;
      var ct = Math.cos(theta), st = Math.sin(theta);
      for (var b = 0; b <= minor; b++) {
        var phi = (b / minor) * Math.PI * 2;
        var cp = Math.cos(phi), sp = Math.sin(phi);
        p.push((R + r * cp) * ct, r * sp, (R + r * cp) * st);
        n.push(cp * ct, sp, cp * st);
        u.push(a / major, b / minor);
      }
    }
    for (a = 0; a < major; a++) {
      for (b = 0; b < minor; b++) {
        var i0 = a * (minor + 1) + b;
        var i1 = i0 + minor + 1;
        i.push(i0, i1, i0 + 1, i0 + 1, i1, i1 + 1);
      }
    }
    return mesh(p, n, u, i);
  };

  /* A box with rounded edges and corners -- the shape the whole avatar is
     built from.

     ``radius`` may be a single number or a per-axis [rx, ry, rz].  The
     per-axis form matters because an instance's model matrix scales the mesh
     non-uniformly: baking one radius into a 1x1x1 mesh and then stretching it
     to a 1x2x1 arm doubles the rounding along the arm, which domes the ends
     into a pill.  Baking [0.17, 0.08, 0.17] instead lands a uniform bevel once
     the limb scale is applied.

     Each of the six faces is sampled on a grid and pushed onto the Minkowski
     sum of an inner box and an ellipsoid of those radii, so the middle of
     every face stays perfectly flat (and keeps an exact face normal, which is
     what the decal test needs) while the edges curve. */
  Geometry.roundedBox = function (radius, bevelSteps) {
    var r = (typeof radius === 'number' || radius === undefined)
      ? [radius === undefined ? 0.12 : radius,
         radius === undefined ? 0.12 : radius,
         radius === undefined ? 0.12 : radius]
      : [radius[0], radius[1], radius[2]];
    for (var axis = 0; axis < 3; axis++) {
      r[axis] = Math.max(0.0005, Math.min(0.4999, r[axis]));
    }
    bevelSteps = Math.max(1, bevelSteps || 2);
    var h = 0.5;
    var a = [h - r[0], h - r[1], h - r[2]];

    /* Sample positions along one axis.  A uniform grid would spend every
       vertex on the flat middle (which needs two) and leave the bevel as a
       single smooth-shaded chamfer, which is what makes a part read as a
       pillow rather than a bevelled brick.  These put the vertices where the
       curvature actually is. */
    function axisSamples(inner) {
      var out = [];
      var span = h - inner;
      for (var k = 0; k <= bevelSteps; k++) out.push(-h + span * (k / bevelSteps));
      out.push(inner);
      for (k = 1; k <= bevelSteps; k++) out.push(inner + span * (k / bevelSteps));
      return out;
    }
    var samples = [axisSamples(a[0]), axisSamples(a[1]), axisSamples(a[2])];

    var p = [], n = [], u = [], i = [];
    var faces = [
      { axis: 2, sign: 1, ua: 0, va: 1 },
      { axis: 2, sign: -1, ua: 0, va: 1 },
      { axis: 0, sign: 1, ua: 2, va: 1 },
      { axis: 0, sign: -1, ua: 2, va: 1 },
      { axis: 1, sign: 1, ua: 0, va: 2 },
      { axis: 1, sign: -1, ua: 0, va: 2 }
    ];
    function clamp(v, limit) { return v < -limit ? -limit : (v > limit ? limit : v); }

    for (var f = 0; f < faces.length; f++) {
      var face = faces[f];
      var us = samples[face.ua];
      var vs = samples[face.va];
      var base = p.length / 3;
      for (var vi = 0; vi < vs.length; vi++) {
        for (var ui = 0; ui < us.length; ui++) {
          var ideal = [0, 0, 0];
          ideal[face.axis] = h * face.sign;
          ideal[face.ua] = us[ui];
          ideal[face.va] = vs[vi];
          var centre = [clamp(ideal[0], a[0]), clamp(ideal[1], a[1]),
                        clamp(ideal[2], a[2])];
          // direction in radius-normalised space, so the corner is an
          // ellipsoid octant rather than a sphere octant
          var tx = (ideal[0] - centre[0]) / r[0];
          var ty = (ideal[1] - centre[1]) / r[1];
          var tz = (ideal[2] - centre[2]) / r[2];
          var len = Math.sqrt(tx * tx + ty * ty + tz * tz) || 1;
          tx /= len; ty /= len; tz /= len;
          p.push(centre[0] + tx * r[0], centre[1] + ty * r[1],
                 centre[2] + tz * r[2]);
          // the ellipsoid's surface normal is the radius-weighted gradient
          var nx = tx / r[0], ny = ty / r[1], nz = tz / r[2];
          var nlen = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
          n.push(nx / nlen, ny / nlen, nz / nlen);
          // UVs run 0..1 across the whole face, and stay linear in position,
          // so a decal still lands square on the flat middle
          var su = us[ui] + h, sv = vs[vi] + h;
          if (face.axis === 2) su = face.sign > 0 ? su : 1 - su;
          if (face.axis === 0) su = face.sign > 0 ? 1 - su : su;
          u.push(su, sv);
        }
      }
      var stride = us.length;
      for (vi = 0; vi < vs.length - 1; vi++) {
        for (ui = 0; ui < us.length - 1; ui++) {
          var i0 = base + vi * stride + ui;
          var i1 = i0 + 1;
          var i2 = i0 + stride;
          var i3 = i2 + 1;
          i.push(i0, i1, i3, i0, i3, i2);
        }
      }
    }
    return mesh(p, n, u, i);
  };

  Geometry.quad = function () {
    return mesh(
      [-0.5, -0.5, 0, 0.5, -0.5, 0, 0.5, 0.5, 0, -0.5, 0.5, 0],
      [0, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 1],
      [0, 0, 1, 0, 1, 1, 0, 1],
      [0, 1, 2, 0, 2, 3]);
  };

  Geometry.build = function () {
    return {
      box: Geometry.box(),
      // three bakes of the same shape, chosen so that once the avatar's part
      // sizes are applied the bevel comes out roughly uniform in world units
      rbox: Geometry.roundedBox(0.085, 2),                  // near-cubic parts
      rlimb: Geometry.roundedBox([0.133, 0.064, 0.133], 2),  // 1:2:1 arms, legs
      rhead: Geometry.roundedBox([0.196, 0.214, 0.202], 3),  // the head
      cyl: Geometry.cylinder(18),
      sph: Geometry.sphere(12, 18),
      cone: Geometry.cone(16),
      wedge: Geometry.wedge(),
      torus: Geometry.torus(20, 9),
      quad: Geometry.quad()
    };
  };

  global.Geometry = Geometry;
})(window);
