// The display's ground: an old set's own pixels, each lit by a broad band
// of colour flowing underneath it, seen through the bulge of the tube.
//
// Plain WebGL - three.js would be 600 KB to draw two triangles. All in one
// pass:
//   - the colour: one wide band of light leaning across the tube from the
//     top left to the bottom right - warm below it, going red to orange to
//     yellow, pale along its ridge, and cool above it, going teal to blue
//     to night - the CRT gradient of the reference picture. It flows, and
//     fast: its ridge sways and slides across the screen and a wave runs
//     along it, quick enough to watch. Asleep, it settles into a dusk horizon
//     instead, as slow as ever - navy
//     overhead, the last orange low down - which is the idle screen's sky.
//   - the pixels: a slot mask, as fine as a set's - cells of a red, a green
//     and a blue slot, six screen pixels across, alternate columns half a
//     cell apart - laid lightly over the colour, so the gradient reads
//     smooth from a chair away and shows its pixels up close. Over them,
//     soft scanlines, and faint ripples crawling up the glass the way the
//     reference picture has them.
//   - the glass: a fisheye that swells the middle of the picture and pinches
//     its corners, which go dark the way a tube's did.
//   - the set it is on: lit, not still - a breath of brightness a second or
//     so, and now and then the faintest dip - never anything you would call
//     a flicker. Decided in JavaScript once a frame and handed in; a
//     whisper of static is hashed here per pixel.
// Drawn at 55 frames a second or more, on evenly spaced frames of the
// screen's own rate, so that what little moves moves smoothly. Dimmed
// throughout: the panels sit on it and have to stay readable.

// The band of colour runs on its own clock, this many times the ground's:
// fast enough to watch it flow - its ridge sliding across the screen and a
// wave running along it - where it used to sway on loops of a minute and
// more. The idle sky keeps the ground's slow clock.
export const FLOW = 12;
// How far the band's middle wanders either way, across the screen (which is
// about 3.6 of these wide).
export const WANDER = 0.55;

const VERTEX = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;

