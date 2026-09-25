/* Apollo as a planet, as data: a sphere of lit dots - quantum dots, each its
 * own small light - spread evenly over it, some land and most sea, tipped on
 * its axis and turning, seen from a little above, with a ring of dots round
 * its middle. app.js draws it (the light and the dark side, the air round
 * it, how it answers your voice); this only says where the dots are, so
 * node can check it (tests/test_planet.py).
 *
 * Units are the planet's own radius. On the screen, x runs right and y
 * down; z comes towards you, so what faces you has z above nothing. */

const GOLDEN = Math.PI * (3 - Math.sqrt(5));
// Tipped on its axis like the Earth, and seen from a little above its equator.
const TILT = 0.3;
const VIEW = 0.32;
// The ring, from and to, in the planet's radii.
export const RING = [1.45, 1.95];

/* `n` points spread evenly over the unit sphere - the Fibonacci lattice:
 * equal steps down the axis, each turned the golden angle from the last, so
 * equal areas get equal numbers and nothing bunches at the poles. */
export function sphere(n) {
  const dots = [];
  for (let i = 0; i < n; i++) {
    const y = 1 - (2 * (i + 0.5)) / n;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const a = i * GOLDEN;
    dots.push({ x: Math.cos(a) * r, y, z: Math.sin(a) * r });
  }
  return dots;
}

/* How high the ground is at a point on the sphere: a few smooth waves across
 * it at odd angles, the same every time. Above nothing is land. */
export function height(p) {
  return Math.sin(2.1 * p.x + 1.3) * Math.sin(1.7 * p.y + 0.4) * Math.sin(2.6 * p.z + 2.2)
       + 0.55 * Math.sin(4.3 * p.x - 3.1 * p.z + 0.7) * Math.sin(3.7 * p.y + 1.9)
       + 0.3 * Math.sin(7.9 * p.y + 5.3 * p.x) * Math.sin(6.1 * p.z - 0.8)
       - 0.12;
}

export const isLand = (p) => height(p) > 0;

/* Where a point of the planet is on the screen: turned about its own axis
 * by `spin` (radians), tipped by its tilt, and seen from a little above. */
export function project(p, spin) {
  const cs = Math.cos(spin), sn = Math.sin(spin);
  let x = p.x * cs + p.z * sn;
  let z = -p.x * sn + p.z * cs;
  let y = p.y;
  const ct = Math.cos(TILT), st = Math.sin(TILT);
  [x, y] = [x * ct - y * st, x * st + y * ct];
  const cv = Math.cos(VIEW), sv = Math.sin(VIEW);
  [y, z] = [y * cv - z * sv, y * sv + z * cv];
  return { x, y: -y, z };
}

/* `n` dots on a flat ring round the equator, in a few bands with gaps
 * between them, the same every time. */
export function ringDots(n) {
  let seed = 7;
  const next = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  const bands = [[RING[0], 1.62], [1.68, 1.82], [1.86, RING[1]]];
  const dots = [];
  for (let i = 0; i < n; i++) {
    const [from, to] = bands[i % bands.length];
    const r = from + (to - from) * next();
    const a = (i / n) * Math.PI * 2 + next() * 0.05;
    dots.push({ x: Math.cos(a) * r, y: 0, z: Math.sin(a) * r });
  }
  return dots;
}

/* `current` moved towards `target` over `dt` seconds, most of the way in
 * about `seconds`: how the planet's pace, its brightness and the white of
 * Apollo speaking come and go - eased, frame by frame, at any frame rate. */
export function ease(current, target, dt, seconds) {
  return current + (target - current) * (1 - Math.exp(-dt / seconds));
}
