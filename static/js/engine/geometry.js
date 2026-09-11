/* BLOCKHAVEN engine -- procedural meshes.
   Every primitive is unit sized and centred on the origin so an instance's
   model matrix carries all of the position/rotation/scale information. */
(function (global) {
  'use strict';

  var Geometry = {};

  function mesh(positions, normals, uvs, indices) {
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
