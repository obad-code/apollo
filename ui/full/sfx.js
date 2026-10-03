/* The display's sounds, made on the spot: no files, just Web Audio - a few
 * oscillators and a little noise, each swept in pitch and shaped by its own
 * envelope, the way an old synth makes a blip. Short and quiet, because they
 * are the interface's and Apollo's voice is the one you listen to.
 *
 * SOUNDS is the recipes, schedule() builds one into a context, and Sfx is
 * the player the page keeps: it makes its context only when first asked,
 * wakes it if it is still waiting for a gesture, and plays a sound only
 * once when it is asked for twice at once - a pointer
 * sweeping over a row of buttons ticks, it does not buzz. tests/test_sfx.py
 * runs it against a stand-in for Web Audio.
 *
 * A voice: `wave` (an oscillator's type, or 'noise'), `at` seconds into the
 * sound, `dur` seconds long, `gain` at its peak after `attack`, its pitch
 * swept `from` -> `to` over `glide` of its length, and optionally a `filter`
 * ({ type, from, to, q }) and a `wobble` ({ rate, depth }: vibrato, in Hz). */

const blip = (wave, from, to, dur, gain, more = {}) => ({ wave, from, to, dur, gain, ...more });

/* A bell: a struck tone and the two inharmonic partials over it that make
 * metal sound like metal, each dying faster than the one under it. */
const bell = (hz, gain, more = {}) => [
  blip('sine', hz, hz, more.dur ?? 0.7, gain, { attack: 0.003, ...more }),
  blip('sine', hz * 2.76, hz * 2.76, (more.dur ?? 0.7) * 0.45, gain * 0.32, { attack: 0.002, ...more }),
  blip('sine', hz * 5.4, hz * 5.4, (more.dur ?? 0.7) * 0.2, gain * 0.14, { attack: 0.001, ...more }),
];
const hiss = (dur, gain, filter, more = {}) => ({ wave: 'noise', dur, gain, filter, ...more });

/* A cloud of grains, the way a granular synth makes a sound: `count` tiny
 * blips of `len` seconds scattered over `span`, their pitch going `from` ->
 * `to` across it, each a little off the line. The scatter is a fixed table
 * rather than Math.random, so a sound is the same every time it plays. */
const SCATTER = [0.13, 0.71, 0.42, 0.93, 0.27, 0.58, 0.05, 0.84, 0.36, 0.66, 0.19, 0.49, 0.77, 0.31, 0.88, 0.02];
function grains({ count, span, from, to, len = 0.026, gain = 0.018, wave = 'triangle', at = 0,
                  spread = 0.12, filter }) {
  const out = [];
  for (let i = 0; i < count; i++) {
    const p = count === 1 ? 0 : i / (count - 1);
    const jitter = SCATTER[i % SCATTER.length];
    const hz = from * Math.pow(to / from, p) * (1 + (jitter - 0.5) * spread);
    out.push(blip(wave, hz, hz * (1 + (jitter - 0.5) * 0.04), len, gain,
                  { at: at + p * span + (jitter - 0.5) * (span / count) * 0.6 + span / count * 0.3,
                    attack: 0.002, ...(filter ? { filter } : {}) }));
  }
  return out;
}

