/* The explanation box: what Apollo is saying, shown, in the middle of the
 * display while he talks - and Apollo himself small in the corner above it.
 *
 * It holds whatever the answer brings: your words, his reply as it arrives,
 * a chart (a stock you asked about), a row of figures, a picture he made, or
 * a visual explanation - a few steps laid out as glowing cards on a line, so
 * a "how does it work" reads as a picture rather than a paragraph.
 *
 * `markup(payload)` builds the inside of #visual from a payload; app.js puts
 * it there and decides when the box is up. Nothing here touches the page,
 * so tests run it under node. Every string from outside is escaped; a
 * picture is only ever a data: image Apollo made, or an https address. */

const esc = (value) => String(value ?? '').replace(/[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* A picture's address, if it is one the box may show. */
export function safeSrc(src) {
  const s = String(src || '');
  if (/^data:image\/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/=]+$/.test(s)) return s;
  if (/^https:\/\/[^\s"'<>]+$/.test(s)) return s;
  return '';
}

/* The steps of a visual explanation: numbered cards on a glowing line, each
 * lighting up a moment after the one before (CSS, --i). */
export function steps(list) {
  const items = (Array.isArray(list) ? list : []).slice(0, 6)
    .map((s) => (typeof s === 'string' ? { title: s } : s || {}))
    .filter((s) => s.title || s.text);
  if (!items.length) return '';
  return `<ol class="ex-steps" style="--n:${items.length}">${items.map((s, i) => `
    <li style="--i:${i}">
      <span class="ex-num">${String(i + 1).padStart(2, '0')}</span>
      <b>${esc(s.title)}</b>${s.text ? `<p>${esc(s.text)}</p>` : ''}
    </li>`).join('')}</ol>`;
}

export function cards(list) {
  const items = (Array.isArray(list) ? list : []).filter((c) => c && c.label && c.value).slice(0, 6);
  if (!items.length) return '';
  return `<div class="ex-cards">${items.map((c, i) => `
    <div class="ex-figure" style="--i:${i}"><small>${esc(c.label)}</small><b>${esc(c.value)}</b></div>`).join('')}</div>`;
}

export function picture(image) {
  const src = safeSrc(image && image.src);
  if (!src) return '';
  return `<figure class="ex-picture">
    <img src="${src}" alt="${esc(image.caption || 'A picture Apollo made')}">
    ${image.caption ? `<figcaption>${esc(image.caption)}</figcaption>` : ''}
  </figure>`;
}

/* The whole of it. `chart(payload)` is the display's own chart drawing. */
export function markup(payload, chart = () => '') {
  const p = payload || {};
  const parts = [];
  if (p.title) parts.push(`<h3 class="ex-title">${esc(p.title)}</h3>`);
  if (p.image) parts.push(picture(p.image));
  if (p.chart) {
    const drawn = chart(p);
    if (drawn) {
      const label = p.chart.label ? `<span class="ex-chart-label">${esc(p.chart.label)}</span>` : '';
      parts.push(`<div class="ex-chart">${label}${drawn}</div>`);
    }
  }
  if (p.steps) parts.push(steps(p.steps));
  if (p.cards) parts.push(cards(p.cards));
  if (p.text) parts.push(`<p class="ex-text" dir="auto">${esc(p.text)}</p>`);
  return parts.join('');
}

/* Where Apollo goes while he talks: from his place in the middle to the top
 * left corner, small. The layout box is read (offsets ignore transforms), so
 * this is right whatever transform he has at the moment. */
export function cornerShift(core, { x = 118, y = 96, scale = 0.34 } = {}) {
  if (!core) return null;
  let left = core.offsetLeft, top = core.offsetTop, parent = core.offsetParent;
  while (parent) { left += parent.offsetLeft; top += parent.offsetTop; parent = parent.offsetParent; }
  const cx = left + core.offsetWidth / 2, cy = top + core.offsetHeight / 2;
  return { dx: Math.round(x - cx), dy: Math.round(y - cy), scale };
}
