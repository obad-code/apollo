/* Embers over the idle sky: a few dozen tiny warm sparks that drift up, sway and twinkle.
 * Drawn every frame the screen gives (a 280 Hz OLED gets 280 of them a second), moved by the real
 * time between frames so the speed is the same at any rate, and added light over true black - on an
 * OLED each one is a few pixels lit in the dark. Runs only while the idle screen is up. */

const COLORS = [[255, 196, 120], [255, 150, 70], [255, 230, 180], [255, 120, 60]];

export class Embers {
  constructor(canvas, count = 70) {
    this.cv = canvas;
    this.ctx = canvas.getContext('2d');
    this.count = count;
    this.raf = 0;
    this.parts = [];
    this.still = matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  _fit() {
    const d = Math.min(2, devicePixelRatio || 1);
    const w = Math.round(innerWidth * d), h = Math.round(innerHeight * d);
    if (this.cv.width !== w || this.cv.height !== h) { this.cv.width = w; this.cv.height = h; }
    this.d = d;
  }

  _spawn(anywhere) {
    const W = this.cv.width, H = this.cv.height;
    return { x: Math.random() * W, y: anywhere ? Math.random() * H : H + 10 * this.d,
             r: (0.6 + Math.random() * 1.6) * this.d, vy: (8 + Math.random() * 26) * this.d,
             sway: 6 + Math.random() * 18, phase: Math.random() * 6.28, tw: 1.5 + Math.random() * 3,
             c: COLORS[(Math.random() * COLORS.length) | 0], life: Math.random() };
  }

  start() {
    if (this.raf || this.still) return;
    this._fit();
    this.parts = Array.from({ length: this.count }, () => this._spawn(true));
    let last = performance.now();
    const frame = (now) => {
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      this._fit();
      const { ctx } = this, W = this.cv.width, H = this.cv.height, t = now / 1000;
      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = 'lighter';
      for (const p of this.parts) {
        p.y -= p.vy * dt;
        const x = p.x + Math.sin(t * 0.6 + p.phase) * p.sway * this.d;
        if (p.y < -10 * this.d) Object.assign(p, this._spawn(false));
        const fade = Math.min(1, p.y / (H * 0.25)) * Math.min(1, (H - p.y) / (H * 0.15) + 0.2);
        const a = Math.max(0, fade) * (0.45 + 0.55 * Math.abs(Math.sin(t * p.tw + p.phase)));
        const g = ctx.createRadialGradient(x, p.y, 0, x, p.y, p.r * 5);
        g.addColorStop(0, `rgba(${p.c[0]},${p.c[1]},${p.c[2]},${a})`);
        g.addColorStop(0.25, `rgba(${p.c[0]},${p.c[1]},${p.c[2]},${a * 0.35})`);
        g.addColorStop(1, `rgba(${p.c[0]},${p.c[1]},${p.c[2]},0)`);
        ctx.fillStyle = g;
        ctx.fillRect(x - p.r * 5, p.y - p.r * 5, p.r * 10, p.r * 10);
      }
      ctx.globalCompositeOperation = 'source-over';
      this.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
  }

  stop() {
    cancelAnimationFrame(this.raf);
    this.raf = 0;
    this.ctx.clearRect(0, 0, this.cv.width, this.cv.height);
  }
}
