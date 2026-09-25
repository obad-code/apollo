// The display's ground: an old set's own pixels, each lit by the colour
// drifting underneath it, seen through the bulge of the tube.
//
// Plain WebGL - three.js would be 600 KB to draw two triangles. Three layers,
// all in one pass:
//   - the colour: five soft lights - rose, cyan, amber, violet, green -
//     drifting across the tube on their own slow loops, so the gradient is
//     always moving, and blooming towards white where they cross; and over
//     them two folds of light like silk catching it, a warm one low across
//     the tube going red to amber to gold, and a cool blue one high on the
//     left - the CRT gradients of the reference pictures. Asleep, it
//     settles into a dusk horizon instead - navy overhead, the last orange
//     low down - which is the idle screen's sky.
//   - the pixels: a slot mask, as fine as a set's - cells of a red, a green
//     and a blue slot, six screen pixels across, alternate columns half a
//     cell apart. Each cell shows the colour at its own centre, so the
//     gradient is drawn in the set's pixels rather than washed across.
//     Where the picture is brightest, faint moire rings: a fine ring
//     pattern met by the mask, one sample a cell, beating into the broad
//     rings a set's glass showed when it was filmed.
//   - the glass: a fisheye that swells the middle of the picture and pinches
//     its corners, which go dark the way a tube's did. Over the pixels, the
//     bloom: the same lights, unbroken, as a haze - the glow a bright tube
//     threw past its own phosphors - and again much wider, the way it
//     spread across the glass round the brightest light, and each cell's
//     colour bleeding round it.
//   - the set it is on: the picture flickers - a shimmer every frame, a hum
//     of a few cycles a second, now and then a dip - its lines shimmer
//     against each other, a dark hum bar rolls slowly up it, a brighter band
//     rolls up it every few seconds, static crawls over it, and now and then
//     a few lines tear sideways for a frame. All but the static are decided
//     in JavaScript once a frame and handed in; the static is hashed here
//     per pixel.
// Drawn at 55 frames a second or more, on evenly spaced frames of the
// screen's own rate, so that the light moves smoothly. Dimmed throughout:
// the panels sit on it and have to stay readable.

const VERTEX = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;

