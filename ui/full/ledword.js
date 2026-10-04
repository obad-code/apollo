// A word in lit cells: an LED sign, seen on an old tube.
//
// The letters come from a font used only as a stencil. What shows is a grid
// of small oblong cells, each lit where the stencil covers it and cut clean
// at the stencil's edge - a word built out of a display's own pixels. Over
// that, the tube: a bloom (the cells blurred and added back), the three guns
// landing a hair apart, a flicker, scanlines, and now and then a brighter
// band rolling down the glass.
//
// It arrives scrambled: every letter a random glyph - symbols, blocks,
// shades - settling into the word from the left, the way the scramble-text
// component does it. `scramble()` plays that; the intro, the idle screen and
// the display's wordmark open with it, and the wordmark does it again under
// the pointer.
//
// And it is seen through the glass: the frame is bent by the same fisheye
// as the dots behind it, with its colours parting towards the edges (see
// `glass` below).
//
// Frames only while it runs, at most `fps` of them.

const DEFAULT_FONT = '"Inter", "IBM Plex Sans Arabic", "Segoe UI", system-ui, sans-serif';
// The scramble component's own alphabet.
const CHARS = '!@#$%^&*()_+-=[]{}|;:,.<>?/~`░▒▓█▀▄■□▪▫●○◆◇◈◊※†‡';

const randomChar = () => CHARS[Math.floor(Math.random() * CHARS.length)] || '?';

/* Where each letter goes when the word is set with room between its letters:
 * the place the font gives it (`prefixes`, the width of everything before
 * it), moved along by `gap` for every letter before it. `full` is the
 * font's own width for the whole word. */
export function spaced(prefixes, widths, full, gap) {
  const slots = prefixes.map((x, i) => ({ x: x + i * gap, w: widths[i] }));
  return { slots, width: full + Math.max(0, prefixes.length - 1) * gap };
}

/* The word with its first `progress` of letters settled and the rest noise. */
export function scrambled(target, progress) {
  const settled = Math.floor(target.length * progress);
  return [...target].map((ch, i) => (ch === ' ' ? ' ' : i < settled ? ch : randomChar())).join('');
}

// The glass the word is seen through: the same bulge as the dots behind it
// (shader.js), and the three guns landing further apart towards the edges.
// A second pass on the GPU over the finished 2D frame; without WebGL the
// word is simply drawn flat.
const GLASS_VERTEX = `
attribute vec2 position;
varying vec2 uv;
void main() { uv = position * 0.5 + 0.5; gl_Position = vec4(position, 0.0, 1.0); }
`;

const GLASS_FRAGMENT = `
precision mediump float;
varying vec2 uv;
uniform sampler2D frame;
uniform float aspect;      // width over height
uniform float bulge;       // how far the middle swells, 0 for flat glass
void main() {
  vec2 p = uv * 2.0 - 1.0;
  // 0 at the centre to 1 in a corner, measured on the real shape.
  float r2 = (p.x * p.x * aspect * aspect + p.y * p.y) / (aspect * aspect + 1.0);
  vec2 q = p * (1.0 - bulge + bulge * r2 * 1.4);
  vec2 at = q * 0.5 + 0.5;
  if (at.x < 0.0 || at.x > 1.0 || at.y < 0.0 || at.y > 1.0) {
    gl_FragColor = vec4(0.0);
    return;
  }
  vec2 miss = q * r2 * 0.012;
  vec4 red = texture2D(frame, at + miss);
  vec4 mid = texture2D(frame, at);
  vec4 blue = texture2D(frame, at - miss);
  // Premultiplied throughout: the alpha has to cover the brightest channel.
  vec4 colour = vec4(red.r, mid.g, blue.b, max(mid.a, max(red.a, blue.a)));
  // Faded out towards the canvas's own edges, so the glow ends softly
  // rather than on a straight line where the canvas stops.
  float edge = smoothstep(0.0, 0.06, at.x) * smoothstep(1.0, 0.94, at.x)
             * smoothstep(0.0, 0.14, at.y) * smoothstep(1.0, 0.86, at.y);
  gl_FragColor = colour * edge;
}
`;