const FRAGMENT = `
precision highp float;
const float FLOW = ${FLOW.toFixed(1)};
const float WANDER = ${WANDER.toFixed(2)};
uniform vec2 resolution;
uniform float time;
uniform float sleep;      // 0 awake, 1 asleep - eased, so the sky changes slowly
uniform float pitch;      // one cell of the mask - red, green and blue slot - in device pixels
uniform float flicker;    // the tube's brightness this frame: a breath under 1
uniform float shimmer;    // how much the lines shimmer against each other this frame
uniform float grain;      // a fresh seed every frame, for the static
uniform float osiris;     // 0 Apollo's colours, 1 OSIRIS's - gold and cyan in the void - eased

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float fbm(vec2 p) {
  float value = 0.0, weight = 0.5;
  for (int i = 0; i < 4; i++) { value += weight * noise(p); p *= 2.03; weight *= 0.5; }
  return value;
}

// The band's colour at u, across it: warm below the ridge (u < 0), cool
// above it (u > 0), pale along it - the stops read off the reference
// picture and brightened a little, since the whole ground is dimmed under
// the panels. With OSIRIS up, the same band in its colours: gold on the warm
// side, its cyan and blue on the cool, the night a void.
vec3 ramp(float u) {
  vec3 c0 = mix(vec3(0.30, 0.07, 0.07), vec3(0.22, 0.16, 0.05), osiris);
  vec3 c1 = mix(vec3(0.62, 0.20, 0.10), vec3(0.58, 0.44, 0.12), osiris);
  vec3 c2 = mix(vec3(0.80, 0.46, 0.17), vec3(0.83, 0.69, 0.22), osiris);
  vec3 c3 = mix(vec3(0.78, 0.70, 0.30), vec3(0.94, 0.82, 0.38), osiris);
  vec3 c4 = mix(vec3(0.68, 0.74, 0.66), vec3(0.80, 0.92, 0.90), osiris);
  vec3 c5 = mix(vec3(0.36, 0.60, 0.74), vec3(0.00, 0.80, 0.95), osiris);
  vec3 c6 = mix(vec3(0.14, 0.42, 0.66), vec3(0.10, 0.40, 0.85), osiris);
  vec3 c7 = mix(vec3(0.07, 0.13, 0.28), vec3(0.03, 0.05, 0.16), osiris);
  vec3 c = c0;
  c = mix(c, c1, smoothstep(-1.70, -1.05, u));
  c = mix(c, c2, smoothstep(-1.05, -0.60, u));
  c = mix(c, c3, smoothstep(-0.60, -0.25, u));
  c = mix(c, c4, smoothstep(-0.25, 0.05, u));
  c = mix(c, c5, smoothstep(0.05, 0.45, u));
  c = mix(c, c6, smoothstep(0.45, 0.95, u));
  c = mix(c, c7, smoothstep(0.95, 1.60, u));
  return c;
}

// The band, awake, at s. q is centred and aspect-correct: x runs about
// -1.8..1.8 on a 16:9 screen, y -1..1, upwards. The ridge leans from the top
// left down to the bottom right and sways either way while its middle slides
// across the screen; it is not quite straight, but carries a wave that runs
// along it.
// Brightest in the middle of the screen, so both far corners - the warm
// one low on the left and the cool one high on the right - go dark, as in
// the picture. (No backticks in here: this is a template string, and one
// would end it.)
vec3 band(vec2 q, float s) {
  float lean = -0.85 + 0.12 * sin(s * 0.070) + 0.05 * sin(s * 0.043 + 1.7);
  vec2 along = vec2(cos(lean), sin(lean));
  vec2 across = vec2(-along.y, along.x);
  vec2 middle = vec2(-0.20 + WANDER * sin(s * 0.037), 0.10 * cos(s * 0.029));
  vec2 d = q - middle;
  float v = dot(d, along);
  float u = dot(d, across) + 0.14 * sin(v * 1.2 + s * 0.090) + 0.06 * sin(v * 2.7 - s * 0.061);
  return ramp(u) * mix(0.55, 1.0, exp(-v * v / 9.0));
}

// The same dots at dusk: the idle screen's sky, from its reference photo.
vec3 dusk(vec2 q, float t, float aspect) {
  float y = q.y;                                   // -1 at the bottom, 1 at the top
  float horizon = -0.54;
  float h = y - horizon;                           // height above the line
  vec3 night = vec3(0.11, 0.17, 0.34);
  vec3 dusky = vec3(0.40, 0.28, 0.40);
  vec3 ember = vec3(0.96, 0.47, 0.22);
  vec3 water = vec3(0.13, 0.09, 0.09);
  // Mostly night, as in the photo: the warmth is a strip just above the
  // line, going dusky purple and then navy within a fifth of the screen.
  vec3 sky = mix(ember * 0.72, dusky, smoothstep(0.0, 0.26, h));
  sky = mix(sky, night, smoothstep(0.22, 1.1, h));
  // A band of cloud just over the horizon, drifting.
  float band = exp(-pow((h - 0.12) * 7.0, 2.0));
  float cloud = smoothstep(0.50, 0.76, fbm(vec2(q.x * 2.2 + t * 0.02, y * 10.0)));
  sky *= 1.0 - band * cloud * 0.8;
  // The glow is brightest just above the line and towards the right, where
  // the sun went down in the photo.
  float glow = exp(-pow(h * 4.6, 2.0)) * (0.45 + 0.55 * smoothstep(-aspect, aspect, q.x));
  sky += ember * glow * 0.34;
  // Below the line: still water, holding a little of it.
  float below = smoothstep(0.02, -0.04, h);
  vec3 sea = water + ember * 0.15 * exp(h * 4.0)
           * (0.7 + 0.3 * noise(vec2(q.x * 30.0, y * 90.0 + t * 0.3)));
  return mix(sky, sea, below);
}

vec3 colourAt(vec2 q, float t, float aspect) {
  vec3 awake = band(q, t * FLOW);
  if (sleep <= 0.001) return awake;
  // The idle sky keeps the slow pace it always had: it is meant to be restful.
  return mix(awake, dusk(q, t * 0.38, aspect), sleep);
}

// Where the picture is for a point on the glass: the fisheye samples nearer
// the middle there, so the middle swells and the corners pinch.
const float K = 0.30;
vec2 bend(vec2 uv) {
  vec2 p = uv * 2.0 - 1.0;                         // -1..1 on both axes
  float r2 = dot(p, p) * 0.5;                      // 0 at the centre, 1 in a corner
  return p * (1.0 - K + K * r2 * 1.35);
}

void main() {
  float aspect = resolution.x / resolution.y;
  vec2 uv = gl_FragCoord.xy / resolution;
  vec2 bent = bend(uv);
  vec2 plane = bent * vec2(aspect, 1.0);
  float t = time;

  // The colour, taken at this pixel: the band is broad and smooth, and
  // sampling it a cell at a time would only draw the cells' edges into it.
  vec3 lit = colourAt(plane, t, aspect);

  // The mask: a set's own pixels, on the glass, square to the screen's -
  // cells of three slots, red, green and blue, alternate columns of cells
  // set half a cell apart, the way a slot mask is. It is not bent: the
  // phosphors are where they are, and it is the picture landing on them
  // that the tube bends. Laid on lightly - a fifth of the way from the
  // plain colour to the slots - so the band stays a gradient.
  vec2 px = gl_FragCoord.xy;
  float column = floor(px.x / pitch);
  float shift = mod(column, 2.0) * 0.5;
  vec2 inCell = vec2(fract(px.x / pitch), fract(px.y / pitch + shift));
  float third = inCell.x * 3.0;
  float slot = floor(third);
  float across = fract(third);
  vec3 gun = vec3(slot < 0.5 ? 1.0 : 0.0, abs(slot - 1.0) < 0.5 ? 1.0 : 0.0, slot > 1.5 ? 1.0 : 0.0);
  float shape = smoothstep(0.0, 0.3, across) * smoothstep(1.0, 0.7, across)
              * smoothstep(0.0, 0.16, inCell.y) * smoothstep(1.0, 0.84, inCell.y);
  vec3 colour = lit * mix(vec3(1.0), gun * shape * 2.5, 0.22);

  // Soft scanlines: one screen row in three a little darker.
  colour *= mod(floor(px.y), 3.0) < 1.0 ? 0.88 : 1.0;
  // The ripples of the reference picture: faint wavy lines across the glass,
  // a dozen pixels apart, crawling slowly up it. None at dusk.
  float wave = sin(px.y * 0.52 + 2.2 * sin(px.x * 0.011 + t * 0.35) - t * 0.8);
  colour *= 1.0 + 0.035 * wave * (1.0 - sleep);
  // The lines breathing against each other, a pair of screen rows at a
  // time - barely.
  colour *= 1.0 + (hash(vec2(floor(px.y * 0.5), grain * 0.37)) - 0.5) * 0.02 * shimmer;
  // A whisper of static, finer than the pixels, new every frame.
  colour += (hash(px * 0.73 + grain) - 0.5) * 0.015;
  colour *= flicker;

  // The tube's corners: dark, and rounded by the same bend.
  vec2 corner = abs(bent);
  float tube = smoothstep(1.02, 0.80, max(corner.x, corner.y))
             * smoothstep(1.55, 0.95, length(corner));
  colour *= mix(0.25, 1.0, tube);

  // Dim enough to read over, and a floor that is not quite black - darker
  // still with OSIRIS up, whose ground is a void with a little blue in it.
  float dim = 0.62 * mix(1.0, 0.62, osiris);
  vec3 ground = mix(vec3(0.014, 0.012, 0.018), vec3(0.016, 0.016, 0.040), osiris);
  gl_FragColor = vec4(colour * dim + ground, 1.0);
}
`;

