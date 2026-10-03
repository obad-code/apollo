/* The cylinder wheel: Apollo's agents as glowing orbs on the outside of a
 * slowly turning drum - the one in front biggest and raised, the rest
 * shrinking and falling away to the sides, rolling off the edge and back
 * round. Drag or flick it, scroll it, or use the arrows; it turns by itself
 * until you touch it. A click picks an orb.
 *
 * Ported from a React component (cylinder-carousel, Motion) to this page's
 * own JS: one position, `scroll`, in items; every orb's place, size and
 * height are worked out from it each frame; a release hands the pointer's
 * speed to a soft spring so a flick keeps rolling and settles on an orb.
 * The geometry functions are pure and tested under node. */

export const GLIDE = { stiffness: 40, damping: 20, mass: 3 };
const FLICK_MOMENTUM = 0.45;
const MAX_FLICK_ITEMS = 6;
const THETA_EDGE = (72 * Math.PI) / 180;
const THETA_CLAMP = (95 * Math.PI) / 180;

/* One orb's offset from the front, wrapped so the wheel goes round. */
export function wrapped(index, scroll, count) {
  let o = index - scroll;
  o -= Math.round(o / count) * count;
  return o;
}

/* Where an orb at offset `o` sits: {x, y, scale}. Convex: the front orb is
 * the biggest and highest, the rest smaller and lower toward the edges. */
export function place(o, { width, visible = 5, minScale = 0.5, arc, convex = true }) {
  const half = width / 2;
  const edge = (visible + 1) / 2;
  const gap = width / (visible + 1);
  const alpha = THETA_EDGE / edge;
  const k = Math.max(0.2, (minScale - Math.cos(THETA_EDGE)) / (1 - minScale));
  const projection = (half * (Math.cos(THETA_EDGE) + k)) / Math.sin(THETA_EDGE);
  let x;
  if (convex) x = o * gap;
  else {
    const th = Math.max(-THETA_CLAMP, Math.min(THETA_CLAMP, o * alpha));
    x = (projection * Math.sin(th)) / (Math.cos(th) + k);
  }
  const t = Math.min(Math.abs(o) / edge, THETA_CLAMP / THETA_EDGE);
  const scale = convex ? 1 - (1 - minScale) * t : minScale + (1 - minScale) * t;
  const tt = x / half;
  const valley = arc * (0.5 - tt * tt);
  return { x, y: convex ? -valley : valley, scale, hidden: Math.abs(x) > half + 260 };
}

/* The orb in front, for a scroll position. */
export const front = (scroll, count) => ((Math.round(scroll) % count) + count) % count;

export class Wheel {
  /* `items` are HTML strings, one per orb; `onPick(i)` hears a click,
   * `onFront(i)` the orb that comes to the front. */
  constructor(root, { items, size = 170, visible = 5, minScale = 0.5, autoSpeed = 0.18,
                      onPick = () => {}, onFront = () => {} } = {}) {
    this.root = root;
    this.size = size;
    this.visible = visible;
    this.minScale = minScale;
    this.autoSpeed = autoSpeed;
    this.onPick = onPick;
    this.onFront = onFront;
    this.scroll = 0;
    this.velocity = 0;
    this.target = null;
    this.dragging = false;
    this.hover = false;
    this.paused = false;
    this.last = performance.now();
    this.frontIndex = 0;
    root.classList.add('wheel');
    root.tabIndex = 0;
    root.setAttribute('role', 'listbox');
    root.setAttribute('aria-roledescription', 'carousel');
    this.balls = items.map((html, i) => {
      const ball = document.createElement('button');
      ball.type = 'button';
      ball.className = 'wheel-ball';
      ball.dataset.index = String(i);
      ball.setAttribute('role', 'option');
      ball.innerHTML = html;
      ball.style.width = ball.style.height = `${size}px`;
      ball.style.marginLeft = ball.style.marginTop = `${-size / 2}px`;
      root.append(ball);
      return ball;
    });
    this.wire();
    this.tick = this.tick.bind(this);
    this.raf = requestAnimationFrame(this.tick);
  }

  get count() { return this.balls.length; }

