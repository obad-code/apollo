/* The consoles' readouts and lights, each one something true.
 *
 * The strip of eighteen lights reads left to right in three sixes:
 *   the sources   prices, news, posts, weather, the machine, Private Eye -
 *                 green while fresh, amber once older than it should be,
 *                 dark before the first reading;
 *   Apollo        listening, thinking, speaking (each blinking while it
 *                 lasts), hands-free and away (steady), LYLA on a job
 *                 (blinking);
 *   the load      the CPU as a meter, green, then amber, then red.
 * Every light says what it is when the pointer rests on it.
 *
 * And the readouts: how long Apollo has been up, how quickly the internet
 * answers, the CPU's load, the card's heat. Plain functions of what the
 * data service last said (sysinfo.py), so node can check them
 * (tests/test_console_lights.py). */

export const SOURCES = ['market', 'news', 'posts', 'weather', 'system', 'finds'];
// How old each may get before its light turns amber - the page's own limits
// (app.js STALE_AFTER), and Private Eye's, which reads every few hours.
export const STALE_AFTER = { market: 180, news: 1800, posts: 900, weather: 2700, system: 15, finds: 6 * 3600 };
const NAMES = { market: 'Prices', news: 'News', posts: 'Posts', weather: 'Weather',
                system: 'The machine', finds: 'Private Eye' };

const light = (colour, on, title, blink = false) => ({ colour: on ? colour : 'off', on, blink: on && blink, title });

export function lights({ stamps = {}, now = Date.now() / 1000, phase = 'idle', listening = false,
                         away = false, lyla = false, cpu = null } = {}) {
  const out = SOURCES.map((key) => {
    const at = Number(stamps[key]) || 0;
    if (!at) return light('green', false, `${NAMES[key]}: not read yet`);
    const age = Math.max(0, now - at);
    return age > STALE_AFTER[key]
      ? light('amber', true, `${NAMES[key]}: ${Math.round(age / 60)} min old`)
      : light('green', true, `${NAMES[key]}: fresh`);
  });
  out.push(light('cyan', phase === 'listening', 'Listening', true));
  out.push(light('amber', phase === 'thinking', 'Thinking', true));
  out.push(light('green', phase === 'speaking', 'Speaking', true));
  out.push(light('cyan', Boolean(listening), 'Hands-free'));
  out.push(light('amber', Boolean(away), 'Away'));
  out.push(light('blue', Boolean(lyla), 'LYLA on a job', true));
  const load = Number.isFinite(cpu) ? Math.max(0, Math.min(100, cpu)) : null;
  const lit = load === null ? 0 : Math.ceil((load / 100) * 6);
  for (let i = 0; i < 6; i++) {
    out.push(light(i < 3 ? 'green' : i < 5 ? 'amber' : 'red', i < lit, `CPU ${load === null ? '—' : `${load}%`}`));
  }
  return out;
}

const pad = (n) => String(n).padStart(2, '0');

export function uptime(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  return `T+${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
}

export const linkText = (ms) => (Number.isFinite(ms) ? `LINK ${Math.round(ms)}ms` : 'LINK DOWN');
export const cpuText = (cpu) => (Number.isFinite(cpu) ? `CPU ${Math.round(cpu)}%` : 'CPU —');
export const tempText = (temp) => (Number.isFinite(temp) ? `GPU ${Math.round(temp)}°C` : 'GPU —');

/* The six bars beside them: the last six CPU readings, oldest first, as
 * heights between 3 and 14 pixels. */
export function bars(history, n = 6) {
  const last = (history || []).filter(Number.isFinite).slice(-n);
  while (last.length < n) last.unshift(0);
  return last.map((cpu) => Math.round(3 + (Math.max(0, Math.min(100, cpu)) / 100) * 11));
}
