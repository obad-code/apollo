// A word in lit cells: an LED sign, seen on an old tube.
//
// The letters are Thmanyah at its heaviest, stretched wide and leaned
// forward, and used only as a stencil. What shows is a grid of small oblong
// cells, each lit where the stencil covers it and cut clean at the stencil's
// edge - a word built out of a display's own pixels. Over that, the tube:
// a bloom (the cells blurred and added back), the three guns landing a hair
// apart, a flicker, scanlines, and now and then a brighter band rolling down
// the glass.
//
// Frames only while it runs, at most `fps` of them. `sweep()` lights it cell
// by cell from the left, each cell stuttering on; the intro and the idle
// screen open with that, the display's wordmark whenever the display opens.

const FONT = '"Thmanyah", "Segoe UI", system-ui, sans-serif';

export class LedWord {
  constructor(canvas, {
    text = 'APOLLO', rows = 16, aspect = 2.1, gap = 0.34, colour = [255, 246, 230],
    glow = 1, stretch = 1.42, lean = -0.18, fps = 30, fill = 0.9,
  } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    Object.assign(this, { text, rows, aspect, gap, colour, glow, stretch, lean, fps, fill });
    this.cells = [];
    this.frame = null;
    this.last = 0;
    this.revealAt = null;      // when the sweep started, in ms; null when fully lit
    this.sweepFor = 1.1;
    this.roll = -1;            // where the bright band is, 0..1 down the glass; -1 when there is none
    this.layer = document.createElement('canvas');
    this.mask = document.createElement('canvas');
    this.lines = document.createElement('canvas');
    // Built again once the font has arrived: drawn before it, the stencil
    // would be the fallback face.
    if (document.fonts && document.fonts.load) {
      document.fonts.load(`900 100px ${FONT}`).then(() => this.resize(), () => {});
    }
    this.resize();
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
    this._stencil(width, height);
    this._grid(width, height);
    this._scanlines(width, height);
    this.draw(performance.now());
  }

  _stencil(width, height) {
    const m = this.mask.getContext('2d');
    m.clearRect(0, 0, width, height);
    m.font = `900 100px ${FONT}`;
    const probe = m.measureText(this.text);
    const cap = probe.actualBoundingBoxAscent || 72;
    const wide = probe.width * this.stretch + cap * Math.abs(this.lean);
    // As large as fits: the cap height to `fill` of the canvas, the word to
    // nine tenths of its width.
    const size = Math.min((height * this.fill) / cap, (width * 0.94) / wide) * 100;
    this.cap = (cap * size) / 100;
    m.save();
    m.translate(width / 2, height / 2 + this.cap / 2);
    // Wide, and leaning forward: x' = stretch·x + lean·y.
    m.transform(this.stretch, 0, this.lean, 1, 0, 0);
    m.font = `900 ${size}px ${FONT}`;
    m.textAlign = 'center';
    m.textBaseline = 'alphabetic';
    m.fillStyle = '#fff';
    m.fillText(this.text, 0, 0);
    m.restore();
  }

  _grid(width, height) {
    const cellH = this.cap / this.rows;
    const cellW = cellH * this.aspect;
    const alpha = this.mask.getContext('2d').getImageData(0, 0, width, height).data;
    const covered = (x, y) => {
      const px = Math.max(0, Math.min(width - 1, Math.round(x)));
      const py = Math.max(0, Math.min(height - 1, Math.round(y)));
      return alpha[(py * width + px) * 4 + 3] > 20;
    };
    const cols = Math.ceil(width / cellW);
    const rows = Math.ceil(height / cellH);
    const x0 = (width - cols * cellW) / 2;
    const y0 = (height - rows * cellH) / 2;
    // The same dark gutter both ways, in pixels: the cells read as cells.
    const gutter = cellH * this.gap;
    this.cells = [];
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const x = x0 + col * cellW, y = y0 + row * cellH;
        // Kept if the stencil touches it anywhere: the stencil cuts it later.
        const hit = [[0.2, 0.25], [0.8, 0.25], [0.5, 0.5], [0.2, 0.75], [0.8, 0.75]]
          .some(([u, v]) => covered(x + u * cellW, y + v * cellH));
        if (!hit) continue;
        const seed = Math.random();
        this.cells.push({
          x: x + gutter / 2, y: y + gutter / 2,
          w: cellW - gutter, h: cellH - gutter,
          across: col / cols, seed,
          // A few cells on any real sign are tired; these burn a little low.
          tired: seed < 0.02 ? 0.45 : 1,
        });
      }
    }
    this.cellH = cellH;
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

  /* How lit one cell is at `now`: its own slow shimmer, and during a sweep,
   * off until its moment and then a stutter before it holds. */
  _level(cell, now) {
    let level = cell.tired * (0.84 + 0.16 * Math.sin(now / 1000 * (1.3 + cell.seed * 2.4) + cell.seed * 40));
    if (this.revealAt !== null) {
      const at = (now - this.revealAt) / 1000 - (cell.across * this.sweepFor + cell.seed * 0.22);
      if (at < 0) return 0;
      if (at < 0.14) level *= Math.random() < 0.55 ? 1 : 0.15;
    }
    return level;
  }

  draw(now) {
    const { canvas, ctx } = this;
    const width = canvas.width, height = canvas.height;
    if (!width || !height) return;
    const [r, g, b] = this.colour;
    const shift = Math.max(0.6, this.cellH * 0.045);   // how far apart the guns land

    // The cells, once per gun, added together: white where they meet, a
    // fringe of colour where they do not.
    const l = this.layer.getContext('2d');
    l.globalCompositeOperation = 'source-over';
    l.globalAlpha = 1;
    l.clearRect(0, 0, width, height);
    l.globalCompositeOperation = 'lighter';
    const levels = this.cells.map((cell) => this._level(cell, now));
    for (const [colour, dx] of [[`rgb(${r},0,0)`, -shift], [`rgb(0,${g},0)`, 0], [`rgb(0,0,${b})`, shift]]) {
      l.fillStyle = colour;
      this.cells.forEach((cell, i) => {
        if (levels[i] <= 0.01) return;
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

    if (this.revealAt !== null && (now - this.revealAt) / 1000 > this.sweepFor + 0.5) {
      this.revealAt = null;
    }
  }

  /* Light it from the left, cell by cell, `delay` seconds from now. */
  sweep(seconds = 1.1, delay = 0) {
    this.sweepFor = seconds;
    this.revealAt = performance.now() + delay * 1000;
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