const FRAGMENT = `
precision highp float;
uniform vec2 resolution;
uniform float time;
uniform float sleep;      // 0 awake, 1 asleep - eased, so the sky changes slowly
uniform float pitch;      // one cell of the mask - red, green and blue slot - in device pixels
uniform float flicker;    // the tube's brightness this frame: ~0.9-1, now and then a dip
uniform float hum;        // the dark hum bar's height, 0..1 up the screen, rolling
uniform float shimmer;    // how much the lines shimmer against each other this frame
uniform float roll;       // the rolling band's height, 0..1 up the screen (off it when there is none)
uniform float tear;       // how far a torn band of lines is pushed sideways
uniform float tearAt;     // ...and where that band is, 0..1 up the screen
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

// One soft light: a gaussian of the given size round the given point.
float lamp(vec2 q, vec2 at, float size) {
  vec2 d = q - at;
  return exp(-dot(d, d) / (size * size));
}

// A fold of light across the tube, like silk catching it: bright along a
// slow curve and falling away either side of it. The curve is two waves
// drifting against each other, so the fold never quite repeats.
float silk(vec2 q, float s, float y, float lift, float along, float turn, float width) {
  float crest = y + lift * sin(q.x * along + s * 0.090 + turn)
                  + lift * 0.45 * sin(q.x * along * 2.1 - s * 0.061 + turn * 1.7);
  float d = (q.y - crest) / width;
  return exp(-d * d);
}

// The lights, awake, at s. q is centred and aspect-correct: x runs about
// -1.8..1.8 on a 16:9 screen, y -1..1. Each light loops on its own pair of
// periods, so they never line up the same way twice and something on the
// screen is always on the move. The spread widens every light and fold
// alike - a gaussian blurred is a wider gaussian - which is how the bloom's
// wide glow is the same light, spread. (No backticks in here: this is a
// template string, and one would end it.)
vec3 lights(vec2 q, float s, float spread) {
  // With OSIRIS up, the same five lights in its colours: gold, its cyan, a
  // pale gold, its blue, and a teal kept low.
  vec3 rose   = mix(vec3(1.00, 0.26, 0.58), vec3(0.83, 0.69, 0.22), osiris);
  vec3 cyan   = mix(vec3(0.16, 0.78, 1.00), vec3(0.00, 0.90, 1.00), osiris);
  vec3 amber  = mix(vec3(1.00, 0.58, 0.12), vec3(0.94, 0.82, 0.38), osiris);
  vec3 violet = mix(vec3(0.50, 0.32, 1.00), vec3(0.27, 0.54, 1.00), osiris);
  vec3 green  = mix(vec3(0.20, 1.00, 0.62), vec3(0.00, 0.42, 0.48), osiris);
  vec3 sum = vec3(0.0);
  sum += rose   * lamp(q, vec2(-0.95 + 0.75 * sin(s * 0.110), 0.30 + 0.40 * cos(s * 0.083)), 0.78 * spread) * 0.72;
  sum += cyan   * lamp(q, vec2( 0.95 + 0.65 * cos(s * 0.093), -0.15 + 0.45 * sin(s * 0.140)), 0.74 * spread) * 0.72;
  sum += amber  * lamp(q, vec2( 0.10 + 0.95 * sin(s * 0.071 + 1.3), -0.62 + 0.30 * cos(s * 0.120)), 0.70 * spread) * 0.72;
  sum += violet * lamp(q, vec2( 0.35 + 0.85 * cos(s * 0.104 + 2.1), 0.62 + 0.30 * sin(s * 0.077)), 0.72 * spread) * 0.72;
  sum += green  * lamp(q, vec2(-0.45 + 0.70 * sin(s * 0.066 + 4.0), -0.30 + 0.50 * cos(s * 0.098)), 0.60 * spread) * 0.55;
  // The two folds of silk: the warm one low across the tube, red on the
  // left going amber and then gold to the right, with a bright edge along
  // its crest; the cool one high on the left, fading out across the middle.
  vec3 ember = mix(vec3(1.00, 0.16, 0.06), vec3(0.83, 0.69, 0.22), osiris);
  vec3 gold  = mix(vec3(1.00, 0.66, 0.12), vec3(0.94, 0.82, 0.38), osiris);
  vec3 deep  = mix(vec3(0.08, 0.42, 1.00), vec3(0.00, 0.90, 1.00), osiris);
  vec3 warm  = mix(ember, gold, smoothstep(-1.5, 1.3, q.x));
  sum += warm * silk(q, s, -0.46, 0.26, 1.10, 0.0, 0.24 * spread) * 0.95;
  sum += vec3(1.00, 0.86, 0.50) * silk(q, s, -0.33, 0.26, 1.10, 0.32, 0.06 * spread) * 0.45;
  sum += deep * silk(q, s, 0.58, 0.18, 0.85, 2.4, 0.32 * spread) * smoothstep(0.9, -1.3, q.x) * 0.9;
  // Light adds up towards white rather than past it: where two cross, the
  // colour blooms instead of clipping to a flat patch.
  return 1.0 - exp(-sum * 1.35);
}

// The dots' colour: the lights, their edges folded by slow, broad noise -
// enough that they read as glow and not as circles, little enough that the
// gradient stays smooth.
vec3 phosphor(vec2 q, float s) {
  vec2 fold = vec2(fbm(q * 0.75 + s * 0.050), fbm(q * 0.75 - s * 0.040 + 5.2)) - 0.5;
  return lights(q + fold * 0.34, s, 1.0);
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
  vec3 awake = phosphor(q, t / 1.5);
  if (sleep <= 0.001) return awake;
  // The idle sky keeps the slow pace it always had: it is meant to be restful.
  return mix(awake, dusk(q, t * 0.38, aspect), sleep);
}

// Where the picture is for a point on the glass: the fisheye samples nearer
// the middle there, so the middle swells and the corners pinch. A torn band
// pushes a few lines of the picture sideways - the picture, not the glass.
const float K = 0.30;
vec2 bend(vec2 uv) {
  vec2 p = uv * 2.0 - 1.0;                         // -1..1 on both axes
  p.x += tear * exp(-pow((uv.y - tearAt) * 38.0, 2.0));
  float r2 = dot(p, p) * 0.5;                      // 0 at the centre, 1 in a corner
  return p * (1.0 - K + K * r2 * 1.35);
}

void main() {
  float aspect = resolution.x / resolution.y;
  vec2 uv = gl_FragCoord.xy / resolution;
  vec2 bent = bend(uv);
  vec2 plane = bent * vec2(aspect, 1.0);
  float t = time;

  // The mask: a set's own pixels, on the glass, square to the screen's -
  // cells of three slots, red, green and blue, alternate columns of cells
  // set half a cell apart, the way a slot mask is. It is not bent: the
  // phosphors are where they are, and it is the picture landing on them
  // that the tube bends. Bending them too would only draw moire.
  vec2 px = gl_FragCoord.xy;
  float column = floor(px.x / pitch);
  float shift = mod(column, 2.0) * 0.5;
  float row = floor(px.y / pitch + shift);
  vec2 inCell = vec2(fract(px.x / pitch), fract(px.y / pitch + shift));

  // Each cell shows one flat colour: the picture where its centre falls -
  // given a set's contrast and colour: its darks deeper, its mids fuller,
  // and its colours pushed away from grey, so the light reads as coloured
  // light on a dark tube rather than a wash over all of it.
  vec2 centre = vec2(column + 0.5, row + 0.5 - shift) * pitch;
  vec3 lit = colourAt(bend(centre / resolution) * vec2(aspect, 1.0), t, aspect);
  lit = lit * lit * (3.0 - 2.0 * lit);
  lit = max(mix(vec3(dot(lit, vec3(0.30, 0.55, 0.15))), lit, 1.3), 0.0);

  // Which slot this pixel is on, and how far into it: lit along its middle,
  // soft at its sides, with a dark seam between one cell and the next.
  float third = inCell.x * 3.0;
  float slot = floor(third);
  float across = fract(third);
  vec3 gun = vec3(slot < 0.5 ? 1.0 : 0.0, abs(slot - 1.0) < 0.5 ? 1.0 : 0.0, slot > 1.5 ? 1.0 : 0.0);
  float shape = smoothstep(0.0, 0.3, across) * smoothstep(1.0, 0.7, across)
              * smoothstep(0.0, 0.16, inCell.y) * smoothstep(1.0, 0.84, inCell.y);
  // One slot in three is lit for each colour, so each is driven harder -
  // seen from a chair away the three add back up to the colour.
  vec3 phosphors = lit * gun * shape * 2.3;

  // Moire, where the picture is bright: a ring pattern a little finer than
  // the mask, round a point drifting low on the left, taken once a cell -
  // what reaches the glass is the slow beat between the rings and the
  // cells, broad rings that are in neither.
  vec2 ringsAt = resolution * vec2(0.20 + 0.10 * sin(t * 0.013), 0.24 + 0.08 * cos(t * 0.011));
  float beat = cos(6.2832 * length(centre - ringsAt) / (pitch * 0.94));
  float bright = smoothstep(0.30, 0.85, dot(lit, vec3(0.30, 0.55, 0.15))) * (1.0 - sleep);
  phosphors *= 1.0 + 0.16 * beat * bright;

  // The bloom, turned up: the lights again, unbroken and unfolded, as a haze
  // over the whole field - the glow a bright tube threw past its own
  // phosphors, and far more of it where the lights are brightest and cross -
  // and the same light spread nearly twice as wide, the glow round the
  // brightest of it reaching well out across the glass. Taken at this
  // pixel, not at the cell's centre, or it would come out in cells.
  // Asleep, the dusk has none.
  float s = t / 1.5;
  vec3 haze = lights(plane, s, 1.0) * (1.0 - sleep);
  vec3 wide = lights(plane, s, 1.85) * (1.0 - sleep);
  // The wide glow cubed: it gathers round the brightest light and falls
  // away into the dark, rather than laying a veil over everything.
  vec3 bloom = haze * 0.10 + haze * haze * 0.95 + wide * wide * wide * 0.62;
  // ...and each cell's own colour bleeding round it, so the mask glows
  // rather than sitting on black.
  vec3 halation = lit * 0.18;

  vec3 colour = phosphors * 0.85 + halation + bloom;

  // The rolling band, a little brighter where it passes.
  colour *= 1.0 + 0.26 * exp(-pow((uv.y - roll) * 7.0, 2.0));
  // The hum bar: a broad, soft dark band rolling slowly up the picture and
  // round again, the way mains hum crawled up an old set.
  float humAt = fract(uv.y - hum + 0.5) - 0.5;
  colour *= 1.0 - 0.10 * exp(-humAt * humAt * 26.0);
  // The lines shimmering against each other, a pair of screen rows at a
  // time, fresh every frame.
  colour *= 1.0 + (hash(vec2(floor(gl_FragCoord.y * 0.5), grain * 0.37)) - 0.5) * 0.09 * shimmer;
  // Static, finer than the dots, new every frame.
  colour += (hash(gl_FragCoord.xy * 0.73 + grain) - 0.5) * 0.05;
  colour *= flicker;

  // The tube's corners: dark, and rounded by the same bend.
  vec2 corner = abs(bent);
  float tube = smoothstep(1.02, 0.80, max(corner.x, corner.y))
             * smoothstep(1.55, 0.95, length(corner));
  colour *= mix(0.25, 1.0, tube);

  // The brightest of the bloom rolled off rather than clipped: the glow
  // keeps its spread, and the words on the panels over its hottest part
  // stay as readable as they were before there was this much of it.
  colour = colour / (1.0 + colour * 0.24);

  // Dim enough to read over, and a floor that is not quite black - darker
  // still with OSIRIS up, whose ground is a void with a little blue in it.
  float dim = mix(0.50, 0.62, sleep) * mix(1.0, 0.62, osiris);
  vec3 ground = mix(vec3(0.014, 0.012, 0.018), vec3(0.016, 0.016, 0.040), osiris);
  gl_FragColor = vec4(colour * dim + ground, 1.0);
}
`;