function glass(canvas) {
  const gl = canvas.getContext('webgl', { premultipliedAlpha: true, alpha: true,
                                          antialias: false, depth: false });
  if (!gl) return null;
  const compile = (type, source) => {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.error('ledword glass:', gl.getShaderInfoLog(shader));
    }
    return shader;
  };
  const program = gl.createProgram();
  gl.attachShader(program, compile(gl.VERTEX_SHADER, GLASS_VERTEX));
  gl.attachShader(program, compile(gl.FRAGMENT_SHADER, GLASS_FRAGMENT));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;
  gl.useProgram(program);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, 'position');
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
  gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
  return { gl, aspect: gl.getUniformLocation(program, 'aspect'),
           bulge: gl.getUniformLocation(program, 'bulge') };
}

// Motion's "easeOut".
const easeOut = (t) => 1 - (1 - t) * (1 - t);

export class LedWord {
  constructor(canvas, {
    text = 'APOLLO', rows = 16, aspect = 2.1, gap = 0.34, colour = [255, 246, 230],
    glow = 1, stretch = 1, lean = 0, fps = 30, fill = 0.9,
    font = DEFAULT_FONT, weight = 900, bulge = 0.22,
    tracking = 0,          // extra room between the letters, in cap heights
  } = {}) {
    this.canvas = canvas;
    // The word is drawn in 2D onto `surface`; the glass bends that onto the
    // canvas on the page. No WebGL, no glass: the surface is the canvas.
    this.glass = glass(canvas);
    this.surface = this.glass ? document.createElement('canvas') : canvas;
    this.ctx = this.surface.getContext('2d');
    Object.assign(this, { text, rows, aspect, gap, colour, glow, stretch, lean, fps, fill,
                          font, weight, bulge, tracking });
    this.shown = text;         // what the stencil says right now
    this.cells = [];
    this.frame = null;
    this.last = 0;
    this.scrambleAt = null;    // when the scramble starts, in ms; null when settled
    this.scrambleFor = 0.75;
    this.roll = -1;            // where the bright band is, 0..1 down the glass; -1 when there is none
    this.layer = document.createElement('canvas');
    this.mask = document.createElement('canvas');
    this.lines = document.createElement('canvas');
    this.cover = document.createElement('canvas');
    // Built again once the font has arrived: drawn before it, the stencil
    // would be the fallback face.
    if (document.fonts && document.fonts.load) {
      document.fonts.load(this._face(100)).then(() => this.resize(), () => {});
    }
    this.resize();
  }

  _face(size) {
    return `${this.weight} ${size}px ${this.font}`;
  }

  resize() {
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const width = Math.round(this.canvas.clientWidth * ratio);
    const height = Math.round(this.canvas.clientHeight * ratio);
    if (!width || !height) return;          // not laid out yet (display: none)
    for (const c of new Set([this.canvas, this.surface, this.layer, this.mask, this.lines])) {
      c.width = width;
      c.height = height;
    }
    this.ratio = ratio;
    this._layout(width, height);
    this._scanlines(width, height);
    this._stencil(this.shown);
    this.draw(performance.now());
  }

