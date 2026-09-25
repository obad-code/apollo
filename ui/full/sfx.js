/* The display's sounds, made on the spot: no files, just Web Audio - a few
 * oscillators and a little noise, each swept in pitch and shaped by its own
 * envelope, the way an old synth makes a blip. Short and quiet, because they
 * are the interface's and Apollo's voice is the one you listen to.
 *
 * SOUNDS is the recipes, schedule() builds one into a context, and Sfx is
 * the player the page keeps: it makes its context only when first asked,
 * wakes it if it is still waiting for a gesture, plays nothing muted, and
 * plays a sound only once when it is asked for twice at once - a pointer
 * sweeping over a row of buttons ticks, it does not buzz. tests/test_sfx.py
 * runs it against a stand-in for Web Audio.
 *
 * A voice: `wave` (an oscillator's type, or 'noise'), `at` seconds into the
 * sound, `dur` seconds long, `gain` at its peak after `attack`, its pitch
 * swept `from` -> `to` over `glide` of its length, and optionally a `filter`
 * ({ type, from, to, q }) and a `wobble` ({ rate, depth }: vibrato, in Hz). */

const blip = (wave, from, to, dur, gain, more = {}) => ({ wave, from, to, dur, gain, ...more });
const hiss = (dur, gain, filter, more = {}) => ({ wave: 'noise', dur, gain, filter, ...more });

export const SOUNDS = {
  // A pointer over a button: the lightest tick.
  tick: [blip('sine', 3200, 2600, 0.022, 0.03, { attack: 0.002 })],
  // A button pressed: a dry click with a little air in it.
  press: [
    blip('square', 1500, 620, 0.045, 0.05, { filter: { type: 'lowpass', from: 3600, q: 0.7 } }),
    hiss(0.018, 0.04, { type: 'bandpass', from: 5200, q: 1.2 }, { attack: 0.001 }),
  ],
  // A tab or a chip: two quick glassy steps.
  tab: [
    blip('triangle', 1240, 1240, 0.045, 0.05),
    blip('sine', 1860, 1860, 0.05, 0.025, { at: 0.025 }),
  ],
  // Something chosen, or Apollo about to answer: a bright upward flick.
  rev: [
    blip('triangle', 660, 1320, 0.09, 0.09, { glide: 0.7 }),
    blip('sine', 1320, 1320, 0.08, 0.04, { at: 0.045 }),
  ],
  // Something brought up - a panel, the display itself: a filter opening on
  // a rising saw, a shimmer over it and a breath of noise under it.
  hud: [
    blip('sawtooth', 180, 720, 0.32, 0.06, { attack: 0.02, filter: { type: 'lowpass', from: 400, to: 3200, q: 6 } }),
    blip('sine', 880, 1760, 0.28, 0.04, { at: 0.08 }),
    hiss(0.3, 0.02, { type: 'bandpass', from: 1200, to: 6000, q: 0.9 }, { attack: 0.08 }),
  ],
  // ...and put away again: the same, closing.
  down: [
    blip('sawtooth', 720, 160, 0.26, 0.05, { filter: { type: 'lowpass', from: 2800, to: 300, q: 5 } }),
    blip('sine', 1320, 660, 0.18, 0.03),
  ],
  // A list folded away: two notes stepping down. Unfolded: stepping up.
  fold: [
    blip('triangle', 880, 880, 0.06, 0.07),
    blip('triangle', 587, 587, 0.08, 0.07, { at: 0.06 }),
  ],
  unfold: [
    blip('triangle', 587, 587, 0.06, 0.07),
    blip('triangle', 880, 880, 0.08, 0.07, { at: 0.06 }),
  ],
  // Apollo starts listening: a rising pair.
  listen: [
    blip('sine', 660, 990, 0.12, 0.07, { glide: 0.5 }),
    blip('sine', 990, 1320, 0.16, 0.06, { at: 0.09, glide: 0.5 }),
  ],
  // What you said, heard: a soft two-note chime with a glint on top.
  heard: [
    blip('sine', 988, 988, 0.22, 0.09),
    blip('sine', 1319, 1319, 0.3, 0.08, { at: 0.07 }),
    blip('triangle', 1976, 1976, 0.12, 0.02, { at: 0.07 }),
  ],
  // OSIRIS linking up: a sonar ping and its echo.
  ping: [
    blip('sine', 1480, 1480, 0.6, 0.07, { attack: 0.003 }),
    blip('triangle', 740, 740, 0.12, 0.03),
    blip('sine', 1480, 1480, 0.45, 0.025, { at: 0.18, attack: 0.003 }),
  ],
  // Ultra mode sweeping its displays up: air rushing past, a tone riding it.
  swipe: [
    hiss(0.45, 0.04, { type: 'bandpass', from: 400, to: 5000, q: 1.5 }, { attack: 0.12 }),
    blip('sine', 440, 1760, 0.4, 0.03, { attack: 0.1 }),
  ],
  // The machine coming up, as the intro starts: a slow rising swell and a
  // sparkle as it lands.
  boot: [
    blip('sine', 110, 880, 0.7, 0.06, { attack: 0.2 }),
    blip('sawtooth', 55, 220, 0.6, 0.03, { attack: 0.15, filter: { type: 'lowpass', from: 300, to: 1800, q: 2 } }),
    blip('triangle', 1760, 1760, 0.25, 0.04, { at: 0.55 }),
  ],
  // Going to sleep, and waking.
  sleep: [
    blip('sine', 880, 110, 0.7, 0.05, { attack: 0.02 }),
    blip('triangle', 440, 55, 0.6, 0.03, { filter: { type: 'lowpass', from: 1200, to: 200, q: 1 } }),
  ],
  wake: [
    blip('sine', 220, 880, 0.35, 0.06, { attack: 0.05 }),
    blip('triangle', 1320, 1320, 0.15, 0.03, { at: 0.25 }),
  ],
  // LYLA's own two, from the old page: an alien button and a liquid hit -
  // soft, because she says something every few seconds while she chats.
  ly1: [
    blip('square', 420, 980, 0.16, 0.04, { filter: { type: 'bandpass', from: 1400, q: 4 }, wobble: { rate: 38, depth: 60 } }),
    blip('sine', 1960, 1960, 0.08, 0.03, { at: 0.1 }),
  ],
  ly2: [
    blip('sine', 1100, 180, 0.14, 0.06, { glide: 0.6 }),
    hiss(0.03, 0.025, { type: 'lowpass', from: 1800, q: 0.7 }, { attack: 0.001 }),
  ],
};