// The ground's clock: units of its own time a second.
const DRIFT = 1.0;
// A breath, never a flicker: the deepest the tube's brightness goes.
const FLICKER_FLOOR = 0.96;
// The fewest frames a second the ground is drawn at, screen allowing.
const SMOOTH = 55;

/* The ground's clock, a second: and half that for anyone who asked for
 * less motion. */
export function driftPerSecond(still) {
  return DRIFT * (still ? 0.5 : 1);
}

/* ...and the band's, on top of it: fast. */
export function bandPerSecond(still) {
  return driftPerSecond(still) * FLOW;
}

/* How bright the tube is this frame, as a share of itself: a shimmer every
 * frame (shimmer, 0..1), a slow breath under it (hum, 0..1) and now and then
 * the faintest dip (dip, 0..1, falling away over a few frames) - all of it
 * scaled by `calm`, and never below FLICKER_FLOOR. Alive the way a lit tube
 * is, and nothing you would notice: the ground is looked at for hours. */
export function flickerLevel({ shimmer = 0, hum = 0, dip = 0, calm = 1 }) {
  const fall = (shimmer * 0.006 + hum * 0.006 + dip * 0.02) * calm;
  return Math.max(FLICKER_FLOOR, 1 - fall);
}

/* On how many of the screen's frames to draw one, for a screen whose frames
 * come `interval` ms apart: as few as keep the ground at SMOOTH a second or
 * more, evenly spaced - every frame at 60Hz, every other at 144, every
 * third at 165 - so the light moves smoothly without a full-resolution pass
 * on every refresh of a fast screen. */
export function framesPerDraw(interval) {
  if (!(interval > 0)) return 1;
  return Math.max(1, Math.floor(1000 / interval / SMOOTH));
}

export class Shader {
  constructor(canvas, { scale = 1, pitch = 6 } = {}) {
    this.canvas = canvas;
    this.scale = scale;
    this.pitch = pitch;
    this.gl = canvas.getContext('webgl', { antialias: false, depth: false });
    this.time = 1.0;
    this.rate = 1.0;
    this.sleepValue = 0.0;
    this.sleepTarget = 0.0;
    this.frame = null;
    this.last = 0;
    // The tube's breathing, decided a frame at a time (see `_set`).
    this.flicker = 1.0;
    this.dip = 0.0;
    this.shimmer = 1.0;
    this.osirisValue = 0.0;
    this.osirisTarget = 0.0;
    // Asked for less motion, the set is steadier and the light slower.
    this.still = typeof matchMedia === 'function'
      && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (this.gl) this._build();
  }

