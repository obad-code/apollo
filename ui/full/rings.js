/* Apollo's shape, as data: a circle, the way the old display drew it - five
 * rings of lit dots nested inside one another, from six dots round the
 * middle to twenty-eight round the edge, each turning the other way from the
 * one inside it, the inner ones faster. app.js draws them (and the scope's
 * graticule, the dark lens in the middle, the wave going out while Apollo
 * works and the white bloom while it speaks); this only says where the dots
 * are, so node can check it (tests/test_rings.py).
 *
 * Radii are in units of the core's own radius; `clock` is the rings' own
 * time in ms, which app.js runs faster while Apollo is busy - accumulated,
 * not multiplied, so a change of pace never makes the rings jump.
 *
 * And in 3D, as the old display's own 3D had them: each ring a latitude of
 * one sphere, meridians joining them pole to pole, the sphere turning slowly
 * about its axis and tipped towards you (sphereDots, meridian, view). On the
 * screen x runs right and y down; z comes towards you. */

export const LAYERS = [
  { r: 0.26, n: 6, sp: 0.00046 },
  { r: 0.44, n: 10, sp: 0.00034 },
  { r: 0.62, n: 14, sp: 0.00025 },
  { r: 0.80, n: 20, sp: 0.00019 },
  { r: 0.98, n: 28, sp: 0.00014 },
];

/* Where layer `index`'s dots are at `clock`: evenly round its ring, turned by
 * its own speed, one way for the even layers and the other for the odd -
 * and each a little set round from the one inside it, as the old one was. */
export function layerDots(index, clock) {
  const layer = LAYERS[index];
  const turn = clock * layer.sp * (index % 2 === 0 ? 1 : -1) + index * 0.4;
  const dots = [];
  for (let k = 0; k < layer.n; k++) {
    const angle = turn + (k / layer.n) * Math.PI * 2;
    dots.push({ x: Math.cos(angle) * layer.r, y: Math.sin(angle) * layer.r });
  }
  return dots;
}

// Which latitude each ring settles on, top pole to bottom: the six-dotted
// ring round the top pole, the ten round the bottom, the fourteen and the
// twenty either side of the middle, the twenty-eight round the equator.
const LATITUDE = [0, 4, 1, 3, 2];
// How far the sphere's axis tips towards you, and leans to the side.
const TIP = 0.42;
const LEAN = 0.2;

/* Layer `index`'s dots on the sphere at `clock`: round its latitude, turning
 * about the axis the way the flat ring turns - one way for the even layers
 * and the other for the odd. Before the sphere is tipped or turned. */
export function sphereDots(index, clock) {
  const layer = LAYERS[index];
  const from = ((LATITUDE[index] + 0.5) / LAYERS.length) * Math.PI;   // down from the top pole
  const round = Math.sin(from), y = -Math.cos(from);
  const turn = clock * layer.sp * (index % 2 === 0 ? 1 : -1) + index * 0.4;
  const dots = [];
  for (let k = 0; k < layer.n; k++) {
    const a = turn + (k / layer.n) * Math.PI * 2;
    dots.push({ x: Math.cos(a) * round, y, z: Math.sin(a) * round });
  }
  return dots;
}

/* Meridian `m` of eight, pole to pole in `steps` steps. */
export function meridian(m, steps) {
  const phi = (m / 8) * Math.PI;
  const line = [];
  for (let i = 0; i <= steps; i++) {
    const from = (i / steps) * Math.PI;
    line.push({ x: Math.sin(from) * Math.cos(phi), y: -Math.cos(from), z: Math.sin(from) * Math.sin(phi) });
  }
  return line;
}

/* A point of the sphere as it is seen: turned about the axis by `spin`,
 * tipped towards you and leaning a little. */
export function view(p, spin) {
  const cs = Math.cos(spin), sn = Math.sin(spin);
  let x = p.x * cs - p.z * sn;
  let z = p.x * sn + p.z * cs;
  let y = p.y;
  const ct = Math.cos(TIP), st = Math.sin(TIP);
  [y, z] = [y * ct + z * st, -y * st + z * ct];
  const cl = Math.cos(LEAN), sl = Math.sin(LEAN);
  [x, y] = [x * cl - y * sl, x * sl + y * cl];
  return { x, y, z };
}

/* `current` moved towards `target` over `dt` seconds, most of the way in
 * about `seconds`: how the rings' pace, their brightness and the white of
 * Apollo speaking come and go - eased, frame by frame, at any frame rate. */
export function ease(current, target, dt, seconds) {
  return current + (target - current) * (1 - Math.exp(-dt / seconds));
}
