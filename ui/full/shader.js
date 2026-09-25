// The display's ground: an old set's own pixels, each lit by the colour
// drifting underneath it, seen through the bulge of the tube.
//
// Plain WebGL - three.js would be 600 KB to draw two triangles. Three layers,
// all in one pass:
//   - the colour: five soft lights - rose, cyan, amber, violet, green -
//     drifting across the tube on their own slow loops, so the gradient is
//     always moving, and blooming towards white where they cross. Asleep,
//     it settles into a dusk horizon instead - navy overhead, the last
//     orange low down - which is the idle screen's sky.
//   - the pixels: a slot mask, as fine as a set's - cells of a red, a green
//     and a blue slot, six screen pixels across, alternate columns half a
//     cell apart. Each cell shows the colour at its own centre, so the
//     gradient is drawn in the set's pixels rather than washed across.
//   - the glass: a fisheye that swells the middle of the picture and pinches
//     its corners, which go dark the way a tube's did. Over the pixels, the
//     bloom: the same lights, unbroken, as a haze - the glow a bright tube
//     threw past its own phosphors - and each cell's colour bleeding round
//     it.
//   - the set it is on: the picture flickers, a brighter band rolls up it,
//     static crawls over it, and now and then a few lines tear sideways for
//     a frame. The flicker, the band and the tear are decided in JavaScript
//     once a frame and handed in; the static is hashed here per pixel.
// Dimmed throughout: the panels sit on it and have to stay readable.

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
uniform float flicker;    // the tube's brightness this frame: ~0.96-1, now and then a dip
uniform float roll;       // the rolling band's height, 0..1 up the screen (off it when there is none)
uniform float tear;       // how far a torn band of lines is pushed sideways
uniform float tearAt;     // ...and where that band is, 0..1 up the screen
uniform float grain;      // a fresh seed every frame, for the static

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

// The lights, awake, at s seconds. q is centred and aspect-correct: x runs
// about -1.8..1.8 on a 16:9 screen, y -1..1. Each light loops on its own
// pair of periods (40 to 90 seconds), so they never line up the same way
// twice and something on the screen is always visibly on the move.
vec3 lights(vec2 q, float s) {
  vec3 rose   = vec3(1.00, 0.26, 0.58);
  vec3 cyan   = vec3(0.16, 0.78, 1.00);
  vec3 amber  = vec3(1.00, 0.58, 0.12);
  vec3 violet = vec3(0.50, 0.32, 1.00);
  vec3 green  = vec3(0.20, 1.00, 0.62);
  vec3 sum = vec3(0.0);
  sum += rose   * lamp(q, vec2(-0.95 + 0.75 * sin(s * 0.110), 0.30 + 0.40 * cos(s * 0.083)), 0.78);
  sum += cyan   * lamp(q, vec2( 0.95 + 0.65 * cos(s * 0.093), -0.15 + 0.45 * sin(s * 0.140)), 0.74);
  sum += amber  * lamp(q, vec2( 0.10 + 0.95 * sin(s * 0.071 + 1.3), -0.62 + 0.30 * cos(s * 0.120)), 0.70);
  sum += violet * lamp(q, vec2( 0.35 + 0.85 * cos(s * 0.104 + 2.1), 0.62 + 0.30 * sin(s * 0.077)), 0.72);
  sum += green  * lamp(q, vec2(-0.45 + 0.70 * sin(s * 0.066 + 4.0), -0.30 + 0.50 * cos(s * 0.098)), 0.60) * 0.7;
  // Light adds up towards white rather than past it: where two cross, the
  // colour blooms instead of clipping to a flat patch.
  return 1.0 - exp(-sum * 1.35);
}

// The dots' colour: the lights, their edges folded by slow noise so they
// read as glow and not as circles.
vec3 phosphor(vec2 q, float s) {
  vec2 fold = vec2(fbm(q * 0.9 + s * 0.050), fbm(q * 0.9 - s * 0.040 + 5.2)) - 0.5;
  return lights(q + fold * 0.55, s);
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
  vec3 awake = phosphor(q, t / 1.5);           // time runs 1.5 a second
  if (sleep <= 0.001) return awake;
  return mix(awake, dusk(q, t, aspect), sleep);
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

  // Each cell shows one flat colour: the picture where its centre falls.
  vec2 centre = vec2(column + 0.5, row + 0.5 - shift) * pitch;
  vec3 lit = colourAt(bend(centre / resolution) * vec2(aspect, 1.0), t, aspect);

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

  // The bloom, turned up: the lights again, unbroken and unfolded, as a haze
  // over the whole field - the glow a bright tube threw past its own
  // phosphors, and far more of it where the lights are brightest and cross.
  // Taken at this pixel, not at the cell's centre, or it would come out in
  // cells. Asleep, the dusk has none.
  vec3 haze = lights(plane, t / 1.5) * (1.0 - sleep);
  vec3 bloom = haze * 0.10 + haze * haze * 0.90;
  // ...and each cell's own colour bleeding round it, so the mask glows
  // rather than sitting on black.
  vec3 halation = lit * 0.12;

  vec3 colour = phosphors * 0.85 + halation + bloom;

  // The rolling band, a little brighter where it passes.
  colour *= 1.0 + 0.24 * exp(-pow((uv.y - roll) * 7.0, 2.0));
  // Static, finer than the dots, new every frame.
  colour += (hash(gl_FragCoord.xy * 0.73 + grain) - 0.5) * 0.05;
  colour *= flicker;

  // The tube's corners: dark, and rounded by the same bend.
  vec2 corner = abs(bent);
  float tube = smoothstep(1.02, 0.80, max(corner.x, corner.y))
             * smoothstep(1.55, 0.95, length(corner));
  colour *= mix(0.25, 1.0, tube);

  // Dim enough to read over, and a floor that is not quite black.
  float dim = mix(0.50, 0.62, sleep);
  gl_FragColor = vec4(colour * dim + vec3(0.014, 0.012, 0.018), 1.0);
}
`;

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

  /* One frame of an old set: a flicker that is never quite still and now
   * and then dips, a brighter band rolling up the picture every few seconds,
   * and once in a while a few lines torn sideways. `dt` in seconds. Quieter
   * asleep - the idle screen is meant to be restful. */
  _set(dt) {
    const calm = 1 - this.sleepValue * 0.7;
    this.flicker = 1 - (Math.random() * 0.04
                        + (Math.random() < 0.01 ? 0.12 : 0)) * calm;
    if (this.roll > -0.5) {
      this.roll += dt * 0.32;
      if (this.roll > 1.25) { this.roll = -1; this.rollWait = 3 + Math.random() * 6; }
    } else if ((this.rollWait -= dt) <= 0) {
      this.roll = -0.25;
    }
    if (this.tear > 0.0004) {
      this.tear *= 0.55;
    } else {
      this.tear = 0;
      if (Math.random() < 0.006 * calm) {
        this.tear = 0.004 + Math.random() * 0.006;
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
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  start() {
    if (!this.gl || this.frame !== null) return;
    this.last = performance.now();
    const tick = (now) => {
      // Thirty frames a second, whatever the screen's own rate: everything
      // here drifts over tens of seconds, and a full-resolution pass every
      // refresh of a 144Hz screen would be GPU spent on nothing. Time is
      // taken from the clock, so the drift is the same speed on any screen.
      if (now - this.last >= 1000 / 30 - 1) {
        const dt = Math.min(0.1, (now - this.last) / 1000);
        this.last = now;
        this.time += dt * 1.5 * this.rate;
        this.sleepValue += (this.sleepTarget - this.sleepValue) * Math.min(1, dt * 1.05);
        this._set(dt);
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
