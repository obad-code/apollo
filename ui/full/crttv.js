/* The idle screen's old television: a cream set in three-quarter view, its
 * green phosphor tube playing little scenes of Apollo and his crew - on the
 * sofa, at a meeting, on the trading floor, in LYLA's studio, round a fire.
 * The picture is drawn small and blown up in whole pixels, then the tube's
 * scanlines, glow and curve go over it in CSS. Only draws while shown. */

const W = 320, H = 210;
const G = (a = 1) => `rgba(110, 255, 150, ${a})`;
const SCENE_SECS = 11;

const CREW = {
  APOLLO: { hat: 'antenna' }, LYLA: { hat: 'bun' }, Q: { hat: 'cap' },
  THEIA: { hat: 'mortar' }, MONEYPENNY: { hat: 'bob' },
};

function px(ctx, x, y, w, h, a = 1) { ctx.fillStyle = G(a); ctx.fillRect(Math.round(x), Math.round(y), w, h); }
function text(ctx, s, x, y, a = 1, align = 'left', size = 7) {
  ctx.font = `${size}px "Courier New", monospace`; ctx.textAlign = align; ctx.textBaseline = 'top';
  ctx.fillStyle = G(a); ctx.fillText(s, Math.round(x), Math.round(y));
}

/* One of the crew. (x, y) is the seat; `talk` opens the mouth, `look` turns the eyes. */
function figure(ctx, name, x, y, t, { talk = false, look = 0, sit = true, bob = 0, scale = 1 } = {}) {
  const hat = CREW[name].hat;
  ctx.save(); ctx.translate(Math.round(x), Math.round(y + Math.sin(t * 2 + bob) * 0.6)); ctx.scale(scale, scale);
  // body and legs
  ctx.fillStyle = G(0.85); ctx.beginPath(); ctx.roundRect(-8, -18, 16, 18, 5); ctx.fill();
  if (sit) { px(ctx, -7, -2, 6, 3, .7); px(ctx, 1, -2, 6, 3, .7); px(ctx, -7, 1, 3, 6, .7); px(ctx, 4, 1, 3, 6, .7); }
  else { px(ctx, -6, 0, 4, 10, .7); px(ctx, 2, 0, 4, 10, .7); }
  // head
  ctx.fillStyle = G(1); ctx.beginPath(); ctx.arc(0, -27, 10, 0, Math.PI * 2); ctx.fill();
  // the eyes - Apollo's are his big round ones
  const blink = (Math.sin(t * 1.3 + bob * 3) > 0.985) ? 1 : 0;
  ctx.fillStyle = '#021a08';
  const ex = look * 2;
  if (name === 'APOLLO') {
    ctx.beginPath(); ctx.ellipse(-4 + ex, -28, 2.6, blink ? .5 : 3.4, 0, 0, 7); ctx.ellipse(4 + ex, -28, 2.6, blink ? .5 : 3.4, 0, 0, 7); ctx.fill();
  } else {
    ctx.fillRect(-4 + ex - 1, -29, 2, blink ? 1 : 3); ctx.fillRect(4 + ex - 1, -29, 2, blink ? 1 : 3);
  }
  if (talk && Math.sin(t * 14) > 0) ctx.fillRect(-2, -22, 4, 2); else ctx.fillRect(-2, -22, 4, 1);
  // what tells them apart
  ctx.fillStyle = G(1);
  if (hat === 'antenna') { px(ctx, -.5, -42, 1, 6); ctx.beginPath(); ctx.arc(0, -43, 2 + Math.sin(t * 4) * .5, 0, 7); ctx.fill(); }
  if (hat === 'bun') { ctx.beginPath(); ctx.arc(0, -39, 4.5, 0, 7); ctx.fill(); px(ctx, -10, -32, 3, 12, .9); px(ctx, 7, -32, 3, 12, .9); }
  if (hat === 'cap') { ctx.beginPath(); ctx.arc(0, -31, 10.5, Math.PI, 0); ctx.fill(); px(ctx, 4, -32, 9, 2); }
  if (hat === 'mortar') { px(ctx, -11, -39, 22, 3); px(ctx, -5, -37, 10, 3); px(ctx, 9, -38, 1, 7, .9); }
  if (hat === 'bob') { ctx.beginPath(); ctx.arc(0, -29, 11.5, Math.PI * 1.05, Math.PI * 1.95); ctx.fill(); px(ctx, -12, -30, 4, 10); px(ctx, 8, -30, 4, 10); }
  ctx.restore();
}

