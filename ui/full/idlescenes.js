/* The idle screen's skies: two scenes behind Apollo's name, in his colours,
 * switched with a button and kept until you press Back.
 *
 *   horizon   A black hole drawn like an engraving: a tilted accretion disk
 *             of hair-thin orbital streaks banded in Apollo's ember and
 *             amber, a photon crown of warm white, nebula banks cut out of
 *             violet contour lines, film grain over everything. Hold the
 *             mouse down to feed it. (Ported from etched-accretion.)
 *   nebula    A pixel-art night sky printed in halftone dots: violet haze
 *             thickening into ember and amber, pixel stars on three
 *             parallax layers, a halftone planet, needle-spiked sparkle
 *             stars; the pointer is a lamp that parts the gas, a click hangs
 *             a new star and sends a shock ring through it. (Ported from
 *             halftone-nebula.)
 *
 * Each is one full-screen WebGL2 fragment pass, made the first time it is
 * shown and kept; only the scene on screen draws, and nothing draws while
 * the idle screen is down. The pure helpers are exported for node's tests. */

export const SCENES = ['horizon', 'nebula'];
export const SCENE_NAMES = { horizon: 'Event horizon', nebula: 'Ember nebula' };

/* "#rgb" / "#rrggbb" -> [r, g, b] in 0..1; anything else is black. */
export function hexToRgb(hex) {
  let h = String(hex).trim().replace(/^#/, '');
  if (/^[0-9a-f]{3}$/i.test(h)) h = h.replace(/./g, (c) => c + c);
  if (!/^[0-9a-f]{6}$/i.test(h)) return [0, 0, 0];
  const n = parseInt(h, 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

/* Frame-rate independent ease toward a target; never overshoots. */
export function approach(current, target, dt, rate) {
  return current + (target - current) * (1 - Math.exp(-Math.max(dt, 0) * rate));
}

/* The drift that stands in for a pointer nobody is moving. */
export function idleDrift(t) {
  return [0.45 * Math.sin(t * 0.13) + 0.15 * Math.sin(t * 0.31 + 1.7), 0.3 * Math.sin(t * 0.17 + 0.6)];
}

export function driftPos(t) {
  const x = 0.5 + 0.32 * Math.sin(t * 0.21) + 0.1 * Math.sin(t * 0.077 + 1.3);
  const y = 0.5 + 0.26 * Math.cos(t * 0.17) + 0.12 * Math.cos(t * 0.053 + 4.2);
  return [Math.min(Math.max(x, 0.05), 0.95), Math.min(Math.max(y, 0.05), 0.95)];
}

export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const MAX_SPARKS = 16;
const MAX_RIPPLES = 4;

/* The seeded sparkle stars: a hero high up, a pale one, the rest small -
 * never hung so close their spikes tangle. */
export function layoutSparkles(seed, count) {
  const rand = mulberry32(seed);
  const out = [];
  const n = Math.max(0, Math.min(Math.floor(count), MAX_SPARKS));
  for (let i = 0; i < n; i++) {
    const hero = i === 0, pale = i === 1;
    let x = 0.5, y = 0.5;
    for (let tries = 0; tries < 40; tries++) {
      x = 0.08 + 0.84 * rand();
      y = hero ? 0.58 + 0.28 * rand() : 0.08 + 0.84 * rand();
      if (out.every((s) => Math.hypot(s.x - x, s.y - y) > (hero ? 0.2 : 0.13))) break;
    }
    out.push({ x, y, reach: hero ? 0.2 + 0.05 * rand() : pale ? 0.08 + 0.03 * rand() : 0.025 + 0.055 * rand(),
               core: hero ? 0.024 : pale ? 0.011 : 0.004 + 0.006 * rand(), tint: pale ? 1 : 0,
               phase: rand() * 6.283, born: -10, user: false });
  }
  return out;
}

/* A clicked sparkle; once full, the oldest clicked one makes room. */
export function pushSparkle(list, next, max = MAX_SPARKS) {
  if (list.length < max) return [...list, next];
  const oldest = list.findIndex((s) => s.user);
  if (oldest === -1) return list;
  return [...list.slice(0, oldest), ...list.slice(oldest + 1), next];
}

/* --- Apollo's palettes ---------------------------------------------------- */

export const HORIZON = {
  diskColor: '#ff7a1a', streakColor: '#fff0ce', glowColor: '#ffe6b0', cloudColor: '#c7b4ea',
  background: '#050307', center: [0.5, 0.47], holeSize: 0.055, angle: 13, inclination: 0.27,
  diskRadius: 1.35, speed: 1, shear: 1, streakDensity: 150, crimson: 0.6, doppler: 0.35,
  flare: 1.1, lensing: 1, clouds: 1, cloudLines: 44, stars: 1, grain: 0.85, vignette: 0.55, exposure: 1.3,
};

export const NEBULA = {
  pixel: 6, dotMin: 0.12, dotMax: 0.56, levels: 7, scale: 1.7, warp: 1.5, drift: 0.035, density: 0.5,
  threshold: 0.54, softness: 0.5, band: 0.55, bandAngle: 1.05, bandOffset: 0.42, bandWidth: 0.34, haze: 0.8,
  stars: 1, twinkle: 1.4, starDrift: 1.2, sparkles: 9, seed: 11, spikeWidth: 1,
  planet: true, planetX: 0.74, planetY: 0.66, planetRadius: 0.075,
  parallax: 1, lens: 0.55, lensRadius: 170, lensPush: 0.3, rippleSpeed: 420, speed: 1, vignette: 0.5, grain: 0.035,
  voidColor: '#050306', hazeColor: '#17132e', duskColor: '#34183f', wineColor: '#5a1f0b',
  crimsonColor: '#e0661a', hotColor: '#ffb000', starColor: '#fff0ce',
};

/* --- the shaders --------------------------------------------------------- */

const VERT = `#version 300 es
void main() {
  vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

const HORIZON_FRAG = `#version 300 es
precision highp float;
out vec4 outColor;
uniform vec2 uRes; uniform float uTime; uniform float uClock; uniform float uFeed; uniform vec2 uParallax;
uniform vec3 uDisk; uniform vec3 uStreak; uniform vec3 uGlow; uniform vec3 uCloud; uniform vec3 uBg;
uniform vec2 uCenter; uniform float uHole; uniform float uAngle; uniform float uIncl; uniform float uDiskRadius;
uniform float uShear; uniform float uDensity; uniform float uCrimson; uniform float uDoppler; uniform float uFlare;
uniform float uLensing; uniform float uClouds; uniform float uCloudLines; uniform float uStars; uniform float uGrain;
uniform float uVignette; uniform float uExposure;
float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash13(vec3 p3){ p3 = fract(p3 * 0.1031); p3 += dot(p3, p3.zyx + 31.32); return fract((p3.x + p3.y) * p3.z); }
float noise2(vec2 p){ vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash12(i), hash12(i + vec2(1, 0)), u.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), u.x), u.y); }
float noise3(vec3 p){ vec3 i = floor(p), f = fract(p); vec3 u = f * f * (3.0 - 2.0 * f);
  float a = mix(mix(hash13(i), hash13(i + vec3(1, 0, 0)), u.x), mix(hash13(i + vec3(0, 1, 0)), hash13(i + vec3(1, 1, 0)), u.x), u.y);
  float b = mix(mix(hash13(i + vec3(0, 0, 1)), hash13(i + vec3(1, 0, 1)), u.x), mix(hash13(i + vec3(0, 1, 1)), hash13(i + vec3(1, 1, 1)), u.x), u.y);
  return mix(a, b, u.z); }
