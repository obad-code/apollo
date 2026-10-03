/* The option wheel: a list that turns like a dial - the chosen item large
 * and bright on the left, the rest curving away above and below it,
 * smaller, fainter and blurred. Scroll it, drag it, click an item or use the
 * arrows; Enter opens the one in front.
 *
 * Ported from a React component (option-wheel) to this page's own JS: a
 * position eased toward its target every frame (`smoothing` ms), and each
 * item placed on an arc from its distance to that position. `placeItem` is
 * pure and tested under node. */

/* Where an item `d` rows from the chosen one sits on the arc. */
export function placeItem(d, { rowH, tilt = 6, curve = 1, blur = 2, fade = 0.25, minOpacity = 0.05, mirror = 1 }) {
  const tiltRad = (tilt * Math.PI) / 180;
  const R = tiltRad > 0.0005 ? rowH / tiltRad : 0;
  const dist = Math.abs(d);
  let x = 0, y = d * rowH, rot = 0;
  if (R > 0) {
    const ang = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, d * tiltRad));
    y = R * Math.sin(ang);
    x = -mirror * R * (1 - Math.cos(ang)) * curve;
    rot = (mirror * ang * 180) / Math.PI;
  }
  return { x, y, rot, opacity: Math.max(minOpacity, 1 - dist * fade),
           blur: blur > 0 ? dist * blur : 0, lit: Math.max(0, 1 - Math.min(dist, 1)) };
}

export class OptionWheel {
  constructor(root, { items = [], selected = 0, onChange = () => {}, onOpen = () => {},
                      fontSize = 1.6, spacing = 1.5, tilt = 7, blur = 1.6, fade = 0.24, inset = 22,
                      smoothing = 190, sound = () => {}, mirror = 1 } = {}) {
    this.root = root;
    this.opts = { fontSize, spacing, tilt, blur, fade, inset, smoothing, mirror };
    if (mirror < 0) root.classList.add('owheel-right');
    this.onChange = onChange;
    this.onOpen = onOpen;
    this.sound = sound;
    this.pos = selected;
    this.target = selected;
    this.selected = selected;
    this.raf = null;
    root.classList.add('owheel');
    root.tabIndex = 0;
    root.setAttribute('role', 'listbox');
    root.style.setProperty('--ow-size', `${fontSize}rem`);
    root.style.setProperty('--ow-inset', `${inset}px`);
    this.setItems(items, selected);
    this.wire();
  }

  get rowH() {
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    return Math.max(this.opts.fontSize * this.opts.spacing * rem, 1);
  }

  /* New items (the projects came in again); the choice kept where it can be. */
  setItems(items, selected = this.selected) {
    this.items = items;
    this.root.innerHTML = items.map((item, i) => `<div class="ow-item" role="option" data-i="${i}">${item}</div>`).join('');
    this.els = [...this.root.querySelectorAll('.ow-item')];
    const pick = Math.max(0, Math.min(items.length - 1, selected));
    this.pos = this.target = this.selected = pick;
    this.mark();
    this.frame(performance.now(), true);
  }

  wire() {
    const r = this.root;
    let wheelTimer = null;
    r.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaMode === 1 ? e.deltaY * 24 : e.deltaY;
      this.aim(this.target + Math.max(-1, Math.min(1, delta / this.rowH)), false);
      clearTimeout(wheelTimer);
      wheelTimer = setTimeout(() => this.aim(this.target, true), 140);
    }, { passive: false });
    let drag = null;
    r.addEventListener('pointerdown', (e) => { drag = { y: e.clientY, start: this.target, id: e.pointerId, moved: false }; });
    r.addEventListener('pointermove', (e) => {
      if (!drag) return;
      const dy = e.clientY - drag.y;
      if (!drag.moved && Math.abs(dy) > 4) {
        drag.moved = true;
        try { r.setPointerCapture(drag.id); } catch { /* gone */ }
      }
      if (drag.moved) this.aim(drag.start - dy / this.rowH, false);
    });
    const end = (e) => {
      if (!drag) return;
      const moved = drag.moved;
      drag = null;
      if (moved) { this.aim(this.target, true); return; }
      const item = e.target.closest('.ow-item');
      if (!item) return;
      const i = Number(item.dataset.i);
      if (i === this.selected) this.onOpen(i);
      else this.aim(i, true);
    };
    r.addEventListener('pointerup', end);
    r.addEventListener('pointercancel', () => { drag = null; });
    r.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') { e.preventDefault(); this.aim(Math.round(this.target) - 1, true); }
      else if (e.key === 'ArrowDown' || e.key === 'ArrowRight') { e.preventDefault(); this.aim(Math.round(this.target) + 1, true); }
      else if (e.key === 'Enter') { e.preventDefault(); this.onOpen(this.selected); }
    });
  }

  aim(value, snap) {
    let v = Math.min(Math.max(value, 0), Math.max(this.items.length - 1, 0));
    if (snap) v = Math.round(v);
    this.target = v;
    const i = Math.round(v);
    if (i !== this.selected) {
      this.selected = i;
      this.mark();
      this.sound('tick');
      this.onChange(i);
    }
    if (this.raf === null) {
      this.last = performance.now();
      this.raf = requestAnimationFrame((t) => this.frame(t));
    }
  }

  mark() {
    this.els.forEach((el, i) => {
      el.classList.toggle('on', i === this.selected);
      el.setAttribute('aria-selected', i === this.selected ? 'true' : 'false');
    });
  }

  frame(now, once = false) {
    const dt = Math.min((now - (this.last || now)) / 1000, 0.05);
    this.last = now;
    const tau = Math.max(this.opts.smoothing, 1) / 1000;
    const k = once ? 1 : 1 - Math.exp(-dt / tau);
    let next = this.pos + (this.target - this.pos) * k;
    const settled = Math.abs(this.target - next) < 0.001;
    if (settled) next = this.target;
    this.pos = next;
    const rowH = this.rowH;
    this.els.forEach((el, i) => {
      const p = placeItem(i - next, { rowH, tilt: this.opts.tilt, blur: this.opts.blur, fade: this.opts.fade, mirror: this.opts.mirror });
      el.style.transform = `translate(${p.x.toFixed(2)}px, calc(${p.y.toFixed(2)}px - 50%)) rotate(${p.rot.toFixed(3)}deg)`;
      el.style.opacity = String(p.opacity);
      el.style.filter = p.blur ? `blur(${p.blur.toFixed(2)}px)` : 'none';
      el.style.setProperty('--ow-p', p.lit.toFixed(3));
    });
    if (once) return;
    this.raf = settled ? null : requestAnimationFrame((t) => this.frame(t));
  }
}