// Half a second of white noise, made once per context.
const noiseFor = new WeakMap();
function noise(ctx) {
  let buffer = noiseFor.get(ctx);
  if (!buffer) {
    buffer = ctx.createBuffer(1, Math.floor(ctx.sampleRate * 0.5), ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    noiseFor.set(ctx, buffer);
  }
  return buffer;
}

// A parameter swept from one value to another, exponentially - the way
// pitch is heard - or held where there is nowhere to go.
function sweep(param, from, to, start, end) {
  param.setValueAtTime(from, start);
  if (to !== undefined && to !== from) param.exponentialRampToValueAtTime(to, end);
}

/* Sound `name` built into `ctx` to play at `when`, into `out`. Returns the
 * sources it started, each already told when to stop. */
export function schedule(ctx, out, name, when) {
  const sources = [];
  for (const voice of SOUNDS[name] || []) {
    const start = when + (voice.at || 0);
    const end = start + voice.dur;
    const attack = Math.min(voice.attack ?? 0.004, voice.dur / 2);

    let src;
    if (voice.wave === 'noise') {
      src = ctx.createBufferSource();
      src.buffer = noise(ctx);
    } else {
      src = ctx.createOscillator();
      src.type = voice.wave;
      sweep(src.frequency, voice.from, voice.to, start, start + voice.dur * (voice.glide ?? 1));
      if (voice.wobble) {
        const lfo = ctx.createOscillator();
        const depth = ctx.createGain();
        lfo.frequency.setValueAtTime(voice.wobble.rate, start);
        depth.gain.setValueAtTime(voice.wobble.depth, start);
        lfo.connect(depth);
        depth.connect(src.frequency);
        lfo.start(start);
        lfo.stop(end + 0.02);
      }
    }

    // From silence, up to its peak, and away to silence again - never a
    // step, which is what a click is.
    const env = ctx.createGain();
    env.gain.setValueAtTime(0, start);
    env.gain.linearRampToValueAtTime(voice.gain, start + attack);
    env.gain.exponentialRampToValueAtTime(0.0001, end);
    env.gain.linearRampToValueAtTime(0, end + 0.01);
    src.connect(env);

    let tail = env;
    if (voice.filter) {
      const filter = ctx.createBiquadFilter();
      filter.type = voice.filter.type;
      filter.Q.setValueAtTime(voice.filter.q ?? 1, start);
      sweep(filter.frequency, voice.filter.from, voice.filter.to, start, end);
      env.connect(filter);
      tail = filter;
    }
    tail.connect(out);

    src.start(start);
    src.stop(end + 0.02);
    sources.push(src);
  }
  return sources;
}

/* The page's player. `make` makes the context (a real AudioContext on the
 * page); nothing is made until the first sound is asked for. */
export class Sfx {
  constructor({ make = () => new (window.AudioContext || window.webkitAudioContext)(),
                muted = false, volume = 1, gap = 0.05 } = {}) {
    this.make = make;
    this.muted = muted;
    this.volume = volume;
    this.gap = gap;
    this.ctx = null;
    this.out = null;
    this.broken = false;
    this.last = {};
  }

  /* Sound `name`, now. True when it was played. */
  play(name) {
    if (this.muted || this.broken || !SOUNDS[name]) return false;
    if (!this.ctx) {
      try {
        this.ctx = this.make();
        this.out = this.ctx.createGain();
        this.out.gain.setValueAtTime(this.volume, this.ctx.currentTime);
        this.out.connect(this.ctx.destination);
      } catch (err) {
        // No Web Audio here: the display works as it did, silently.
        this.broken = true;
        this.ctx = null;
        return false;
      }
    }
    const ctx = this.ctx;
    if (ctx.state === 'suspended' && ctx.resume) ctx.resume().catch(() => {});
    const now = ctx.currentTime;
    if (this.last[name] !== undefined && now - this.last[name] < this.gap) return false;
    this.last[name] = now;
    schedule(ctx, this.out, name, now + 0.005);
    return true;
  }
}
