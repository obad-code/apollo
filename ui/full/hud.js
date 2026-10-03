/* The normal display as a HUD you arrange: every panel moved, resized,
 * scaled or hidden, and kept that way (hud.py keeps it, the same rules).
 *
 * A panel is kept as fractions of the stage - x, y, w, h - so the layout
 * fits any screen, with `s` the scale of what is inside it and `hidden`. Until
 * you first arrange anything the display is laid out by its own grid; the
 * first time you do, every panel is taken from where it is and from then
 * on the HUD is `free`.
 *
 * What moves where is worked out here, as plain numbers, so it can be
 * tested under node (tests/test_hud.py): snapping to the grid and to the
 * other panels' edges and centres, the guides that shows, resizing by a
 * corner, and the box a scaled panel needs. app.js does the hands and the
 * motion. */

export const PANELS = ['today', 'markets', 'system', 'core', 'lyla', 'feed', 'scan', 'crew',
  'console-left', 'console-right'];

// The element each one is on the page.
export const ELEMENT = {
  today: 'clock-block', markets: 'markets', system: 'status-block', core: 'core',
  lyla: 'lyla-block', feed: 'headlines', scan: 'scan-block', crew: 'crew-mini',
  'console-left': 'console-left', 'console-right': 'console-right',
};

export const NAMES = {
  today: 'Today', markets: 'Stocks', system: 'System', core: 'Apollo', lyla: 'LYLA',
  feed: 'Feed', scan: 'Scanner', 'console-left': 'SYS console', 'console-right': 'Protocol console',
};

// Panels whose insides do not reflow - Apollo's ring, the consoles - grow
// and shrink as a whole: a corner scales them, keeping their shape.
export const WHOLE = new Set(['core', 'console-left', 'console-right']);

export const MIN_W = 0.08;         // of the stage: narrower than this is not a panel
export const MIN_H = 0.04;
export const SCALE_MIN = 0.6;
export const SCALE_MAX = 1.6;
export const SCALE_STEP = 0.05;
export const GRID = 8;             // px every edge falls on
export const PULL = 10;            // px within which an edge is pulled to a guide

const finite = (value) => typeof value === 'number' && Number.isFinite(value);
const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
// Four places, rounded the way hud.py rounds - halves up - so both keep the same.
const fixed = (value) => Math.floor(value * 10000 + 0.5) / 10000;

export function emptyHud() {
  return { free: false, items: {} };
}

/* One panel's place made safe, or null if it is not one. */
function cleanItem(item) {
  if (!isObject(item) || ![item.x, item.y, item.w, item.h].every(finite)) return null;
  const w = fixed(clamp(item.w, MIN_W, 1));
  const h = fixed(clamp(item.h, MIN_H, 1));
  return {
    x: fixed(clamp(item.x, 0, 1 - w)),
    y: fixed(clamp(item.y, 0, 1 - h)),
    w, h,
    s: finite(item.s) ? fixed(clamp(item.s, SCALE_MIN, SCALE_MAX)) : 1,
    hidden: item.hidden === true,
  };
}

/* A kept HUD made safe to lay out, exactly as hud.sanitize does it. */
export function sanitize(raw) {
  const out = emptyHud();
  if (!isObject(raw)) return out;
  const given = isObject(raw.items) ? raw.items : {};
  for (const id of PANELS) {
    const item = cleanItem(given[id]);
    if (item) out.items[id] = item;
  }
  // Free only when every panel has its place: half a layout is no layout.
  out.free = raw.free === true && PANELS.every((id) => id in out.items);
  return out;
}

/* Fractions of the stage to pixels, and back. */
export function toPixels(item, stage) {
  return { x: item.x * stage.w, y: item.y * stage.h, w: item.w * stage.w, h: item.h * stage.h };
}

export function toItem(rect, stage, s = 1, hidden = false) {
  return cleanItem({ x: rect.x / stage.w, y: rect.y / stage.h, w: rect.w / stage.w, h: rect.h / stage.h,
                     s, hidden });
}

/* The box a panel is laid out in so that, scaled by `s` about its centre,
 * it covers `rect` exactly: its insides are laid out 1/s as large. */
export function box(rect, s = 1) {
  const width = rect.w / s;
  const height = rect.h / s;
  return { left: rect.x + (rect.w - width) / 2, top: rect.y + (rect.h - height) / 2, width, height };
}