  _build() {
    const gl = this.gl;
    const compile = (type, source) => {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        // Written where the probe can read it; a blank background is the
        // only other sign that this failed.
        console.error('shader:', gl.getShaderInfoLog(shader));
      }
      return shader;
    };
    const program = gl.createProgram();
    gl.attachShader(program, compile(gl.VERTEX_SHADER, VERTEX));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FRAGMENT));
    gl.linkProgram(program);
    gl.useProgram(program);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const position = gl.getAttribLocation(program, 'position');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    this.resolution = gl.getUniformLocation(program, 'resolution');
    this.clock = gl.getUniformLocation(program, 'time');
    this.sleepUniform = gl.getUniformLocation(program, 'sleep');
    this.pitchUniform = gl.getUniformLocation(program, 'pitch');
    this.flickerUniform = gl.getUniformLocation(program, 'flicker');
    this.grainUniform = gl.getUniformLocation(program, 'grain');
    this.osirisUniform = gl.getUniformLocation(program, 'osiris');
    this.shimmerUniform = gl.getUniformLocation(program, 'shimmer');
    this.resize();
  }

  resize() {
    if (!this.gl) return;
    // The screen's own pixels: a mask of slots two pixels wide, rendered any
    // smaller and stretched, is a smudge. On a scaled screen the cells keep
    // their size on the glass.
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.floor(window.innerWidth * ratio * this.scale));
    const height = Math.max(1, Math.floor(window.innerHeight * ratio * this.scale));
    this.canvas.width = width;
    this.canvas.height = height;
    this.gl.viewport(0, 0, width, height);
    this.gl.uniform2f(this.resolution, width, height);
    this.gl.uniform1f(this.pitchUniform, Math.max(3, Math.round(this.pitch * ratio * this.scale)));
    this.draw();
  }

  speed(rate) { this.rate = rate; }

  // Asleep, the phosphors settle into the dusk sky; awake, back. Eased over
  // a few seconds, the way light changes.
  sleep(on) { this.sleepTarget = on ? 1 : 0; }

  // OSIRIS up: the lights go over to its colours, in about a second.
  theme(osiris) { this.osirisTarget = osiris ? 1 : 0; }

  /* One frame of the tube: a shimmer too small to see as such, a slow
   * breath of about a second under it, and once in a while the faintest dip,
   * gone in a quarter second. `dt` in seconds, `now` in ms. Chances are per
   * second, not per frame, so it behaves the same at any frame rate. Quieter
   * asleep, and quieter still for anyone who asked for less motion. */
  _set(dt, now) {
    const calm = (1 - this.sleepValue * 0.7) * (this.still ? 0.3 : 1);
    this.dip *= Math.pow(0.02, dt);
    if (Math.random() < dt * 0.12) this.dip = 0.5 + Math.random() * 0.5;
    this.flicker = flickerLevel({
      shimmer: Math.random(),
      hum: 0.5 + 0.5 * Math.sin((now / 1000) * Math.PI * 2 * 0.9),
      dip: this.dip,
      calm,
    });
    this.shimmer = calm;
  }

  draw() {
    if (!this.gl) return;
    const gl = this.gl;
    gl.uniform1f(this.clock, this.time);
    gl.uniform1f(this.sleepUniform, this.sleepValue);
    gl.uniform1f(this.flickerUniform, this.flicker);
    gl.uniform1f(this.grainUniform, Math.random() * 97.0);
    gl.uniform1f(this.osirisUniform, this.osirisValue);
    gl.uniform1f(this.shimmerUniform, this.shimmer);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  start() {
    if (!this.gl || this.frame !== null) return;
    this.last = performance.now();
    let previous = this.last;
    let interval = 1000 / 60;         // the screen's own frame time, learned as it goes
    let waited = 0;                   // the screen's frames since the last one drawn
    const tick = (now) => {
      // Drawn on evenly spaced frames of the screen's own rate, at 55 a
      // second or more (framesPerDraw). Time is taken from the clock, so
      // the drift is the same speed on any screen.
      const gap = now - previous;
      previous = now;
      if (gap > 0 && gap < 100) interval += (gap - interval) * 0.05;
      if (++waited >= framesPerDraw(interval)) {
        waited = 0;
        const dt = Math.min(0.1, (now - this.last) / 1000);
        this.last = now;
        this.time += dt * driftPerSecond(this.still) * this.rate;
        this.sleepValue += (this.sleepTarget - this.sleepValue) * Math.min(1, dt * 1.05);
        this.osirisValue += (this.osirisTarget - this.osirisValue) * Math.min(1, dt * 3.2);
        this._set(dt, now);
        this.draw();
      }
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  stop() {
    // Nothing is watching while the overlay has the screen, and a shader that
    // keeps drawing to a hidden window is a GPU burning for nobody.
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.frame = null;
  }
}
