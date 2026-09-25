// The display's ground: space. Black, with a faint blue haze drifting
// through it, seen through a lattice of tiny triangles - the set's own pixels,
// if its pixels were triangles - and through the bulge of the tube.
//
// Plain WebGL - three.js would be 600 KB to draw two triangles. All in one
// pass:
//   - the colour: near black, and in it two soft clouds of blue drifting on
//     slow loops of their own, with a wider, fainter wash round the middle
//     where Apollo is. Asleep, it settles into a dusk horizon instead - navy
//     overhead, the last orange low down - which is the idle screen's sky.
//   - the pixels: tiny triangles, point up and point down in turn, row after
//     row, each smaller than its place so that black shows between them, and
//     each lit flat by the colour at its own middle. A few of them are stars:
//     brighter, bluish white, each twinkling on its own.
//   - the glass: a fisheye that swells the middle of the picture and pinches
//     its corners, which go dark the way a tube's did; soft scanlines over it.
//   - the set it is on: lit, not still - a breath of brightness a second or
//     so, and now and then the faintest dip - never anything you would call
//     a flicker. Decided in JavaScript once a frame and handed in; a
//     whisper of static is hashed here per pixel.
// Drawn at 55 frames a second or more, on evenly spaced frames of the
// screen's own rate, so that what little moves moves smoothly.

const VERTEX = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;

const FRAGMENT = `
precision highp float;
uniform vec2 resolution;
uniform float time;
uniform float sleep;      // 0 awake, 1 asleep - eased, so the sky changes slowly
uniform float pitch;      // one triangle of the lattice, side to side, in device pixels
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

// One soft cloud: a gaussian of the given size round the given point.
float lamp(vec2 q, vec2 at, float size) {
  vec2 d = q - at;
  return exp(-dot(d, d) / (size * size));
}

// Space, awake, at s. q is centred and aspect-correct: x runs about -1.8..1.8
// on a 16:9 screen, y -1..1, upwards. Two clouds of blue - a deep one high on
// the left, a paler one low on the right - drifting on their own slow loops,
// a faint wash round the middle, and a floor of blue so that every triangle
// is just there in the dark. With OSIRIS up, its gold and cyan instead.
// (No backticks in here: this is a template string, and one would end it.)
vec3 space(vec2 q, float s) {
  vec3 deep = mix(vec3(0.10, 0.28, 0.95), vec3(0.83, 0.69, 0.22), osiris);
  vec3 pale = mix(vec3(0.06, 0.55, 0.88), vec3(0.00, 0.90, 1.00), osiris);
  float a = lamp(q, vec2(-1.00 + 0.30 * sin(s * 0.050), 0.40 + 0.20 * cos(s * 0.041)), 1.15);
  float b = lamp(q, vec2(1.05 + 0.25 * cos(s * 0.043), -0.45 + 0.20 * sin(s * 0.037)), 0.95);
  float c = lamp(q, vec2(0.20 * sin(s * 0.031), 0.05 * cos(s * 0.027)), 1.6);
  return deep * a * 0.36 + pale * b * 0.26 + deep * c * 0.10 + mix(vec3(0.05, 0.09, 0.22), vec3(0.08), osiris) * 0.4;
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
  vec3 awake = space(q, t);
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

  // The lattice: rows of tiny triangles, a row's height a triangle's, every
  // other row set half a triangle along and pointing the other way. It is
  // not bent: the phosphors are where they are, and it is the picture
  // landing on them that the tube bends.
  vec2 px = gl_FragCoord.xy;
  float rowH = pitch * 0.866;
  float row = floor(px.y / rowH);
  float odd = mod(row, 2.0);
  float across = px.x / pitch + odd * 0.5;
  float col = floor(across);
  // Where in its triangle this pixel is: 0 at the point, 1 along the base.
  float fy = fract(px.y / rowH);
  float fromPoint = odd > 0.5 ? fy : 1.0 - fy;
  // Each triangle shrunk about its middle, so there is black between them.
  vec2 middle = vec2(0.5, 0.6667);
  vec2 p = middle + (vec2(fract(across), fromPoint) - middle) / 0.72;
  float inside = min(1.0 - p.y, (p.y * 0.5 - abs(p.x - 0.5)) * 1.79);
  float shape = smoothstep(0.0, 1.4 / (rowH * 0.72), inside);

  // Each triangle lit flat by the colour at its own middle.
  vec2 centre = vec2((col + 0.5 - odd * 0.5) * pitch,
                     (row + (odd > 0.5 ? 0.6667 : 0.3333)) * rowH);
  vec3 lit = colourAt(bend(centre / resolution) * vec2(aspect, 1.0), t, aspect);
  // A few are stars: bluish white, twinkling each on its own. None at dusk.
  float which = hash(vec2(col, row) * 0.731 + 11.3);
  float star = step(0.992, which) * (0.45 + 0.55 * sin(t * (1.1 + which * 2.3) + which * 91.0))
             * (1.0 - sleep);
  lit += vec3(0.62, 0.78, 1.0) * max(star, 0.0) * 1.3;
  // ...and a little of the colour between them too, as haze, so the clouds
  // read as clouds and not only as brighter triangles.
  vec3 colour = lit * shape + colourAt(plane, t, aspect) * 0.10;

  // Soft scanlines: one screen row in three a little darker.
  colour *= mod(floor(px.y), 3.0) < 1.0 ? 0.88 : 1.0;
  // The lines breathing against each other, a pair of screen rows at a
  // time - barely.
  colour *= 1.0 + (hash(vec2(floor(px.y * 0.5), grain * 0.37)) - 0.5) * 0.02 * shimmer;
  // A whisper of static, finer than the triangles, new every frame.
  colour += (hash(px * 0.73 + grain) - 0.5) * 0.008;
  colour *= flicker;

  // The tube's corners: dark, and rounded by the same bend.
  vec2 corner = abs(bent);
  float tube = smoothstep(1.02, 0.80, max(corner.x, corner.y))
             * smoothstep(1.55, 0.95, length(corner));
  colour *= mix(0.25, 1.0, tube);

  // Black under it all, with the least blue in it - a void with OSIRIS up.
  float dim = 0.9 * mix(1.0, 0.7, osiris);
  vec3 ground = mix(vec3(0.004, 0.005, 0.010), vec3(0.010, 0.010, 0.030), osiris);
  gl_FragColor = vec4(colour * dim + ground, 1.0);
}
`;

// How fast the band drifts: units of its own time a second.
const DRIFT = 1.0;
// A breath, never a flicker: the deepest the tube's brightness goes.
const FLICKER_FLOOR = 0.96;
// The fewest frames a second the ground is drawn at, screen allowing.
const SMOOTH = 55;

/* How far the band moves a second of the clock: slowly, and half that for
 * anyone who asked for less motion. */
export function driftPerSecond(still) {
  return DRIFT * (still ? 0.5 : 1);
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
  constructor(canvas, { scale = 1, pitch = 10 } = {}) {
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
    // The screen's own pixels: triangles a few pixels across, rendered any
    // smaller and stretched, are a smudge. On a scaled screen they keep their
    // size on the glass.
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
