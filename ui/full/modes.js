/* The display's modes: one at a time, on the bar along the bottom of the
 * screen, and by voice ("summary mode", "trading mode", "الوضع الموسع").
 *
 *   normal    - the display as it always was
 *   summary   - the whole of Apollo on one calm page (summarymode.js)
 *   trading   - the trading desk: insiders, Congress, the filings and
 *               headlines that move a price, what traders are on, and the
 *               read of what they pick next
 *   agents    - the agents, each as its pipeline - LYLA, for now
 *   expanded  - ultra mode: every display at once, as tiles
 *   osiris    - the OSIRIS map laid into the display
 *
 * Underneath they are three switches: ultra mode, the map, and which view
 * of the normal display is up (normal, summary, trading or agents). This says
 * which mode those make, and which to throw, in order, to get to another:
 * leaving before arriving, so the map and ultra mode never fight over the
 * screen. Going into ultra mode from the map leaves the map on - ultra mode
 * takes it in as one of its tiles. app.js throws them; node checks the plan
 * (tests/test_modes.py). */

export const MODES = [
  { id: 'normal', label: 'Normal' },
  { id: 'summary', label: 'Summary' },
  { id: 'trading', label: 'Trading' },
  { id: 'agents', label: 'Agents' },
  { id: 'expanded', label: 'Expanded' },
  { id: 'osiris', label: 'OSIRIS' },
];

// The views of the normal display; each is a mode of its own.
export const VIEWS = ['normal', 'summary', 'trading', 'agents'];

/* Which mode the switches make. */
export function current({ ultra, osiris, view }) {
  if (ultra) return 'expanded';
  if (osiris) return 'osiris';
  return VIEWS.includes(view) ? view : 'normal';
}

/* The switches to throw, in order, from `on` to mode `wanted`: each a
 * [switch, state] pair - ['view', name] for the view. Nothing for a mode
 * that is already on, or one there is not. */
export function plan(on, wanted) {
  if (!MODES.some((m) => m.id === wanted) || current(on) === wanted) return [];
  const view = VIEWS.includes(on.view) ? on.view : 'normal';
  const steps = [];
  if (wanted === 'expanded') {
    if (view !== 'normal') steps.push(['view', 'normal']);
    if (!on.ultra) steps.push(['ultra', true]);
    return steps;
  }
  if (on.ultra) steps.push(['ultra', false]);
  if (wanted === 'osiris') {
    if (view !== 'normal') steps.push(['view', 'normal']);
    if (!on.osiris) steps.push(['osiris', true]);
    return steps;
  }
  if (on.osiris) steps.push(['osiris', false]);
  if (view !== wanted) steps.push(['view', wanted]);
  return steps;
}
