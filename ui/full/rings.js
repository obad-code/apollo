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
 * not multiplied, so a change of pace never makes the rings jump. */

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

/* `current` moved towards `target` over `dt` seconds, most of the way in
 * about `seconds`: how the rings' pace, their brightness and the white of
 * Apollo speaking come and go - eased, frame by frame, at any frame rate. */
export function ease(current, target, dt, seconds) {
  return current + (target - current) * (1 - Math.exp(-dt / seconds));
}