export const SOUNDS = {
  // A pointer over a button: the lightest tick.
  tick: [
    blip('sine', 3200, 2600, 0.022, 0.03, { attack: 0.002, space: 0.2 })
  ],
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
    // Apollo about to answer: a bright arpeggio of bells walking across
    // the room, left to right, over a soft swell.
    blip('sine', 262, 392, 0.4, 0.03, { attack: 0.08, unison: 3, filter: { type: 'lowpass', from: 900, q: 0.6 }, space: 0.6 }),
    ...bell(1047, 0.03, { dur: 0.45, pan: -0.6, space: 0.8 }),
    ...bell(1319, 0.028, { dur: 0.45, at: 0.06, pan: 0, space: 0.8 }),
    ...bell(1568, 0.026, { dur: 0.5, at: 0.12, pan: 0.6, space: 0.8 }),
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
    // Apollo starts listening: a breath opening, two notes rising through
    // it from the left and the right, and a glint as they meet.
    hiss(0.32, 0.018, { type: 'bandpass', from: 600, to: 3400, q: 1.1 }, { attack: 0.12, pan: 0, space: 0.6 }),
    blip('sine', 523, 784, 0.22, 0.05, { glide: 0.55, pan: -0.5, unison: 3, space: 0.5 }),
    blip('sine', 784, 1047, 0.26, 0.045, { at: 0.08, glide: 0.5, pan: 0.5, unison: 3, space: 0.5 }),
    blip('triangle', 2093, 2093, 0.12, 0.012, { at: 0.2, pan: 0.2, space: 0.8 }),
  ],
  // What you said, heard: a soft two-note chime with a glint on top.
  heard: [
    // What you said, heard: a small glass bell, then its fifth, warm under
    // the room's reverb.
    ...bell(1047, 0.05, { dur: 0.55, pan: -0.25, space: 0.7 }),
    ...bell(1568, 0.035, { dur: 0.6, at: 0.07, pan: 0.25, space: 0.7 }),
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
    // Waking: a slow chord swelling out of the dark, and a sparkle on top.
    blip('sine', 220, 440, 0.6, 0.035, { attack: 0.18, unison: 3, pan: -0.3, space: 0.7 }),
    blip('sine', 330, 660, 0.6, 0.03, { attack: 0.2, unison: 3, pan: 0.3, space: 0.7 }),
    ...grains({ count: 6, span: 0.2, from: 1800, to: 3600, wave: 'sine', gain: 0.012, at: 0.4 }),
  ],
  // --- the granular family: a sound for every change on the display -------
  // A display expanded, or restored: grains rising, a swell under them.
  expand: [
    ...grains({ count: 10, span: 0.22, from: 520, to: 2400 }),
    blip('sine', 300, 900, 0.26, 0.04, { attack: 0.04 }),
  ],
  // ...and put back, or minimized: falling.
  collapse: [
    ...grains({ count: 10, span: 0.2, from: 2200, to: 460 }),
    blip('sine', 900, 260, 0.22, 0.035, { attack: 0.01 }),
  ],
  // A display, a panel or a list shown, and hidden.
  show: [...grains({ count: 7, span: 0.14, from: 900, to: 2600, wave: 'sine', gain: 0.022 })],
  hide: [...grains({ count: 7, span: 0.14, from: 2400, to: 700, wave: 'sine', gain: 0.022 })],
  // Two displays trading places: a thunk each, and a glint between them.
  swap: [
    blip('triangle', 230, 160, 0.06, 0.07, { attack: 0.002 }),
    ...grains({ count: 6, span: 0.1, from: 1400, to: 1900, gain: 0.014, at: 0.03 }),
    blip('triangle', 200, 140, 0.07, 0.07, { at: 0.1, attack: 0.002 }),
  ],
  // One grain: a display's corner passing a cell as it is resized.
  grain: [blip('triangle', 2400, 2300, 0.018, 0.03, { attack: 0.002 })],
  // A mode switched: the set changing channel - static, a fizz of grains
  // and the tube's whine.
  channel: [
    hiss(0.12, 0.05, { type: 'bandpass', from: 3200, to: 1400, q: 0.8 }, { attack: 0.004 }),
    ...grains({ count: 8, span: 0.12, from: 4200, to: 1200, wave: 'square', gain: 0.011,
                filter: { type: 'lowpass', from: 6000, q: 0.7 } }),
    blip('sine', 9000, 8800, 0.1, 0.008, { attack: 0.01 }),
  ],
  // Something opened - a story, a stock, a display's settings - and closed.
  open: [
    ...grains({ count: 6, span: 0.1, from: 700, to: 1800, gain: 0.016 }),
    blip('sine', 880, 880, 0.08, 0.03, { at: 0.06 }),
  ],
  close: [
    ...grains({ count: 6, span: 0.1, from: 1800, to: 700, gain: 0.016 }),
    blip('sine', 660, 660, 0.08, 0.025, { at: 0.06 }),
  ],
  // The boot screen: a check passing, a check failing, and the machine
  // ready - grains climbing into a chord.
  check: [
    blip('square', 1800, 1700, 0.02, 0.025, { attack: 0.002, filter: { type: 'lowpass', from: 4000, q: 0.7 } }),
    ...grains({ count: 3, span: 0.03, from: 2600, to: 3000, gain: 0.012, at: 0.015 }),
  ],
  fault: [
    blip('square', 180, 150, 0.18, 0.05, { filter: { type: 'lowpass', from: 900, q: 1.5 } }),
    ...grains({ count: 4, span: 0.1, from: 420, to: 300, gain: 0.02, at: 0.04 }),
  ],
  ready: [
    ...grains({ count: 12, span: 0.42, from: 400, to: 3200, gain: 0.015 }),
    blip('sine', 523, 523, 0.5, 0.04, { at: 0.3, attack: 0.02 }),
    blip('sine', 784, 784, 0.48, 0.03, { at: 0.36, attack: 0.02 }),
    blip('sine', 1046, 1046, 0.44, 0.02, { at: 0.42, attack: 0.02 }),
  ],
  // The scanner: a file landing on it, the sweep while it reads, and the
  // answer - clean, or something to look at.
  drop: [
    blip('sine', 180, 90, 0.12, 0.08, { attack: 0.003 }),
    ...grains({ count: 6, span: 0.08, from: 3000, to: 1500, gain: 0.015, at: 0.01 }),
  ],
  scan: [
    ...grains({ count: 14, span: 0.6, from: 300, to: 3000, gain: 0.012, wave: 'sine' }),
    blip('sine', 200, 1200, 0.6, 0.03, { attack: 0.05 }),
  ],
  clean: [
    blip('sine', 880, 880, 0.1, 0.05),
    blip('sine', 1318, 1318, 0.16, 0.05, { at: 0.08 }),
    ...grains({ count: 4, span: 0.08, from: 2600, to: 3200, gain: 0.01, at: 0.1 }),
  ],
  alert: [
    // Something that needs you - big market news: three bells climbing a
    // minor triad over a low pulse, urgent without being an alarm.
    blip('sine', 110, 110, 0.5, 0.05, { attack: 0.01, unison: 2, space: 0.3 }),
    ...bell(880, 0.04, { dur: 0.5, pan: -0.4, space: 0.6 }),
    ...bell(1047, 0.04, { dur: 0.5, at: 0.12, pan: 0, space: 0.6 }),
    ...bell(1319, 0.045, { dur: 0.6, at: 0.24, pan: 0.4, space: 0.6 }),
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

    // Unison: copies of the oscillator a few cents either side, into the same
    // envelope - the width a chorus gives. Only the first is counted as the
    // voice's source; the copies start and stop with it.
    const extra = [];
    if (voice.unison > 1 && voice.wave !== 'noise' && src.detune) {
      for (let u = 1; u < voice.unison; u++) {
        const copy = ctx.createOscillator();
        copy.type = voice.wave;
        sweep(copy.frequency, voice.from, voice.to, start, start + voice.dur * (voice.glide ?? 1));
        copy.detune.setValueAtTime((u % 2 ? 1 : -1) * 7 * Math.ceil(u / 2), start);
        extra.push(copy);
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
    for (const copy of extra) {
      const share = ctx.createGain();
      share.gain.setValueAtTime(0.6, start);
      copy.connect(share);
      share.connect(env);
    }

    let tail = env;
    if (voice.filter) {
      const filter = ctx.createBiquadFilter();
      filter.type = voice.filter.type;
      filter.Q.setValueAtTime(voice.filter.q ?? 1, start);
      sweep(filter.frequency, voice.filter.from, voice.filter.to, start, end);
      env.connect(filter);
      tail = filter;
    }
    // Where it sits, left to right, and how much of it goes to the room.
    if (voice.pan && ctx.createStereoPanner) {
      const panner = ctx.createStereoPanner();
      panner.pan.setValueAtTime(voice.pan, start);
      tail.connect(panner);
      tail = panner;
    }
    tail.connect(out);
    if (voice.space && out.room) {
      const send = ctx.createGain();
      send.gain.setValueAtTime(voice.space, start);
      tail.connect(send);
      send.connect(out.room);
    }

    src.start(start);
    src.stop(end + 0.02);
    for (const copy of extra) { copy.start(start); copy.stop(end + 0.02); }
    sources.push(src);
  }
  return sources;
}

/* The bus every sound ends on: a gentle compressor, so a stack of them
 * never clips, and a room - a reverb from an impulse made here, two
 * seconds of decaying noise, darker as it dies - that sounds can send to
 * (`space`). Where the context has no such nodes, the sounds go straight
 * out, dry. */
function room(ctx, into) {
  if (!ctx.createConvolver) return null;
  const seconds = 1.6, length = Math.floor(ctx.sampleRate * seconds);
  const impulse = ctx.createBuffer(2, length, ctx.sampleRate);
  for (let channel = 0; channel < 2; channel++) {
    const data = impulse.getChannelData(channel);
    let low = 0;
    for (let i = 0; i < length; i++) {
      const t = i / length;
      low += ((Math.random() * 2 - 1) - low) * (0.5 - t * 0.4);    // darker as it decays
      data[i] = low * Math.pow(1 - t, 3.2);
    }
  }
  const verb = ctx.createConvolver();
  verb.buffer = impulse;
  const wet = ctx.createGain();
  wet.gain.setValueAtTime(0.32, ctx.currentTime);
  verb.connect(wet);
  wet.connect(into);
  return verb;
}

function master(ctx) {
  if (!ctx.createDynamicsCompressor) return ctx.destination;
  const glue = ctx.createDynamicsCompressor();
  glue.threshold.setValueAtTime(-18, ctx.currentTime);
  glue.ratio.setValueAtTime(3, ctx.currentTime);
  glue.attack.setValueAtTime(0.004, ctx.currentTime);
  glue.release.setValueAtTime(0.2, ctx.currentTime);
  glue.connect(ctx.destination);
  return glue;
}

/* The page's player. `make` makes the context (a real AudioContext on the
 * page); nothing is made until the first sound is asked for. */
export class Sfx {
  constructor({ make = () => new (window.AudioContext || window.webkitAudioContext)(),
                volume = 1, gap = 0.05 } = {}) {
    this.make = make;
    this.volume = volume;
    this.gap = gap;
    this.ctx = null;
    this.out = null;
    this.broken = false;
    this.last = {};
  }

  /* Sound `name`, now. True when it was played. */
  play(name) {
    if (this.broken || !SOUNDS[name]) return false;
    if (!this.ctx) {
      try {
        this.ctx = this.make();
        this.out = this.ctx.createGain();
        this.out.gain.setValueAtTime(this.volume, this.ctx.currentTime);
        const bus = master(this.ctx);
        this.out.connect(bus);
        this.out.room = room(this.ctx, bus);
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
