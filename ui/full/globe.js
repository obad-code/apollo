/* Apollo's shape, as data: a globe drawn the way a wireframe icon draws
 * one - a wide ellipse, meridians from pole to pole as narrower ellipses
 * inside it, parallels straight across - and a four-pointed star of light
 * at its heart. Seen from over its equator and turning about its upright
 * axis, so the meridians widen and narrow as they come round, each great
 * circle a near half and a far half. app.js draws it (and the glow, the
 * bloom while Apollo speaks and the wave while it works); this says where
 * everything is, in units of the globe's half-width, with y running down,
 * so node can check it (tests/test_globe.py). */

// The globe's height to its width: wide, like the picture it was drawn from.
export const ASPECT = 0.52;
// Great circles through the poles, this many to a half turn: 30 degrees
// apart, so at rest they are the picture's - an upright line, ellipses at
// half the width and most of it, and the outline.
export const CIRCLES = 6;
// The lines across, as the sine of their latitude: the equator and 30
// degrees either side of it.
const ACROSS = [-0.5, 0, 0.5];

/* The meridians at `turn` (radians): each great circle through the poles as
 * two halves - x = w·cos(φ), y = ASPECT·sin(φ), pole to pole - its near
 * half then its far one. `w` is where a half crosses the equator (-1 left
 * .. 1 right), `near` how far towards you its middle is (-1 .. 1). */
export function meridians(turn) {
  const halves = [];
  for (let k = 0; k < CIRCLES; k++) {
    const a = turn + (k * Math.PI) / CIRCLES;
    // The half facing you first, whichever way round the circle is.
    const front = Math.cos(a) >= 0 ? a : a + Math.PI;
    for (const lon of [front, front + Math.PI]) {
      halves.push({ w: Math.sin(lon), near: Math.cos(lon) });
    }
  }
  return halves;
}

/* The parallels: straight across at height `y`, from -half to half. */
export function parallels() {
  return ACROSS.map((s) => ({ y: ASPECT * s, half: Math.sqrt(1 - s * s) }));
}

/* The star, `r` from its middle to each point: four arms, each a tip on an
 * axis and the curve in to the next drawn towards `pinch`, close to the
 * middle, so the arms are thin and curved in. Clockwise from the right. */
export function star(r) {
  const c = r * 0.11;
  return [
    { tip: [r, 0], pinch: [c, c] },
    { tip: [0, r], pinch: [-c, c] },
    { tip: [-r, 0], pinch: [-c, -c] },
    { tip: [0, -r], pinch: [c, -c] },
  ];
}

/* `current` moved towards `target` over `dt` seconds, most of the way in
 * about `seconds`: how its pace, its brightness and the white of Apollo
 * speaking come and go - eased, frame by frame, at any frame rate. */
export function ease(current, target, dt, seconds) {
  return current + (target - current) * (1 - Math.exp(-dt / seconds));
}
