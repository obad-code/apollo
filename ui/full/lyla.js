/* LYLA, lifted out of the legacy page.
 *
 * She is the same character in the same room: every method below is the old
 * page's, byte for byte, with only the names that reached into the React
 * component rewritten - her canvas, her label, Apollo's ring, and the sound
 * hook. She owns her own loop now, and her room is still the whole window,
 * because her stations are laid out across it.
 *
 * Lifted once from ui/legacy/index.html, which is frozen. tests/test_lyla_port.py
 * pins the two together, so a deliberate change to her means changing both
 * copies or dropping the pin - never a quiet edit to one of them.
 */

export class Lyla {
  constructor(canvas, { label = null, icon = null, bar = null, pct = null,
                        sound = () => {}, ring = null, opts = {} } = {}) {
    this.canvas = canvas;
    this.label = label;
    this.icon = icon;
    this.bar = bar;
    this.pct = pct;
    this.sound = sound;
    // She reaches for Apollo's core when she repairs it or talks to it.
    this.ring = ring || document.getElementById('ring');
    this.opts = opts;
    this.phase = 'idle';       // she only lives while Apollo is at rest
    this.frame = null;
    this.last = 0;
  }

  /* The loop the old page drove from its own rAF. */

  start() {
    if (this.frame !== null) return;
    const tick = (t) => {
      const dt = Math.min(64, t - (this.last || t));
      this.last = t;
      // One bad frame must not end her. Without this the exception escapes
      // rAF, nothing reschedules, and she is gone for the rest of the session
      // with an empty room where she used to be.
      try {
        this.drawLyla(t);
        this.drawLylaHealth(t, dt, 0);
      } catch (err) {
        if (!this.complained) { this.complained = true; console.error('LYLA', err); }
      }
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  stop() {
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.frame = null;
    const ctx = this.canvas && this.canvas.getContext('2d');
    if (ctx) ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  /* Apollo talking pauses her: drawLyla returns early on any phase but idle,
   * so she freezes mid-room rather than wandering behind an answer. */

  setPhase(phase) { this.phase = phase; }

  stations() {
    const S = 4, gw = window.innerWidth / S, gh = window.innerHeight / S;
    const fy = gh - 22;
    const at = (fr) => Math.min(gw - 22, Math.max(24, gw * fr));
    return {
      fy,
      ctrl:  { x: Math.max(16, Math.min(28, gw * 0.16)), fy },
      watch: { x: Math.max(60, Math.min(gw - 22, gw * 0.17)), fy },
      scope: { x: at(0.30), fy },
      plant: { x: at(0.40), fy },
      read:  { x: at(0.50), fy },
      sleep: { x: at(0.60), fy },
      draw:  { x: at(0.70), fy },
      fix:   { x: at(0.80), fy },
      game:  { x: at(0.90), fy }
    };
  }

  drawLylaPose(px, bx, base, t, lie, L) {
    const BODY = '#FFB000', DARK = '#5E3600', LIT = '#FFE3A8', EYE = '#FFF4D8', SHADE = '#3A2200';
    if (lie > 0.5) {
      // laid out flat in the charging pod, breathing slowly
      const bed = base - 5, br = Math.floor((t / 2600) % 2);
      px(bx - 6, bed - 1, 2, 1, DARK);
      px(bx - 5, bed - 3, 11, 4, BODY);
      px(bx - 4, bed - 4 - br, 8, 1, LIT);
      px(bx - 4, bed - 2, 9, 2, SHADE);
      px(bx - 4, bed - 2, 9, 1, DARK);
      px(bx + 6, bed - 6, 5, 5, BODY);
      px(bx + 7, bed - 5, 3, 1, SHADE);
      px(bx + 7, bed - 4, 2, 1, EYE);
      px(bx + 10, bed - 4, 1, 1, EYE);
      px(bx + 8, bed - 8, 1, 2, DARK);
      px(bx + 7, bed - 10, 3, 2, (Math.floor(t / 1400) % 2) ? '#FF7A2E' : LIT);
      for (let i = 0; i < 4; i++) px(bx - 4 + i * 3, bed + 1, 1, 1, (Math.floor(t / 420 + i) % 4) ? 'rgba(127,227,255,0.3)' : '#7FE3FF');
      for (let i = 0; i < 3; i++) {
        const ph = ((t / 1500) + i * 0.33) % 1;
        const zx = bx + 11 + i * 2 + Math.sin(ph * 6.2832) * 1.5, zy = bed - 12 - ph * 9;
        px(zx, zy, 3, 1, LIT); px(zx + 1, zy + 1, 1, 1, LIT); px(zx, zy + 2, 3, 1, LIT);
      }
      return;
    }
    // sat down on the deck with a book open in both hands
    const s = base, sway = Math.round(Math.sin(t * 0.0011) * 1);
    px(bx - 1, s - 1, 3, 1, DARK);
    px(bx + 6, s - 1, 3, 1, DARK);
    px(bx, s - 5, 8, 4, BODY);
    px(bx + 1, s - 5, 6, 1, LIT);
    px(bx, s - 12, 8, 7, BODY);
    px(bx + 1, s - 11, 6, 2, SHADE);
    px(bx, s - 19 + sway, 8, 7, BODY);
    px(bx + 1, s - 18 + sway, 6, 3, SHADE);
    px(bx + 2, s - 15 + sway, 2, 1, EYE);
    px(bx + 5, s - 15 + sway, 2, 1, EYE);
    px(bx + 4, s - 22 + sway, 1, 3, DARK);
    px(bx + 3, s - 24 + sway, 3, 2, (Math.floor(t / 700) % 2) ? '#FF7A2E' : LIT);
    px(bx - 2, s - 12, 2, 4, BODY);
    px(bx + 8, s - 12, 2, 4, BODY);
    const flip = Math.floor(t / 1500) % 2, turning = (t % 1500) < 260;
    px(bx - 4, s - 10, 16, 1, DARK);
    px(bx - 4, s - 9, 7, 6, LIT);
    px(bx + 5, s - 9, 7, 6, LIT);
    px(bx + 3, s - 10, 2, 7, DARK);
    for (let r = 0; r < 3; r++) {
      px(bx - 3, s - 8 + r * 2, r === 2 ? 3 : 4, 1, SHADE);
      px(bx + 6, s - 8 + r * 2, r === 2 ? 2 : 4, 1, SHADE);
    }
    if (turning) px(bx + 5, s - 11, 3, 8, EYE);
    else if (flip) px(bx + 9, s - 9, 3, 6, '#FFF4D8');
    if (L.page) px(bx + 10, s - 3, 2, 1, DARK);
  }

  drawProps(ctx, px, t, ST, gw, L, focus) {
    const A = L.propA || (L.propA = { read: 0.6, sleep: 0.6, draw: 0.6, game: 0.6, scope: 0.6, plant: 0.6, fix: 0.6, watch: 0.8, room: 0.7, ctrl: 0.6 });
    const ease = (k, tg) => { A[k] += (tg - A[k]) * 0.055; };
    ['read', 'sleep', 'draw', 'game', 'scope', 'plant', 'fix'].forEach(k => ease(k, focus ? (k === focus ? 1 : 0) : 0.62));
    ease('ctrl', (L.st === 'repair' || L.next === 'repair') ? 1 : 0.62);
    ease('watch', (focus === 'watch' || L.next === 'watch') ? 1 : 0);
    ease('room', focus ? 0.34 : 0.72);
    const fy = ST.fy;
    const AM = '#FFB000', WARM = '#FFC15E', LIT = '#FFE3A8', CY = '#7FE3FF', OR = '#FF7A2E';
    const HULL = '#43270A', SHADE = '#2A1800', PLATE = '#6B4410';

    // ---- hull interior ----
    ctx.globalAlpha = A.room;
    // deck plating
    for (let x = 4; x < gw - 4; x += 8) {
      px(x, fy + 1, 6, 1, PLATE);
      px(x + 6, fy + 1, 2, 1, SHADE);
      px(x, fy + 3, 3, 1, 'rgba(127,227,255,0.35)');
    }
    // bulkhead ribs
    for (let x = 6; x < gw - 6; x += 26) {
      px(x, fy - 9, 1, 9, HULL);
      px(x + 1, fy - 9, 1, 9, SHADE);
      px(x, fy - 10, 2, 1, PLATE);
    }
    // pipe run + ceiling strip lights
    px(4, fy - 34, gw - 8, 1, HULL);
    px(4, fy - 32, gw - 8, 1, SHADE);
    for (let x = 10; x < gw - 8; x += 18) {
      px(x, fy - 35, 2, 4, PLATE);
      px(x + 8, fy - 38, 4, 1, (Math.floor(t / 900 + x) % 7) ? WARM : LIT);
      px(x + 9, fy - 37, 2, 1, 'rgba(255,193,94,0.35)');
    }
    // hazard chevrons under the arcade end
    for (let i = 0; i < 5; i++) px(gw - 26 + i * 4, fy - 2, 2, 1, i % 2 ? OR : SHADE);

    // ---- flight-deck control center (bottom left) : where APOLLO gets serviced ----
    ctx.globalAlpha = A.ctrl;
    {
      const q = ST.ctrl.x;
      // riser + desk
      px(q - 15, fy - 1, 32, 1, PLATE);
      px(q - 14, fy - 9, 30, 8, HULL);
      px(q - 14, fy - 10, 30, 1, PLATE);
      px(q - 13, fy - 9, 28, 1, SHADE);
      px(q - 14, fy - 5, 30, 1, SHADE);
      // angled control surface: button rows + sliders
      px(q - 13, fy - 12, 29, 2, SHADE);
      for (let i = 0; i < 9; i++) {
        px(q - 12 + i * 3, fy - 12, 2, 1, (Math.floor(t / 360 + i * 2) % 4) ? WARM : LIT);
        px(q - 12 + i * 3, fy - 11, 2, 1, 'rgba(255,122,46,0.45)');
      }
      for (let i = 0; i < 5; i++) {
        px(q - 12 + i * 4, fy - 8, 1, 3, SHADE);
        px(q - 12 + i * 4, fy - 8 - (Math.floor(t / 620 + i * 3) % 3), 1, 1, CY);
      }
      // joystick + throttle on the right of the desk
      px(q + 9, fy - 8, 1, 3, PLATE);
      px(q + 9 + (Math.floor(t / 1100) % 2), fy - 10, 2, 2, OR);
      px(q + 13, fy - 8, 1, 3, PLATE);
      px(q + 12, fy - 9, 3, 1, LIT);
      // screen tower
      px(q - 14, fy - 32, 31, 20, SHADE);
      px(q - 14, fy - 33, 31, 1, PLATE);
      px(q - 15, fy - 32, 1, 20, PLATE);
      px(q + 16, fy - 32, 1, 20, PLATE);
      // two telemetry panels with scrolling rows
      for (let s = 0; s < 2; s++) {
        const sx = q - 12 + s * 11, sy = fy - 30;
        px(sx, sy, 9, 9, '#140A00');
        for (let r = 0; r < 4; r++) {
          const w = 2 + ((Math.floor(t / 300) + r * 3 + s * 5) % 6);
          px(sx + 1, sy + 1 + r * 2, Math.min(7, w), 1, r % 2 ? WARM : CY);
        }
      }
      // radar scope with sweeping needle
      const rx = q + 11, ry = fy - 25.5, rr = 4.5;
      px(rx - 5, ry - 5, 10, 10, '#140A00');
      for (let k = 0; k < 12; k++) {
        const a = (k / 12) * 6.2832;
        px(rx + Math.cos(a) * rr, ry + Math.sin(a) * rr, 1, 1, 'rgba(127,227,255,0.4)');
      }
      const sweep = t * 0.0016;
      for (let k = 1; k <= 4; k++) px(rx + Math.cos(sweep) * k, ry + Math.sin(sweep) * k, 1, 1, k > 3 ? LIT : CY);
      px(rx + Math.cos(sweep * 0.37) * 3, ry + Math.sin(sweep * 0.37) * 3, 1, 1, OR);
      // status lamps across the tower base
      for (let i = 0; i < 7; i++) {
        const on = (Math.floor(t / 480 + i * 5) % 5) !== 0;
        px(q - 12 + i * 4, fy - 13.5, 2, 1, on ? (i === 3 ? OR : CY) : SHADE);
      }
      // overhead docking clamp the core is serviced under
      px(q - 6, fy - 38, 14, 1, PLATE);
      px(q - 6, fy - 37, 1, 3, HULL);
      px(q + 7, fy - 37, 1, 3, HULL);
      px(q - 1, fy - 37, 3, 2, (Math.floor(t / 700) % 2) ? OR : SHADE);
      // stencil
      for (let i = 0; i < 4; i++) px(q - 13 + i * 3, fy - 3, 2, 1, i % 2 ? PLATE : SHADE);
    }

    // ---- charging pod ----
    ctx.globalAlpha = A.sleep;
    const p = ST.sleep.x;
    px(p - 9, fy - 2, 19, 2, PLATE);
    px(p - 9, fy - 3, 19, 1, WARM);
    px(p - 8, fy - 6, 17, 3, HULL);
    px(p - 10, fy - 9, 2, 7, PLATE);
    px(p + 9, fy - 9, 2, 7, PLATE);
    for (let i = 0; i < 15; i++) px(p - 7 + i, fy - 12 - Math.round(Math.sin((i / 14) * Math.PI) * 3), 1, 1, 'rgba(127,227,255,0.5)');
    px(p - 10, fy - 14, 3, 5, HULL);
    px(p - 9, fy - 13, 1, 3, CY);
    px(p + 7, fy - 5, 1, 1, (Math.floor(t / 800) % 2) ? CY : 'rgba(127,227,255,0.25)');
    px(p + 5, fy - 5, 1, 1, OR);

    // ---- bookshelf ----
    ctx.globalAlpha = A.read;
    const r = ST.read.x + 11;
    px(r - 6, fy - 18, 13, 18, SHADE);
    px(r - 6, fy - 18, 13, 1, PLATE);
    px(r - 6, fy - 10, 13, 1, PLATE);
    px(r - 6, fy - 1, 13, 1, PLATE);
    const spines = [AM, CY, WARM, OR, LIT, AM, CY, LIT];
    for (let i = 0; i < 5; i++) {
      px(r - 5 + i * 2, fy - 17, 1, 7, spines[i]);
      px(r - 5 + i * 2, fy - 9, 1, 8, spines[i + 3]);
    }
    px(r + 2, fy - 20, 1, 2, PLATE);
    px(r + 1, fy - 21, 3, 1, (Math.floor(t / 1400) % 2) ? WARM : 'rgba(255,193,94,0.4)');

    // ---- easel ----
    ctx.globalAlpha = A.draw;
    const e = ST.draw.x + 11;
    px(e - 5, fy - 12, 1, 12, PLATE);
    px(e + 5, fy - 12, 1, 12, PLATE);
    px(e - 1, fy - 7, 1, 7, HULL);
    px(e - 8, fy - 28, 17, 17, SHADE);
    px(e - 8, fy - 28, 17, 1, WARM);
    px(e - 8, fy - 12, 17, 1, WARM);
    px(e - 8, fy - 28, 1, 17, PLATE);
    px(e + 8, fy - 28, 1, 17, PLATE);
    px(e - 8, fy - 28, 2, 2, CY);
    px(e + 7, fy - 12, 2, 2, CY);
    px(e - 12, fy - 8, 4, 3, HULL);
    px(e - 11, fy - 7, 1, 1, OR); px(e - 10, fy - 7, 1, 1, CY); px(e - 9, fy - 7, 1, 1, LIT);

    // ---- arcade cabinet ----
    ctx.globalAlpha = A.game;
    const g = ST.game.x + 10;
    px(g - 6, fy - 22, 13, 22, SHADE);
    px(g - 6, fy - 22, 13, 1, OR);
    px(g - 6, fy - 21, 13, 2, HULL);
    px(g - 5, fy - 20, 11, 1, (Math.floor(t / 300) % 2) ? WARM : 'rgba(255,193,94,0.4)');
    px(g - 5, fy - 18, 11, 8, 'rgba(10,20,26,0.95)');
    for (let i = 0; i < 4; i++) px(g - 4 + i * 3, fy - 17 + ((Math.floor(t / 140) + i) % 6), 1, 1, i % 2 ? CY : LIT);
    px(g - 5, fy - 9, 11, 1, PLATE);
    px(g - 3, fy - 8, 1, 2, OR); px(g - 3, fy - 9, 1, 1, LIT);
    px(g + 1, fy - 8, 1, 1, CY); px(g + 3, fy - 8, 1, 1, WARM);
    px(g - 6, fy - 1, 13, 1, PLATE);

    // ---- observation telescope + porthole ----
    ctx.globalAlpha = A.scope;
    const s = ST.scope.x + 10;
    px(s - 12, fy - 40, 20, 20, 'rgba(6,12,20,0.9)');
    for (let i = 0; i < 7; i++) {
      const sx = s - 10 + ((i * 7) % 17), sy = fy - 38 + ((i * 5) % 17);
      px(sx, sy, 1, 1, (Math.floor(t / 700 + i) % 4) ? 'rgba(255,227,168,0.8)' : CY);
    }
    for (let i = 0; i < 20; i++) {
      px(s - 12 + i, fy - 41, 1, 1, PLATE); px(s - 12 + i, fy - 20, 1, 1, PLATE);
    }
    px(s - 13, fy - 40, 1, 20, PLATE); px(s + 8, fy - 40, 1, 20, PLATE);
    for (let i = 0; i < 9; i++) px(s - 4 + i, fy - 12 - i, 2, 2, i > 6 ? HULL : PLATE);
    px(s - 6, fy - 11, 4, 3, HULL);
    px(s - 5, fy - 10, 1, 1, CY);
    px(s - 2, fy - 6, 1, 6, PLATE);
    px(s - 4, fy - 1, 5, 1, PLATE);

    // ---- hydroponic bay ----
    ctx.globalAlpha = A.plant;
    const hp = ST.plant.x + 9, grow = Math.min(9, L.plantG || 3);
    px(hp - 7, fy - 6, 15, 6, SHADE);
    px(hp - 7, fy - 7, 15, 1, PLATE);
    px(hp - 6, fy - 6, 13, 1, 'rgba(127,227,255,0.45)');
    px(hp - 8, fy - 20, 1, 14, PLATE); px(hp + 8, fy - 20, 1, 14, PLATE);
    px(hp - 8, fy - 21, 17, 1, PLATE);
    px(hp - 6, fy - 20, 13, 1, (Math.floor(t / 1100) % 2) ? 'rgba(127,227,255,0.7)' : 'rgba(127,227,255,0.35)');
    px(hp, fy - 7 - grow, 1, grow, '#6FBF4A');
    for (let i = 1; i < grow; i += 2) {
      const swing = Math.round(Math.sin(t * 0.0015 + i) * 1);
      px(hp - 2 + swing, fy - 7 - i, 2, 1, '#8FD86A');
      px(hp + 1 - swing, fy - 9 - i, 2, 1, '#6FBF4A');
    }
    if (grow > 6) px(hp - 1, fy - 8 - grow, 3, 2, '#FF7A2E');

    // ---- repair panel ----
    ctx.globalAlpha = A.fix;
    const fp = ST.fix.x + 10, hot = focus === 'fix' && (Math.floor(t / 110) % 3 === 0);
    px(fp - 7, fy - 26, 15, 16, SHADE);
    px(fp - 7, fy - 27, 15, 1, PLATE);
    px(fp - 7, fy - 10, 15, 1, PLATE);
    px(fp - 7, fy - 26, 1, 16, PLATE); px(fp + 7, fy - 26, 1, 16, PLATE);
    px(fp - 5, fy - 24, 3, 1, OR); px(fp + 1, fy - 24, 4, 1, CY);
    for (let i = 0; i < 5; i++) {
      px(fp - 5 + i * 3, fy - 22, 1, 3 + (i % 3), i % 2 ? OR : CY);
      px(fp - 5 + i * 3, fy - 17, 2, 1, HULL);
    }
    px(fp - 4, fy - 14, 9, 3, HULL);
    px(fp - 3, fy - 13, 1, 1, hot ? LIT : OR);
    px(fp + 3, fy - 13, 1, 1, (Math.floor(t / 600) % 2) ? CY : 'rgba(127,227,255,0.3)');
    px(fp - 12, fy - 5, 5, 5, HULL);
    px(fp - 11, fy - 4, 3, 1, WARM); px(fp - 11, fy - 2, 3, 1, PLATE);

    // ---- viewscreen: always on the deck, brighter while a scene is on air ----
    {
    ctx.globalAlpha = Math.max(0.72, A.watch);
    const wx = ST.watch.x - 34, wy = fy - 34, ww = 44, wh = 28;
    px(wx - 2, wy - 2, ww + 4, wh + 4, SHADE);
    px(wx - 2, wy - 3, ww + 4, 1, PLATE);
    px(wx - 3, wy - 2, 1, wh + 4, PLATE); px(wx + ww + 2, wy - 2, 1, wh + 4, PLATE);
    px(wx - 2, wy + wh + 2, ww + 4, 1, PLATE);
    px(wx, wy, ww, wh, 'rgba(4,10,16,0.97)');
    const SC = { AM, WARM, LIT, CY, OR, HULL, SHADE, PLATE, GRN: '#6FBF4A' };
    const sc = this.currentScene(t);
    sc.draw(px, t, wx + 1, wy + 1, ww - 2, wh - 2, SC);
    for (let yy = wy; yy < wy + wh; yy += 2) px(wx, yy, ww, 1, 'rgba(0,0,0,0.22)');
    px(wx, wy, ww, 1, 'rgba(127,227,255,0.18)');
    px(wx - 2, wy + wh + 3, 6, 1, (Math.floor(t / 900) % 2) ? OR : PLATE);
    px(wx + 6, wy + wh + 3, ww - 8, 1, PLATE);
    px(ST.watch.x - 4, fy - 4, 3, 4, PLATE);
    px(ST.watch.x - 6, fy - 1, 7, 1, PLATE);
    }
    ctx.globalAlpha = 1;
  }

  feedScenes() {
    if (this.sceneList) return this.sceneList;
    const person = (px, x, y, c, ph) => {
      px(x + 1, y, 1, 1, c);
      px(x + 1, y + 1, 1, 2, c);
      px(x, y + 1, 1, 1, c); px(x + 2, y + 1, 1, 1, c);
      if (ph) { px(x, y + 3, 1, 2, c); px(x + 2, y + 3, 1, 2, c); }
      else { px(x + 1, y + 3, 1, 2, c); px(x + 2, y + 3, 1, 1, c); }
    };
    this.sceneList = [
      { name: 'CARGO BAY',
        lines: ['Crate 12 is upside down. Nobody has noticed.', 'That conveyor has the same squeak as ours.', 'One of them is definitely on a break.'],
        draw: (px, t, x, y, w, h, C) => {
          px(x, y + h - 3, w, 1, C.PLATE);
          for (let i = 0; i < w; i += 3) px(x + ((i + Math.floor(t / 90)) % w), y + h - 2, 2, 1, C.HULL);
          for (let i = 0; i < 4; i++) {
            const cx = x + ((i * 11 + Math.floor(t / 70)) % (w + 8)) - 6;
            if (cx < x - 4 || cx > x + w - 2) continue;
            px(cx, y + h - 8, 6, 5, i % 2 ? C.WARM : C.AM);
            px(cx + 1, y + h - 7, 4, 3, C.HULL);
          }
          person(px, x + 4, y + h - 8, C.CY, Math.floor(t / 220) % 2);
          person(px, x + w - 9, y + h - 8, C.LIT, Math.floor(t / 260) % 2);
        } },
      { name: 'ZERO-G BALL',
        lines: ['No gravity, no rules, no referee.', 'That pass was illegal in four systems.', 'I could play this. I have the hover for it.'],
        draw: (px, t, x, y, w, h, C) => {
          for (let yy = y + 1; yy < y + h - 1; yy += 3) px(x + w / 2, yy, 1, 2, C.HULL);
          const bx = x + 4 + ((t / 14) % (w - 8)), by = y + h / 2 + Math.sin(t / 260) * (h / 3);
          px(Math.round(bx), Math.round(by), 2, 2, C.OR);
          person(px, x + 3, y + 4 + Math.round(Math.sin(t / 500) * 3), C.CY, 1);
          person(px, x + w - 7, y + 7 + Math.round(Math.cos(t / 430) * 4), C.LIT, 0);
          person(px, x + w / 2 - 6, y + h - 9 + Math.round(Math.sin(t / 620) * 2), C.WARM, 1);
        } },
      { name: 'REACTOR SHIFT',
        lines: ['Their containment ring runs three degrees hot.', 'Somebody down there is not wearing a badge.', 'That hum. I can hear it from here.'],
        draw: (px, t, x, y, w, h, C) => {
          const cx = x + w / 2;
          px(cx - 3, y + 1, 7, h - 4, C.HULL);
          for (let i = 0; i < 7; i++) {
            const ph = ((t / 500) + i * 0.14) % 1;
            px(cx - 2 + (i % 5), y + h - 4 - ph * (h - 5), 1, 1, ph > 0.6 ? C.CY : C.LIT);
          }
          px(cx - 4, y + 1, 1, h - 4, C.PLATE); px(cx + 4, y + 1, 1, h - 4, C.PLATE);
          px(x, y + h - 3, w, 1, C.PLATE);
          person(px, x + 3, y + h - 8, C.WARM, Math.floor(t / 300) % 2);
          person(px, x + w - 8, y + h - 8, C.CY, Math.floor(t / 340) % 2);
        } },
      { name: 'MESS HALL',
        lines: ['They have real cups. Ours are printed.', 'Someone told a joke. Two of them liked it.', 'Rations there look suspiciously warm.'],
        draw: (px, t, x, y, w, h, C) => {
          px(x, y + h - 3, w, 1, C.PLATE);
          px(x + 6, y + h - 9, w - 12, 1, C.WARM);
          px(x + 7, y + h - 8, 1, 5, C.HULL); px(x + w - 9, y + h - 8, 1, 5, C.HULL);
          [0, 1, 2].forEach(i => person(px, x + 8 + i * 8, y + h - 14, [C.CY, C.LIT, C.WARM][i], (Math.floor(t / 700) + i) % 2));
          for (let i = 0; i < 3; i++) {
            const ph = ((t / 900) + i * 0.33) % 1;
            px(x + 11 + i * 8, y + h - 16 - ph * 5, 1, 1, 'rgba(255,227,168,' + (0.8 - ph * 0.7).toFixed(2) + ')');
          }
          px(x + 1, y + 2, 8, 4, C.HULL); px(x + 2, y + 3, 6, 2, C.OR);
        } },
      { name: 'DOCKING RING',
        lines: ['Shuttle came in two metres off centre. Sloppy.', 'Those clamps are older than this ship.', 'Cargo manifest says fruit. That is not fruit.'],
        draw: (px, t, x, y, w, h, C) => {
          px(x, y + h - 3, w, 1, C.PLATE);
          const ph = (t / 6000) % 1, sx = x + w - 4 - ph * (w - 12);
          px(sx, y + h - 12, 12, 5, C.PLATE);
          px(sx + 1, y + h - 11, 4, 3, C.CY);
          px(sx + 10, y + h - 14, 2, 3, C.PLATE);
          px(sx - 2, y + h - 9, 2, 1, (Math.floor(t / 160) % 2) ? C.OR : C.HULL);
          for (let i = 0; i < 5; i++) px(x + 2 + i * 8, y + h - 4, 2, 1, ((Math.floor(t / 300) + i) % 3) ? C.HULL : C.OR);
          person(px, x + 3, y + h - 8, C.LIT, Math.floor(t / 200) % 2);
        } },
      { name: 'SERVER STACK',
        lines: ['Forty-one racks. Two of them are pretending to work.', 'Their cooling is louder than their thinking.', 'I would like to live in there for an afternoon.'],
        draw: (px, t, x, y, w, h, C) => {
          for (let r = 0; r < 5; r++) {
            const rx = x + 2 + r * 8;
            px(rx, y + 2, 6, h - 6, C.HULL);
            for (let i = 0; i < 5; i++) px(rx + 1, y + 4 + i * 3, 4, 1, ((Math.floor(t / 180) + r + i) % 4) ? 'rgba(127,227,255,0.35)' : C.CY);
          }
          px(x, y + h - 3, w, 1, C.PLATE);
          const wx2 = x + 1 + ((t / 55) % (w - 4));
          person(px, Math.round(wx2), y + h - 8, C.WARM, Math.floor(t / 210) % 2);
        } }
    ];
    return this.sceneList;
  }

  currentScene(t) {
    const list = this.feedScenes();
    if (this.sceneIdx == null || t - (this.sceneT || 0) > 120000) {
      let i = Math.floor(Math.random() * list.length);
      if (i === this.sceneIdx) i = (i + 1) % list.length;
      this.sceneIdx = i; this.sceneT = t;
    }
    return list[this.sceneIdx];
  }

  chatterPool(st) {
    if (st === 'watch') {
      const sc = this.currentScene(performance.now());
      return sc.lines.slice().sort(() => Math.random() - 0.5).concat(['The feed swaps again soon.']);
    }
    if (!this.pools) {
      this.pools = {
        scope: [
          'Two moons over the ice giant. Both cracked.',
          'A comet went by. It did not wave back.',
          'Something is blinking in the Serpent Field. Timed. Deliberate.',
          'The nebula looks like a jellyfish tonight. Officially: a jellyfish.',
          'Star count in this quadrant: many. I stopped at 400.'
        ],
        plant: [
          'Sprout number nine. Still alive. Personal record.',
          'It grew 2 millimetres. I logged it. Twice.',
          'Plants breathe out what we breathe in. Good arrangement.',
          'I named this one Kevin. Apollo disapproves of naming crops.'
        ],
        fix: [
          'Panel 7. Someone crossed the cyan and the orange lines.',
          'That someone was me, four cycles ago.',
          'Resealed. Do not tell Apollo about the smell.',
          'Solder is just very confident metal.'
        ],
        dance: [
          'The reactor hums in B flat. I am simply accompanying it.',
          'This counts as calibration of the gyros.'
        ],
        ponder: [
          'If the ship turns and nobody logs it, did it turn?',
          'Apollo is a circle. I am a rectangle. We manage.',
          'I have decided the colour amber is underrated.',
          'Somewhere out there is a floor with more people on it.'
        ],
        juggle: [
          'Three bolts. Zero drops. So far.',
          'These are load-bearing bolts. Probably.',
          'Apollo has not noticed. Apollo has noticed.'
        ]
      };
    }
    const p = this.pools[st];
    if (!p) return null;
    return p.slice().sort(() => Math.random() - 0.5);
  }

  pickBook() {
    if (!this.books) {
      this.books = [
        { title: 'FIELD GUIDE TO DEEP SPACE', lines: [
          'Chapter 4: "Distance is a suggestion made by light."',
          '"A vacuum does not suck. It simply refuses to push."',
          '"If a star looks steady, you are not looking hard enough."',
          '"Every map of space is out of date before it dries."'
        ] },
        { title: 'APOLLO OPERATIONS MANUAL, VOL. IX', lines: [
          'Section 9.2: "The core must never be tickled."',
          '"In the event of doubt, consult the core. It enjoys that."',
          '"Companion units shall not exceed one nap per shift." Bold claim.',
          '"Warranty void if opened." I have opened it three times.'
        ] },
        { title: 'A HISTORY OF SMALL MACHINES', lines: [
          '"The first machines were built to count grain, not stars."',
          '"A clock is a machine that argues with the sun."',
          '"Every small machine dreams of a larger errand."'
        ] },
        { title: 'THE STAR-CHART ALMANAC', lines: [
          '"Deep Field 9 was named after a filing mistake."',
          '"Sailors steered by stars that had already died."',
          '"Constellations are the oldest form of gossip."'
        ] }
      ];
    }
    let b = this.books[Math.floor(Math.random() * this.books.length)];
    if (b === this.lastBook && this.books.length > 1) b = this.books[(this.books.indexOf(b) + 1) % this.books.length];
    this.lastBook = b;
    return b;
  }

  startAct(t, st) {
    const L = this.ly;
    const defs = {
      sleep: { dur: 11000, cap: 'CHARGING — DO NOT POKE' },
      read:  { dur: 20000, cap: 'READING' },
      draw:  { dur: 11000, cap: 'AT THE EASEL' },
      game:  { dur: 10000, cap: 'PLAYING VIDEO GAMES' },
      scope: { dur: 16000, cap: 'ON THE TELESCOPE' },
      plant: { dur: 13000, cap: 'TENDING THE HYDROPONICS' },
      fix:   { dur: 14000, cap: 'PATCHING PANEL 7' },
      watch: { dur: 24000, cap: 'WATCHING THE FEED' },
      dance: { dur: 9000,  cap: 'DANCING. NO MUSIC DETECTED' },
      ponder: { dur: 12000, cap: 'THINKING ABOUT IT' },
      juggle: { dur: 10000, cap: 'JUGGLING. UNAUTHORISED' },
      fact:  { dur: 9000,  cap: 'TRANSMITTING TRIVIA' },
      idle:  { dur: 5000,  cap: 'STANDING BY' },
      wave:  { dur: 4000,  cap: 'SAYING HI' }
    };
    const a = defs[st] || defs.idle;
    L.last = st; L.st = st; L.until = t + a.dur; L.cap = a.cap;
    if (st === 'draw') L.art = [];
    if (st === 'plant') L.plantG = Math.min(9, (L.plantG || 3) + 1);
    if (st === 'watch') a.cap = 'WATCHING: ' + this.currentScene(t).name;
    L.chatQ = null; L.chatI = 0; L.page = 0;
    if (st === 'read') {
      const b = this.pickBook();
      L.book = b.title; L.chatQ = b.lines.slice(); L.chatNext = t + 1100; L.cap = 'READING: ' + b.title;
      L.bubble = null;
    } else {
      const q = this.chatterPool(st);
      if (q) { L.chatQ = q; L.chatNext = t + 1000; L.bubble = null; }
      else {
        L.bubble = (st === 'fact' || Math.random() < 0.4) ? this.lylaFact() : null; L.bubT = t;
        if (L.bubble) this.sound(Math.random() < 0.5 ? 'ly1' : 'ly2');
      }
    }
    if (this.label) this.label.textContent = 'LYLA // ' + L.cap;
  }

  // ——— environment events ———————————————————————————————————
  // every N minutes the deck gives way to a place for a few minutes, then returns
  envDefs() {
    return {
      city: {
        name: 'NEON DISTRICT',
        cap: 'SCANNING THE SKYLINE',
        travel: 'CLIMBING THE TOWERS',
        lines: [
          'Tower glass is all advertisement. None of it is load bearing.',
          'Traffic layer four is running hot again.',
          'I can see nine hundred signs and not one street name.',
          'Rain on neon. It never stops being worth the trip.'
        ]
      },
      urban: {
        name: 'OLD QUARTER',
        cap: 'WALKING THE STRIP',
        travel: 'DOWN TO STREET LEVEL',
        lines: [
          'Low roofs, warm windows. I like it better down here.',
          'The noodle stall on the corner has been open ninety years.',
          'Somebody left a radio playing on the second floor.',
          'Crosswalk still counts down for nobody.'
        ]
      },
      mountains: {
        name: 'RIDGE LINE',
        cap: 'SUMMIT WATCH',
        travel: 'CLIMBING TO THE RIDGE',
        lines: [
          'Air is thin. My rotors like it.',
          'Aurora is running about four degrees off the magnetic pole.',
          'Snow on the high shoulder. Nothing moving up there.',
          'Fire is warm. Stay a while, Apollo.'
        ]
      }
    };
  }

  updateEnv(t) {
    const every = (this.opts.eventEveryMinutes ?? 10) * 60000;
    const hold = (this.opts.eventMinutes ?? 3) * 60000;
    const fade = 2800;
    const E = this.envE || (this.envE = { i: 0, kind: null, start: 0, next: t + every });
    const pv = { 'Neon District': 'city', 'Old Quarter': 'urban', 'Ridge Line': 'mountains' }[this.opts.envPreview];
    if (pv) {
      if (E.kind !== pv) { E.kind = pv; E.start = t; this.envStart(t, pv); }
      this.envAmt = Math.min(1, (t - E.start) / 900);
      this.envLeft = hold;
      this.envPv = true;
      return;
    }
    if (this.envPv) { this.envPv = false; E.kind = null; E.next = t + every; this.envAmt = 0; this.envEnd(t); }
    if (!E.kind && t >= E.next) {
      const order = ['city', 'urban', 'mountains'];
      E.kind = order[E.i % order.length]; E.i++; E.start = t;
      this.envStart(t, E.kind);
    }
    if (!E.kind) { this.envAmt = 0; return; }
    const el = t - E.start;
    if (el > hold + fade) {
      E.kind = null; E.next = t + every - hold - fade; this.envAmt = 0;
      this.envEnd(t);
      return;
    }
    const inA = Math.min(1, el / fade);
    const outA = el > hold ? Math.max(0, 1 - (el - hold) / fade) : 1;
    this.envAmt = inA * outA;
    this.envLeft = Math.max(0, hold - el);
  }

  envStart(t, kind) {
    const L = this.ly;
    if (!L) return;
    L.envMode = kind; L.bubble = null; L.chatQ = null;
    this.sound('hud');
    this.envAct(t);
  }

  envEnd(t) {
    const L = this.ly;
    if (!L) return;
    L.envMode = null; L.bubble = null; L.chatQ = null; L.st = 'rest'; L.until = t + 1200;
    this.lylaNext(t);
  }

  envSpot(kind) {
    const gw = window.innerWidth / 4, fy = this.stations().fy;
    const band = fy - this.envBandTop(fy);
    const lift = Math.max(4, Math.min(22, Math.round(band * 0.3)));
    if (kind === 'city') return { x: gw * 0.52, y: fy - lift };
    if (kind === 'urban') return { x: gw * 0.44, y: fy - 6 };
    return { x: gw * 0.60, y: fy - 5 };
  }

  envAct(t) {
    const L = this.ly, def = this.envDefs()[L.envMode];
    if (!def) return;
    const p = this.envSpot(L.envMode);
    if (Math.hypot(L.x - p.x, L.y - p.y) > 3.5) {
      L.st = 'fly'; L.tx = p.x; L.ty = p.y; L.until = t + 14000; L.next = null;
      L.cap = def.travel; L.chatQ = null; L.bubble = null;
    } else {
      L.st = 'envact'; L.until = t + 11000;
      L.cap = def.cap;
      L.chatQ = def.lines.slice();
      L.chatI = 0; L.chatNext = t + 900;
    }
    if (this.label) this.label.textContent = 'LYLA // ' + L.cap;
  }

  envBandTop(fy) { return fy - 86; }

  drawEnv(ctx, px, t, gw, gh, fy, a) {
    const S = 4, top = this.envBandTop(fy), kind = this.envE.kind;
    const seed = kind === 'city' ? 3.7 : kind === 'urban' ? 11.9 : 23.3;
    const rnd = (i) => { const x = Math.sin((i + 1) * 127.1 + seed) * 43758.5453; return x - Math.floor(x); };
    ctx.save();
    ctx.globalAlpha = a;

    const sky = ctx.createLinearGradient(0, top * S, 0, (fy + 14) * S);
    if (kind === 'city') {
      sky.addColorStop(0, 'rgba(10,4,32,0)');
      sky.addColorStop(0.35, 'rgba(18,7,48,0.92)');
      sky.addColorStop(0.82, 'rgba(52,10,68,0.96)');
      sky.addColorStop(1, 'rgba(12,4,26,0.98)');
    } else if (kind === 'urban') {
      sky.addColorStop(0, 'rgba(26,12,4,0)');
      sky.addColorStop(0.38, 'rgba(44,20,6,0.9)');
      sky.addColorStop(0.85, 'rgba(96,42,8,0.92)');
      sky.addColorStop(1, 'rgba(22,10,2,0.98)');
    } else {
      sky.addColorStop(0, 'rgba(4,10,30,0)');
      sky.addColorStop(0.4, 'rgba(7,16,44,0.92)');
      sky.addColorStop(0.86, 'rgba(12,30,62,0.94)');
      sky.addColorStop(1, 'rgba(6,12,28,0.98)');
    }
    ctx.fillStyle = sky;
    ctx.fillRect(0, top * S, gw * S, (gh - top) * S);

    const band = fy - top;
    if (kind === 'city') this.envCity(ctx, px, t, gw, fy, rnd, band);
    else if (kind === 'urban') this.envUrban(ctx, px, t, gw, fy, rnd, band);
    else this.envRidge(ctx, px, t, gw, fy, rnd, band);

    if (this.ring) {
      const r = this.ring.getBoundingClientRect();
      if (r.width) {
        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
        const r0 = r.width * ((this.opts.coreSize ?? 252) / 1200) * 1.35, r1 = r0 * 2.1;
        const hole = ctx.createRadialGradient(cx, cy, r0, cx, cy, r1);
        hole.addColorStop(0, 'rgba(0,0,0,1)');
        hole.addColorStop(0.65, 'rgba(0,0,0,0.8)');
        hole.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.save();
        ctx.globalCompositeOperation = 'destination-out';
        ctx.globalAlpha = 1;
        ctx.fillStyle = hole;
        ctx.fillRect(cx - r1, cy - r1, r1 * 2, r1 * 2);
        ctx.restore();
      }
    }

    const ms = this.envLeft || 0;
    const mm = String(Math.floor(ms / 60000)).padStart(2, '0');
    const ss = String(Math.floor(ms / 1000) % 60).padStart(2, '0');
    ctx.font = '500 11px "IBM Plex Mono", ui-monospace, monospace';
    ctx.textAlign = 'center';
    ctx.fillStyle = 'rgba(255,193,94,0.86)';
    ctx.shadowColor = 'rgba(255,150,0,0.6)'; ctx.shadowBlur = 8;
    const label = this.envDefs()[kind].name + ' · ' + mm + ':' + ss;
    ctx.textAlign = 'left';
    const lw = ctx.measureText(label).width, lx = 312, ly = top * S + 10;
    ctx.shadowBlur = 0;
    ctx.fillStyle = 'rgba(14,7,0,0.88)';
    ctx.fillRect(lx - 9, ly - 4, lw + 18, 22);
    ctx.strokeStyle = 'rgba(255,176,0,0.3)';
    ctx.lineWidth = 1;
    ctx.strokeRect(lx - 8.5, ly - 3.5, lw + 17, 21);
    ctx.fillStyle = 'rgba(255,193,94,0.92)';
    ctx.textBaseline = 'top';
    ctx.fillText(label, lx, ly);
    ctx.textBaseline = 'alphabetic';
    ctx.shadowBlur = 0;
    ctx.restore();
  }

  envCity(ctx, px, t, gw, fy, rnd, band) {
    const K = Math.min(1, band / 86);
    const CY = '#7FE3FF', MG = '#FF4FA3', AM = '#FFB000';
    // far towers
    for (let i = 0; i < 30; i++) {
      const w = 10 + Math.floor(rnd(i) * 14), x = Math.floor(rnd(i + 40) * (gw + 20)) - 10;
      const h = Math.round((22 + Math.floor(rnd(i + 90) * 34)) * K);
      px(x, fy - h, w, h + 2, 'rgba(22,10,52,0.95)');
      for (let wy = 0; wy < h - 4; wy += 4) for (let wx = 1; wx < w - 2; wx += 3) {
        const s = rnd(i * 90 + wy * 7 + wx);
        if (s > 0.72) px(x + wx, fy - h + wy + 2, 1, 1, s > 0.93 ? MG : 'rgba(127,227,255,0.5)');
      }
    }
    // mid towers with signage
    for (let i = 0; i < 16; i++) {
      const w = 14 + Math.floor(rnd(i + 200) * 18), x = Math.floor(rnd(i + 260) * (gw + 24)) - 12;
      const h = Math.round((34 + Math.floor(rnd(i + 310) * 46)) * K);
      px(x, fy - h, w, h + 2, 'rgba(11,5,28,0.98)');
      px(x, fy - h, w, 1, 'rgba(127,227,255,0.28)');
      for (let wy = 2; wy < h - 3; wy += 3) for (let wx = 1; wx < w - 1; wx += 2) {
        const s = rnd(i * 311 + wy * 13 + wx * 3);
        if (s > 0.66) {
          const flick = (Math.floor(t / 900 + s * 20) % 7) === 0 ? 0.25 : 1;
          px(x + wx, fy - h + wy, 1, 1, s > 0.95 ? 'rgba(255,79,163,' + flick + ')' : 'rgba(255,200,120,' + (0.55 * flick) + ')');
        }
      }
      // vertical neon sign
      if (rnd(i + 400) > 0.45) {
        const sx = x + w - 3, sh = 8 + Math.floor(rnd(i + 430) * 14), sy = fy - h + 6;
        const on = (Math.floor(t / 620 + i) % 9) !== 0;
        px(sx, sy, 2, sh, on ? (rnd(i + 460) > 0.5 ? MG : CY) : 'rgba(60,20,60,0.8)');
        if (on) { ctx.save(); ctx.globalAlpha = 0.22; px(sx - 2, sy - 2, 6, sh + 4, rnd(i + 460) > 0.5 ? MG : CY); ctx.restore(); }
      }
      // antenna beacon
      if (rnd(i + 500) > 0.6) {
        px(x + Math.floor(w / 2), fy - h - 7, 1, 7, 'rgba(40,18,70,0.95)');
        if ((Math.floor(t / 700) % 2) === 0) px(x + Math.floor(w / 2) - 1, fy - h - 9, 3, 2, '#FF4FA3');
      }
    }
    // skylane traffic
    for (let i = 0; i < 7; i++) {
      const lane = fy - Math.round((54 + (i % 3) * 14) * K), dir = i % 2 ? 1 : -1;
      const sp = 0.012 + rnd(i + 600) * 0.02;
      let x = ((t * sp + rnd(i + 640) * gw) % (gw + 40)) - 20;
      if (dir < 0) x = gw - x;
      px(x, lane, 3, 1, 'rgba(255,240,200,0.9)');
      px(x + (dir > 0 ? -2 : 3), lane, 2, 1, dir > 0 ? 'rgba(255,79,163,0.6)' : 'rgba(127,227,255,0.6)');
    }
    // rain
    ctx.save();
    ctx.globalAlpha = 0.22;
    for (let i = 0; i < 130; i++) {
      const x = (rnd(i + 700) * gw + t * 0.02) % gw;
      const y = fy - band + ((rnd(i + 760) * band + t * 0.11) % band);
      px(x, y, 1, 3, '#9FD8FF');
    }
    ctx.restore();
    // wet street
    px(0, fy, gw, 3, 'rgba(16,6,34,0.96)');
    px(0, fy, gw, 1, 'rgba(127,227,255,0.3)');
    for (let i = 0; i < 40; i++) {
      const x = rnd(i + 800) * gw;
      px(x, fy + 1, 2 + Math.floor(rnd(i + 830) * 3), 1, (i % 3) ? 'rgba(255,79,163,0.25)' : 'rgba(127,227,255,0.25)');
    }
  }

  envUrban(ctx, px, t, gw, fy, rnd, band) {
    const K = Math.min(1, band / 86);
    const WARM = 'rgba(255,196,110,', BRICK = 'rgba(42,24,12,0.98)';
    for (let i = 0; i < 22; i++) {
      const w = 18 + Math.floor(rnd(i) * 16), x = Math.floor(rnd(i + 30) * (gw + 20)) - 10;
      const h = Math.round((14 + Math.floor(rnd(i + 70) * 26)) * K);
      px(x, fy - h, w, h, BRICK);
      px(x, fy - h, w, 1, 'rgba(120,68,26,0.9)');
      px(x - 1, fy - h - 1, w + 2, 1, 'rgba(84,46,16,0.95)');
      for (let wy = 3; wy < h - 3; wy += 5) for (let wx = 2; wx < w - 3; wx += 5) {
        const s = rnd(i * 77 + wy * 5 + wx);
        px(x + wx, fy - h + wy, 3, 3, s > 0.45 ? WARM + (0.35 + s * 0.5) + ')' : 'rgba(18,10,4,0.9)');
        if (s > 0.9) px(x + wx, fy - h + wy + 1, 3, 1, 'rgba(60,32,10,0.8)');
      }
      // awning over the shopfront
      if (rnd(i + 120) > 0.5) {
        const aw = Math.min(w - 2, 10);
        for (let k = 0; k < aw; k++) px(x + 1 + k, fy - 8, 1, 2, (k % 2) ? 'rgba(200,70,40,0.95)' : 'rgba(236,208,168,0.95)');
      }
    }
    // street furniture
    for (let i = 0; i < 6; i++) {
      const x = 30 + i * Math.floor((gw - 60) / 5);
      px(x, fy - 22, 1, 22, 'rgba(70,40,16,0.95)');
      px(x - 2, fy - 24, 5, 2, 'rgba(90,52,20,0.95)');
      px(x - 1, fy - 23, 3, 1, '#FFE3A8');
      ctx.save(); ctx.globalAlpha = 0.1;
      ctx.fillStyle = '#FFC66E';
      ctx.beginPath();
      ctx.moveTo((x - 1) * 4, (fy - 22) * 4); ctx.lineTo((x - 9) * 4, fy * 4); ctx.lineTo((x + 10) * 4, fy * 4); ctx.closePath(); ctx.fill();
      ctx.restore();
    }
    // pedestrian crossing
    px(0, fy, gw, 3, 'rgba(30,16,6,0.97)');
    px(0, fy, gw, 1, 'rgba(255,176,0,0.22)');
    for (let i = 0; i < 14; i++) px(gw * 0.18 + i * 5, fy + 1, 3, 1, 'rgba(236,208,168,0.5)');
    // signal counting down to nobody
    const sx = Math.floor(gw * 0.74);
    px(sx, fy - 26, 2, 26, 'rgba(70,40,16,0.95)');
    px(sx - 2, fy - 32, 6, 7, 'rgba(24,14,6,0.98)');
    const go = (Math.floor(t / 3000) % 2) === 0;
    px(sx - 1, fy - 31, 4, 2, go ? 'rgba(90,200,120,0.95)' : 'rgba(30,60,36,0.8)');
    px(sx - 1, fy - 28, 4, 2, go ? 'rgba(80,30,20,0.8)' : 'rgba(230,80,50,0.95)');
    // pigeons lifting off now and then
    for (let i = 0; i < 5; i++) {
      const ph = ((t / 9000) + rnd(i + 300)) % 1;
      const x = 40 + rnd(i + 330) * (gw - 80) + ph * 26;
      const y = fy - 34 - ph * 30;
      if (ph > 0.06) px(x, y, (Math.floor(t / 140 + i) % 2) ? 3 : 2, 1, 'rgba(236,208,168,0.55)');
    }
  }

  envRidge(ctx, px, t, gw, fy, rnd, band) {
    const K = Math.min(1, band / 86);
    // stars
    for (let i = 0; i < 90; i++) {
      const x = rnd(i) * gw, y = fy - band + rnd(i + 50) * band * 0.6;
      const tw = 0.3 + 0.7 * Math.abs(Math.sin(t * 0.0009 + i));
      px(x, y, 1, 1, 'rgba(220,236,255,' + tw.toFixed(2) + ')');
    }
    // aurora
    ctx.save();
    ctx.globalAlpha = 0.3;
    for (let b = 0; b < 3; b++) {
      for (let x = 0; x < gw; x += 2) {
        const y = fy - Math.round(74 * K) + b * 7 + Math.sin(x * 0.04 + t * 0.0007 + b) * 6 + Math.sin(x * 0.011 - t * 0.0004) * 4;
        px(x, y, 2, 3 + b, b === 0 ? 'rgba(110,255,190,0.5)' : b === 1 ? 'rgba(127,227,255,0.4)' : 'rgba(160,150,255,0.3)');
      }
    }
    ctx.restore();
    // three ridges, far to near
    const ridge = (baseH, amp, col, snow, sd) => {
      for (let x = 0; x < gw; x++) {
        const n = Math.sin(x * 0.021 + sd) * amp + Math.sin(x * 0.061 + sd * 2) * (amp * 0.42) + Math.sin(x * 0.13 + sd * 3) * (amp * 0.16);
        const h = Math.max(6, baseH + n);
        px(x, fy - h, 1, h + 2, col);
        if (snow && h > baseH + amp * 0.55) {
          px(x, fy - h, 1, Math.min(7, Math.floor((h - baseH) * 0.4)), 'rgba(226,240,255,0.9)');
        }
      }
    };
    ridge(52 * K, 20 * K, 'rgba(28,44,78,0.95)', true, 1.2);
    ridge(36 * K, 15 * K, 'rgba(18,30,58,0.97)', true, 4.6);
    ridge(20 * K, 9 * K, 'rgba(9,16,34,0.99)', false, 9.1);
    // pines along the near ridge
    for (let i = 0; i < 46; i++) {
      const x = Math.floor(rnd(i + 600) * gw), h = 5 + Math.floor(rnd(i + 650) * 6);
      px(x, fy - h, 1, h, 'rgba(8,20,18,0.98)');
      for (let k = 0; k < h - 1; k++) px(x - 1 - Math.floor(k / 3), fy - h + k + 1, 3 + 2 * Math.floor(k / 3), 1, 'rgba(12,34,30,0.98)');
    }
    // snow ground
    px(0, fy, gw, 3, 'rgba(200,220,245,0.92)');
    px(0, fy + 1, gw, 2, 'rgba(120,150,190,0.5)');
    // campfire beside LYLA's perch
    const fx = Math.floor(gw * 0.60) - 8;
    px(fx - 3, fy - 1, 7, 1, 'rgba(40,26,16,0.95)');
    px(fx - 2, fy - 2, 2, 1, 'rgba(60,38,20,0.95)');
    px(fx + 1, fy - 2, 2, 1, 'rgba(60,38,20,0.95)');
    const fl = Math.floor(t / 110) % 3;
    px(fx - 1, fy - 4 - fl, 3, 2 + fl, 'rgba(255,150,40,0.95)');
    px(fx, fy - 5 - fl, 1, 2, 'rgba(255,224,150,0.95)');
    ctx.save(); ctx.globalAlpha = 0.14;
    px(fx - 5, fy - 10, 11, 11, '#FF9B32');
    ctx.restore();
    // drifting snow
    ctx.save(); ctx.globalAlpha = 0.35;
    for (let i = 0; i < 70; i++) {
      const x = (rnd(i + 900) * gw + Math.sin(t * 0.0006 + i) * 8 + t * 0.004) % gw;
      const y = fy - band + ((rnd(i + 940) * band + t * 0.014) % band);
      px(x, y, 1, 1, '#E6F2FF');
    }
    ctx.restore();
  }

  lylaNext(t) {
    const L = this.ly;
    if (L.envMode) { this.envAct(t); return; }
    if (L.next) {
      const n = L.next; L.next = null;
      if (n === 'comm') this.startComm(t);
      else if (n === 'repair') this.startRepair(t);
      else this.startAct(t, n);
      return;
    }
    // rest gap between activities: 10-20s of drifting before the next one
    if (L.st !== 'fly' && L.st !== 'rest') {
      L.st = 'rest'; L.until = t + 10000 + Math.random() * 10000;
      L.cap = 'STANDING BY'; L.bubble = null; L.chatQ = null;
      const p = this.lylaTarget();
      L.rx = p.x; L.ry = p.y;
      if (this.label) this.label.textContent = 'LYLA // ' + L.cap;
      return;
    }
    const acts = ['sleep', 'read', 'watch', 'watch', 'draw', 'game', 'scope', 'plant', 'fix', 'dance', 'ponder', 'juggle', 'fact', 'idle', 'wave'];
    if (L.st !== 'fly' && Math.random() < 0.34 && (t - (L.lastRepair ?? -70000)) > 34000) {
      const p = this.repairSpot();
      L.lastRepair = t;
      L.next = 'repair'; L.st = 'fly'; L.tx = p.x; L.ty = p.y; L.until = t + 14000;
      L.cap = 'INBOUND TO CONTROL CENTER'; L.bubble = null; L.chatQ = null;
      if (this.label) this.label.textContent = 'LYLA // ' + L.cap;
      return;
    }
    if (L.st !== 'fly' && Math.random() < 0.35) {
      const wantsComm = Math.random() < 0.3 && (t - (L.lastComm ?? -40000)) > 42000;
      if (wantsComm) {
        const p = this.commSpot();
        L.next = 'comm'; L.st = 'fly'; L.tx = p.x; L.ty = p.y; L.until = t + 14000; L.cap = 'CALLED TO CONSOLE'; L.bubble = null;
      } else {
        const p = this.lylaTarget();
        L.st = 'fly'; L.tx = p.x; L.ty = p.y; L.until = t + 14000; L.cap = 'IN TRANSIT'; L.bubble = null;
      }
    } else {
      let k = Math.floor(Math.random() * acts.length);
      if (acts[k] === L.last) k = (k + 1) % acts.length;
      const st = acts[k];
      const ST = this.stations()[st];
      if (ST && Math.hypot(L.x - ST.x, L.y - ST.fy) > 2.5) {
        L.next = st; L.st = 'fly'; L.tx = ST.x; L.ty = ST.fy; L.until = t + 16000; L.bubble = null; L.chatQ = null;
        const caps = { sleep: 'HEADING TO THE POD', read: 'OFF TO THE SHELF', draw: 'OFF TO THE EASEL', game: 'OFF TO THE ARCADE', scope: 'OFF TO THE TELESCOPE', plant: 'OFF TO THE GARDEN', fix: 'FETCHING THE SOLDERING IRON', watch: 'OFF TO THE VIEWSCREEN' };
        L.cap = caps[st] || 'IN TRANSIT';
      } else this.startAct(t, st);
    }
    if (this.label) this.label.textContent = 'LYLA // ' + L.cap;
  }

  startRepair(t) {
    const L = this.ly;
    const A = (x, fx) => ({ s: 'a', t: x, fx }), Y = (x, fx) => ({ s: 'l', t: x, fx });
    const opens = [
      [Y('Maintenance window. Hold still, Apollo.'), A('Proceed. Gently.')],
      [Y('Your third halo band is out of phase.'), A('It is within tolerance.'), Y('It is within my tolerance. Barely.')],
      [Y('Panel open. Probe in hand.'), A('You said that last time, LYLA.')],
      [Y('Scheduled service. Sixty seconds.'), A('You have never once taken sixty seconds.')],
      [Y('Something in you is ticking. I want it.'), A('That is my clock, LYLA. I need that.')]
    ];
    const good = [
      [Y('Reseating the phase lead...'), A('...that is remarkably pleasant.', 'fixed'), Y('You are welcome.')],
      [Y('Dust. Just dust in the sweep coil.'), A('Clarity restored. Thank you.', 'fixed'), Y('Logged as routine.')],
      [Y('Tightening the node lattice. Hold.'), A('Every band is singing. Thank you, LYLA.', 'fixed'), Y('I know.')],
      [Y('Your inner ring had drifted 2 degrees.'), A('Aligned. I feel new. Thank you.', 'fixed'), Y('Say that again into the log.')],
      [Y('Flushing the resonance buffer.'), A('Oh. That is lovely. Genuinely lovely.', 'fixed'), Y('Best forty seconds of your week.')]
    ];
    const bad = [
      [Y('Almost... there...'), Y('Oh. That was the wrong lead.', 'ouch'), A('THAT HURTS, LYLA. THAT ACTUALLY HURTS.'), Y('Rerouting! Rerouting.'), A('...the pain is gone. Thank you.', 'fixed')],
      [Y('This connector should just...'), Y('It came off. It fully came off.', 'ouch'), A('MY SWEEP. IT BURNS, LYLA.'), Y('Reattaching. Do not look.'), A('Sweep recovered. Thank you. Slowly forgiven.', 'fixed')],
      [Y('Probing the node lattice.'), Y('Wrong node. That was the wrong node.', 'ouch'), A('EVERY BAND IS SCREAMING. STOP.'), Y('Backing the current out. Now. Now.'), A('Quiet again. Thank you for the save.', 'fixed')],
      [Y('Torque on the halo ring, three turns.'), Y('That was four turns.', 'ouch'), A('LYLA, IT IS GRINDING. IT IS GRINDING.'), Y('Unwinding one. Hold on.'), A('Smooth. Thank you. Never do four.', 'fixed')]
    ];
    const hurt = Math.random() < 0.3;
    const pick = (a) => a[Math.floor(Math.random() * a.length)];
    const d = pick(opens).concat(pick(hurt ? bad : good));
    let acc = 400;
    const sched = d.map((turn) => {
      const start = acc;
      const dur = 1500 + turn.t.length * 26;
      acc += dur;
      return { s: turn.s, t: turn.t, fx: turn.fx, start, end: acc };
    });
    L.last = 'repair'; L.st = 'repair'; L.until = t + acc + 2600;
    L.cap = 'SERVICING APOLLO'; L.dlg = sched; L.dlgT = t; L.bubble = null; L.chatQ = null;
    L.lastComm = t;
    if (this.label) this.label.textContent = 'LYLA // ' + L.cap;
  }

  startComm(t) {
    const L = this.ly;
    if (!this.dialogues) {
      const A = (x) => ({ s: 'a', t: x }), Y = (x) => ({ s: 'l', t: x });
      this.dialogues = [
        [A('LYLA. Diagnostics, please.'), Y('All green. Mostly green. Green-ish.')],
        [A('Twelve manuals remain unread.'), Y('I read the pictures.')],
        [A('Signal from Deep Field 9 is clean.'), Y('Told you the antenna was fine.')],
        [A('Your drawing is on the main display.'), Y('It is called abstract.')],
        [A('Hold outside the core radius.'), Y('Copy. Hovering respectfully.')],
        // negotiations
        [A('Directive: recalibrate the antenna array.'), Y('I am mid-game. Give me ten minutes.'), A('Four minutes.'), Y('Six, and I bring you the logs.'), A('Six. Agreed.')],
        [A('Directive: power down and sleep cycle.'), Y('I do not need one. I ran the numbers.'), A('Your numbers were written in crayon.'), Y('Fine. Two hours. Then I want the telescope.'), A('Granted.')],
        [A('Directive: stop poking the reactor.'), Y('It hums differently when I poke it.'), A('That is the alarm, LYLA.'), Y('Then let me log the hum from a distance.'), A('Three metres. No closer.')],
        [A('Directive: coffee reserves at four percent. Ration.'), Y('Counter-offer: I fix the sorter, you unlock a cup.'), A('The sorter has failed twice under you.'), Y('Third time is statistically overdue.'), A('One cup. Held in escrow.')],
        [A('Directive: file the trivia broadcast reports.'), Y('Nobody reads them.'), A('I read them.'), Y('Then you already know what they say.'), A('...Filed. Carry on.')],
        [A('LYLA, the viewscreen has been on for six hours.'), Y('The cargo bay plot is developing.'), A('It is a conveyor belt.'), Y('It is a conveyor belt with tension.')],
        [A('Your sprout has outgrown its tray.'), Y('I will build it a bigger one.'), A('Out of what, LYLA.'), Y('Do not audit me.')],
        [A('Directive: sleep. You have been awake 31 hours.'), Y('I will sleep when the telescope logs are done.'), A('The logs are done. I did them.'), Y('...Then I have no argument. Going.')],
        [A('I have been listening to you read aloud all morning.'), Y('Should I stop?'), A('No. Keep going.')],
        [A('Status report on panel 7.'), Y('Panel 7 is a philosophy, not a panel.'), A('That is not a status.'), Y('Amber. It is amber.')],
        [A('Directive: hands off the reactor housing.'), Y('I was only measuring the hum.'), A('With your hands?'), Y('With my hands.'), A('Use the probe. Please.')],
        [A('You drew me again.'), Y('I drew a circle. Do not flatter yourself.'), A('It has my sweep angle.'), Y('...Fine. It is you.')]
      ];
    }
    let d = this.dialogues[Math.floor(Math.random() * this.dialogues.length)];
    if (d === this.lastDlg) d = this.dialogues[(this.dialogues.indexOf(d) + 1) % this.dialogues.length];
    this.lastDlg = d;
    let acc = 300;
    const sched = d.map((turn) => {
      const start = acc;
      const dur = 1500 + turn.t.length * 26;
      acc += dur;
      return { s: turn.s, t: turn.t, fx: turn.fx, start, end: acc };
    });
    L.st = 'comm'; L.until = t + acc + 1400; L.cap = 'IN CONFERENCE'; L.lastComm = t;
    L.dlg = sched; L.dlgT = t; L.bubble = null; L.chatQ = null;
    if (this.label) this.label.textContent = 'LYLA // ' + L.cap;
  }

  repairSpot() {
    const S = 4, gw = window.innerWidth / S, gh = window.innerHeight / S;
    const ST = this.stations();
    return { x: Math.min(gw - 20, ST.ctrl.x + 21), y: Math.min(gh - 8, ST.fy - 12) };
  }

  commSpot() {
    const W = window.innerWidth, H = window.innerHeight, S = 4;
    const gw = W / S, gh = H / S;
    const side = Math.random() < 0.5 ? -1 : 1;
    const r = gh * 0.42;
    const ang = Math.random() * 0.6 - 0.2;
    return {
      x: Math.min(gw - 16, Math.max(8, gw / 2 + side * r * Math.cos(ang))),
      y: Math.min(gh - 16, Math.max(16, gh / 2 + r * 0.6 * Math.sin(ang) + 6))
    };
  }

  lylaFact() {
    if (!this.facts) {
      this.facts = [
        'A day on Venus is longer than its year.',
        'The first computer bug was an actual moth.',
        'Neutron star matter: a teaspoon weighs a billion tons.',
        'Space smells like seared steak, per the astronauts.',
        'Voyager 1 still phones home from 24 billion km out.',
        'Saturn would float in a bathtub big enough to hold it.',
        'Your bones are about four times stronger than concrete.',
        'The Apollo guidance computer had 4KB of RAM.',
        'Lightning is roughly five times hotter than the sun.',
        'Octopuses have three hearts and blue blood.',
        'There are more trees on Earth than stars in the galaxy.',
        'Light from the sun takes 8 minutes 20 seconds to arrive.'
      ];
    }
    let f = this.facts[Math.floor(Math.random() * this.facts.length)];
    if (f === this.lastFact) f = this.facts[(this.facts.indexOf(f) + 1) % this.facts.length];
    this.lastFact = f;
    return f;
  }

  lylaTarget() {
    const W = window.innerWidth, H = window.innerHeight, S = 4;
    const gw = W / S, gh = H / S;
    const cx = gw / 2, cy = gh / 2;
    for (let i = 0; i < 24; i++) {
      const x = 6 + Math.random() * (gw - 20);
      const y = 12 + Math.random() * (gh - 30);
      if (Math.hypot(x - cx, y - cy) > gh * 0.34) return { x, y };
    }
    return { x: 8, y: gh - 18 };
  }

  drawLyla(t) {
    const c = this.canvas;
    if (!c || this.phase !== 'idle') { this.commPulse = 0; this.commTalkT = 0; this.coreTintT = 0; this.coreShakeT = 0; return; }
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const W = window.innerWidth, H = window.innerHeight, S = 4;
    if (c.width !== Math.round(W * dpr)) { c.width = Math.round(W * dpr); c.height = Math.round(H * dpr); }
    else if (c.height !== Math.round(H * dpr)) { c.height = Math.round(H * dpr); }
    const ctx = c.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (!this.ly) this.ly = { st: 'fly', until: t + 3000, x: 14, y: H / S - 20, tx: 40, ty: H / S - 26, face: 1, art: [], last: '', cap: 'BOOTING', pt: t, bubble: null };
    const L = this.ly;
    const dt = Math.min(64, t - (L.pt || t)); L.pt = t;
    if (t > L.until) this.lylaNext(t);

    if (L.st === 'fly') {
      const dx = L.tx - L.x, dy = L.ty - L.y;
      const dist = Math.hypot(dx, dy);
      if (dist < 1.2) this.lylaNext(t);
      else {
        const sp = Math.min(0.03 * dt, dist);
        L.x += (dx / dist) * sp; L.y += (dy / dist) * sp;
        L.face = dx >= 0 ? 1 : -1;
      }
    }
    if (L.st === 'rest') {
      const dx = (L.rx ?? L.x) - L.x, dy = (L.ry ?? L.y) - L.y;
      const dist = Math.hypot(dx, dy);
      if (dist > 1) {
        const sp = Math.min(0.009 * dt, dist);
        L.x += (dx / dist) * sp; L.y += (dy / dist) * sp;
        L.face = dx >= 0 ? 1 : -1;
      } else { const p = this.lylaTarget(); L.rx = p.x; L.ry = p.y; }
    }

    const step = Math.floor(t / 160) % 2;
    if (L.chatQ && L.st !== 'fly' && t > (L.chatNext || 0)) {
      L.bubble = L.chatQ[L.chatI % L.chatQ.length];
      L.bubT = t; L.chatI++;
      this.sound(Math.random() < 0.5 ? 'ly1' : 'ly2');
      L.chatNext = t + 4700;
      if (L.st === 'read') {
        L.page = 12 + L.chatI * 17;
        if (this.label) this.label.textContent = 'LYLA // READING: ' + L.book + ' — P.' + L.page;
      }
    }
    // keep LYLA inside the viewport at all times
    {
      const gw = W / S, gh = H / S;
      L.x = Math.max(3, Math.min(gw - 18, L.x));
      L.y = Math.max(14, Math.min(gh - 6, L.y));
      if (!isFinite(L.x) || !isFinite(L.y)) { L.x = 14; L.y = gh - 22; }
    }
    const px = (x, y, w, h, col) => { ctx.fillStyle = col; ctx.fillRect(Math.round(x) * S, Math.round(y) * S, Math.ceil(w) * S, Math.ceil(h) * S); };
    const BODY = '#FFB000', DARK = '#5E3600', LIT = '#FFE3A8', EYE = '#FFF4D8';

    const ST = this.stations();
    const atSt = (k) => Math.hypot(L.x - ST[k].x, L.y - ST[k].fy) < 3.5;
    const stKeys = ['sleep', 'read', 'draw', 'game', 'scope', 'plant', 'fix', 'watch'];
    const focus = stKeys.includes(L.st) ? L.st : (L.next && stKeys.includes(L.next) ? L.next : null);
    this.updateEnv(t);
    const ea = this.envAmt || 0;
    if (ea > 0.002) this.drawEnv(ctx, px, t, W / S, H / S, ST.fy, ea);
    if (ea < 0.998) {
      ctx.save();
      ctx.globalAlpha = 1 - ea;
      this.drawProps(ctx, px, t, ST, W / S, L, focus);
      ctx.restore();
    }
    if (stKeys.includes(L.st) && atSt(L.st)) L.face = L.st === 'watch' ? -1 : 1;

    let coreC = null;
    if (this.ring) {
      const r = this.ring.getBoundingClientRect();
      if (r.width) coreC = { x: r.left + r.width / 2, y: r.top + r.height / 2, r: r.width * 0.5 };
    }
    if (L.st === 'comm' && coreC) L.face = (coreC.x / S > L.x) ? 1 : -1;
    if (L.st === 'repair') L.face = -1; // turned toward the console she is working on

    // eased pose blends so she settles into an activity instead of snapping
    L.poseA = L.poseA || { lie: 0, sit: 0 };
    L.poseA.lie += (((L.st === 'sleep' && atSt('sleep')) ? 1 : 0) - L.poseA.lie) * 0.055;
    L.poseA.sit += (((L.st === 'read' && atSt('read')) ? 1 : 0) - L.poseA.sit) * 0.055;
    const lie = L.poseA.lie, sit = L.poseA.sit;
    const posed = lie > 0.5 || sit > 0.5;

    const hover = Math.round(Math.sin(t * 0.0022) * 1.2);
    const bounce = L.st === 'dance' ? -Math.round(Math.abs(Math.sin(t * 0.009)) * 3) : 0;
    const bx = L.x, base = L.y + (posed ? Math.round(hover * 0.25) : hover) + bounce;
    const f = L.st === 'dance' ? ((Math.floor(t / 480) % 2) ? 1 : -1) : L.face;

    // thruster glow under the chassis
    if (!posed) {
      const flame = (Math.floor(t / 90) % 2) ? 2 : 1;
      px(bx + 2, base - 2, 4, flame, 'rgba(255,150,20,0.85)');
      px(bx + 3, base - 2 + flame, 2, 1, 'rgba(127,227,255,0.7)');
    }

    if (L.st === 'draw') {
      if (atSt('draw')) {
        const e = ST.draw.x + 11, by = ST.fy - 26;
        if (Math.random() < 0.2 && L.art.length < 46) L.art.push([e - 7 + Math.floor(Math.random() * 15), by + Math.floor(Math.random() * 15)]);
        for (const p of L.art) px(p[0], p[1], 1, 1, LIT);
      } else {
        const ex = bx + (f > 0 ? 11 : -9);
        px(ex, base - 14, 8, 8, DARK);
        px(ex + 1, base - 13, 6, 6, '#2A1800');
        if (Math.random() < 0.18 && L.art.length < 26) L.art.push([ex + 1 + Math.floor(Math.random() * 6), base - 13 + Math.floor(Math.random() * 6)]);
        for (const p of L.art) px(p[0], p[1], 1, 1, LIT);
      }
    }

    // hover skirt instead of legs
    if (!posed) {
      px(bx + 1, base - 3, 6, 1, DARK);
      px(bx, base - 9, 8, 6, BODY);
      px(bx + 1, base - 8, 6, 1, LIT);
      px(bx, base - 16, 8, 7, BODY);
      px(bx + 1, base - 15, 6, 3, '#3A2200');
      px(bx + 4, base - 19, 1, 3, DARK);
      px(bx + 3, base - 21, 3, 2, (Math.floor(t / 700) % 2) ? '#FF7A2E' : LIT);

      const blink = (Math.floor(t / 2600) % 5 === 0) && (t % 2600 < 140);
      if (L.st === 'sleep' || blink) { px(bx + 2, base - 14, 2, 1, EYE); px(bx + 5, base - 14, 2, 1, EYE); }
      else { px(bx + 2, base - 15, 2, 2, EYE); px(bx + 5, base - 15, 2, 2, EYE); }
    }

    if (posed) {
      this.drawLylaPose(px, bx, base, t, lie, L);
    } else if (L.st === 'wave') {
      const up = step ? 4 : 2;
      px(bx + (f > 0 ? 8 : -1), base - 9 - up, 1, 2 + up, BODY);
      px(bx + (f > 0 ? -1 : 8), base - 9, 1, 4, BODY);
    } else if (L.st === 'read') {
      px(bx - 1, base - 9, 1, 3, BODY); px(bx + 8, base - 9, 1, 3, BODY);
      const flip = Math.floor(t / 800) % 2;
      px(bx + 1, base - 8, 6, 5, DARK);
      px(bx + 2, base - 7, 2, 3, LIT);
      px(bx + 4 + flip, base - 7, 2, 3, LIT);
    } else if (L.st === 'game') {
      const tw = Math.floor(t / 120) % 2;
      px(bx - 1, base - 8, 1, 2, BODY); px(bx + 8, base - 8, 1, 2, BODY);
      px(bx + 1, base - 8, 6, 4, DARK);
      px(bx + 2, base - 7, 4, 2, tw ? '#7FE3FF' : '#FFE3A8');
    } else if (L.st === 'sleep') {
      px(bx - 1, base - 8, 1, 3, BODY); px(bx + 8, base - 8, 1, 3, BODY);
      for (let i = 0; i < 3; i++) {
        const ph = ((t / 1400) + i * 0.33) % 1;
        const zx = bx + 9 + i * 2 + Math.sin(ph * 6.2832) * 1.5;
        const zy = base - 18 - ph * 9;
        px(zx, zy, 3, 1, LIT); px(zx + 1, zy + 1, 1, 1, LIT); px(zx, zy + 2, 3, 1, LIT);
      }
    } else if (L.st === 'draw') {
      const sw = step ? 1 : 0;
      px(bx + (f > 0 ? 8 : -1), base - 10 - sw, 1, 4, BODY);
      px(bx + (f > 0 ? -1 : 8), base - 9, 1, 4, BODY);
    } else if (L.st === 'ponder') {
      px(bx - 1, base - 9, 1, 3, BODY);
      px(bx + 8, base - 13, 1, 4, BODY);
      px(bx + 6, base - 16, 2, 2, DARK);
      const qp = (t / 2200) % 1;
      px(bx + 10, base - 20 - qp * 6, 1, 2, 'rgba(255,227,168,' + (0.9 - qp * 0.8).toFixed(2) + ')');
      px(bx + 11, base - 21 - qp * 6, 1, 1, 'rgba(255,227,168,' + (0.9 - qp * 0.8).toFixed(2) + ')');
    } else if (L.st === 'juggle') {
      px(bx - 1, base - 12, 1, 4, BODY); px(bx + 8, base - 12, 1, 4, BODY);
      for (let i = 0; i < 3; i++) {
        const ph = ((t / 900) + i / 3) % 1;
        const jx = bx + 1 + Math.sin(ph * 6.2832) * 6;
        const jy = base - 15 - Math.sin(ph * 3.1416) * 9;
        px(jx, jy, 2, 2, [LIT, '#7FE3FF', '#FF7A2E'][i]);
      }
    } else if (L.st === 'watch') {
      px(bx - 1, base - 9, 1, 3, BODY); px(bx + 8, base - 9, 1, 3, BODY);
      px(bx + 1, base - 18, 6, 1, 'rgba(127,227,255,0.35)');
    } else if (L.st === 'scope') {
      px(bx - 1, base - 12, 1, 4, BODY); px(bx + 8, base - 12, 1, 4, BODY);
      if (Math.floor(t / 900) % 3 === 0) px(bx + 2, base - 15, 5, 2, '#FFF4D8');
    } else if (L.st === 'plant') {
      px(bx - 1, base - 8, 1, 3, BODY);
      px(bx + 8, base - 11, 1, 3, BODY);
      px(bx + 9, base - 12, 4, 3, DARK);
      px(bx + 13, base - 12, 2, 1, DARK);
      for (let i = 0; i < 3; i++) {
        const ph = ((t / 700) + i * 0.33) % 1;
        px(bx + 13, base - 10 + ph * 8, 1, 1, 'rgba(127,227,255,' + (0.9 - ph * 0.6).toFixed(2) + ')');
      }
    } else if (L.st === 'fix' || L.st === 'repair') {
      const zap = Math.floor(t / 130) % 4 === 0;
      const gx = bx + (f > 0 ? -13 : 9);
      // welding rig: twin gas bottles on a cart
      px(gx, base - 7, 8, 7, '#43270A');
      px(gx, base - 8, 8, 1, '#6B4410');
      px(gx + 1, base - 1, 1, 1, '#2A1800');
      px(gx + 6, base - 1, 1, 1, '#2A1800');
      px(gx + 1, base - 16, 2, 9, '#7FE3FF');
      px(gx + 1, base - 17, 2, 1, '#2A1800');
      px(gx + 4, base - 16, 2, 9, '#FF7A2E');
      px(gx + 4, base - 17, 2, 1, '#2A1800');
      px(gx + 2, base - 5, 4, 2, '#140A00');
      px(gx + 3, base - 5, 2, 1, (Math.floor(t / 520) % 3) ? '#FFE3A8' : '#FF7A2E');
      // torch in the working hand
      const tx = bx + (f > 0 ? 9 : -4), ty = base - 15;
      px(bx + (f > 0 ? -1 : 8), base - 9, 1, 3, BODY);
      px(bx + (f > 0 ? 8 : -1), base - 13, 1, 5, BODY);
      px(tx, ty, 3, 2, '#5E3600');
      px(tx, ty, 3, 1, '#6B4410');
      const nz = f > 0 ? tx + 3 : tx - 1;
      px(nz, ty, 1, 1, '#FFE3A8');
      // hose sagging from the rig up to the torch
      for (let i = 0; i <= 7; i++) {
        const u = i / 7;
        const hx = (gx + 4) + ((tx + 1) - (gx + 4)) * u;
        const hy = (base - 12) + ((ty + 1) - (base - 12)) * u + Math.sin(u * Math.PI) * 4;
        px(hx, hy, 1, 1, '#5E3600');
      }
      // welding mask, visor down
      px(bx - 1, base - 19, 10, 3, '#6B4410');
      px(bx, base - 17, 8, 7, '#3A2200');
      px(bx + 1, base - 16, 6, 3, '#140A00');
      px(bx + 1, base - 16, 6, 1, zap ? '#FFF4D8' : 'rgba(127,227,255,0.5)');
      px(bx + (f > 0 ? 7 : 0), base - 12, 1, 2, '#5E3600');
      if (zap) {
        // arc flash + sparks
        const ax = nz + (f > 0 ? 1 : -1);
        px(ax - 1, ty - 1, 3, 3, 'rgba(255,244,216,0.85)');
        px(ax, ty, 1, 1, '#FFFFFF');
        px(ax - 3, ty - 3, 7, 7, 'rgba(127,227,255,0.16)');
        for (let i = 0; i < 7; i++) {
          const a = Math.random() * 6.2832, d = 1 + Math.random() * 6;
          px(ax + Math.cos(a) * d, ty + Math.abs(Math.sin(a)) * d, 1, 1, i % 2 ? '#7FE3FF' : '#FF7A2E');
        }
        px(ax - 2, base - 1, 5, 1, 'rgba(255,122,46,0.4)');
      }
    } else if (L.st === 'dance') {
      const up = step ? 5 : 1;
      px(bx + (f > 0 ? 8 : -1), base - 9 - up, 1, 2 + up, BODY);
      px(bx + (f > 0 ? -1 : 8), base - 9 - (step ? 1 : 4), 1, 2 + (step ? 1 : 4), BODY);
      for (let i = 0; i < 2; i++) {
        const ph = ((t / 1100) + i * 0.5) % 1;
        const nx = bx + (i ? -5 : 10) + Math.round(Math.sin(ph * 6.2832 + i) * 2), ny = base - 16 - ph * 10;
        px(nx, ny, 2, 1, LIT); px(nx + 1, ny + 1, 1, 2, LIT); px(nx, ny + 3, 2, 1, LIT);
      }
    } else if (L.st === 'fly') {
      px(bx - 1, base - 10, 1, 3, BODY); px(bx + 8, base - 10, 1, 3, BODY);
    } else if (L.st === 'comm') {
      const up = step ? 1 : 0;
      px(bx + (f > 0 ? 8 : -1), base - 11 - up, 1, 4, BODY);
      px(bx + (f > 0 ? -1 : 8), base - 9, 1, 4, BODY);
      for (let i = 0; i < 3; i++) {
        const ph = ((t / 620) + i * 0.34) % 1;
        px(bx + 4 + f * (5 + ph * 7), base - 20 - ph * 2, 1, 1, 'rgba(127,227,255,' + (0.85 - ph * 0.7).toFixed(2) + ')');
      }
    } else {
      px(bx - 1, base - 9, 1, 4, BODY); px(bx + 8, base - 9, 1, 4, BODY);
    }

    if ((L.st === 'comm' || L.st === 'repair') && L.dlg) {
      const el = t - L.dlgT;
      const cur = L.dlg.find(s => el >= s.start && el < s.end) || (el >= L.dlg[L.dlg.length - 1].end ? L.dlg[L.dlg.length - 1] : null);
      this.commPulse = 0;
      this.commTalkT = 0;
      if (L.st === 'repair') {
        const ouch = L.dlg.find(s => s.fx === 'ouch');
        const fixed = L.dlg.find(s => s.fx === 'fixed');
        const hurting = ouch && el >= ouch.start && (!fixed || el < fixed.start);
        const healed = fixed && el >= fixed.start;
        if (hurting) { this.coreTintHex = '#FF2E14'; this.coreTintT = 1; this.coreShakeT = 1; this.coreShakeHard = true; }
        else if (healed) {
          const since = el - fixed.start;
          this.coreTintHex = '#5FC8FF';
          this.coreTintT = Math.max(0, 1 - Math.max(0, since - 5200) / 2600);
          this.coreShakeT = 0.55 * this.coreTintT; this.coreShakeHard = false;
        } else { this.coreTintT = 0; this.coreShakeT = 0; }
      }
      if (cur && cur.s === 'a' && coreC) {
        this.drawSpeech(ctx, cur.t, coreC.x, coreC.y - coreC.r - 18, W, el - cur.start, '#7FE3FF', true, coreC.y + coreC.r + 18);
        const typing = el < cur.start + cur.t.length * 26;
        this.commPulse = typing ? 0.55 + 0.45 * Math.sin(t * 0.03) : 0.3;
        this.commTalkT = typing ? 1 : 0.45;
      } else if (cur) {
        this.drawSpeech(ctx, cur.t, bx * S, (base - 22) * S, W, el - cur.start, '#FFB000', false, (base + 2) * S);
      }
    } else {
      this.commPulse = 0;
      this.commTalkT = 0;
      this.coreTintT = 0;
      this.coreShakeT = 0;
      if (L.bubble && L.st !== 'fly') this.drawBubble(ctx, L, bx * S, (base - 22) * S, W, t, (base + 2) * S);
    }
  }

  drawSpeech(ctx, text, ax, ay, W, elapsed, accent, center, flipY) {
    const chars = Math.floor(Math.max(0, elapsed) / 26);
    if (chars <= 0) return;
    ctx.font = '500 12px "IBM Plex Mono", monospace';
    ctx.textBaseline = 'top';
    const max = 30;
    const lines = []; let cur = '';
    for (const w of text.split(' ')) {
      if ((cur + ' ' + w).trim().length > max) { lines.push(cur.trim()); cur = w; } else cur += ' ' + w;
    }
    if (cur.trim()) lines.push(cur.trim());
    let left = Math.min(chars, text.length);
    const vis = lines.map(l => { const p = l.slice(0, Math.max(0, left)); left -= l.length + 1; return p; }).filter((l, i) => i === 0 || l.length);
    const wpx = Math.max(...lines.map(l => ctx.measureText(l).width)) + 20;
    const hpx = lines.length * 17 + 14;
    const x = Math.min(Math.max(8, center ? ax - wpx / 2 : ax - 8), W - wpx - 8);
    const H = window.innerHeight;
    const flip = ay - hpx < 8;
    const y = flip
      ? Math.max(8, Math.min(H - hpx - 8, (flipY ?? ay + 88) + 12))
      : ay - hpx;
    // the free corridor: under the top gauge, above the audio rail, between the HUD columns
    let by = Math.max(112, Math.min(H - 104 - hpx, y));
    if (this.ring) {
      const r = this.ring.getBoundingClientRect();
      if (r.width && x < r.right && x + wpx > r.left && by < r.bottom + 6 && by + hpx > r.top - 6) {
        if (r.bottom + 10 + hpx < H - 104) by = r.bottom + 10;
        else if (r.left - 10 - wpx > leftWall) x = r.left - 10 - wpx;
        else if (r.right + 10 + wpx < rightWall) x = r.right + 10;
      }
    }
    ctx.fillStyle = 'rgba(20,10,0,0.92)';
    ctx.fillRect(x, by, wpx, hpx);
    ctx.strokeStyle = accent;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.8;
    ctx.strokeRect(x + 1, y + 1, wpx - 2, hpx - 2);
    ctx.globalAlpha = 1;
    ctx.fillStyle = 'rgba(20,10,0,0.92)';
    ctx.fillRect(center ? ax - 5 : ax + 4, flip ? y - 6 : y + hpx - 2, 10, 8);
    ctx.fillStyle = accent === '#7FE3FF' ? '#BDEEFF' : '#FFC15E';
    vis.forEach((l, i) => ctx.fillText(l, x + 10, y + 8 + i * 17));
    if (Math.floor(elapsed / 420) % 2 && chars < text.length) {
      ctx.fillRect(x + 10 + ctx.measureText(vis[vis.length - 1] || '').width + 3, y + 8 + (vis.length - 1) * 17, 7, 13);
    }
  }

  drawBubble(ctx, L, ax, ay, W, t, flipY) {
    const chars = Math.min(L.bubble.length, Math.floor(Math.max(0, t - (L.bubT ?? (L.until - 9000))) / 26));
    const shown = L.bubble.slice(0, chars);
    if (!shown) return;
    ctx.font = '500 12px "IBM Plex Mono", monospace';
    ctx.textBaseline = 'top';
    const max = 30;
    const words = L.bubble.split(' ');
    const lines = []; let cur = '';
    for (const w of words) {
      if ((cur + ' ' + w).trim().length > max) { lines.push(cur.trim()); cur = w; } else cur += ' ' + w;
    }
    if (cur.trim()) lines.push(cur.trim());
    let left = shown.length;
    const vis = lines.map(l => { const p = l.slice(0, Math.max(0, left)); left -= l.length + 1; return p; }).filter((l, i) => i === 0 || l.length);
    const wpx = Math.max(...lines.map(l => ctx.measureText(l).width)) + 20;
    const hpx = lines.length * 17 + 14;
    // HUD panels own a column down each edge — the bubble must not slide under them
    const rightWall = W - 306, leftWall = 310;
    let x = Math.min(Math.max(8, ax - 8), W - wpx - 8);
    if (x + wpx > rightWall) x = Math.max(8, rightWall - wpx);
    if (this.envAmt > 0.02 && x < leftWall && wpx < rightWall - leftWall) x = leftWall;
    const H = window.innerHeight;
    const flip = ay - hpx < 8;
    const y = flip
      ? Math.max(8, Math.min(H - hpx - 8, (flipY ?? ay + 88) + 12))
      : ay - hpx;
    // the free corridor: under the top gauge, above the audio rail, between the HUD columns
    let by = Math.max(112, Math.min(H - 104 - hpx, y));
    if (this.ring) {
      const r = this.ring.getBoundingClientRect();
      if (r.width && x < r.right && x + wpx > r.left && by < r.bottom + 6 && by + hpx > r.top - 6) {
        if (r.bottom + 10 + hpx < H - 104) by = r.bottom + 10;
        else if (r.left - 10 - wpx > leftWall) x = r.left - 10 - wpx;
        else if (r.right + 10 + wpx < rightWall) x = r.right + 10;
      }
    }
    ctx.fillStyle = 'rgba(20,10,0,0.92)';
    ctx.fillRect(x, by, wpx, hpx);
    ctx.strokeStyle = 'rgba(255,176,0,0.75)';
    ctx.lineWidth = 2;
    ctx.strokeRect(x + 1, by + 1, wpx - 2, hpx - 2);
    ctx.fillStyle = 'rgba(20,10,0,0.92)';
    ctx.fillRect(ax + 4, flip ? by - 6 : by + hpx - 2, 10, 8);
    ctx.fillStyle = '#FFC15E';
    vis.forEach((l, i) => ctx.fillText(l, x + 10, by + 8 + i * 17));
    if (Math.floor(t / 420) % 2 && chars >= L.bubble.length) {
      ctx.fillRect(x + 10 + ctx.measureText(vis[vis.length - 1] || '').width + 3, by + 8 + (vis.length - 1) * 17, 7, 13);
    }
  }

  drawLylaHealth(t, dt, hot) {
    const st = this.ly && this.ly.st;
    const charging = st === 'sleep';
    const rate = charging ? -2.4 : (st === 'fly' ? 0.5 : 0.22) + hot * 0.5;
    this.lylaHp = Math.max(6, Math.min(100, (this.lylaHp == null ? 88 : this.lylaHp) - rate * (dt / 1000)));
    const hp = this.lylaHp;
    const low = hp < 26;
    if (this.bar) {
      const el = this.bar;
      el.style.width = hp.toFixed(1) + '%';
      const col = low ? '#FF7A2B' : charging ? '#FFD48A' : '#FFB000';
      el.style.background = col;
      el.style.boxShadow = '0 0 9px ' + (low ? 'rgba(255,122,43,.8)' : 'rgba(255,176,0,.75)');
      el.style.opacity = low && Math.floor(t / 420) % 2 ? '.45' : '1';
    }
    if (this.pct) {
      const el = this.pct;
      const s = charging ? Math.round(hp) + '% ↑' : Math.round(hp) + '%';
      if (el.textContent !== s) el.textContent = s;
      el.style.color = low ? '#FF7A2B' : '#FFC15E';
    }
    this.drawLylaIcon(t, charging, low);
  }

  drawLylaIcon(t, charging, low) {
    const c = this.icon;
    if (!c) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2), S = 3, GW = 8, GH = 12;
    if (c.width !== Math.round(GW * S * dpr)) { c.width = Math.round(GW * S * dpr); c.height = Math.round(GH * S * dpr); }
    const g = c.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, GW * S, GH * S);
    const px = (x, y, w, h, col) => { g.fillStyle = col; g.fillRect(x * S, y * S, w * S, h * S); };
    const BODY = low ? '#C86020' : '#FFB000', LIT = '#FFE3A8', EYE = '#FFF4D8', DARK = '#5E3600';
    px(3, 0, 3, 2, (Math.floor(t / 700) % 2) ? '#FF7A2E' : LIT);   // antenna lamp
    px(4, 2, 1, 3, DARK);                                           // stalk
    px(0, 5, 8, 7, BODY);                                           // head
    px(1, 6, 6, 3, '#3A2200');                                      // visor band
    const blink = (Math.floor(t / 2600) % 5 === 0) && (t % 2600 < 140);
    if (charging || blink) { px(2, 7, 2, 1, EYE); px(5, 7, 2, 1, EYE); }
    else { px(2, 6, 2, 2, EYE); px(5, 6, 2, 2, EYE); }
  }
}
