/* BLOCKHAVEN engine -- the avatar base system.
   One rig, driven entirely by a descriptor from the server, used by the
   profile preview, the avatar editor, item thumbnails and the game itself. */
(function (global) {
  'use strict';

  var M = GLX.mat;

  var RIG = {
    torso: { size: [2.0, 2.0, 1.0], centre: [0, 3.0, 0] },
    head: { size: [1.5, 1.4, 1.4], centre: [0, 4.7, 0] },
    arm: { size: [1.0, 2.0, 1.0], pivotY: 4.0, x: 1.5 },
    leg: { size: [1.0, 2.0, 1.0], pivotY: 2.0, x: 0.5 },
    height: 5.4,
    headTop: 5.4,
    hipY: 2.0
  };

  var Avatar = {
    RIG: RIG,
    EYE_HEIGHT: 4.85
  };

  function rotateY(x, z, yaw) {
    var c = Math.cos(yaw), s = Math.sin(yaw);
    return [x * c + z * s, -x * s + z * c];
  }

  /* Rotate a point around the X axis (used for limb swing). */
  function rotateX(y, z, angle) {
    var c = Math.cos(angle), s = Math.sin(angle);
    return [y * c - z * s, y * s + z * c];
  }

  function colourOf(descriptor, key, fallback) {
    var colors = descriptor.colors || {};
    return colors[key] || fallback || '#f5cd30';
  }

  function itemData(descriptor, slot) {
    var items = descriptor.items || {};
    return items[slot] || null;
  }

  /* Compute the animation pose for a given state. */
  Avatar.pose = function (state, time, speed) {
    var pose = { armL: 0, armR: 0, legL: 0, legR: 0, lean: 0, bob: 0,
                 armLZ: 0, armRZ: 0 };
    speed = speed === undefined ? 0 : speed;
    if (state === 'walk' || state === 'run') {
      var rate = state === 'run' ? 9.5 : 7.0;
      var amp = state === 'run' ? 0.85 : 0.62;
      var phase = time * rate;
      pose.legL = Math.sin(phase) * amp;
      pose.legR = -Math.sin(phase) * amp;
      pose.armL = -Math.sin(phase) * amp * 0.85;
      pose.armR = Math.sin(phase) * amp * 0.85;
      pose.bob = Math.abs(Math.sin(phase)) * 0.10;
      pose.lean = state === 'run' ? 0.09 : 0.045;
    } else if (state === 'jump') {
      pose.armL = -2.1; pose.armR = -2.1;
      pose.legL = -0.25; pose.legR = 0.35;
    } else if (state === 'fall') {
      pose.armL = -1.5; pose.armR = -1.5;
      pose.legL = 0.3; pose.legR = -0.2;
    } else if (state === 'sit') {
      pose.legL = -1.5; pose.legR = -1.5;
      pose.armL = -0.4; pose.armR = -0.4;
    } else {
      pose.armL = Math.sin(time * 1.4) * 0.035;
      pose.armR = -Math.sin(time * 1.4) * 0.035;
      pose.bob = Math.sin(time * 1.4) * 0.02;
    }
    return pose;
  };

  /* Build every renderable part for one character.
     opts: {position, yaw, pitch, pose, holding, dead, scale} */
  Avatar.build = function (descriptor, opts) {
    opts = opts || {};
    var parts = [];
    var pos = opts.position || [0, 0, 0];
    var yaw = opts.yaw || 0;
    var pose = opts.pose || Avatar.pose('idle', 0, 0);
    var shirt = itemData(descriptor, 'shirt');
    var pants = itemData(descriptor, 'pants');
    var hat = itemData(descriptor, 'hat');
    var face = itemData(descriptor, 'face');
    var back = itemData(descriptor, 'back');
    var shirtData = (shirt && shirt.data) || {};
    var pantsData = (pants && pants.data) || {};
    var bob = pose.bob || 0;
    var lean = pose.lean || 0;

    function place(local, size, colour, extra) {
      var xz = rotateY(local[0], local[2], yaw);
      var part = {
        t: (extra && extra.t) || 'box',
        p: [pos[0] + xz[0], pos[1] + local[1] + bob, pos[2] + xz[1]],
        s: size,
        c: colour,
        r: [(extra && extra.rx) || 0, yaw + ((extra && extra.ry) || 0),
            (extra && extra.rz) || 0]
      };
      if (extra) {
        if (extra.decSlot) part.decSlot = extra.decSlot;
        if (extra.dec) part.dec = extra.dec;
        if (extra.m) part.m = extra.m;
        if (extra.a !== undefined) part.a = extra.a;
        if (extra.st) part.st = extra.st;
      }
      parts.push(part);
      return part;
    }

    // --------------------------------------------------------------- torso
    var torsoColour = shirtData.torso || colourOf(descriptor, 'torso', '#0d69ac');
    var torsoDecal = null;
    if (shirtData.decal) torsoDecal = Textures.decal(shirtData.decal);
    place([0, RIG.torso.centre[1], 0], RIG.torso.size.slice(), torsoColour, {
      rx: lean, decSlot: torsoDecal
    });
    if (shirtData.stripe) {
      place([0, RIG.torso.centre[1] - 0.62, 0], [2.04, 0.36, 1.04],
            shirtData.stripe, { rx: lean });
    }
    if (shirtData.stripes) {
      for (var si = 0; si < shirtData.stripes; si++) {
        place([0, 2.15 + si * 0.32, 0], [2.04, 0.16, 1.04],
              shirtData.stripe || '#1b2a35', { rx: lean });
      }
    }
    if (shirtData.hood) {
      place([0, 4.02, -0.36], [1.7, 0.6, 0.7], shirtData.torso || torsoColour, {});
    }

    // ---------------------------------------------------------------- head
    var headColour = colourOf(descriptor, 'head', '#f5cd30');
    var faceSlot = null;
    if (face && face.data) faceSlot = Textures.faceSlot(face.item_id, face.data);
    place([0, RIG.head.centre[1], 0], RIG.head.size.slice(), headColour, {
      decSlot: faceSlot
    });

    // ---------------------------------------------------------------- arms
    function arm(side, swing, sleeveOverride) {
      var x = RIG.arm.x * side;
      var pivotY = RIG.arm.pivotY;
      var yz = rotateX(-1.0, 0, swing);
      var centre = [x, pivotY + yz[0], yz[1]];
      var skin = colourOf(descriptor, side < 0 ? 'right_arm' : 'left_arm', '#f5cd30');
      var sleeve = sleeveOverride !== undefined ? sleeveOverride : shirtData.arms;
      var coverage = shirtData.sleeves === undefined ? 1.0 : shirtData.sleeves;
      if (sleeve && coverage >= 0.99) {
        place(centre, RIG.arm.size.slice(), sleeve, { rx: swing });
      } else if (sleeve && coverage > 0.01) {
        var upperLen = 2.0 * coverage;
        var upperOffset = 1.0 - upperLen / 2;
        var uy = rotateX(-(1.0 - upperOffset), 0, swing);
        place([x, pivotY + uy[0] - 0, uy[1]], [1.02, upperLen, 1.02], sleeve,
              { rx: swing });
        var lowerLen = 2.0 - upperLen;
        var ly = rotateX(-(upperLen + lowerLen / 2), 0, swing);
        place([x, pivotY + ly[0], ly[1]], RIG.arm.size.slice().map(function (v, i) {
          return i === 1 ? lowerLen : v;
        }), skin, { rx: swing });
      } else {
        place(centre, RIG.arm.size.slice(), skin, { rx: swing });
      }
      var hand = rotateX(-2.0, 0, swing);
      return { x: x, y: pivotY + hand[0], z: hand[1], swing: swing };
    }

    var holding = opts.holding;
    var rightSwing = pose.armR;
    if (holding) rightSwing = -1.32 + (opts.pitch || 0) * 0.55;
    var leftSwing = pose.armL;
    if (holding && holding.twoHanded !== false) leftSwing = -1.15 + (opts.pitch || 0) * 0.4;
    var rightHand = arm(-1, rightSwing);
    arm(1, leftSwing);

    // ---------------------------------------------------------------- legs
    function leg(side, swing) {
      var x = RIG.leg.x * side;
      var pivotY = RIG.leg.pivotY;
      var yz = rotateX(-1.0, 0, swing);
      var centre = [x, pivotY + yz[0], yz[1]];
      var skin = colourOf(descriptor, side < 0 ? 'right_leg' : 'left_leg', '#a4bd47');
      var trouser = pantsData.legs;
      var length = pantsData.length === undefined ? 1.0 : pantsData.length;
      if (trouser && length >= 0.99) {
        place(centre, RIG.leg.size.slice(), trouser, { rx: swing });
      } else if (trouser && length > 0.01) {
        var upperLen = 2.0 * length;
        var uy = rotateX(-(upperLen / 2), 0, swing);
        place([x, pivotY + uy[0], uy[1]], [1.02, upperLen, 1.02], trouser, { rx: swing });
        var lowerLen = 2.0 - upperLen;
        var ly = rotateX(-(upperLen + lowerLen / 2), 0, swing);
        place([x, pivotY + ly[0], ly[1]], [1.0, lowerLen, 1.0],
              pantsData.skin || skin, { rx: swing });
      } else {
        place(centre, RIG.leg.size.slice(), skin, { rx: swing });
      }
      if (pantsData.cuff) {
        var cy = rotateX(-1.85, 0, swing);
        place([x, pivotY + cy[0], cy[1]], [1.04, 0.3, 1.04], pantsData.cuff,
              { rx: swing });
      }
      if (pantsData.stripe) {
        var sy = rotateX(-1.0, 0, swing);
        place([x + side * 0.52, pivotY + sy[0], sy[1]], [0.06, 1.9, 0.5],
              pantsData.stripe, { rx: swing, m: pantsData.glow ? 'neon' : '' });
      }
    }
    leg(-1, pose.legR);
    leg(1, pose.legL);

    // ------------------------------------------------------- accessories
    function attach(itemParts, origin, extraYaw) {
      (itemParts || []).forEach(function (piece) {
        var local = [origin[0] + piece.p[0], origin[1] + piece.p[1],
                     origin[2] + piece.p[2]];
        var spin = piece.spin ? (opts.time || 0) * piece.spin : 0;
        var xz = rotateY(local[0], local[2], yaw);
        parts.push({
          t: piece.t || 'box',
          p: [pos[0] + xz[0], pos[1] + local[1] + bob, pos[2] + xz[1]],
          s: piece.s.slice(),
          c: piece.c,
          r: [(piece.r ? piece.r[0] : 0), yaw + (piece.r ? piece.r[1] : 0) + spin +
              (extraYaw || 0), (piece.r ? piece.r[2] : 0)],
          m: piece.m,
          a: piece.a,
          decSlot: piece.decal ? Textures.decal(piece.decal) : null
        });
      });
    }

    if (hat && hat.data && hat.data.parts) {
      attach(hat.data.parts, [0, RIG.headTop, 0]);
    }
    if (back && back.data && back.data.parts) {
      attach(back.data.parts, [0, RIG.torso.centre[1], -0.5]);
    }

    // ---------------------------------------------------------- held item
    if (holding && holding.data && holding.data.parts) {
      var gripSwing = rightSwing;
      (holding.data.parts).forEach(function (piece) {
        var ly = rotateX(piece.p[1] - 0.0, piece.p[2] + 0.0, gripSwing + Math.PI / 2);
        var local = [rightHand.x + piece.p[0], rightHand.y + ly[0], rightHand.z + ly[1]];
        var xz = rotateY(local[0], local[2], yaw);
        parts.push({
          t: piece.t || 'box',
          p: [pos[0] + xz[0], pos[1] + local[1] + bob, pos[2] + xz[1]],
          s: piece.s.slice(),
          c: piece.c,
          r: [(piece.r ? piece.r[0] : 0) + gripSwing + Math.PI / 2,
              yaw + (piece.r ? piece.r[1] : 0),
              (piece.r ? piece.r[2] : 0)],
          m: piece.m
        });
      });
    }
    return parts;
  };

  /* World position of the hat emitter (for Unusual particle effects). */
  Avatar.hatAnchor = function (position, yaw, hat) {
    var y = RIG.headTop + 0.55;
    if (hat && hat.data && hat.data.parts && hat.data.parts.length) {
      var top = 0;
      hat.data.parts.forEach(function (piece) {
        top = Math.max(top, piece.p[1] + piece.s[1] * 0.5);
      });
      y = RIG.headTop + top + 0.18;
    }
    return [position[0], position[1] + y, position[2]];
  };

  /* A compact first-person view model: the right arm plus the held item,
     positioned relative to the camera basis. */
  Avatar.viewModel = function (descriptor, holding, camera, sway, opts) {
    opts = opts || {};
    var parts = [];
    var eye = camera.eye;
    var fwd = camera.forward;
    var right = camera.right;
    var up = camera.up;
    var flen = Math.hypot(fwd[0], fwd[1], fwd[2]) || 1;
    var f = [fwd[0] / flen, fwd[1] / flen, fwd[2] / flen];
    var rlen = Math.hypot(right[0], right[1], right[2]) || 1;
    var r = [right[0] / rlen, right[1] / rlen, right[2] / rlen];
    var ulen = Math.hypot(up[0], up[1], up[2]) || 1;
    var u = [up[0] / ulen, up[1] / ulen, up[2] / ulen];
    var yaw = Math.atan2(f[0], f[2]);
    var pitch = Math.asin(M.clamp(f[1], -1, 1));

    function toWorld(local) {
      return [
        eye[0] + r[0] * local[0] + u[0] * local[1] + f[0] * local[2],
        eye[1] + r[1] * local[0] + u[1] * local[1] + f[1] * local[2],
        eye[2] + r[2] * local[0] + u[2] * local[1] + f[2] * local[2]
      ];
    }

    var bobX = (sway && sway.x) || 0;
    var bobY = (sway && sway.y) || 0;
    var recoil = (sway && sway.recoil) || 0;
    var base = [1.05 + bobX, -0.98 + bobY - recoil * 0.30, 2.35 - recoil * 0.55];
    var armColour = (descriptor.items && descriptor.items.shirt &&
                     descriptor.items.shirt.data && descriptor.items.shirt.data.arms) ||
                    colourOf(descriptor, 'right_arm', '#f5cd30');

    // forearm
    var armLocal = [base[0] - 0.10, base[1] - 0.34, base[2] - 0.78];
    parts.push({
      t: 'box',
      p: toWorld(armLocal),
      s: [0.42, 0.42, 1.5],
      c: armColour,
      r: [pitch + 0.14, yaw, 0]
    });

    if (holding && holding.data && holding.data.parts) {
      holding.data.parts.forEach(function (piece) {
        var local = [base[0] + piece.p[0] * 0.45,
                     base[1] + piece.p[1] * 0.45,
                     base[2] + piece.p[2] * 0.45];
        parts.push({
          t: piece.t || 'box',
          p: toWorld(local),
          s: [piece.s[0] * 0.45, piece.s[1] * 0.45, piece.s[2] * 0.45],
          c: piece.c,
          r: [pitch + (piece.r ? piece.r[0] : 0),
              yaw + (piece.r ? piece.r[1] : 0),
              (piece.r ? piece.r[2] : 0)],
          m: piece.m
        });
      });
    }
    if (opts.muzzle) {
      var mz = [base[0], base[1] + 0.08, base[2] + 1.1];
      parts.push({
        t: 'sph', p: toWorld(mz), s: [0.5, 0.5, 0.5], c: '#ffd95e',
        r: [0, 0, 0], m: 'neon'
      });
    }
    return parts;
  };

  global.Avatar = Avatar;
})(window);
