/* The draggable widget grid, on the page: widgets you rearrange by dragging
 * them, the rest sliding out of the way on a spring. tiler.js decides where
 * everything goes; this draws it and moves it.
 *
 * - A mouse or pen drags at once. A touch drags after a long press, so the
 *   page still scrolls under a finger.
 * - Keyboard: focus a widget, hold Alt and use the arrows.
 * - The DOM order never changes - only each widget's place on the grid - and
 *   every move is a FLIP: measured, placed, then eased in from where it was
 *   with the Web Animations API. */

import * as T from './tiler.js';

const SPRING = 'cubic-bezier(.32,.72,0,1)';
const MOVE_MS = 420;
const SETTLE_MS = 40;          // the least time between two reorders mid-drag
const LONG_PRESS_MS = 350;
const PRESS_SLOP = 8;
const LIFT = 1.05;

export class WidgetGrid {
  /* `render(item, size)` fills a widget; `onChange(items)` hears a new order. */
  constructor(root, { items, render, onChange = () => {}, maxColumns = 4, cellSize = 230,
                      gap = 14, label = 'Widgets' } = {}) {
    this.root = root;
    this.items = items.slice();
    this.render = render;
    this.onChange = onChange;
    this.maxColumns = maxColumns;
    this.cellSize = cellSize;
    this.gap = gap;
    this.columns = maxColumns;
    this.unit = 0;
    this.drag = null;
    root.classList.add('wg');
    root.setAttribute('role', 'list');
    root.setAttribute('aria-label', label);
    this.hint = document.createElement('p');
    this.hint.className = 'sr-only';
    this.hint.id = `${root.id || 'wg'}-hint`;
    this.hint.textContent = 'Drag to rearrange. On touch screens, press and hold first. With a keyboard, hold Alt and press the arrow keys.';
    root.before(this.hint);
    this.els = new Map();
    for (const item of this.items) this.els.set(item.id, this.make(item));
    this.observer = new ResizeObserver(() => this.measure());
    this.observer.observe(root);
    this.measure();
  }

  make(item) {
    const el = document.createElement('div');
    el.className = 'wg-item';
    el.dataset.widgetId = item.id;
    el.setAttribute('role', 'listitem');
    el.tabIndex = 0;
    el.setAttribute('aria-label', item.label || item.id);
    el.setAttribute('aria-describedby', this.hint.id);
    el.innerHTML = '<div class="wg-face"></div>';
    el.addEventListener('pointerdown', (e) => this.press(e, item.id));
    el.addEventListener('keydown', (e) => this.key(e, item.id));
    el.addEventListener('click', (e) => {
      if (performance.now() < (this.swallowUntil || 0)) { e.preventDefault(); e.stopPropagation(); }
    }, true);
    this.root.append(el);
    return el;
  }

  /* Columns from the width, square cells, and everything placed again. */
  measure() {
    const width = this.root.getBoundingClientRect().width;
    if (width < 1) return;
    const columns = Math.max(Math.min(2, this.maxColumns),
                             Math.min(this.maxColumns, Math.round(width / this.cellSize)));
    this.columns = columns;
    this.unit = (width - this.gap * (columns - 1)) / columns;
    const s = this.root.style;
    s.gap = `${this.gap}px`;
    s.gridTemplateColumns = `repeat(${columns}, minmax(0, 1fr))`;
    s.gridAutoRows = `${this.rowHeight}px`;
    this.place(false);
  }

  /* Rows a little shorter than a column is wide: a dashboard, not a gallery. */
  get rowHeight() { return Math.round(Math.max(150, Math.min(210, this.unit * 0.48))); }

  get rowStep() { return this.rowHeight + this.gap; }

