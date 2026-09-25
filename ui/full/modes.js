/* The display's modes: one at a time, on the bar along the bottom of the
 * screen, and by voice ("clear mode", "الوضع الموسع").
 *
 *   normal    - the display as it always was
 *   clear     - nothing but Apollo and the sign to press Ctrl+Alt
 *   expanded  - ultra mode: every display at once, as tiles
 *   osiris    - the OSIRIS map laid into the display
 *
 * Underneath they are three switches the page already had or has now -
 * ultra mode, the map, and clear - and this says which mode those make, and
 * which of them to throw, in order, to get to another: leaving before
 * arriving, so the map and ultra mode never fight over the screen. Going
 * into ultra mode from the map leaves the map on - ultra mode takes it in
 * as one of its tiles. app.js throws them; node checks the plan
 * (tests/test_modes.py). */

export const MODES = [
  { id: 'normal', label: 'Normal' },
  { id: 'clear', label: 'Clear' },
  { id: 'expanded', label: 'Expanded' },
  { id: 'osiris', label: 'OSIRIS' },
];

/* Which mode the switches make. */
export function current({ ultra, osiris, clear }) {
  if (ultra) return 'expanded';
  if (osiris) return 'osiris';
  if (clear) return 'clear';
  return 'normal';
}

/* The switches to throw, in order, from `on` to mode `wanted`: each a
 * [switch, state] pair. Nothing for a mode that is already on, or one there
 * is not. */
export function plan(on, wanted) {
  if (!MODES.some((m) => m.id === wanted) || current(on) === wanted) return [];
  const steps = [];
  const set = (what, state) => { if (Boolean(on[what]) !== state) steps.push([what, state]); };
  if (wanted === 'expanded') {
    set('clear', false);
    set('ultra', true);
    return steps;
  }
  set('ultra', false);
  set('osiris', wanted === 'osiris');
  set('clear', wanted === 'clear');
  return steps;
}