function bubble(ctx, x, y, s, a = 1) {
  ctx.font = '7px "Courier New", monospace';
  const w = ctx.measureText(s).width + 8;
  ctx.strokeStyle = G(a); ctx.lineWidth = 1;
  ctx.beginPath(); ctx.roundRect(Math.round(x - w / 2) + .5, Math.round(y - 12) + .5, Math.round(w), 11, 3); ctx.stroke();
  px(ctx, x - 1, y - 1, 2, 3, a);
  text(ctx, s, x, y - 10, a, 'center');
}

function floor(ctx, y) { for (let x = 0; x < W; x += 4) px(ctx, x, y, 2, 1, .35); }

const SCENES = [
  { name: 'LIVING ROOM', draw(ctx, t) {
    floor(ctx, 168);
    // the little set they watch, flickering
    ctx.strokeStyle = G(.9); ctx.strokeRect(258.5, 112.5, 44, 32); px(ctx, 262, 116, 37, 25, .15 + .15 * Math.abs(Math.sin(t * 7)));
    px(ctx, 270, 145, 3, 10, .7); px(ctx, 288, 145, 3, 10, .7);
    // the sofa
    ctx.fillStyle = G(.28); ctx.beginPath(); ctx.roundRect(22, 128, 210, 30, 6); ctx.fill();
    px(ctx, 16, 136, 12, 30, .4); px(ctx, 226, 136, 12, 30, .4); px(ctx, 30, 158, 4, 10, .4); px(ctx, 222, 158, 4, 10, .4);
    const who = ['LYLA', 'THEIA', 'APOLLO', 'MONEYPENNY', 'Q'];
    who.forEach((n, i) => figure(ctx, n, 50 + i * 40, 150, t, { look: 1, bob: i, talk: n === 'Q' && (t % 6) < 1.4 }));
    if ((t % 6) < 1.4) bubble(ctx, 210, 96, 'PASS THE POPCORN');
    if ((t % 6) > 3 && (t % 6) < 4.6) bubble(ctx, 130, 96, 'SHH. BEST PART.');
  } },
  { name: 'CREW MEETING', draw(ctx, t) {
    floor(ctx, 172);
    ctx.fillStyle = G(.3); ctx.beginPath(); ctx.ellipse(160, 150, 92, 14, 0, 0, 7); ctx.fill();
    px(ctx, 157, 152, 6, 20, .45);
    const lines = [['MONEYPENNY', 'NVDA: HOLD'], ['THEIA', 'BUT WHY?'], ['MONEYPENNY', 'PRICE > TARGET'],
                   ['Q', 'TICKET #42 FILED'], ['LYLA', 'SHORT IS READY'], ['APOLLO', 'GOOD WORK, TEAM']];
    const k = Math.floor(t / 1.8) % lines.length;
    const seats = { LYLA: 64, THEIA: 112, APOLLO: 160, MONEYPENNY: 208, Q: 256 };
    Object.entries(seats).forEach(([n, x], i) => figure(ctx, n, x, 140, t, { talk: lines[k][0] === n, bob: i, look: (lines[k][0] === n) ? 0 : Math.sign(seats[lines[k][0]] - x) }));
    bubble(ctx, seats[lines[k][0]], 92, lines[k][1]);
  } },
  { name: 'TRADING FLOOR', draw(ctx, t) {
    floor(ctx, 174);
    // the big chart on the wall
    ctx.strokeStyle = G(.6); ctx.strokeRect(70.5, 30.5, 180, 70);
    ctx.strokeStyle = G(1); ctx.beginPath();
    for (let i = 0; i <= 60; i++) {
      const x = 72 + i * 2.95, v = Math.sin(i * .35 + t * 1.4) * 12 + Math.sin(i * .11 + t * .4) * 10 - i * .25;
      i ? ctx.lineTo(x, 68 + v) : ctx.moveTo(x, 68 + v);
    }
    ctx.stroke();
    text(ctx, 'TEAM CALL: ' + ['BUY', 'HOLD', 'BUY', 'HOLD'][Math.floor(t / 2.7) % 4], 160, 104, .9, 'center');
    figure(ctx, 'MONEYPENNY', 160, 168, t, { sit: false, talk: (t % 3) < 1.5 });
    ['THEIA', 'Q', 'APOLLO', 'LYLA'].forEach((n, i) => figure(ctx, n, [42, 92, 228, 278][i], 166, t, { look: i < 2 ? 1 : -1, bob: i, talk: (t % 4) > 2 && i === 0 }));
    if ((t % 4) > 2) bubble(ctx, 42, 120, 'BULL CASE!');
    if ((t % 4) < 2) bubble(ctx, 278, 120, 'BEAR CASE!');
  } },
  { name: "LYLA'S STUDIO", draw(ctx, t) {
    floor(ctx, 170);
    // the lamp, its cone of light
    px(ctx, 250, 40, 3, 128, .5); px(ctx, 240, 36, 22, 6, .8);
    ctx.fillStyle = G(.08); ctx.beginPath(); ctx.moveTo(240, 42); ctx.lineTo(262, 42); ctx.lineTo(220, 168); ctx.lineTo(110, 168); ctx.fill();
    figure(ctx, 'APOLLO', 170, 166, t, { sit: false, talk: true, look: -1 });
    figure(ctx, 'LYLA', 72, 166, t, { sit: false, look: 1 });
    // her camera on its legs
    px(ctx, 86, 124, 20, 12, .95); px(ctx, 106, 127, 6, 6, .8); px(ctx, 95, 136, 2, 30, .6); px(ctx, 88, 160, 16, 2, .6);
    if ((t % 1) < .6) { ctx.fillStyle = G(1); ctx.beginPath(); ctx.arc(22, 30, 3, 0, 7); ctx.fill(); text(ctx, 'REC', 30, 26); }
    text(ctx, `00:${String(Math.floor(t) % 60).padStart(2, '0')}`, 298, 26, .8, 'right');
    bubble(ctx, 170, 112, ['DID YOU KNOW...', 'POV: YOU ARE RICH', 'FOLLOW FOR MORE'][Math.floor(t / 3) % 3]);
  } },
  { name: 'CAMPFIRE', draw(ctx, t) {
    for (let i = 0; i < 40; i++) { const sx = (i * 73) % W, sy = (i * 37) % 90; px(ctx, sx, sy, 1, 1, .3 + .5 * Math.abs(Math.sin(t * 1.5 + i))); }
    ctx.fillStyle = G(.9); ctx.beginPath(); ctx.arc(268, 30, 11, 0, 7); ctx.fill();
    ctx.fillStyle = '#031407'; ctx.beginPath(); ctx.arc(273, 27, 10, 0, 7); ctx.fill();
    floor(ctx, 172);
    // the fire
    for (let i = 0; i < 7; i++) {
      const h = 10 + 9 * Math.abs(Math.sin(t * 6 + i * 1.7));
      ctx.fillStyle = G(.55 + .4 * Math.sin(t * 9 + i)); ctx.beginPath();
      ctx.moveTo(150 + i * 3, 166); ctx.lineTo(152 + i * 3, 166 - h); ctx.lineTo(155 + i * 3, 166); ctx.fill();
    }
    px(ctx, 144, 166, 32, 3, .7);
    [['THEIA', 70], ['APOLLO', 108], ['MONEYPENNY', 212], ['LYLA', 250]].forEach(([n, x], i) => figure(ctx, n, x, 168, t, { look: x < 160 ? 1 : -1, bob: i }));
    figure(ctx, 'Q', 290, 168, t, { look: -1, bob: 5, talk: (t % 5) < 2 });
    if ((t % 5) < 2) bubble(ctx, 290, 116, 'ONE MORE STORY');
  } },
];

