// As Apollo comes up, an old machine boots: its checks typed out line by
// line on a green tube, the name settling out of its scramble in the middle,
// and then the prompt. Text on the glass and nothing else.
//
// The checks are real ones now (diagnostics.py and the start in apollo.py):
// each is a line as it lands, what went wrong is said under it, and the log
// scrolls like a terminal's when there is more of it than the glass holds.

const WIDTH = 34;        // every check the same width, its status flush right
const WORDS = { ok: 'OK', warn: 'WARN', fail: 'FAIL' };

export const HEADER = ['APOLLO/OS  REV 8.0   (C) 1986', 'RUNNING SELF-DIAGNOSTICS', ''];

/* "VOICE LINK", "ONLINE" -> "VOICE LINK ............... ONLINE" */
function check(label, status) {
  const dots = Math.max(3, WIDTH - label.length - status.length - 2);
  return `${label} ${'.'.repeat(dots)} ${status}`;
}

/* One check's line: its name, and how it went. */
export function checkLine(step) {
  return check(String(step.label || '').toUpperCase(), WORDS[step.status] || 'OK');
}

/* What went wrong, under the line that says so. */
export function detailLine(step) {
  const detail = String(step.detail || '').replace(/\s+/g, ' ').trim();
  return `  - ${detail.length > WIDTH - 4 ? `${detail.slice(0, WIDTH - 5)}…` : detail}`;
}

/* The whole log for these steps: the header, then a line a check - and
 * one more under each that did not go right. */
export function bootLines(steps = []) {
  const lines = [...HEADER];
  for (const step of steps) {
    lines.push(checkLine(step));
    if (step.status !== 'ok' && step.detail) lines.push(detailLine(step));
  }
  return lines;
}

/* The prompt under the name: online, and whether there is anything to fix. */
export function readyLine(summary) {
  const n = summary && Number.isFinite(summary.issues) ? summary.issues : 0;
  if (!n) return '> SYSTEM ONLINE';
  return `> SYSTEM ONLINE · ${n} ISSUE${n === 1 ? '' : 'S'} ON THE SYSTEM PANEL`;
}

/* When each line starts typing: when it came, but never before the one
 * before it has had `gap` seconds. [{text, arrived}] -> [{text, at}]. */
export function schedule(entries, gap = 0.09) {
  let last = -Infinity;
  return entries.map((entry) => {
    const at = Math.max(entry.arrived, last + gap);
    last = at;
    return { ...entry, at: Math.round(at * 1000) / 1000 };
  });
}

/* The log `now` seconds in: every line that has started, typed at `rate`
 * letters a second from its own start. */
export function typedAt(scheduled, now, rate = 300) {
  return scheduled.filter((entry) => now >= entry.at)
    .map((entry) => entry.text.slice(0, Math.floor((now - entry.at) * rate + 1e-9)))
    .join('\n');
}

/* The last `most` lines: the glass holds so many, and a terminal scrolls. */
export function lastLines(text, most) {
  const lines = String(text).split('\n');
  return lines.slice(Math.max(0, lines.length - most)).join('\n');
}

/* What has been typed `seconds` in: line i starts `gap` after the one
 * before it and types at `rate` letters a second. A line that has started
 * shows, even with nothing typed on it yet: the cursor has moved down. */
export function typed(lines, seconds, { start = 0.15, gap = 0.13, rate = 260 } = {}) {
  const shown = [];
  lines.forEach((line, i) => {
    const t = seconds - (start + i * gap);
    if (t >= 0) shown.push(line.slice(0, Math.floor(t * rate + 1e-9)));
  });
  return shown.join('\n');
}