  /* Every widget to its place; `animate` slides them there. */
  place(animate = true) {
    const before = new Map();
    if (animate) for (const [id, el] of this.els) if (!this.drag || this.drag.id !== id) before.set(id, el.getBoundingClientRect());
    const places = T.layout(this.items, this.columns);
    const order = [...places].sort((a, b) => a.row - b.row || a.col - b.col);
    for (const p of places) {
      const el = this.els.get(p.id);
      el.style.gridColumn = `${p.col + 1} / span ${p.w}`;
      el.style.gridRow = `${p.row + 1} / span ${p.h}`;
      el.setAttribute('aria-posinset', String(order.indexOf(p) + 1));
      el.setAttribute('aria-setsize', String(places.length));
      const item = this.items.find((i) => i.id === p.id);
      const size = T.sizeOf(p.w, p.h);
      if (el.dataset.size !== size || !el.dataset.drawn) {
        el.dataset.size = size;
        el.dataset.drawn = '1';
        this.fill(item);
      }
    }
    if (!animate) return;
    for (const [id, was] of before) {
      const el = this.els.get(id);
      const now = el.getBoundingClientRect();
      const dx = was.left - now.left, dy = was.top - now.top;
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue;
      el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }],
                 { duration: MOVE_MS, easing: SPRING });
    }
  }

  /* A widget's content drawn again (fresh data, or a new size). */
  fill(item) {
    const el = this.els.get(item.id);
    if (!el) return;
    el.querySelector('.wg-face').innerHTML = this.render(item, el.dataset.size || item.size);
  }

  refresh() { for (const item of this.items) this.fill(item); }

  /* Where a box of the grid is on screen. */
  toSlot(box) {
    const rect = this.root.getBoundingClientRect();
    const colStep = this.unit + this.gap;
    const left = rect.left + box.col * colStep, top = rect.top + box.row * this.rowStep;
    return { left, top, right: left + box.w * colStep - this.gap, bottom: top + box.h * this.rowStep - this.gap };
  }

  commit(next) {
    this.items = next;
    this.place(true);
  }

  // -- dragging -----------------------------------------------------------------

  press(e, id) {
    if (e.button !== 0 || !e.isPrimary) return;
    if (e.target.closest('a, button, input, select, textarea')) return;
    if (e.pointerType !== 'touch') { this.start(e, id); return; }
    const el = this.els.get(id);
    el.classList.add('holding');
    const x = e.clientX, y = e.clientY;
    const cancel = () => {
      clearTimeout(timer);
      el.classList.remove('holding');
      el.removeEventListener('pointermove', moved);
      el.removeEventListener('pointerup', cancel);
      el.removeEventListener('pointercancel', cancel);
    };
    const moved = (ev) => { if (Math.hypot(ev.clientX - x, ev.clientY - y) > PRESS_SLOP) cancel(); };
    const timer = setTimeout(() => {
      cancel();
      navigator.vibrate?.(10);
      this.start(e, id);
    }, LONG_PRESS_MS);
    el.addEventListener('pointermove', moved);
    el.addEventListener('pointerup', cancel);
    el.addEventListener('pointercancel', cancel);
  }

  start(e, id) {
    const el = this.els.get(id);
    const rect = el.getBoundingClientRect();
    this.drag = { id, el, grabX: e.clientX - rect.left, grabY: e.clientY - rect.top,
                  startOrder: this.items, lastMove: 0, x: e.clientX, y: e.clientY, frame: 0 };
    el.classList.add('lifted');
    try { el.setPointerCapture?.(e.pointerId); } catch { /* a pointer that is gone */ }
    const move = (ev) => {
      this.drag.x = ev.clientX; this.drag.y = ev.clientY;
      this.follow();
      if (!this.drag.frame) this.drag.frame = requestAnimationFrame(() => this.step());
    };
    const up = () => {
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerup', up);
      el.removeEventListener('pointercancel', up);
      this.drop();
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerup', up);
    el.addEventListener('pointercancel', up);
    this.follow();
  }

  /* The lifted widget stays under the pointer, wherever its slot has moved. */
  follow() {
    const d = this.drag;
    const me = T.layout(this.items, this.columns).find((p) => p.id === d.id);
    if (!me) return;
    const slot = this.toSlot(me);
    d.el.style.transform = `translate(${d.x - d.grabX - slot.left}px, ${d.y - d.grabY - slot.top}px) scale(${LIFT})`;
  }

  step(force = false) {
    const d = this.drag;
    if (!d) return;
    d.frame = 0;
    const now = performance.now();
    if (!force && now - d.lastMove < SETTLE_MS) {
      d.frame = requestAnimationFrame(() => this.step());
      return;
    }
    const me = T.layout(this.items, this.columns).find((p) => p.id === d.id);
    if (!me) return;
    const r = d.el.getBoundingClientRect();
    const order = T.choose(this.toSlot(me), T.candidatesFor(this.items, d.id, this.columns, (b) => this.toSlot(b)),
                           r.left + r.width / 2, r.top + r.height / 2);
    if (!order) return;
    d.lastMove = now;
    this.commit(T.canonical(order, this.columns));
    this.follow();
  }

  drop() {
    const d = this.drag;
    if (!d) return;
    cancelAnimationFrame(d.frame);
    this.step(true);
    this.drag = null;
    const from = d.el.style.transform;
    d.el.style.transform = '';
    d.el.classList.remove('lifted');
    d.el.animate([{ transform: from }, { transform: 'none' }], { duration: MOVE_MS, easing: SPRING });
    d.el.classList.add('landed');
    setTimeout(() => d.el.classList.remove('landed'), 640);
    this.swallowUntil = performance.now() + 300;
    if (!T.sameOrder(d.startOrder, this.items)) this.onChange(this.items);
  }

  // -- the keyboard -----------------------------------------------------------------

  key(e, id) {
    if (!e.altKey) return;
    const delta = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1
      : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!delta) return;
    e.preventDefault();
    const from = this.items.findIndex((item) => item.id === id);
    for (let to = from + delta; to >= 0 && to < this.items.length; to += delta) {
      const next = T.canonical(T.moveTo(this.items, id, to), this.columns);
      if (T.sameOrder(next, this.items)) continue;
      this.commit(next);
      this.els.get(id).focus();
      this.onChange(this.items);
      return;
    }
  }

  /* A saved order, as ids, put back - unknown ids dropped, new ones kept. */
  restore(ids) {
    if (!Array.isArray(ids)) return;
    const byId = new Map(this.items.map((item) => [item.id, item]));
    const kept = ids.map((id) => byId.get(id)).filter(Boolean);
    const rest = this.items.filter((item) => !ids.includes(item.id));
    this.items = [...kept, ...rest];
    this.place(false);
  }
}
