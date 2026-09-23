// The display's ground: a field of dots, each lit by the colour drifting
// underneath it, seen through the bulge of an old tube.
//
// Plain WebGL - three.js would be 600 KB to draw two triangles. Three layers,
// all in one pass:
//   - the colour: CRT phosphors (amber, red, green, a deep blue) folded
//     through each other by slow noise. Asleep, it settles into a dusk
//     horizon instead - navy overhead, the last orange low down - which is
//     the idle screen's sky.
//   - the dots: a halftone of that colour. Each dot takes the colour at its
//     own centre and grows with its brightness, so the gradient is drawn in
//     dots rather than washed across the screen.
//   - the glass: a fisheye that swells the middle of the grid and pinches its
//     corners, the three guns landing a hair apart towards the edges, and the
//     scanlines. The corners go dark the way a tube's did.
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

// The phosphors, awake. q is centred, aspect-correct and already bent.
vec3 phosphor(vec2 q, float t) {
  vec2 w = q + 0.45 * vec2(fbm(q * 0.8 + t * 0.045), fbm(q * 0.8 - t * 0.035 + 3.1));
  float a = fbm(w * 1.25 + vec2(t * 0.030, -t * 0.020));
  float b = fbm(w * 1.05 - vec2(t * 0.022, t * 0.031) + 7.3);
  vec3 amber = vec3(1.00, 0.64, 0.12);
  vec3 red   = vec3(1.00, 0.30, 0.22);
  vec3 green = vec3(0.32, 1.00, 0.58);
  vec3 blue  = vec3(0.22, 0.46, 1.00);
  vec3 colour = mix(blue, amber, smoothstep(0.38, 0.68, a));
  colour = mix(colour, red, smoothstep(0.52, 0.78, b) * 0.65);
  colour = mix(colour, green, smoothstep(0.60, 0.82, 1.0 - a) * 0.40);
  float light = smoothstep(0.30, 0.86, a * 0.62 + b * 0.52);
  return colour * light;
}

// The same dots at dusk: the idle screen's sky, from its reference photo.
vec3 dusk(vec2 q, float t, float aspect) {
  float y = q.y;                                   // -1 at the bottom, 1 at the top
  float horizon = -0.46;
  vec3 night = vec3(0.07, 0.12, 0.24);
  vec3 mauve = vec3(0.34, 0.24, 0.34);
  vec3 ember = vec3(1.00, 0.48, 0.20);
  vec3 water = vec3(0.16, 0.09, 0.08);
  float above = smoothstep(horizon - 0.02, 1.1, y);
  vec3 sky = mix(ember, mauve, smoothstep(0.0, 0.42, above));
  sky = mix(sky, night, smoothstep(0.30, 1.0, above));
  // A band of cloud just over the horizon, drifting.
  float band = exp(-pow((y - horizon - 0.16) * 5.5, 2.0));
  float cloud = smoothstep(0.52, 0.78, fbm(vec2(q.x * 2.4 + t * 0.02, y * 9.0)));
  sky *= 1.0 - band * cloud * 0.72;
  // The glow is brightest just above the line and towards the right, where
  // the sun went down in the photo.
  float glow = exp(-pow((y - horizon) * 3.2, 2.0)) * (0.55 + 0.45 * smoothstep(-aspect, aspect, q.x));
  sky += ember * glow * 0.55;
  // Below the line: still water, holding a little of it.
  float below = smoothstep(horizon + 0.02, horizon - 0.06, y);
  vec3 sea = water + ember * 0.22 * exp(-(horizon - y) * 3.0)
           * (0.7 + 0.3 * noise(vec2(q.x * 30.0, y * 90.0 + t * 0.3)));
  return mix(sky, sea, below);
}

vec3 colourAt(vec2 q, float t, float aspect) {
  vec3 awake = phosphor(q, t);
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

  // A little of the colour between the dots, and a halo round each, so the
  // grid glows rather than sitting on black.
  float halo = exp(-length(f) * 5.0) * 0.16;

  vec3 colour = dots * 0.92 + lit * (halo + 0.075);

  // Scanlines, every other row.
  colour *= 0.86 + 0.14 * sin(gl_FragCoord.y * 3.14159);

  // The tube's corners: dark, and rounded by the same bend.
  vec2 corner = abs(bent);
  float tube = smoothstep(1.02, 0.80, max(corner.x, corner.y))
             * smoothstep(1.55, 0.95, length(corner));
  colour *= mix(0.25, 1.0, tube);

  // Dim enough to read over, and a floor that is not quite black.
  float dim = mix(0.44, 0.62, sleep);
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
