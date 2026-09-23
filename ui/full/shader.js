// The display's ground: a field of dots, each lit by the colour drifting
// underneath it, seen through the bulge of an old tube.
//
// Plain WebGL - three.js would be 600 KB to draw two triangles. Three layers,
// all in one pass:
//   - the colour: five soft lights - rose, cyan, amber, violet, green -
//     drifting across the tube on their own slow loops, so the gradient is
//     always moving, and blooming towards white where they cross. Asleep,
//     it settles into a dusk horizon instead - navy overhead, the last
//     orange low down - which is the idle screen's sky.
//   - the dots: a halftone of that colour. Each dot takes the colour at its
//     own centre and grows with its brightness, so the gradient is drawn in
//     dots rather than washed across the screen.
//   - the glass: a fisheye that swells the middle of the grid and pinches its
//     corners, the three guns landing a hair apart towards the edges, and the
//     scanlines. The corners go dark the way a tube's did. Over the dots, the
//     bloom: the same lights, unbroken, as a haze - the glow a bright tube
//     threw past its own phosphors.
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
uniform float pitch;      // dot spacing at the edge of the screen, in pixels

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

void main() {
  float aspect = resolution.x / resolution.y;
  vec2 uv = gl_FragCoord.xy / resolution;
  vec2 p = uv * 2.0 - 1.0;                         // -1..1 on both axes

  // The fisheye: sampled nearer the middle there, so the middle swells and
  // the corners pinch. r2 runs 0 at the centre to 1 in a corner.
  float r2 = dot(p, p) * 0.5;
  float k = 0.30;
  vec2 bent = p * (1.0 - k + k * r2 * 1.35);

  // The grid, in dots, on the bent plane.
  vec2 plane = bent * vec2(aspect, 1.0);
  float across = resolution.y / pitch * 0.5;
  vec2 g = plane * across;
  vec2 id = floor(g);
  vec2 f = fract(g) - 0.5;

  // Each dot is one flat colour: the field at its own centre.
  vec2 centre = (id + 0.5) / across;
  float t = time;
  vec3 lit = colourAt(centre, t, aspect);
  float bright = max(lit.r, max(lit.g, lit.b));

  // Its size follows its brightness - the halftone.
  float radius = mix(0.10, 0.44, clamp(bright * 1.15, 0.0, 1.0));
  float edge = 0.9 / (pitch * (1.0 - k + k * r2 * 3.0));   // a pixel, in cells
  // The three guns do not quite converge away from the middle.
  vec2 miss = p * r2 * 0.055;
  float red   = smoothstep(radius + edge, radius - edge, length(f - miss));
  float green = smoothstep(radius + edge, radius - edge, length(f));
  float blue  = smoothstep(radius + edge, radius - edge, length(f + miss));
  vec3 dots = lit * vec3(red, green, blue);

  // A halo round each dot, so the grid glows rather than sitting on black.
  float halo = exp(-length(f) * 5.0) * 0.18;

  // The bloom: the lights again, unbroken and unfolded, as a haze over the
  // whole field - a wash of their colour, and more of it where they are
  // brightest. Taken at this pixel, not at the dot's centre, or it would
  // come out in squares the size of the grid. Asleep, the dusk has none.
  vec3 haze = lights(plane, t / 1.5) * (1.0 - sleep);
  vec3 bloom = haze * 0.16 + haze * haze * 0.30;

  vec3 colour = dots * 0.92 + lit * (halo + 0.06) + bloom;

  // Scanlines, every other row.
  colour *= 0.86 + 0.14 * sin(gl_FragCoord.y * 3.14159);

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
  constructor(canvas, { scale = 1, pitch = 15 } = {}) {
    this.canvas = canvas;
    this.scale = scale;
    this.pitch = pitch;
    this.gl = canvas.getContext('webgl', { antialias: false, depth: false });
    this.time = 1.0;
    this.rate = 1.0;
    this.sleepValue = 0.0;
    this.sleepTarget = 0.0;
    this.frame = null;
    this.skip = false;
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
    this.resize();
  }

  resize() {
    if (!this.gl) return;
    // Full resolution: a dot grid rendered at half size and stretched is a
    // grid of smudges.
    const width = Math.max(1, Math.floor(window.innerWidth * this.scale));
    const height = Math.max(1, Math.floor(window.innerHeight * this.scale));
    this.canvas.width = width;
    this.canvas.height = height;
    this.gl.viewport(0, 0, width, height);
    this.gl.uniform2f(this.resolution, width, height);
    this.gl.uniform1f(this.pitchUniform, this.pitch * this.scale);
    this.draw();
  }

  speed(rate) { this.rate = rate; }

  // Asleep, the phosphors settle into the dusk sky; awake, back. Eased over
  // a few seconds, the way light changes.
  sleep(on) { this.sleepTarget = on ? 1 : 0; }

  draw() {
    if (!this.gl) return;
    this.gl.uniform1f(this.clock, this.time);
    this.gl.uniform1f(this.sleepUniform, this.sleepValue);
    this.gl.drawArrays(this.gl.TRIANGLES, 0, 3);
  }

  start() {
    if (!this.gl || this.frame !== null) return;
    const tick = () => {
      // Thirty frames a second: everything here drifts over tens of seconds,
      // and a full-resolution pass every frame would be GPU spent on nothing.
      this.skip = !this.skip;
      if (!this.skip) {
        this.time += 0.05 * this.rate;
        this.sleepValue += (this.sleepTarget - this.sleepValue) * 0.035;
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