// How fast the light drifts: units of the lights' own time a second.
const DRIFT = 3.9;
// A flicker, never a flash: the deepest the tube's brightness goes.
const FLICKER_FLOOR = 0.74;
// The fewest frames a second the ground is drawn at, screen allowing.
const SMOOTH = 55;

/* How bright the tube is this frame, as a share of itself: a shimmer every
 * frame (shimmer, 0..1), a hum of a few cycles a second under it (hum, 0..1)
 * and now and then a dip (dip, 0..1, falling away over a few frames) - all
 * of it scaled by `calm`, and never below FLICKER_FLOOR. */
export function flickerLevel({ shimmer = 0, hum = 0, dip = 0, calm = 1 }) {
  const fall = (shimmer * 0.07 + hum * 0.03 + dip * 0.16) * calm;
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
    // The set's misbehaviour, decided a frame at a time (see `_set`).
    this.flicker = 1.0;
    this.roll = -1.0;
    this.rollWait = 3.0;
    this.tear = 0.0;
    this.tearAt = 0.5;
    this.dip = 0.0;
    this.hum = 0.0;
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
    this.rollUniform = gl.getUniformLocation(program, 'roll');
    this.tearUniform = gl.getUniformLocation(program, 'tear');
    this.tearAtUniform = gl.getUniformLocation(program, 'tearAt');
    this.grainUniform = gl.getUniformLocation(program, 'grain');
    this.osirisUniform = gl.getUniformLocation(program, 'osiris');
    this.humUniform = gl.getUniformLocation(program, 'hum');
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

  /* One frame of an old set: a flicker that is never quite still - a
   * shimmer, a hum under it, and a dip now and then that falls away over a
   * few frames - lines shimmering against each other, a dark hum bar
   * crawling up, a brighter band rolling up every few seconds, and once in a
   * while a few lines torn sideways. `dt` in seconds, `now` in ms. Chances
   * are per second, not per frame, so the set behaves the same at any frame
   * rate. Quieter asleep - the idle screen is meant to be restful - and
   * quieter still for anyone who asked for less motion. */
  _set(dt, now) {
    const calm = (1 - this.sleepValue * 0.7) * (this.still ? 0.3 : 1);
    this.dip *= Math.pow(0.02, dt);                  // gone in about a quarter second
    if (Math.random() < dt * 0.7) this.dip = 0.6 + Math.random() * 0.4;
    this.flicker = flickerLevel({
      shimmer: Math.random(),
      hum: 0.5 + 0.5 * Math.sin((now / 1000) * Math.PI * 2 * 5.3),
      dip: this.dip,
      calm,
    });
    this.shimmer = calm;
    this.hum = (this.hum + dt * 0.055) % 1;
    if (this.roll > -0.5) {
      this.roll += dt * 0.42;
      if (this.roll > 1.25) { this.roll = -1; this.rollWait = 2 + Math.random() * 4; }
    } else if ((this.rollWait -= dt) <= 0) {
      this.roll = -0.25;
    }
    if (this.tear > 0.0004) {
      this.tear *= Math.pow(0.55, dt * 30);
    } else {
      this.tear = 0;
      if (Math.random() < dt * 0.22 * calm) {
        this.tear = 0.004 + Math.random() * 0.007;
        this.tearAt = Math.random();
      }
    }
  }

  draw() {
    if (!this.gl) return;
    const gl = this.gl;
    gl.uniform1f(this.clock, this.time);
    gl.uniform1f(this.sleepUniform, this.sleepValue);
    gl.uniform1f(this.flickerUniform, this.flicker);
    gl.uniform1f(this.rollUniform, this.roll);
    gl.uniform1f(this.tearUniform, this.tear);
    gl.uniform1f(this.tearAtUniform, this.tearAt);
    gl.uniform1f(this.grainUniform, Math.random() * 97.0);
    gl.uniform1f(this.osirisUniform, this.osirisValue);
    gl.uniform1f(this.humUniform, this.hum);
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
        this.time += dt * DRIFT * this.rate * (this.still ? 0.5 : 1);
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
