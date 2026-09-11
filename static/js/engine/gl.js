/* BLOCKHAVEN engine -- WebGL context helpers and the little bit of maths the
   rest of the renderer needs.  No external libraries anywhere in this project. */
(function (global) {
  'use strict';

  var GLX = {};

  // ---------------------------------------------------------------- context
  GLX.createContext = function (canvas, opts) {
    opts = opts || {};
    var attrs = {
      alpha: !!opts.alpha,
      antialias: opts.antialias !== false,
      depth: true,
      stencil: false,
      premultipliedAlpha: false,
      preserveDrawingBuffer: !!opts.preserveDrawingBuffer,
      powerPreference: 'high-performance',
      failIfMajorPerformanceCaveat: false
    };
    var gl = canvas.getContext('webgl2', attrs);
    var version = 2;
    if (!gl) {
      gl = canvas.getContext('webgl', attrs) || canvas.getContext('experimental-webgl', attrs);
      version = 1;
    }
    if (!gl) return null;
    gl.__version = version;
    if (version === 1) {
      var ext = gl.getExtension('ANGLE_instanced_arrays');
      if (!ext) return null;
      gl.vertexAttribDivisor = ext.vertexAttribDivisorANGLE.bind(ext);
      gl.drawElementsInstanced = ext.drawElementsInstancedANGLE.bind(ext);
      gl.createVertexArray = function () { return null; };
      gl.bindVertexArray = function () {};
      gl.__noVAO = true;
      gl.getExtension('OES_element_index_uint');
    }
    return gl;
  };

  GLX.compile = function (gl, vertexSource, fragmentSource, name) {
    function shader(type, source) {
      var sh = gl.createShader(type);
      gl.shaderSource(sh, source);
      gl.compileShader(sh);
      if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
        console.error('[' + (name || 'shader') + '] ' + gl.getShaderInfoLog(sh));
        console.error(source.split('\n').map(function (l, i) {
          return (i + 1) + ': ' + l;
        }).join('\n'));
        return null;
      }
      return sh;
    }
    var vs = shader(gl.VERTEX_SHADER, vertexSource);
    var fs = shader(gl.FRAGMENT_SHADER, fragmentSource);
    if (!vs || !fs) return null;
    var program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('[link] ' + gl.getProgramInfoLog(program));
      return null;
    }
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    program.uniforms = {};
    program.attribs = {};
    var count = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS);
    for (var i = 0; i < count; i++) {
      var info = gl.getActiveUniform(program, i);
      var uname = info.name.replace(/\[0\]$/, '');
      program.uniforms[uname] = gl.getUniformLocation(program, uname);
    }
    count = gl.getProgramParameter(program, gl.ACTIVE_ATTRIBUTES);
    for (i = 0; i < count; i++) {
      var ainfo = gl.getActiveAttrib(program, i);
      program.attribs[ainfo.name] = gl.getAttribLocation(program, ainfo.name);
    }
    return program;
  };

  // ------------------------------------------------------------------ maths
  var M = {};

  M.identity = function (out) {
    out = out || new Float32Array(16);
    out[0] = 1; out[1] = 0; out[2] = 0; out[3] = 0;
    out[4] = 0; out[5] = 1; out[6] = 0; out[7] = 0;
    out[8] = 0; out[9] = 0; out[10] = 1; out[11] = 0;
    out[12] = 0; out[13] = 0; out[14] = 0; out[15] = 1;
    return out;
  };

  M.perspective = function (out, fovyRadians, aspect, near, far) {
    var f = 1.0 / Math.tan(fovyRadians / 2);
    out[0] = f / aspect; out[1] = 0; out[2] = 0; out[3] = 0;
    out[4] = 0; out[5] = f; out[6] = 0; out[7] = 0;
    out[8] = 0; out[9] = 0; out[11] = -1;
    out[12] = 0; out[13] = 0; out[15] = 0;
    var nf = 1 / (near - far);
    out[10] = (far + near) * nf;
    out[14] = 2 * far * near * nf;
    return out;
  };

  M.ortho = function (out, left, right, bottom, top, near, far) {
    var lr = 1 / (left - right), bt = 1 / (bottom - top), nf = 1 / (near - far);
    out[0] = -2 * lr; out[1] = 0; out[2] = 0; out[3] = 0;
    out[4] = 0; out[5] = -2 * bt; out[6] = 0; out[7] = 0;
    out[8] = 0; out[9] = 0; out[10] = 2 * nf; out[11] = 0;
    out[12] = (left + right) * lr; out[13] = (top + bottom) * bt;
    out[14] = (far + near) * nf; out[15] = 1;
    return out;
  };

  M.lookAt = function (out, eye, centre, up) {
    var z0 = eye[0] - centre[0], z1 = eye[1] - centre[1], z2 = eye[2] - centre[2];
    var len = Math.sqrt(z0 * z0 + z1 * z1 + z2 * z2);
    if (len < 1e-6) { z0 = 0; z1 = 0; z2 = 1; len = 1; }
    len = 1 / len; z0 *= len; z1 *= len; z2 *= len;
    var x0 = up[1] * z2 - up[2] * z1;
    var x1 = up[2] * z0 - up[0] * z2;
    var x2 = up[0] * z1 - up[1] * z0;
    len = Math.sqrt(x0 * x0 + x1 * x1 + x2 * x2);
    if (len < 1e-6) { x0 = 1; x1 = 0; x2 = 0; len = 1; }
    len = 1 / len; x0 *= len; x1 *= len; x2 *= len;
    var y0 = z1 * x2 - z2 * x1;
    var y1 = z2 * x0 - z0 * x2;
    var y2 = z0 * x1 - z1 * x0;
    out[0] = x0; out[1] = y0; out[2] = z0; out[3] = 0;
    out[4] = x1; out[5] = y1; out[6] = z1; out[7] = 0;
    out[8] = x2; out[9] = y2; out[10] = z2; out[11] = 0;
    out[12] = -(x0 * eye[0] + x1 * eye[1] + x2 * eye[2]);
    out[13] = -(y0 * eye[0] + y1 * eye[1] + y2 * eye[2]);
    out[14] = -(z0 * eye[0] + z1 * eye[1] + z2 * eye[2]);
    out[15] = 1;
    return out;
  };

  M.multiply = function (out, a, b) {
    var a00 = a[0], a01 = a[1], a02 = a[2], a03 = a[3],
        a10 = a[4], a11 = a[5], a12 = a[6], a13 = a[7],
        a20 = a[8], a21 = a[9], a22 = a[10], a23 = a[11],
        a30 = a[12], a31 = a[13], a32 = a[14], a33 = a[15];
    for (var i = 0; i < 4; i++) {
      var b0 = b[i * 4], b1 = b[i * 4 + 1], b2 = b[i * 4 + 2], b3 = b[i * 4 + 3];
      out[i * 4] = b0 * a00 + b1 * a10 + b2 * a20 + b3 * a30;
      out[i * 4 + 1] = b0 * a01 + b1 * a11 + b2 * a21 + b3 * a31;
      out[i * 4 + 2] = b0 * a02 + b1 * a12 + b2 * a22 + b3 * a32;
      out[i * 4 + 3] = b0 * a03 + b1 * a13 + b2 * a23 + b3 * a33;
    }
    return out;
  };

  /* Compose a model matrix from position, euler rotation (XYZ) and scale.
     Written straight into a Float32Array slice for the instance buffer. */
  M.compose = function (out, offset, px, py, pz, rx, ry, rz, sx, sy, sz) {
    var cx = Math.cos(rx), sxr = Math.sin(rx);
    var cy = Math.cos(ry), syr = Math.sin(ry);
    var cz = Math.cos(rz), szr = Math.sin(rz);
    // R = Ry * Rx * Rz  (yaw, then pitch, then roll)
    var m00 = cy * cz + syr * sxr * szr;
    var m01 = cx * szr;
    var m02 = -syr * cz + cy * sxr * szr;
    var m10 = -cy * szr + syr * sxr * cz;
    var m11 = cx * cz;
    var m12 = syr * szr + cy * sxr * cz;
    var m20 = syr * cx;
    var m21 = -sxr;
    var m22 = cy * cx;
    out[offset] = m00 * sx; out[offset + 1] = m01 * sx; out[offset + 2] = m02 * sx; out[offset + 3] = 0;
    out[offset + 4] = m10 * sy; out[offset + 5] = m11 * sy; out[offset + 6] = m12 * sy; out[offset + 7] = 0;
    out[offset + 8] = m20 * sz; out[offset + 9] = m21 * sz; out[offset + 10] = m22 * sz; out[offset + 11] = 0;
    out[offset + 12] = px; out[offset + 13] = py; out[offset + 14] = pz; out[offset + 15] = 1;
    return out;
  };

  M.transformPoint = function (out, m, x, y, z) {
    out[0] = m[0] * x + m[4] * y + m[8] * z + m[12];
    out[1] = m[1] * x + m[5] * y + m[9] * z + m[13];
    out[2] = m[2] * x + m[6] * y + m[10] * z + m[14];
    return out;
  };

  M.invert = function (out, a) {
    var a00 = a[0], a01 = a[1], a02 = a[2], a03 = a[3],
        a10 = a[4], a11 = a[5], a12 = a[6], a13 = a[7],
        a20 = a[8], a21 = a[9], a22 = a[10], a23 = a[11],
        a30 = a[12], a31 = a[13], a32 = a[14], a33 = a[15];
    var b00 = a00 * a11 - a01 * a10, b01 = a00 * a12 - a02 * a10,
        b02 = a00 * a13 - a03 * a10, b03 = a01 * a12 - a02 * a11,
        b04 = a01 * a13 - a03 * a11, b05 = a02 * a13 - a03 * a12,
        b06 = a20 * a31 - a21 * a30, b07 = a20 * a32 - a22 * a30,
        b08 = a20 * a33 - a23 * a30, b09 = a21 * a32 - a22 * a31,
        b10 = a21 * a33 - a23 * a31, b11 = a22 * a33 - a23 * a32;
    var det = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06;
    if (!det) return null;
    det = 1.0 / det;
    out[0] = (a11 * b11 - a12 * b10 + a13 * b09) * det;
    out[1] = (a02 * b10 - a01 * b11 - a03 * b09) * det;
    out[2] = (a31 * b05 - a32 * b04 + a33 * b03) * det;
    out[3] = (a22 * b04 - a21 * b05 - a23 * b03) * det;
    out[4] = (a12 * b08 - a10 * b11 - a13 * b07) * det;
    out[5] = (a00 * b11 - a02 * b08 + a03 * b07) * det;
    out[6] = (a32 * b02 - a30 * b05 - a33 * b01) * det;
    out[7] = (a20 * b05 - a22 * b02 + a23 * b01) * det;
    out[8] = (a10 * b10 - a11 * b08 + a13 * b06) * det;
    out[9] = (a01 * b08 - a00 * b10 - a03 * b06) * det;
    out[10] = (a30 * b04 - a31 * b02 + a33 * b00) * det;
    out[11] = (a21 * b02 - a20 * b04 - a23 * b00) * det;
    out[12] = (a11 * b07 - a10 * b09 - a12 * b06) * det;
    out[13] = (a00 * b09 - a01 * b07 + a02 * b06) * det;
    out[14] = (a31 * b01 - a30 * b03 - a32 * b00) * det;
    out[15] = (a20 * b03 - a21 * b01 + a22 * b00) * det;
    return out;
  };

  // ----------------------------------------------------------------- colour
  var colorCache = {};
  M.hexToRgb = function (hex) {
    if (colorCache[hex]) return colorCache[hex];
    var value = String(hex || '#ffffff').replace('#', '');
    if (value.length === 3) {
      value = value[0] + value[0] + value[1] + value[1] + value[2] + value[2];
    }
    var num = parseInt(value, 16);
    if (isNaN(num)) num = 0xffffff;
    var out = [((num >> 16) & 255) / 255, ((num >> 8) & 255) / 255, (num & 255) / 255];
    colorCache[hex] = out;
    return out;
  };

  M.clamp = function (v, a, b) { return v < a ? a : (v > b ? b : v); };
  M.lerp = function (a, b, t) { return a + (b - a) * t; };
  M.toRad = Math.PI / 180;

  GLX.mat = M;
  global.GLX = GLX;
})(window);
