/* The room's sound: a steady, quiet bed under each mode - never music, no
 * tune, nothing that repeats as a melody. Just what a place sounds like:
 * the engine of a ship, the air of a cabin, fans in a server room, an air
 * conditioner. Made on the spot from filtered noise and a low hum, with the
 * filters drifting slowly so it breathes instead of droning.
 *
 * SCENES are the recipes; Ambient crossfades between them as the mode
 * changes, plays a slow power-up when the display first comes on, and goes
 * almost silent while the display sleeps. Very low by default; `setOn`
 * turns it off and is remembered per viewer. */

export const SCENES = {
  // The bridge of a ship: a deep engine bed and a faint hum under it.
  normal: { noise: [{ color: 'brown', type: 'lowpass', hz: 320, q: 0.6, gain: 0.32, drift: 60, rate: 0.05 }],
            hum: [{ hz: 55, gain: 0.05 }, { hz: 110.4, gain: 0.025 }] },
  // A server room: fans (a band of air) and mains hum.
  agents: { noise: [{ color: 'pink', type: 'bandpass', hz: 1500, q: 0.5, gain: 0.07, drift: 200, rate: 0.08 },
                    { color: 'brown', type: 'lowpass', hz: 220, q: 0.5, gain: 0.22, drift: 30, rate: 0.03 }],
            hum: [{ hz: 60, gain: 0.03 }, { hz: 120, gain: 0.015 }] },
  // An air conditioner: bright, soft air.
  trading: { noise: [{ color: 'pink', type: 'lowpass', hz: 2200, q: 0.4, gain: 0.08, drift: 300, rate: 0.04 },
                     { color: 'brown', type: 'lowpass', hz: 380, q: 0.5, gain: 0.14, drift: 40, rate: 0.03 }],
             hum: [] },
  // An aeroplane cabin: a broad, low rush.
  clear: { noise: [{ color: 'brown', type: 'lowpass', hz: 520, q: 0.5, gain: 0.34, drift: 50, rate: 0.03 }],
           hum: [{ hz: 82, gain: 0.015 }] },
  // Deep space: very low, very slow.
  expanded: { noise: [{ color: 'brown', type: 'lowpass', hz: 180, q: 0.7, gain: 0.36, drift: 40, rate: 0.02 }],
              hum: [{ hz: 41, gain: 0.05 }, { hz: 41.6, gain: 0.04 }] },
  // Asleep: the engine idling, barely there.
  asleep: { noise: [{ color: 'brown', type: 'lowpass', hz: 240, q: 0.5, gain: 0.12, drift: 20, rate: 0.02 }], hum: [] },
};
SCENES.osiris = SCENES.expanded;

const FADE = 2.5;

function noiseBuffer(ctx, color) {
  const n = ctx.sampleRate * 4;
  const buf = ctx.createBuffer(1, n, ctx.sampleRate);
  const d = buf.getChannelData(0);
  let last = 0, b0 = 0, b1 = 0, b2 = 0;
  for (let i = 0; i < n; i++) {
    const w = Math.random() * 2 - 1;
    if (color === 'brown') { last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; }
    else { b0 = 0.997 * b0 + w * 0.029591; b1 = 0.985 * b1 + w * 0.032534; b2 = 0.95 * b2 + w * 0.048056; d[i] = (b0 + b1 + b2 + w * 0.1848) * 0.6; }
  }
  return buf;
}

export class Ambient {
  constructor({ volume = 0.35 } = {}) {
    this.volume = volume;
    this.ctx = null;
    this.scene = null;
    this.layer = null;
    this.on = (() => { try { return localStorage.getItem('ambient') !== 'off'; } catch { return true; } })();
    this.buffers = {};
  }

  ensure() {
    if (this.ctx) return this.ctx;
    try {
      this.ctx = new (window.AudioContext || window.webkitAudioContext)();
      this.out = this.ctx.createGain();
      this.out.gain.value = this.on ? this.volume : 0;
      this.out.connect(this.ctx.destination);
    } catch { this.ctx = null; }
    return this.ctx;
  }

  buffer(color) {
    if (!this.buffers[color]) this.buffers[color] = noiseBuffer(this.ctx, color);
    return this.buffers[color];
  }