  wire() {
    const r = this.root;
    let start = null;
    r.addEventListener('pointerdown', (e) => {
      if (e.button !== 0) return;
      start = { x: e.clientX, scroll: this.scroll, t: performance.now(), lastX: e.clientX,
                lastT: performance.now(), prevX: e.clientX, prevT: performance.now(), moved: false,
                ball: e.target.closest('.wheel-ball') };
      this.dragging = true;
      this.target = null;
      try { r.setPointerCapture?.(e.pointerId); } catch { /* a pointer that is gone */ }
    });
    r.addEventListener('pointermove', (e) => {
      if (!start) return;
      if (Math.abs(e.clientX - start.x) > 5) start.moved = true;
      const gap = this.width / (this.visible + 1);
      this.scroll = start.scroll - ((e.clientX - start.x) * 1.4) / gap;
      start.prevX = start.lastX; start.prevT = start.lastT;
      start.lastX = e.clientX; start.lastT = performance.now();
    });
    const up = () => {
      if (!start) return;
      this.dragging = false;
      if (!start.moved && start.ball) {
        const i = Number(start.ball.dataset.index);
        this.rollTo(i);
        this.onPick(i % this.count, start.ball);
      } else {
        const gap = this.width / (this.visible + 1);
        const dt = start.lastT - start.prevT;
        const vpx = dt > 0 ? (start.lastX - start.prevX) / dt : 0;
        this.release((-vpx * 1.4 * 1000) / gap);
      }
      start = null;
    };
    r.addEventListener('pointerup', up);
    r.addEventListener('pointercancel', up);
    r.addEventListener('pointerenter', () => { this.hover = true; });
    r.addEventListener('pointerleave', () => { this.hover = false; });
    r.addEventListener('wheel', (e) => {
      e.preventDefault();
      const gap = this.width / (this.visible + 1);
      this.scroll += (Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY) / gap;
      clearTimeout(this.wheelTimer);
      this.wheelTimer = setTimeout(() => this.release(0), 140);
    }, { passive: false });
    r.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') { e.preventDefault(); this.rollTo(Math.round(this.scroll) + 1); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); this.rollTo(Math.round(this.scroll) - 1); }
      else if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.onPick(this.frontIndex, this.balls[this.frontIndex]);
      }
    });
  }

  get width() { return this.root.getBoundingClientRect().width || 900; }

  /* A flick: projected on by its speed, then settled on the nearest orb. */
  release(velocity) {
    const projected = this.scroll + Math.max(-MAX_FLICK_ITEMS, Math.min(MAX_FLICK_ITEMS, velocity * FLICK_MOMENTUM));
    this.velocity = velocity;
    this.target = Math.round(projected);
  }

  /* Roll the shortest way round to orb `i`. */
  rollTo(i) {
    const now = Math.round(this.scroll);
    let d = (i - now) % this.count;
    if (d > this.count / 2) d -= this.count;
    if (d < -this.count / 2) d += this.count;
    this.target = now + d;
  }

  tick(now) {
    const dt = Math.min((now - this.last) / 1000, 0.05);
    this.last = now;
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (this.target !== null && !this.dragging) {
      if (still) { this.scroll = this.target; this.target = null; this.velocity = 0; }
      else {
        // A damped spring, integrated a frame at a time.
        const { stiffness, damping, mass } = GLIDE;
        const force = -stiffness * (this.scroll - this.target) - damping * this.velocity;
        this.velocity += (force / mass) * dt;
        this.scroll += this.velocity * dt;
        if (Math.abs(this.scroll - this.target) < 0.001 && Math.abs(this.velocity) < 0.005) {
          this.scroll = this.target; this.velocity = 0; this.target = null;
        }
      }
    } else if (!this.dragging && !this.hover && !this.paused && !still) {
      this.scroll += this.autoSpeed * dt;
    }
    this.draw();
    this.raf = requestAnimationFrame(this.tick);
  }

  draw() {
    const width = this.width;
    const arc = this.size * 0.35;
    const lead = front(this.scroll, this.count);
    this.balls.forEach((ball, i) => {
      const o = wrapped(i, this.scroll, this.count);
      const p = place(o, { width, visible: this.visible, minScale: this.minScale, arc, convex: true });
      ball.style.transform = `translate(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px) scale(${p.scale.toFixed(3)})`;
      ball.style.zIndex = String(100 - Math.round(Math.abs(o) * 10));
      ball.style.visibility = p.hidden ? 'hidden' : 'visible';
      ball.style.setProperty('--near', (1 - Math.min(1, Math.abs(o) / 2.5)).toFixed(3));
      ball.classList.toggle('front', i === lead);
      ball.setAttribute('aria-selected', i === lead ? 'true' : 'false');
    });
    if (lead !== this.frontIndex) {
      this.frontIndex = lead;
      this.onFront(lead % this.count);
    }
  }

  stop() { cancelAnimationFrame(this.raf); }
}