export class CrtTv {
  constructor(root) {
    this.root = root;
    this.running = false;
    root.innerHTML = `
      <div class="tv-room">
        <div class="tv">
          <div class="tv-top"></div>
          <div class="tv-face">
            <div class="tv-bezel">
              <div class="tv-tube">
                <canvas width="${W}" height="${H}"></canvas>
                <div class="tv-hud"><span class="tv-ch">CH 01</span><span class="tv-menu">
                  <u>CREW</u> &nbsp; MARKETS &nbsp; STUDIO</span><span class="tv-clock"></span></div>
                <div class="tv-lines"></div><div class="tv-glass"></div>
              </div>
            </div>
            <div class="tv-badge"><b>apollo</b><i>crew</i></div>
            <div class="tv-panel">
              <span class="tv-btn"><i></i></span>
              ${['VOLUME', 'CHANNEL', 'TONE', 'MIX'].map((l, i) => `<span class="tv-knob" style="--r:${-40 + i * 37}deg"><em>${l}</em><i></i><small>${['-0.0', '01', '+0.0', '100'][i]}</small></span>`).join('')}
              <span class="tv-btn tv-power"><i></i></span>
            </div>
            <div class="tv-jacks"><span></span><span></span><span class="tv-jack-empty"></span></div>
            <div class="tv-glare"></div>
          </div>
          <div class="tv-cable tv-cable-a"></div><div class="tv-cable tv-cable-b"></div>
        </div>
        <div class="tv-floor"></div>
      </div>`;
    // The floating-card tilt: the set leans toward the pointer in 3D, its parts
    // standing off the case at different depths, and settles back when it leaves.
    this.tv = root.querySelector('.tv');
    this.room = root.querySelector('.tv-room');
    root.addEventListener('mousemove', (e) => this.tilt(e));
    root.addEventListener('mouseleave', () => this.untilt());
    this.canvas = root.querySelector('canvas');
    this.ctx = this.canvas.getContext('2d');
    this.ch = root.querySelector('.tv-ch');
    this.clock = root.querySelector('.tv-clock');
    this.t0 = performance.now();
    this.frame = this.frame.bind(this);
  }

