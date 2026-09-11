/* BLOCKHAVEN engine -- the avatar base system.
   One rig, driven entirely by a descriptor from the server, used by the
   profile preview, the avatar editor, item thumbnails and the game itself.

   The rig is built from rounded boxes rather than hard cubes, with a neck, a
   tapered torso and softened limbs, so a bare default character already has a
   silhouette instead of reading as a stack of blocks.

   Two body types ship: "male" and "female".  They differ only from the neck
   down -- head, neck and RIG.headTop are identical for both, which is what
   guarantees every hat and every face fits either body without adjustment.
   Cosmetics that colour the body (shirts, pants) are driven from the same
   metrics, so they follow whichever silhouette is in use. */
(function (global) {
  'use strict';

  var M = GLX.mat;

  var HEIGHT = 5.4;          // feet to the top of the head, both body types
  var HEAD_TOP = 5.4;

  /* Shared head/neck.  The width is pinned at 1.46 because the tightest
     brims in the catalogue are 1.56-1.62 across and the skull has to stay
     inside them; the friendlier proportion therefore comes out of the other
     two axes.  It is wider than it is tall (1.14:1 rather than the old
     1.07:1) and a little deeper, which reads as a round face rather than a
     tall brick, and the top stays pinned to HEAD_TOP so every hat anchor,
     the eye height and the hitbox are all untouched.  The neck is shorter
     and thicker so the head sits down on the shoulders instead of being
     served up on a post -- a short neck is most of what makes a character
     read as cute. */
  var HEAD = {
    size: [1.46, 1.28, 1.40],
    centre: [0, 4.76, 0],
    neck: { size: [0.70, 0.30, 0.66], y: 4.03 }
  };

  /* The two builds differ by silhouette, not by parts: same segments, same
     anchors, different measurements.  The male reads as a near-uniform block
     (the waist is only a hair narrower than the chest); the female has
     narrower shoulders, a real waist, hips back out to shoulder width and
     slimmer, slightly longer limbs.  Because the head is shared and
     unchanged, the smaller female body also reads as a larger head, which is
     where the softer, cuter proportion comes from -- no extra geometry, and
     nothing for a hat or a face to trip over. */
  var BODIES = {
    male: {
      id: 'male',
      label: 'Male',
      // Stacked torso segments, top first; "decal" marks the one a shirt
      // graphic is printed on.  Consecutive segments overlap by more than
      // their two bevels put together (here 0.32 against 0.20), because
      // rounded boxes that merely touch leave a groove between them and the
      // torso reads as a stack of trays rather than one body.
      torso: [
        { size: [2.00, 1.39, 1.06], y: 3.315, decal: true },
        { size: [1.94, 0.94, 1.02], y: 2.47 }
      ],
      chest: { size: [2.00, 1.30, 1.06], y: 3.36 },
      waistLine: 2.00,
      hips: { size: [1.96, 0.38, 1.06], y: 2.06 },
      // narrow across, deeper front to back: a rectangle in section, not a
      // post.  x moves in with the half-width so the inner face still
      // meets the torso at the same place and the shoulder joint is sound.
      arm: { size: [0.82, 2.02, 0.96], x: 1.36, pivotY: 3.98 },
      leg: { size: [1.00, 2.00, 1.02], x: 0.52, pivotY: 2.00 },
      foot: { size: [1.06, 0.28, 1.24], z: 0.10 },
      backAnchor: [0, 3.02, -0.54]
    },
    female: {
      id: 'female',
      label: 'Female',
      // Three segments of two widths.  The top two share a width so there is
      // no step across the front, but the upper one is deeper -- which reads
      // as a chest in profile and leaves the front flat for a shirt graphic.
      // Each pair overlaps by 0.20 against a combined bevel of 0.13, so the
      // three read as one tapering body instead of three slabs.
      torso: [
        { size: [1.56, 0.73, 1.00], y: 3.645 },
        { size: [1.56, 0.82, 0.90], y: 3.07, decal: true },
        { size: [1.38, 0.70, 0.84], y: 2.51 }
      ],
      chest: { size: [1.56, 1.26, 0.95], y: 3.38 },
      waistLine: 2.16,
      hips: { size: [1.70, 0.54, 0.98], y: 2.12 },
      arm: { size: [0.64, 2.12, 0.78], x: 1.07, pivotY: 3.99 },
      leg: { size: [0.76, 2.12, 0.86], x: 0.40, pivotY: 2.12 },
      foot: { size: [0.82, 0.24, 1.04], z: 0.10 },
      backAnchor: [0, 3.06, -0.46]
    }
  };

  var RIG = {
    head: HEAD,
    height: HEIGHT,
    headTop: HEAD_TOP,
    hipY: 2.0,
    bodies: BODIES,
    // legacy shorthands a few callers still read
    torso: { size: BODIES.male.chest.size, centre: [0, 3.0, 0] },
    arm: { size: BODIES.male.arm.size, pivotY: BODIES.male.arm.pivotY,
           x: BODIES.male.arm.x },
    leg: { size: BODIES.male.leg.size, pivotY: BODIES.male.leg.pivotY,
           x: BODIES.male.leg.x }
  };

  var Avatar = {
    RIG: RIG,
    BODY_TYPES: ['male', 'female'],
    // The first person camera sits a touch above the middle of the head so the
    // view reads as "behind the eyes" rather than "inside the chin".
    EYE_HEIGHT: 5.05,
    // Third person orbits the old, lower pivot so that camera is unchanged.
    CHASE_PIVOT: 4.85
  };

  Avatar.body = function (descriptor) {
    var key = descriptor && (descriptor.body_type || descriptor.body);
    return BODIES[key] || BODIES.male;
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
      pose.armLZ = 0.06;
      pose.armRZ = -0.06;
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
      // a relaxed idle keeps the arms just off the torso
      pose.armLZ = 0.07;
      pose.armRZ = -0.07;
      pose.bob = Math.sin(time * 1.4) * 0.02;
    }
    return pose;
  };

  /* Build every renderable part for one character.
     opts: {position, yaw, pitch, pose, holding, dead, scale} */
  Avatar.build = function (descriptor, opts) {
    descriptor = descriptor || {};
    opts = opts || {};
    var body = Avatar.body(descriptor);
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
        t: (extra && extra.t) || 'rbox',
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
        if (extra.k) part.k = extra.k;
      }
      parts.push(part);
      return part;
    }

    // --------------------------------------------------------------- torso
    var torsoColour = shirtData.torso || colourOf(descriptor, 'torso', '#0d69ac');
    var torsoDecal = null;
    if (shirtData.decal) torsoDecal = Textures.decal(shirtData.decal);
    body.torso.forEach(function (segment) {
      place([0, segment.y, 0], segment.size.slice(), torsoColour, {
        rx: lean, decSlot: segment.decal ? torsoDecal : null, k: 'torso'
      });
    });
    // hips read as part of the lower body, so they take the trousers colour
    var hipColour = pantsData.legs || colourOf(descriptor, 'left_leg', '#a4bd47');
    place([0, body.hips.y, 0], body.hips.size.slice(), hipColour, { k: 'hips' });

    var lowest = body.torso[body.torso.length - 1];
    if (shirtData.stripe) {
      place([0, lowest.y - lowest.size[1] / 2 + 0.18, 0],
            [lowest.size[0] + 0.04, 0.34, lowest.size[2] + 0.04],
            shirtData.stripe, { rx: lean, k: 'torso' });
    }
    if (shirtData.stripes) {
      var span = body.chest.size[1] - 0.3;
      for (var si = 0; si < shirtData.stripes; si++) {
        var t = shirtData.stripes > 1 ? si / (shirtData.stripes - 1) : 0.5;
        place([0, body.chest.y - span / 2 + span * t, 0],
              [body.chest.size[0] + 0.03, 0.15, body.chest.size[2] + 0.03],
              shirtData.stripe || '#1b2a35', { rx: lean, k: 'torso' });
      }
    }
    if (shirtData.hood) {
      place([0, body.chest.y + body.chest.size[1] / 2 - 0.06, -0.34],
            [body.chest.size[0] * 0.86, 0.62, 0.72],
            shirtData.torso || torsoColour, { k: 'torso' });
    }

    // ---------------------------------------------------------------- neck
    var headColour = colourOf(descriptor, 'head', '#f5cd30');
    place([0, HEAD.neck.y, 0], HEAD.neck.size.slice(), headColour,
          { t: 'cyl', k: 'neck' });

    // ---------------------------------------------------------------- head
    var faceSlot = null;
    if (face && face.data) faceSlot = Textures.faceSlot(face.item_id, face.data);
    place([0, HEAD.centre[1], 0], HEAD.size.slice(), headColour, {
      t: 'rhead', decSlot: faceSlot, k: 'head'
    });

    // ---------------------------------------------------------------- arms
    var armLen = body.arm.size[1];
    function arm(side, swing, roll) {
      var x = body.arm.x * side;
      var pivotY = body.arm.pivotY;
      var half = armLen / 2;
      var yz = rotateX(-half, 0, swing);
      var centre = [x, pivotY + yz[0], yz[1]];
      var skin = colourOf(descriptor, side < 0 ? 'right_arm' : 'left_arm', '#f5cd30');
      var sleeve = shirtData.arms;
      var coverage = shirtData.sleeves === undefined ? 1.0 : shirtData.sleeves;
      var extra = { t: 'rlimb', rx: swing, rz: roll || 0, k: 'arm' };
      if (sleeve && coverage >= 0.99) {
        place(centre, body.arm.size.slice(), sleeve, extra);
      } else if (sleeve && coverage > 0.01) {
        var upperLen = armLen * coverage;
        var uy = rotateX(-(upperLen / 2), 0, swing);
        place([x, pivotY + uy[0], uy[1]],
              [body.arm.size[0] * 1.02, upperLen, body.arm.size[2] * 1.02],
              sleeve, extra);
        var lowerLen = armLen - upperLen;
        var ly = rotateX(-(upperLen + lowerLen / 2), 0, swing);
        place([x, pivotY + ly[0], ly[1]],
              [body.arm.size[0], lowerLen, body.arm.size[2]], skin, extra);
      } else {
        place(centre, body.arm.size.slice(), skin, extra);
      }
      var hand = rotateX(-armLen, 0, swing);
      return { x: x, y: pivotY + hand[0], z: hand[1], swing: swing };
    }

    var holding = opts.holding;
    var rightSwing = pose.armR;
    if (holding) rightSwing = -1.32 + (opts.pitch || 0) * 0.55;
    var leftSwing = pose.armL;
    if (holding && holding.twoHanded !== false) leftSwing = -1.15 + (opts.pitch || 0) * 0.4;
    var rightHand = arm(-1, rightSwing, holding ? 0 : pose.armRZ);
    arm(1, leftSwing, holding ? 0 : pose.armLZ);

    // ---------------------------------------------------------------- legs
    var legLen = body.leg.size[1];
    function leg(side, swing) {
      var x = body.leg.x * side;
      var pivotY = body.leg.pivotY;
      var yz = rotateX(-legLen / 2, 0, swing);
      var centre = [x, pivotY + yz[0], yz[1]];
      var skin = colourOf(descriptor, side < 0 ? 'right_leg' : 'left_leg', '#a4bd47');
      var trouser = pantsData.legs;
      var length = pantsData.length === undefined ? 1.0 : pantsData.length;
      var extra = { t: 'rlimb', rx: swing, k: 'leg' };
      var shoeColour = skin;
      if (trouser && length >= 0.99) {
        place(centre, body.leg.size.slice(), trouser, extra);
        shoeColour = pantsData.cuff || trouser;
      } else if (trouser && length > 0.01) {
        var upperLen = legLen * length;
        var uy = rotateX(-(upperLen / 2), 0, swing);
        place([x, pivotY + uy[0], uy[1]],
              [body.leg.size[0] * 1.02, upperLen, body.leg.size[2] * 1.02],
              trouser, extra);
        var lowerLen = legLen - upperLen;
        var ly = rotateX(-(upperLen + lowerLen / 2), 0, swing);
        place([x, pivotY + ly[0], ly[1]],
              [body.leg.size[0], lowerLen, body.leg.size[2]],
              pantsData.skin || skin, extra);
      } else {
        place(centre, body.leg.size.slice(), skin, extra);
      }
      if (pantsData.cuff) {
        var cy = rotateX(-(legLen - 0.2), 0, swing);
        place([x, pivotY + cy[0], cy[1]],
              [body.leg.size[0] + 0.05, 0.3, body.leg.size[2] + 0.05],
              pantsData.cuff, { rx: swing, k: 'leg' });
      }
      if (pantsData.stripe) {
        var sy = rotateX(-legLen / 2, 0, swing);
        place([x + side * (body.leg.size[0] / 2 + 0.01), pivotY + sy[0], sy[1]],
              [0.07, legLen * 0.92, body.leg.size[2] * 0.5],
              pantsData.stripe,
              { t: 'rlimb', rx: swing, m: pantsData.glow ? 'neon' : '', k: 'leg' });
      }
      // a shallow foot block: cheap, and it stops the legs reading as bare posts
      if (body.foot) {
        var fy = rotateX(-(legLen - body.foot.size[1] / 2), body.foot.z, swing);
        place([x, pivotY + fy[0], fy[1]], body.foot.size.slice(), shoeColour,
              { rx: swing, k: 'foot' });
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
      attach(back.data.parts, body.backAnchor);
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
    var body = Avatar.body(descriptor);
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
    // the real arm is rectangular now, so the view model takes the mean of
    // its two cross-section axes rather than the narrow one alone
    var armThickness = (body.arm.size[0] + body.arm.size[2]) * 0.5 * 0.46;

    // forearm
    var armLocal = [base[0] - 0.10, base[1] - 0.34, base[2] - 0.78];
    parts.push({
      // long in Z rather than Y, so the general bake is the right one here
      t: 'rbox',
      p: toWorld(armLocal),
      s: [armThickness, armThickness, 1.5],
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
