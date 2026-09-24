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
// Frames only while it runs, at most `fps` of them.

const DEFAULT_FONT = '"Thmanyah", "Segoe UI", system-ui, sans-serif';
// The scramble component's own alphabet.
const CHARS = '!@#$%^&*()_+-=[]{}|;:,.<>?/~`░▒▓█▀▄■□▪▫●○◆◇◈◊※†‡';

const randomChar = () => CHARS[Math.floor(Math.random() * CHARS.length)] || '?';

/* The word with its first `progress` of letters settled and the rest noise. */
export function scrambled(target, progress) {
  const settled = Math.floor(target.length * progress);
  return [...target].map((ch, i) => (ch === ' ' ? ' ' : i < settled ? ch : randomChar())).join('');
}

// Motion's "easeOut".
const easeOut = (t) => 1 - (1 - t) * (1 - t);

export class LedWord {
  constructor(canvas, {
    text = 'APOLLO', rows = 16, aspect = 2.1, gap = 0.34, colour = [255, 246, 230],
    glow = 1, stretch = 1, lean = 0, fps = 30, fill = 0.9,
    font = DEFAULT_FONT, weight = 900,
  } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    Object.assign(this, { text, rows, aspect, gap, colour, glow, stretch, lean, fps, fill,
                          font, weight });
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
    for (const c of [this.canvas, this.layer, this.mask, this.lines]) {
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
    const wide = probe.width * this.stretch + cap * Math.abs(this.lean);
    const size = Math.min((height * this.fill) / cap, (width * 0.94) / wide) * 100;
    this.size = size;
    this.cap = (cap * size) / 100;
    this.wordWidth = (probe.width * size) / 100;

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
    if (text === this.text) {
      ctx.fillText(text, -this.wordWidth / 2, 0);
      return;
    }
    // Mid-scramble, each glyph in its own letter's slot and no wider: the
    // symbols and blocks come from whatever font has them, some far wider
    // than a letter, and would otherwise shove the word about and spill
    // off the edge.
    const chars = [...text];
    const slot = this.wordWidth / Math.max(1, [...this.text].length);
    chars.forEach((ch, i) => {
      ctx.fillText(ch, -this.wordWidth / 2 + i * slot, 0, slot * 0.96);
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
    const { canvas, ctx } = this;
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

    // The tube: bloom under, the cells, a flicker through all of it.
    const flicker = Math.random() < 0.012 ? 0.62 : 0.93 + Math.random() * 0.07;
    ctx.clearRect(0, 0, width, height);
    ctx.globalCompositeOperation = 'lighter';
    ctx.filter = `blur(${(this.cellH * 2.2).toFixed(1)}px)`;
    ctx.globalAlpha = 0.55 * this.glow * flicker;
    ctx.drawImage(this.layer, 0, 0);
    ctx.filter = `blur(${(this.cellH * 0.6).toFixed(1)}px)`;
    ctx.globalAlpha = 0.5 * this.glow * flicker;
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