  /* Sized and placed for the word itself, once: the scramble's glyphs are
   * drawn in the same place, so the word does not jump about while it
   * settles. */
  _layout(width, height) {
    const m = this.mask.getContext('2d');
    m.font = this._face(100);
    const probe = m.measureText(this.text);
    const cap = probe.actualBoundingBoxAscent || 72;
    const letters = [...this.text];
    const tracked = probe.width + Math.max(0, letters.length - 1) * this.tracking * cap;
    const wide = tracked * this.stretch + cap * Math.abs(this.lean);
    const size = Math.min((height * this.fill) / cap, (width * 0.94) / wide) * 100;
    this.size = size;
    this.cap = (cap * size) / 100;
    // Where each letter of the word sits, and how wide it is: a scrambled
    // glyph goes in its letter's place, so nothing moves when it settles.
    // The room between the letters is added to those places.
    m.font = this._face(size);
    const set = spaced(
      letters.map((_, i) => m.measureText(letters.slice(0, i).join('')).width),
      letters.map((ch) => m.measureText(ch).width),
      m.measureText(this.text).width,
      this.tracking * this.cap);
    this.slots = set.slots;
    this.wordWidth = set.width;

    const cellH = this.cap / this.rows;
    const cellW = cellH * this.aspect;
    const cols = Math.ceil(width / cellW);
    const rows = Math.ceil(height / cellH);
    const x0 = (width - cols * cellW) / 2;
    const y0 = (height - rows * cellH) / 2;
    // The same dark gutter both ways, in pixels: the cells read as cells.
    const gutter = cellH * this.gap;
    this.cellH = cellH;
    this.grid = { cols, rows, x0, y0, cellW, cellH };
    this.cover.width = cols;
    this.cover.height = rows;
    this.all = [];
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const seed = Math.random();
        this.all.push({
          x: x0 + col * cellW + gutter / 2, y: y0 + row * cellH + gutter / 2,
          w: cellW - gutter, h: cellH - gutter, seed,
          // A few cells on any real sign are tired; these burn a little low.
          tired: seed < 0.02 ? 0.45 : 1,
        });
      }
    }
  }

  /* Draw `text` where the word goes, on `ctx`, in the word's own space. */
  _write(ctx, text) {
    ctx.translate(this.canvas.width / 2, this.canvas.height / 2 + this.cap / 2);
    ctx.transform(this.stretch, 0, this.lean, 1, 0, 0);
    ctx.font = this._face(this.size);
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = '#fff';
    if (text === this.text && !this.tracking) {
      ctx.fillText(text, -this.wordWidth / 2, 0);
      return;
    }
    // Letter by letter, each in its own place: the word set with room
    // between its letters, or mid-scramble, where every glyph also stays no
    // wider than its letter - the symbols and blocks come from whatever font
    // has them, some far wider than a letter, and would otherwise shove the
    // word about and spill off the edge.
    [...text].forEach((ch, i) => {
      const slot = this.slots[i];
      if (slot) ctx.fillText(ch, -this.wordWidth / 2 + slot.x, 0, Math.max(1, slot.w));
    });
  }

  /* The stencil for what the word says now, and which cells it touches -
   * read from a copy drawn one pixel per cell, so it costs next to nothing
   * to do every frame of a scramble. */
  _stencil(text) {
    this.shown = text;
    const width = this.mask.width, height = this.mask.height;
    const m = this.mask.getContext('2d');
    m.setTransform(1, 0, 0, 1, 0, 0);
    m.clearRect(0, 0, width, height);
    m.save();
    this._write(m, text);
    m.restore();

    const { cols, rows, x0, y0, cellW, cellH } = this.grid;
    const c = this.cover.getContext('2d');
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.clearRect(0, 0, cols, rows);
    c.save();
    c.setTransform(1 / cellW, 0, 0, 1 / cellH, -x0 / cellW, -y0 / cellH);
    this._write(c, text);
    c.restore();
    const alpha = c.getImageData(0, 0, cols, rows).data;
    this.cells = this.all.filter((cell, i) => alpha[i * 4 + 3] > 16);
  }

  _scanlines(width, height) {
    const l = this.lines.getContext('2d');
    l.clearRect(0, 0, width, height);
    // Only where a cell is tall enough to carry them: across a small one
    // they turn every cell into two stripes, and the word into a barcode.
    if (this.cellH < 12 * this.ratio) return;
    l.fillStyle = 'rgba(0, 0, 0, .22)';
    const step = Math.max(2, Math.round(3 * this.ratio));
    for (let y = 0; y < height; y += step) l.fillRect(0, y, width, Math.max(1, Math.round(this.ratio)));
  }

  /* Where the scramble is: the text to show now, or null when there is none. */
  _scrambling(now) {
    if (this.scrambleAt === null) return null;
    const t = (now - this.scrambleAt) / 1000;
    if (t < 0) return '';                            // not started: nothing lit yet
    if (t >= this.scrambleFor) {
      this.scrambleAt = null;
      return this.text;
    }
    return scrambled(this.text, easeOut(t / this.scrambleFor));
  }

  draw(now) {
    const { surface: canvas, ctx } = this;
    const width = canvas.width, height = canvas.height;
    if (!width || !height || !this.grid) return;
    const next = this._scrambling(now);
    if (next !== null && next !== this.shown) this._stencil(next);

    const [r, g, b] = this.colour;
    const shift = Math.max(0.6, this.cellH * 0.045);   // how far apart the guns land

    // The cells, once per gun, added together: white where they meet, a
    // fringe of colour where they do not. Each has its own slow shimmer.
    const l = this.layer.getContext('2d');
    l.globalCompositeOperation = 'source-over';
    l.globalAlpha = 1;
    l.clearRect(0, 0, width, height);
    l.globalCompositeOperation = 'lighter';
    const seconds = now / 1000;
    const levels = this.cells.map((cell) =>
      cell.tired * (0.84 + 0.16 * Math.sin(seconds * (1.3 + cell.seed * 2.4) + cell.seed * 40)));
    for (const [colour, dx] of [[`rgb(${r},0,0)`, -shift], [`rgb(0,${g},0)`, 0], [`rgb(0,0,${b})`, shift]]) {
      l.fillStyle = colour;
      this.cells.forEach((cell, i) => {
        l.globalAlpha = levels[i];
        l.fillRect(cell.x + dx, cell.y, cell.w, cell.h);
      });
    }
    // Cut clean at the letters' edges.
    l.globalAlpha = 1;
    l.globalCompositeOperation = 'destination-in';
    l.drawImage(this.mask, 0, 0);
    l.globalCompositeOperation = 'source-over';

    // The tube: bloom under, the cells, a flicker through all of it - a
    // restless one, and now and then a dip.
    const flicker = Math.random() < 0.02 ? 0.55 : 0.87 + Math.random() * 0.13;
    ctx.clearRect(0, 0, width, height);
    ctx.globalCompositeOperation = 'lighter';
    ctx.filter = `blur(${(this.cellH * 2.6).toFixed(1)}px)`;
    ctx.globalAlpha = 0.7 * this.glow * flicker;
    ctx.drawImage(this.layer, 0, 0);
    ctx.filter = `blur(${(this.cellH * 0.7).toFixed(1)}px)`;
    ctx.globalAlpha = 0.6 * this.glow * flicker;
    ctx.drawImage(this.layer, 0, 0);
    ctx.filter = 'none';
    ctx.globalAlpha = flicker;
    ctx.drawImage(this.layer, 0, 0);

    // Now and then a brighter band rolls down the glass.
    if (this.roll < 0 && Math.random() < 0.004) this.roll = 0;
    if (this.roll >= 0) {
      const band = height * 0.16;
      const y = this.roll * (height + band) - band;
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, y, width, band);
      ctx.clip();
      ctx.globalAlpha = 0.35;
      ctx.drawImage(this.layer, 0, 0);
      ctx.restore();
      this.roll += 0.02;
      if (this.roll > 1) this.roll = -1;
    }

    // Scanlines: taken out of whatever was drawn, row by row.
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'destination-out';
    ctx.drawImage(this.lines, 0, 0);
    ctx.globalCompositeOperation = 'source-over';

    // Through the glass.
    if (this.glass) {
      const { gl } = this.glass;
      gl.viewport(0, 0, width, height);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, canvas);
      gl.uniform1f(this.glass.aspect, width / height);
      gl.uniform1f(this.glass.bulge, this.bulge);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }
  }

  /* Arrive scrambled and settle into the word over `seconds`, `delay`
   * seconds from now - the component's 0.75s, easing out. */
  scramble(seconds = 0.75, delay = 0) {
    this.scrambleFor = seconds;
    this.scrambleAt = performance.now() + delay * 1000;
    this.start();
  }

  start() {
    if (this.frame !== null) return;
    const tick = (now) => {
      if (now - this.last >= 1000 / this.fps - 1) {
        this.last = now;
        this.draw(now);
      }
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  stop() {
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.frame = null;
  }
}