  build(recipe) {
    const ctx = this.ctx, now = ctx.currentTime;
    const bus = ctx.createGain();
    bus.gain.setValueAtTime(0, now);
    bus.gain.linearRampToValueAtTime(1, now + FADE);
    bus.connect(this.out);
    const stops = [];
    for (const n of recipe.noise) {
      const src = ctx.createBufferSource();
      src.buffer = this.buffer(n.color);
      src.loop = true;
      const f = ctx.createBiquadFilter();
      f.type = n.type; f.frequency.value = n.hz; f.Q.value = n.q;
      const lfo = ctx.createOscillator(); const depth = ctx.createGain();
      lfo.frequency.value = n.rate; depth.gain.value = n.drift;
      lfo.connect(depth).connect(f.frequency);
      const g = ctx.createGain(); g.gain.value = n.gain;
      src.connect(f).connect(g).connect(bus);
      src.start(now, Math.random() * 3); lfo.start(now);
      stops.push(src, lfo);
    }
    for (const h of recipe.hum) {
      const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.value = h.hz;
      const g = ctx.createGain(); g.gain.value = h.gain;
      o.connect(g).connect(bus); o.start(now); stops.push(o);
    }
    return { bus, stops };
  }

  /* Move to scene `name`, crossfading. */
  play(name) {
    const recipe = SCENES[name] || SCENES.normal;
    if (this.scene === name) return;
    this.scene = name;
    if (!this.ensure()) return;
    if (this.ctx.state === 'suspended') this.ctx.resume().catch(() => {});
    const old = this.layer;
    this.layer = this.build(recipe);
    if (old) {
      const now = this.ctx.currentTime;
      old.bus.gain.cancelScheduledValues(now);
      old.bus.gain.setValueAtTime(old.bus.gain.value, now);
      old.bus.gain.linearRampToValueAtTime(0, now + FADE);
      setTimeout(() => { old.stops.forEach((s) => { try { s.stop(); } catch { /* gone */ } }); old.bus.disconnect(); }, FADE * 1000 + 200);
    }
  }

  /* The display coming on: a slow power-up, an engine spinning up to idle. */
  powerUp() {
    if (!this.on || !this.ensure()) return;
    const ctx = this.ctx, now = ctx.currentTime;
    const o = ctx.createOscillator(); o.type = 'sawtooth';
    o.frequency.setValueAtTime(28, now); o.frequency.exponentialRampToValueAtTime(110, now + 2.6);
    const f = ctx.createBiquadFilter(); f.type = 'lowpass';
    f.frequency.setValueAtTime(120, now); f.frequency.exponentialRampToValueAtTime(900, now + 2.2);
    f.frequency.exponentialRampToValueAtTime(300, now + 3.6);
    const g = ctx.createGain(); g.gain.setValueAtTime(0, now);
    g.gain.linearRampToValueAtTime(0.16, now + 1.6); g.gain.exponentialRampToValueAtTime(0.0008, now + 4);
    o.connect(f).connect(g).connect(this.out); o.start(now); o.stop(now + 4.1);
    const n = ctx.createBufferSource(); n.buffer = this.buffer('pink');
    const nf = ctx.createBiquadFilter(); nf.type = 'bandpass'; nf.Q.value = 0.8;
    nf.frequency.setValueAtTime(300, now); nf.frequency.exponentialRampToValueAtTime(2400, now + 2.4);
    const ng = ctx.createGain(); ng.gain.setValueAtTime(0, now);
    ng.gain.linearRampToValueAtTime(0.05, now + 2); ng.gain.linearRampToValueAtTime(0, now + 3.4);
    n.connect(nf).connect(ng).connect(this.out); n.start(now); n.stop(now + 3.5);
  }

  /* All of it quiet (the display hidden), or back. */
  pause(off) {
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    this.out.gain.cancelScheduledValues(now);
    this.out.gain.setValueAtTime(this.out.gain.value, now);
    this.out.gain.linearRampToValueAtTime(off || !this.on ? 0 : this.volume, now + 1.2);
  }

  setOn(on) {
    this.on = Boolean(on);
    try { localStorage.setItem('ambient', this.on ? 'on' : 'off'); } catch { /* private */ }
    this.pause(false);
  }
}