float fbm(vec2 p, int oct){ float s = 0.0, a = 0.5; mat2 m = mat2(1.6, 1.2, -1.2, 1.6);
  for (int i = 0; i < 7; i++) { if (i >= oct) break; s += a * noise2(p); p = m * p + 17.13; a *= 0.5; } return s; }
float lines(float x, float w){ float fw = fwidth(x) + 1e-5; float dist = 0.5 - abs(fract(x) - 0.5);
  float l = 1.0 - smoothstep(w * 0.5 - fw, w * 0.5 + fw, dist); return mix(l, w, smoothstep(0.25, 0.7, fw)); }
float nebula(vec2 w, float t){ vec2 q = vec2(fbm(w * 1.1 + vec2(0.0, t * 0.012), 4), fbm(w * 1.1 + vec2(5.2, 1.3) - t * 0.009, 4));
  return fbm(w * 1.8 + 1.5 * q, 6); }
vec4 bank(vec2 w, float mask, float t, vec2 toHole, float px){
  float d = nebula(w, t);
  float body = d + 0.42 * (mask - 1.0) + 0.05 * mask + 0.1 * (uClouds - 1.0);
  float cover = smoothstep(0.5, 0.56, body);
  if (cover <= 0.0) return vec4(0.0);
  float x = (d + 0.012 * noise2(w * 55.0)) * uCloudLines;
  float ink = max(lines(x, 0.16), 0.45 * lines(x * 2.7 + 3.0 * noise2(w * 9.0), 0.12));
  float rim = 1.0 - smoothstep(0.0, 0.07, body - 0.5);
  vec2 g = vec2(dFdx(d), dFdy(d)) / px;
  float lam = clamp(0.5 + 0.5 * dot(-normalize(g + 1e-5), toHole), 0.0, 1.0);
  float lit = ink * (0.26 + 0.95 * rim) * (0.3 + 0.7 * lam) + rim * rim * 0.12 * lam;
  return vec4(uBg * 0.55 + uCloud * lit, cover);
}
float starField(vec2 w, float scale, float dens, float t){
  vec2 g = w * scale; vec2 id = floor(g); float h = hash12(id);
  if (h < 1.0 - dens) return 0.0;
  vec2 o = vec2(hash12(id + 7.1), hash12(id + 3.7)) - 0.5;
  float dpx = length(fract(g) - 0.5 - o * 0.7) / scale * uRes.y;
  float tw = 0.65 + 0.35 * sin(t * (1.5 + h * 3.0) + h * 60.0);
  return exp(-dpx * dpx * 0.9) * tw * (0.4 + 0.6 * hash12(id + 1.9));
}
void main(){
  vec2 frag = gl_FragCoord.xy; float px = 1.0 / uRes.y; float aspect = uRes.x / uRes.y;
  vec2 uv = (frag - 0.5 * uRes) * px; float t = uTime;
  vec2 c = vec2((uCenter.x - 0.5) * aspect, 0.5 - uCenter.y);
  vec2 p = uv - c - uParallax * 0.012;
  float ang = radians(uAngle) + uParallax.x * 0.03; float ca = cos(ang), sa = sin(ang);
  vec2 pr = vec2(ca * p.x - sa * p.y, sa * p.x + ca * p.y);
  float incl = clamp(uIncl + uParallax.y * 0.035, 0.06, 0.98);
  vec2 q = vec2(pr.x, pr.y / incl); float r = length(q);
  float Rh = uHole * (1.0 + 0.06 * uFeed); float d = length(p); vec2 dir = p / max(d, 1e-5);
  float RE = Rh * 1.7 * uLensing;
  vec2 pl = p * (1.0 - min(RE * RE / max(d * d, 1e-6), 1.6)); vec2 uvL = pl + c;
  vec3 col = uBg + vec3(0.024, 0.012, 0.004) * smoothstep(-0.2, 0.6, uv.y + 0.3 * uv.x);
  float st = starField(uvL + uParallax * 0.004, 42.0, 0.09 * uStars, uClock)
           + 0.7 * starField(uvL + uParallax * 0.002 + 3.3, 95.0, 0.07 * uStars, uClock);
  col += vec3(1.0, 0.94, 0.86) * st;
  vec2 toHole = normalize(c - uv + 1e-5);
  if (uClouds > 0.0) {
    float maskT = smoothstep(-0.02, 0.3, pr.y + 0.15 * pr.x - 0.06);
    if (maskT > 0.0) {
      vec4 b = bank(uvL * 0.95 + uParallax * 0.02 + vec2(t * 0.004, 0.0), maskT, t, toHole, px);
      b.rgb += vec3(0.05, 0.03, 0.09) * b.a * smoothstep(0.1, 0.5, uv.y);
      col = mix(col, b.rgb, b.a);
    }
  }
  float inside = 1.0 - smoothstep(Rh - px, Rh + px, d);
  vec2 sp = p / Rh; float z = sqrt(max(0.0, 1.0 - dot(sp, sp))); vec3 n = vec3(sp, z);
  float lit = max(0.0, dot(n, normalize(vec3(0.15, 0.85, 0.5))));
  vec3 sphere = uBg * 0.4 + vec3(0.11, 0.09, 0.07) * lit * lit + uGlow * pow(1.0 - z, 4.0) * 0.18;
  col = mix(col, sphere, inside);
  float rin = Rh * 1.55;
  if (r < uDiskRadius * 1.6) {
    float theta = atan(q.y, q.x);
    float om = 0.5 * uShear * pow(max(r, rin) / 0.3, -1.5) + 0.05;
    float th = theta + t * om; vec2 a2 = vec2(cos(th), sin(th)); float lr = log(max(r, 1e-4));
    float arm = sin(2.0 * theta - t * 0.08 + 6.5 * lr);
    float w1 = noise3(vec3(a2 * 1.3, lr * 2.0 + 3.1)); float w2 = noise3(vec3(a2 * 4.0, lr * 7.0 - 1.7));
    float rr = r * (1.0 + 0.035 * (w1 - 0.5) + 0.012 * arm) + 0.004 * (w2 - 0.5);
    float x1 = rr * uDensity; float x2 = rr * uDensity * 1.618 + 0.7 * w2; float x3 = rr * uDensity * 0.47 + 0.3 * w1;
    float dash1 = smoothstep(0.3, 0.62, noise3(vec3(a2 * 2.2, r * uDensity * 0.09)));
    float dash2 = smoothstep(0.36, 0.7, noise3(vec3(a2 * 4.5, r * uDensity * 0.14 + 9.0)));
    float s = lines(x1, 0.2) * dash1 + 0.6 * lines(x2, 0.14) * dash2 + 0.25 * lines(x3, 0.18) * (0.4 + 0.6 * dash2);
    float band = noise3(vec3(a2 * 1.7, r * 6.0 + 11.0)) + 0.16 * arm;
    float prof = smoothstep(0.1, 0.3, r) * (1.0 - smoothstep(0.95, 1.5, r / uDiskRadius * 1.35));
    float red = smoothstep(0.62 - 0.4 * uCrimson, 0.72 - 0.4 * uCrimson, band) * (0.25 + 0.75 * prof);
    float hot = exp(-(r - rin) / (Rh * 2.2));
    vec3 lineCol = mix(uStreak * 0.5, uDisk * 1.55, red);
    lineCol = mix(lineCol, uStreak * 1.4 + uGlow * 0.3, clamp(hot, 0.0, 1.0));
    float edge = smoothstep(rin, rin * 1.18, r) * (1.0 - smoothstep(uDiskRadius * 0.55, uDiskRadius, r));
    float bright = edge * (0.3 + 1.25 * exp(-(r - rin) * 1.9) + 1.6 * hot);
    float dop = 1.0 - uDoppler * (q.x / max(r, 1e-4));
    vec3 disk = lineCol * s * bright * dop;
    disk += (uDisk * 0.035 * (0.3 + red) + vec3(0.08, 0.04, 0.02) * hot) * edge * dop;
    disk *= 1.0 + 0.6 * uFeed;
    float far = smoothstep(-0.25 * px, 1.5 * px, pr.y);
    col += disk * (1.0 - inside * far);
  }
  float outside = 1.0 - inside; float fl = uFlare * (1.0 + 1.3 * uFeed);
  float up = dot(dir, normalize(vec2(sa * 0.6, 1.0)));
  float ring = exp(-pow((d - Rh * 1.02) / (Rh * 0.035), 2.0)) * (0.55 + 0.9 * smoothstep(-0.4, 1.0, up));
  float crown = exp(-pow((d - Rh * 1.14) / (Rh * 0.09), 2.0)) * smoothstep(-0.05, 0.7, dir.y * ca - dir.x * sa);
  float halo = exp(-max(d - Rh, 0.0) / (Rh * 0.7)) * (0.35 + 0.65 * smoothstep(-0.3, 1.0, up));
  float rays = noise3(vec3(dir * 7.0, t * 0.06 + uClock * 0.02));
  rays = pow(rays, 3.0) * 1.6 * exp(-max(d - Rh, 0.0) / (Rh * 1.7)) * smoothstep(0.25, 1.0, up);
  float plane = exp(-abs(pr.y) / (Rh * 0.12)) * exp(-abs(pr.x) / (Rh * 2.6)) * smoothstep(Rh * 0.6, Rh * 1.3, abs(pr.x));
  float jet = exp(-abs(dot(p, vec2(ca, -sa))) / (Rh * 0.22)) * exp(-max(dot(p, vec2(sa, ca)), 0.0) / (Rh * 7.0)) * step(0.0, dot(p, vec2(sa, ca)));
  col += uGlow * fl * (ring * 1.3 + crown * 0.9 + (halo * 0.8 + rays * 0.7 + jet * 0.07) * outside + plane * 0.9);
  if (uClouds > 0.0) {
    float maskB = smoothstep(0.0, 0.3, -pr.y - 0.3 * pr.x - 0.03);
    if (maskB > 0.0) {
      vec4 b = bank(uv * 0.85 + uParallax * 0.05 + vec2(7.0 - t * 0.006, 2.0), maskB, t + 40.0, toHole, px);
      col = mix(col, b.rgb, b.a);
    }
  }
  col = 1.0 - exp(-col * uExposure);
  vec2 vq = uv / vec2(aspect, 1.0);
  col *= mix(1.0, smoothstep(0.95, 0.2, length(vq * vec2(1.25, 1.05))), uVignette);
  float f = floor(uClock * 24.0);
  float g1 = hash12(frag + f * vec2(37.1, 91.7)); float g2 = hash12(floor(frag / 2.0) + f * vec2(13.3, 7.9));
  float grain = (g1 - 0.5) * 0.8 + (g2 - 0.5) * 0.55;
  float luma = dot(col, vec3(0.299, 0.587, 0.114));
  col += grain * uGrain * (0.045 + 0.4 * luma * (1.0 - luma));
  col += step(0.99965, hash12(floor(frag / 2.0) + f * 3.1)) * uGrain * 0.12;
  outColor = vec4(max(col, 0.0), 1.0);
}`;

const NEBULA_UNIFORMS = [
  ['pixel', 'f'], ['dotMin', 'f'], ['dotMax', 'f'], ['levels', 'f'], ['scale', 'f'], ['warp', 'f'],
  ['drift', 'f'], ['density', 'f'], ['threshold', 'f'], ['softness', 'f'], ['band', 'f'], ['bandAngle', 'f'],
  ['bandOffset', 'f'], ['bandWidth', 'f'], ['haze', 'f'], ['stars', 'f'], ['twinkle', 'f'], ['starDrift', 'f'],
  ['spikeWidth', 'f'], ['parallax', 'f'], ['lens', 'f'], ['lensRadius', 'f'], ['lensPush', 'f'],
  ['rippleSpeed', 'f'], ['vignette', 'f'], ['grain', 'f'], ['voidColor', 'c'], ['hazeColor', 'c'],
  ['duskColor', 'c'], ['wineColor', 'c'], ['crimsonColor', 'c'], ['hotColor', 'c'], ['starColor', 'c'],
];
const uName = (k) => `u${k[0].toUpperCase()}${k.slice(1)}`;

const NEBULA_FRAG = `#version 300 es
precision highp float;
uniform vec2 uRes; uniform float uDpr; uniform float uTime; uniform vec2 uPointer; uniform float uPointerOn;
uniform vec2 uLook; uniform int uSparkCount; uniform vec4 uSpark[${MAX_SPARKS}]; uniform vec4 uSparkB[${MAX_SPARKS}];
uniform vec4 uRipple[${MAX_RIPPLES}]; uniform vec4 uPlanet;
${NEBULA_UNIFORMS.map(([k, kind]) => `uniform ${kind === 'c' ? 'vec3' : 'float'} ${uName(k)};`).join('\n')}
out vec4 frag;
float hash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float vnoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  float a = hash12(i), b = hash12(i + vec2(1.0, 0.0)); float c = hash12(i + vec2(0.0, 1.0)), d = hash12(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y); }
float fbm(vec2 p){ float s = 0.0, a = 0.5; mat2 r = mat2(0.8, -0.6, 0.6, 0.8);
  for (int i = 0; i < 5; i++) { s += a * vnoise(p); p = r * p * 2.03 + 17.1; a *= 0.5; } return s / 0.96875; }