export function clampInto(rect, stage) {
  const w = Math.min(rect.w, stage.w);
  const h = Math.min(rect.h, stage.h);
  return { x: clamp(rect.x, 0, stage.w - w), y: clamp(rect.y, 0, stage.h - h), w, h };
}

const toGrid = (value, grid) => Math.round(value / grid) * grid;

/* Where each axis of a rect could line up: its two edges and its centre,
 * and the same of every other panel and of the stage. */
const marks = (rect, axis) => (axis === 'x'
  ? [rect.x, rect.x + rect.w / 2, rect.x + rect.w]
  : [rect.y, rect.y + rect.h / 2, rect.y + rect.h]);

function nearest(moving, targets, pull) {
  let best = null;
  for (const [i, from] of moving.entries()) {
    for (const at of targets) {
      const delta = at - from;
      if (Math.abs(delta) <= pull && (!best || Math.abs(delta) < Math.abs(best.delta))) best = { delta, at, i };
    }
  }
  return best;
}

/* A panel let go of at `rect`: pulled onto another panel's edge or centre,
 * or the stage's, when one is within PULL - with the guide to draw - and
 * otherwise onto the grid. */
export function snap(rect, others, stage, { grid = GRID, pull = PULL } = {}) {
  const out = { ...rect };
  const lines = [];
  for (const axis of ['x', 'y']) {
    const size = axis === 'x' ? stage.w : stage.h;
    const targets = [0, size / 2, size, ...others.flatMap((other) => marks(other, axis))];
    const found = nearest(marks(rect, axis), targets, pull);
    if (found) {
      out[axis] = rect[axis] + found.delta;
      lines.push({ axis, at: found.at });
    } else {
      out[axis] = toGrid(rect[axis], grid);
    }
  }
  return { rect: clampInto(out, stage), lines };
}

/* A panel resized by one corner - nw, ne, sw or se - by dx, dy: the far
 * corner stays put, the moving edges snap, and it is never smaller than
 * the least a panel can be. A `whole` panel keeps its shape. */
export function resize(start, corner, dx, dy, stage, { others = [], whole = false, grid = GRID, pull = PULL } = {}) {
  const minW = MIN_W * stage.w;
  const minH = MIN_H * stage.h;
  const west = corner.includes('w');
  const north = corner.includes('n');
  let w = Math.max(minW, start.w + (west ? -dx : dx));
  let h = Math.max(minH, start.h + (north ? -dy : dy));
  const lines = [];
  if (whole) {
    const k = Math.max(w / start.w, h / start.h);
    w = Math.max(minW, start.w * k);
    h = start.h * (w / start.w);
  } else {
    // The moving edges, pulled to what is near or to the grid.
    const edgeX = west ? start.x + start.w - w : start.x + w;
    const edgeY = north ? start.y + start.h - h : start.y + h;
    const xs = [0, stage.w / 2, stage.w, ...others.flatMap((o) => marks(o, 'x'))];
    const ys = [0, stage.h / 2, stage.h, ...others.flatMap((o) => marks(o, 'y'))];
    const fx = nearest([edgeX], xs, pull);
    const fy = nearest([edgeY], ys, pull);
    const toX = fx ? fx.at : toGrid(edgeX, grid);
    const toY = fy ? fy.at : toGrid(edgeY, grid);
    if (fx) lines.push({ axis: 'x', at: fx.at });
    if (fy) lines.push({ axis: 'y', at: fy.at });
    w = Math.max(minW, west ? start.x + start.w - toX : toX - start.x);
    h = Math.max(minH, north ? start.y + start.h - toY : toY - start.y);
  }
  const x = west ? start.x + start.w - w : start.x;
  const y = north ? start.y + start.h - h : start.y;
  return { rect: clampInto({ x, y, w, h }, stage), lines, k: w / start.w };
}

/* One step of the content scale, kept within its range. */
export function scaled(s, steps) {
  return fixed(clamp((s || 1) + steps * SCALE_STEP, SCALE_MIN, SCALE_MAX));
}

/* A spring, one frame of it: where a thing is and how fast it moves,
 * pulled towards where it should be. Stiff enough to keep up with a hand,
 * damped enough to settle with one small overshoot. */
export function spring(position, velocity, target, { stiffness = 0.3, damping = 0.55 } = {}) {
  const v = (velocity + (target - position) * stiffness) * damping;
  return [position + v, v];
}