  tilt(e) {
    const { left, top, width, height } = this.room.getBoundingClientRect();
    const x = e.clientX - left, y = e.clientY - top;
    const rotateX = ((y - height / 2) / height) * 15;
    const rotateY = ((x - width / 2) / width) * -15;
    this.tv.classList.add('tilting');
    this.tv.style.transform = `rotateX(${3 + rotateX}deg) rotateY(${-8 + rotateY}deg) scale(1.02)`;
    this.tv.style.setProperty('--gx', `${Math.max(0, Math.min(100, x / width * 100))}%`);
    this.tv.style.setProperty('--gy', `${Math.max(0, Math.min(100, y / height * 100))}%`);
  }

  untilt() {
    this.tv.style.transform = 'rotateX(3deg) rotateY(-8deg) scale(1)';
    this.tv.classList.remove('tilting');
  }

  start() {
    if (this.running) return;
    this.running = true;
    this.root.classList.add('on');
    this.t0 = performance.now();
    this.raf = requestAnimationFrame(this.frame);
  }

  stop() {
    this.running = false;
    this.root.classList.remove('on');
    cancelAnimationFrame(this.raf);
  }

  frame(now) {
    if (!this.running) return;
    this.raf = requestAnimationFrame(this.frame);
    if (now - (this.last || 0) < 1000 / 30) return;        // a tube's own pace: 30 a second
    this.last = now;
    const secs = Math.max(0, now - this.t0) / 1000;
    const k = Math.floor(secs / SCENE_SECS) % SCENES.length;
    const t = secs % SCENE_SECS;
    const ctx = this.ctx;
    ctx.fillStyle = '#031407'; ctx.fillRect(0, 0, W, H);
    SCENES[k].draw(ctx, secs);
    // the change of channel: a burst of snow either side of the cut
    const edge = Math.min(t, SCENE_SECS - t);
    if (edge < 0.35) {
      const img = ctx.getImageData(0, 0, W, H), d = img.data;
      for (let i = 0; i < d.length; i += 4) { const v = Math.random() * 200 * (1 - edge / .35); d[i] = v * .45; d[i + 1] = v; d[i + 2] = v * .6; }
      ctx.putImageData(img, 0, 0);
    }
    this.ch.textContent = `CH ${String(k + 1).padStart(2, '0')}  ${SCENES[k].name}`;
    const d = new Date();
    this.clock.textContent = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  }
}