float bayer4(vec2 c){ vec2 m = mod(c, 4.0); int i = int(m.x) + int(m.y) * 4;
  int b[16] = int[16](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5); return (float(b[i]) + 0.5) / 16.0; }
vec3 ramp(float d, vec3 haze){ vec3 c = mix(uVoidColor, haze, smoothstep(0.0, 0.22, d));
  c = mix(c, uWineColor, smoothstep(0.18, 0.44, d)); c = mix(c, uCrimsonColor, smoothstep(0.42, 0.72, d));
  return mix(c, uHotColor, smoothstep(0.7, 0.96, d)); }
vec2 shift(float depth){ return floor(uLook * uParallax * depth * 28.0); }
vec3 field(vec2 pos, vec2 resCss){
  float minSide = min(resCss.x, resCss.y); vec2 uv = (pos - 0.5 * resCss) / minSide;
  vec2 p = uv * uScale + uLook * uParallax * 0.05;
  vec2 toP = pos - uPointer; float lamp = exp(-dot(toP, toP) / (uLensRadius * uLensRadius)) * uPointerOn;
  p += toP / minSide * lamp * uLensPush * uScale;
  float ring = 0.0;
  for (int i = 0; i < ${MAX_RIPPLES}; i++) {
    vec4 r = uRipple[i]; float age = uTime - r.z;
    if (r.w <= 0.0 || age < 0.0 || age > 2.4) continue;
    vec2 dv = pos - r.xy; float dist = length(dv); float w = 14.0 + age * 26.0;
    float k = exp(-pow((dist - age * uRippleSpeed) / w, 2.0)) * (1.0 - age / 2.4) * r.w;
    ring += k; p += dv / max(dist, 1.0) * k * 0.12;
  }
  float t = uTime * uDrift;
  vec2 q = vec2(fbm(p + vec2(0.0, t * 0.7)), fbm(p + vec2(5.2, 1.3) - t * 0.5));
  float n = fbm(p + uWarp * q + vec2(t * 0.4, -t * 0.25));
  vec2 dir = vec2(cos(uBandAngle), sin(uBandAngle)); float along = dot(uv, dir);
  float across = dot(uv, vec2(-dir.y, dir.x)) - uBandOffset - 0.22 * sin(along * 2.3 + t * 3.0) - (q.x - 0.5) * 0.35;
  float river = exp(-across * across / (uBandWidth * uBandWidth));
  float raw = n + river * uBand * 0.5 + (uDensity - 0.5) * 0.5;
  float d = smoothstep(uThreshold, uThreshold + uSoftness, raw);
  d = clamp(d + lamp * uLens * 0.45 + ring * 0.55, 0.0, 1.0);
  for (int i = 0; i < ${MAX_SPARKS}; i++) {
    if (i >= uSparkCount) break;
    vec4 s = uSpark[i]; vec4 b = uSparkB[i]; float grow = smoothstep(0.0, 0.6, uTime - s.w);
    float dist = length(pos - s.xy - shift(1.2));
    d += exp(-dist / max(b.w * 2.2 * (1.0 + b.z * 0.6), 1.0)) * 0.55 * grow;
  }
  float hz = smoothstep(0.25, 0.75, n + river * 0.25) * uHaze;
  float tone = fbm(p * 0.45 + vec2(11.0, -3.0) + t * 0.2);
  return vec3(clamp(d, 0.0, 1.0), hz, tone);
}
void main(){
  vec2 resCss = uRes / uDpr; vec2 css = gl_FragCoord.xy / uDpr; float px = max(uPixel, 1.0);
  vec2 cell = floor(css / px); vec2 cellC = (cell + 0.5) * px; vec2 f = fract(css / px) - 0.5;
  float L = max(uLevels, 2.0); float dith = bayer4(cell);
  vec3 g = field(cellC, resCss);
  vec3 hazeCol = mix(uHazeColor, uDuskColor, smoothstep(0.38, 0.62, g.z));
  float dq = clamp(floor(g.x * L + dith) / L, 0.0, 1.0); float hq = floor(g.y * 3.0 + dith) / 3.0;
  vec3 bg = mix(uVoidColor, hazeCol, hq * 0.7);
  bg = mix(bg, ramp(dq * 0.7, hazeCol) * 0.42, smoothstep(0.0, 0.3, dq));
  float r = mix(uDotMin, uDotMax, sqrt(dq)); float dotMask = step(length(f), r);
  vec3 dotCol = dq < 0.01 ? mix(uVoidColor, hazeCol, 0.35 + hq * 0.5) : ramp(min(dq + 0.1, 1.0), hazeCol);
  vec3 col = mix(bg, dotCol, dotMask);
  vec3 starAcc = vec3(0.0); float starA = 0.0;
  for (int l = 0; l < 3; l++) {
    float fl = float(l); float depth = 0.3 + fl * 0.4; float gpx = px * (l == 2 ? 2.0 : 1.0);
    vec2 sp = css + shift(depth) + vec2(0.0, floor(uTime * uStarDrift * depth));
    vec2 id = floor(sp / gpx); vec2 fr = fract(sp / gpx) - 0.5;
    float prob = uStars * (l == 0 ? 0.009 : l == 1 ? 0.014 : 0.01); float h = hash12(id + fl * 71.3);
    if (h > 1.0 - prob) {
      float h2 = hash12(id * 1.7 + 3.1 + fl);
      float tw = 0.45 + 0.55 * (0.5 + 0.5 * sin(uTime * uTwinkle * (0.6 + h2 * 2.5) + h2 * 40.0));
      float rad = l == 2 ? 0.42 : 0.26 + h2 * 0.22; float m = step(length(fr), rad);
      vec3 c = (l == 0 || h2 > 0.82) ? uStarColor : uHotColor;
      starAcc = max(starAcc, c * m * tw); starA = max(starA, m * tw);
    }
  }
  col = mix(col, starAcc / max(starA, 1e-3), starA * (1.0 - g.x * 0.55));
  if (uPlanet.w > 0.5) {
    vec2 pc = uPlanet.xy + shift(0.8); float R = uPlanet.z; vec2 dc = cellC - pc;
    if (length(dc) < R) {
      vec2 n2 = dc / R; float z = sqrt(max(1.0 - dot(n2, n2), 0.0));
      float lit = clamp(dot(vec3(n2, z), normalize(vec3(-0.45, 0.55, 0.7))), 0.0, 1.0);
      float surf = fbm(vec2(n2.x * 1.4 + uTime * 0.015, n2.y * 4.2) * 1.6 + 9.0);
      float pd = clamp(lit * 1.05 - smoothstep(0.55, 0.75, surf) * 0.45 * (1.0 - lit * 0.5) + 0.05, 0.0, 1.0);
      float pq = floor(pd * L + dith) / L;
      vec3 pbg = mix(mix(uVoidColor, uWineColor, 0.35), uWineColor, pq);
      float pr = mix(0.2, 0.62, sqrt(pq)); vec3 pdot = ramp(min(pq * 0.85 + 0.25, 1.0), hazeCol);
      col = mix(pbg, pdot, step(length(f), pr));
    }
  }
  vec2 sh = shift(1.2);
  for (int i = 0; i < ${MAX_SPARKS}; i++) {
    if (i >= uSparkCount) break;
    vec4 s = uSpark[i]; vec4 b = uSparkB[i]; float age = uTime - s.w;
    if (age < 0.0) continue;
    float grow = smoothstep(0.0, 0.55, age) * (1.0 + 0.3 * exp(-age * 3.0) * sin(age * 13.0));
    float tw = 0.84 + 0.16 * sin(uTime * uTwinkle * 1.7 + b.y); float flare = 1.0 + b.z * 0.6;
    float reach = s.z * grow * tw * flare; float core = b.w * grow * flare;
    vec3 tint = mix(uHotColor, uStarColor, b.x); vec2 c = s.xy + sh; vec2 d = css - c;
    float th = uSpikeWidth * 0.5 + 0.25;
    float hx = step(abs(d.y), th) * pow(max(1.0 - abs(d.x) / max(reach, 1.0), 0.0), 1.1);
    float vy = step(abs(d.x), th) * pow(max(1.0 - abs(d.y) / max(reach, 1.0), 0.0), 1.1);
    vec2 rd = vec2(d.x + d.y, d.x - d.y) * 0.7071;
    float diag = step(0.5, core / px - 1.5) * 0.45 * max(
      step(abs(rd.y), th) * pow(max(1.0 - abs(rd.x) / max(reach * 0.22, 1.0), 0.0), 2.0),
      step(abs(rd.x), th) * pow(max(1.0 - abs(rd.y) / max(reach * 0.22, 1.0), 0.0), 2.0));
    col = mix(col, tint, clamp(max(max(hx, vy), diag), 0.0, 1.0));
    float hp = px * 0.5; vec2 dcell = (floor(css / hp) + 0.5) * hp - (floor(c / hp) + 0.5) * hp;
    float disc = step(length(dcell), core); float glow = exp(-length(d) / max(core * 1.4, 1.0)) * (1.0 - disc);
    col += tint * glow * 0.35; col = mix(col, tint, disc);
    float cross = max(step(abs(d.y), th) * step(abs(d.x), core * 0.85), step(abs(d.x), th) * step(abs(d.y), core * 0.85));
    col = mix(col, uStarColor, cross * disc * 0.9);
  }
  vec2 vu = gl_FragCoord.xy / uRes - 0.5;
  col *= 1.0 - uVignette * smoothstep(0.35, 0.95, length(vu * vec2(uRes.x / uRes.y, 1.0) * 1.1));
  col += (hash12(floor(css) + fract(uTime) * 91.0) - 0.5) * uGrain;
  frag = vec4(max(col, vec3(0.0)), 1.0);
}`;

/* --- the player ------------------------------------------------------------ */

export class IdleScenes {
  constructor(canvas, { scene = 'horizon' } = {}) {
    this.canvas = canvas;
    this.scene = SCENES.includes(scene) ? scene : 'horizon';
    this.gl = null;
    this.programs = {};
    this.raf = 0;
    this.running = false;
    this.failed = false;
    this.clock = 0;
    this.time = 7.3;
    this.feed = 0;
    this.feeding = false;
    this.par = [0, 0];
    this.pointer = null;         // [x, y] in 0..1, y up
    this.lastPointer = -1e9;
    this.sparks = layoutSparkles(NEBULA.seed, NEBULA.sparkles);
    this.flare = new Float32Array(MAX_SPARKS);
    this.sparkA = new Float32Array(MAX_SPARKS * 4);
    this.sparkB = new Float32Array(MAX_SPARKS * 4);
    this.ripples = new Float32Array(MAX_RIPPLES * 4);
    this.rippleNext = 0;
    this.lamp = [0.5, 0.5];
    this.look = [0, 0];
    this.lampOn = 0;
    this.wire();
  }

  wire() {
    const c = this.canvas;
    const at = (e) => {
      const r = c.getBoundingClientRect();
      return [Math.min(Math.max((e.clientX - r.left) / Math.max(r.width, 1), 0), 1),
              Math.min(Math.max(1 - (e.clientY - r.top) / Math.max(r.height, 1), 0), 1)];
    };
    c.addEventListener('pointermove', (e) => { this.pointer = at(e); this.lastPointer = this.clock; });
    c.addEventListener('pointerleave', () => { this.pointer = null; this.feeding = false; });
    c.addEventListener('pointerdown', (e) => {
      if (e.button > 0) return;
      this.pointer = at(e);
      this.lastPointer = this.clock;
      if (this.scene === 'horizon') { this.feeding = true; return; }
      const [x, y] = this.pointer;
      const rand = Math.random();
      this.sparks = pushSparkle(this.sparks, { x, y, reach: 0.045 + 0.08 * rand, core: 0.006 + 0.008 * rand,
        tint: Math.random() < 0.2 ? 1 : 0, phase: Math.random() * 6.283, born: this.clock, user: true });
      this.ripples.set([x * c.clientWidth, y * c.clientHeight, this.clock, 1], this.rippleNext * 4);
      this.rippleNext = (this.rippleNext + 1) % MAX_RIPPLES;
    });
    window.addEventListener('pointerup', () => { this.feeding = false; });
  }

  ensure() {
    if (this.gl || this.failed) return Boolean(this.gl);
    const gl = this.canvas.getContext('webgl2', { antialias: false, alpha: false, depth: false,
                                                 powerPreference: 'high-performance' });
    if (!gl) { this.failed = true; return false; }
    this.gl = gl;
    this.vao = gl.createVertexArray();
    return true;
  }

  program(name) {
    if (this.programs[name] !== undefined) return this.programs[name];
    const gl = this.gl;
    const compile = (type, src) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
        console.error(`idle ${name}:`, gl.getShaderInfoLog(s));
        return null;
      }
      return s;
    };
    const vs = compile(gl.VERTEX_SHADER, VERT);
    const fs = compile(gl.FRAGMENT_SHADER, name === 'horizon' ? HORIZON_FRAG : NEBULA_FRAG);
    let program = null;
    if (vs && fs) {
      program = gl.createProgram();
      gl.attachShader(program, vs);
      gl.attachShader(program, fs);
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        console.error(`idle ${name}:`, gl.getProgramInfoLog(program));
        program = null;
      }
    }
    const loc = (n) => (program ? gl.getUniformLocation(program, n) : null);
    this.programs[name] = program && { program, loc };
    return this.programs[name];
  }

  resize() {
    const c = this.canvas;
    const scale = this.scene === 'horizon' ? Math.min(window.devicePixelRatio || 1, 1.25) : Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.floor(c.clientWidth * scale)), h = Math.max(1, Math.floor(c.clientHeight * scale));
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  }

  setScene(name) {
    if (!SCENES.includes(name)) return;
    this.scene = name;
    this.resize();
    if (!this.running) this.paint(0);
  }

  next() {
    this.setScene(SCENES[(SCENES.indexOf(this.scene) + 1) % SCENES.length]);
    return this.scene;
  }

  start() {
    if (!this.ensure()) return false;
    this.running = true;
    this.last = performance.now();
    this.resize();
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const frame = (now) => {
      this.raf = 0;
      if (!this.running) return;
      const dt = Math.min((now - this.last) / 1000, 0.05);
      this.last = now;
      this.paint(still ? 0 : dt);
      if (!still) this.raf = requestAnimationFrame(frame);
    };
    this.raf = requestAnimationFrame(frame);
    return true;
  }

  stop() {
    this.running = false;
    cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  paint(dt) {
    if (!this.ensure()) return;
    this.clock += dt;
    const p = this.program(this.scene);
    if (!p) return;
    const gl = this.gl;
    gl.useProgram(p.program);
    gl.bindVertexArray(this.vao);
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    if (this.scene === 'horizon') this.paintHorizon(p.loc, dt);
    else this.paintNebula(p.loc, dt);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  paintHorizon(loc, dt) {
    const gl = this.gl, P = HORIZON;
    this.feed = approach(this.feed, this.feeding ? 1 : 0, dt, this.feeding ? 1.6 : 0.9);
    this.time += dt * P.speed * (1 + 2.6 * this.feed);
    const idle = this.clock - this.lastPointer > 4 || !this.pointer;
    const goal = idle ? idleDrift(this.clock) : [this.pointer[0] * 2 - 1, this.pointer[1] * 2 - 1];
    this.par = [approach(this.par[0], goal[0], dt, 2.2), approach(this.par[1], goal[1], dt, 2.2)];
    for (const [u, k] of [['uDisk', 'diskColor'], ['uStreak', 'streakColor'], ['uGlow', 'glowColor'],
                          ['uCloud', 'cloudColor'], ['uBg', 'background']]) gl.uniform3fv(loc(u), hexToRgb(P[k]));
    for (const [u, k] of [['uHole', 'holeSize'], ['uAngle', 'angle'], ['uIncl', 'inclination'],
                          ['uDiskRadius', 'diskRadius'], ['uShear', 'shear'], ['uDensity', 'streakDensity'],
                          ['uCrimson', 'crimson'], ['uDoppler', 'doppler'], ['uFlare', 'flare'],
                          ['uLensing', 'lensing'], ['uClouds', 'clouds'], ['uCloudLines', 'cloudLines'],
                          ['uStars', 'stars'], ['uGrain', 'grain'], ['uVignette', 'vignette'],
                          ['uExposure', 'exposure']]) gl.uniform1f(loc(u), P[k]);
    gl.uniform2f(loc('uRes'), this.canvas.width, this.canvas.height);
    gl.uniform2f(loc('uCenter'), P.center[0], P.center[1]);
    gl.uniform1f(loc('uTime'), this.time);
    gl.uniform1f(loc('uClock'), this.clock);
    gl.uniform1f(loc('uFeed'), this.feed);
    gl.uniform2f(loc('uParallax'), this.par[0], this.par[1]);
  }

  paintNebula(loc, dt) {
    const gl = this.gl, P = NEBULA, c = this.canvas;
    const cssW = Math.max(c.clientWidth, 1), cssH = Math.max(c.clientHeight, 1);
    const t = this.clock * P.speed;
    const idle = !this.pointer || this.clock - this.lastPointer > 6;
    const [gx, gy] = driftPos(t * 0.6);
    const want = idle ? [gx, gy] : this.pointer;
    const k = 1 - Math.exp(-dt * (idle ? 1.5 : 7));
    this.lamp = [this.lamp[0] + (want[0] - this.lamp[0]) * k, this.lamp[1] + (want[1] - this.lamp[1]) * k];
    this.look = [this.look[0] + ((want[0] - 0.5) * 2 - this.look[0]) * k,
                 this.look[1] + ((want[1] - 0.5) * 2 - this.look[1]) * k];
    this.lampOn += ((idle ? 0.55 : 1) - this.lampOn) * (1 - Math.exp(-dt * 3));
    const minSide = Math.min(cssW, cssH);
    const n = Math.min(this.sparks.length, MAX_SPARKS);
    for (let i = 0; i < n; i++) {
      const s = this.sparks[i];
      const reach = s.reach * minSide;
      const d = Math.hypot(s.x * cssW - this.lamp[0] * cssW, s.y * cssH - this.lamp[1] * cssH);
      const goal = Math.exp(-(d * d) / Math.max(reach * reach * 0.6, 400));
      this.flare[i] += (goal - this.flare[i]) * (1 - Math.exp(-dt * 6));
      this.sparkA.set([s.x * cssW, s.y * cssH, reach, s.born], i * 4);
      this.sparkB.set([s.tint, s.phase, this.flare[i], Math.max(s.core * minSide, 1.5)], i * 4);
    }
    for (const [key, kind] of NEBULA_UNIFORMS) {
      if (kind === 'c') gl.uniform3fv(loc(uName(key)), hexToRgb(P[key]));
      else gl.uniform1f(loc(uName(key)), P[key]);
    }
    gl.uniform2f(loc('uRes'), c.width, c.height);
    gl.uniform1f(loc('uDpr'), c.width / cssW);
    gl.uniform1f(loc('uTime'), t);
    gl.uniform2f(loc('uPointer'), this.lamp[0] * cssW, this.lamp[1] * cssH);
    gl.uniform1f(loc('uPointerOn'), this.lampOn);
    gl.uniform2f(loc('uLook'), this.look[0], this.look[1]);
    gl.uniform1i(loc('uSparkCount'), n);
    gl.uniform4fv(loc('uSpark'), this.sparkA);
    gl.uniform4fv(loc('uSparkB'), this.sparkB);
    gl.uniform4fv(loc('uRipple'), this.ripples);
    gl.uniform4f(loc('uPlanet'), P.planetX * cssW, P.planetY * cssH, P.planetRadius * minSide, P.planet ? 1 : 0);
  }
}
