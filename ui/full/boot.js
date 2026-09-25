// As Apollo comes up, an old machine boots: its checks typed out line by
// line on a green tube, the name settling out of its scramble in the middle,
// and then the prompt. Text on the glass and nothing else.

const WIDTH = 34;        // every check the same width, its status flush right

/* "VOICE LINK", "ONLINE" -> "VOICE LINK ............... ONLINE" */
function check(label, status) {
  const dots = Math.max(3, WIDTH - label.length - status.length - 2);
  return `${label} ${'.'.repeat(dots)} ${status}`;
}

export function bootLines() {
  return [
    'APOLLO/OS  REV 7.1   (C) 1986',
    '',
    check('MEMORY', '640K OK'),
    check('VOICE LINK', 'ONLINE'),
    check('MARKET FEED', 'ONLINE'),
    check('PRIVATE EYE', 'ON WATCH'),
    check('NEURAL CORE', 'READY'),
  ];
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
