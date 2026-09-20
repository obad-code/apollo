// The ring shader from the brief, in plain WebGL: three.js would be 600 KB to
// draw two triangles. Tinted to Apollo's palette and dimmed - it sits behind
// text that has to stay readable - and rendered at half resolution, which is
// both cheaper and softer, the way a CRT is.

const VERTEX = `
attribute vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;

const FRAGMENT = `
precision highp float;
uniform vec2 resolution;
uniform float time;

void main() {
  vec2 uv = (gl_FragCoord.xy * 2.0 - resolution.xy) / min(resolution.x, resolution.y);
  float t = time * 0.05;
  float lineWidth = 0.002;

  vec3 colour = vec3(0.0);
  for (int j = 0; j < 3; j++) {
    for (int i = 0; i < 5; i++) {
      colour[j] += lineWidth * float(i * i) /
        abs(fract(t - 0.01 * float(j) + float(i) * 0.01) * 5.0
            - length(uv) + mod(uv.x + uv.y, 0.2));
    }
  }

  // Where that denominator nears zero the term runs away to infinity; left
  // alone it paints white sheets across the page. Clamped, the same shape
  // reads as light instead of as glare.
  colour = colour / (colour + 0.85);

  // The three channels become Apollo's three lights rather than red, green
  // and blue.
  vec3 tinted = colour.r * vec3(0.55, 0.35, 0.85)
              + colour.g * vec3(0.95, 0.70, 0.30)
              + colour.b * vec3(0.25, 0.75, 0.80);

  // Brightest out at the edges, quiet through the middle third, where the
  // ring, the wordmark and every answer have to stay readable.
  float radius = length(uv);
  float clear = smoothstep(0.30, 1.15, radius) * 0.82 + 0.18;

  gl_FragColor = vec4(tinted * 0.20 * clear + vec3(0.016, 0.018, 0.036), 1.0);
}
`;

export class Shader {
  constructor(canvas, { scale = 0.5 } = {}) {
    this.canvas = canvas;
    this.scale = scale;
    this.gl = canvas.getContext('webgl', { antialias: false, depth: false });
    this.time = 1.0;
    this.rate = 1.0;
    this.frame = null;
    if (this.gl) this._build();
  }

  _build() {
    const gl = this.gl;
    const compile = (type, source) => {
      const shader = gl.createShader(type);
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
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
    this.resize();
  }

  resize() {
    if (!this.gl) return;
    const width = Math.max(1, Math.floor(window.innerWidth * this.scale));
    const height = Math.max(1, Math.floor(window.innerHeight * this.scale));
    this.canvas.width = width;
    this.canvas.height = height;
    this.gl.viewport(0, 0, width, height);
    this.gl.uniform2f(this.resolution, width, height);
  }

  speed(rate) { this.rate = rate; }

  start() {
    if (!this.gl || this.frame !== null) return;
    const draw = () => {
      this.time += 0.05 * this.rate;
      this.gl.uniform1f(this.clock, this.time);
      this.gl.drawArrays(this.gl.TRIANGLES, 0, 3);
      this.frame = requestAnimationFrame(draw);
    };
    this.frame = requestAnimationFrame(draw);
  }

  stop() {
    // Nothing is watching while the overlay has the screen, and a shader that
    // keeps drawing to a hidden window is a GPU burning for nobody.
    if (this.frame !== null) cancelAnimationFrame(this.frame);
    this.frame = null;
  }
}
