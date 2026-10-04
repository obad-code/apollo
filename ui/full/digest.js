/* Your summary: a small button by the clock that lights when a new one is
 * ready, and a quiet page it opens - the markets with their lines, your
 * stocks' moves as one chart, how right MONEYPENNY has been, the weather,
 * the news, earnings and reminders. Nothing is spoken. */

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pct = (v) => `${v >= 0 ? '+' : ''}${Number(v).toFixed(2)}%`;
const MARK = `<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="12" rx="10" ry="6.2" fill="none" stroke="currentColor" stroke-width="1.3"/>
  <ellipse cx="12" cy="12" rx="4.6" ry="6.2" fill="none" stroke="currentColor" stroke-width="1"/><path d="M12 8.2l.9 2.9 2.9.9-2.9.9-.9 2.9-.9-2.9-2.9-.9 2.9-.9z" fill="currentColor"/></svg>`;

/* One line, filled faintly to its baseline, with a crosshair on hover. */
function area(points, up, w = 220, h = 54) {
  if (!points || points.length < 2) return '<div class="dg-nochart">no chart</div>';
  const lo = Math.min(...points), hi = Math.max(...points), span = hi - lo || 1;
  const xy = points.map((p, i) => [i / (points.length - 1) * w, 4 + (1 - (p - lo) / span) * (h - 8)]);
  const line = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join('');
  const tone = up ? 'var(--up)' : 'var(--down)';
  return `<svg class="dg-area" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" data-points="${points.join(',')}">
    <path d="${line}L${w},${h}L0,${h}Z" fill="${tone}" opacity=".10"/>
    <path d="${line}" fill="none" stroke="${tone}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
    <line class="dg-cross" x1="0" x2="0" y1="0" y2="${h}" vector-effect="non-scaling-stroke"/></svg>`;
}

/* Today's move of each stock: bars either side of zero. */
function moves(stocks) {
  if (!stocks?.length) return '<p class="dg-empty">Your watchlist is empty.</p>';
  const most = Math.max(1, ...stocks.map((s) => Math.abs(s.change_pct)));
  return `<div class="dg-moves" role="table" aria-label="Today's move per stock">${stocks.map((s) => {
    const w = Math.abs(s.change_pct) / most * 50;
    const up = s.change_pct >= 0;
    return `<div class="dg-move" role="row" title="${esc(s.symbol)} ${pct(s.change_pct)} · ${s.price}">
      <span class="dg-sym" role="cell">${esc(s.symbol)}</span>
      <span class="dg-track" role="cell"><i class="${up ? 'up' : 'down'}" style="${up ? 'left:50%' : `left:${50 - w}%`};width:${w}%"></i><b></b></span>
      <span class="dg-val" role="cell">${pct(s.change_pct)}</span>
      <span class="dg-call" role="cell">${esc(s.verdict || '')}</span></div>`;
  }).join('')}</div>`;
}

function accuracy(a) {
  if (!a) return '<p class="dg-empty">Not available.</p>';
  const tile = (mark) => {
    const m = a.marks?.[mark] || {};
    return `<div class="dg-stat"><b>${m.rate == null ? '—' : `${m.rate}%`}</b>
      <span>right after ${mark} days</span><small>${m.calls ? `${m.right} of ${m.calls} calls` : 'none graded yet'}</small></div>`;
  };
  const recent = (a.recent || []).map((r) => `<li><span>${esc(r.symbol)}</span><em>${esc(r.verdict)}</em>
    <span class="${r.move >= 0 ? 'up' : 'down'}">${r.move >= 0 ? '+' : ''}${r.move}%</span><b>${r.right ? '✓' : '✗'}</b></li>`).join('');
  const lessons = (a.lessons || []).map((l) => `<li><span>${esc(l.symbol)}</span><p>${esc(l.lesson)}</p></li>`).join('');
  return `<div class="dg-stats">${tile(7)}${tile(30)}<div class="dg-stat"><b>${a.open ?? 0}</b><span>calls waiting</span><small>graded a week after</small></div></div>
    ${recent ? `<ul class="dg-recent">${recent}</ul>` : ''}
    ${lessons ? `<h4 class="dg-sub">What she learned from her misses</h4><ul class="dg-lessons">${lessons}</ul>` : ''}`;
}

export function markup(d) {
  if (!d || !d.made) return '<div class="dg-loading">No summary yet - press refresh to make one.</div>';
  const sky = d.weather || {};
  const idx = (d.indices || []).map((q) => `<div class="dg-index">
      <div class="dg-index-head"><span>${esc(q.symbol === '^GSPC' ? 'S&P 500' : q.symbol === '^IXIC' ? 'Nasdaq' : q.symbol)}</span>
      <b>${Number(q.price).toLocaleString('en-US')}</b><em class="${q.change_pct >= 0 ? 'up' : 'down'}">${pct(q.change_pct)}</em></div>
      ${area(q.spark, q.change_pct >= 0)}</div>`).join('');
  const news = Object.entries(d.news || {}).filter(([, rows]) => rows?.length).map(([topic, rows]) => `
      <div class="dg-topic"><h4>${esc(topic)}</h4>${rows.map((r) => `<a href="#" data-link="${esc(r.link)}">${esc(r.title)}<small>${esc(r.source)} · ${esc(r.age)}</small></a>`).join('')}</div>`).join('');
  const earnings = (d.earnings || []).map((e) => `<li><b>${esc(e.symbol)}</b> reports ${e.days === 0 ? 'today' : e.days === 1 ? 'tomorrow' : `in ${e.days} days`}</li>`).join('');
  const rem = (d.reminders || []).map((r) => `<li>${esc(r.text)}<small>${esc(r.due)}</small></li>`).join('');
  const made = new Date(d.made);
  return `
  <header class="dg-head">
    <div><h2>Your summary</h2><p>${esc(d.date)}${d.hijri ? ` · ${esc(d.hijri)}` : ''}</p></div>
    <div class="dg-head-right">
      ${sky.temp != null ? `<div class="dg-sky"><b>${Math.round(sky.temp)}°</b><span>${esc(sky.text || '')}<br>H ${esc(sky.high)}° · L ${esc(sky.low)}°</span></div>` : ''}
      <button type="button" class="dg-refresh" data-act="refresh" title="Make a new one now">↻</button>
      <button type="button" class="dg-close" data-act="close" aria-label="Close">✕</button>
    </div>
  </header>
  <div class="dg-grid">
    <section class="dg-card dg-wide"><h3>Markets <small>${esc(d.status || '')}</small></h3><div class="dg-indices">${idx || '<p class="dg-empty">The market feed did not answer.</p>'}</div></section>
    <section class="dg-card"><h3>Your stocks <small>today · call</small></h3>${moves(d.stocks)}</section>
    <section class="dg-card"><h3>MONEYPENNY's record</h3>${accuracy(d.accuracy)}</section>
    ${(d.theia || []).length ? `<section class="dg-card dg-wide dg-theia"><h3>THEIA · for today</h3><div class="dg-three">${d.theia.map((t) =>
      `<div><em>${esc(t.kind)}</em><p dir="auto">${esc(t.text)}</p></div>`).join('')}</div></section>` : ''}
    <section class="dg-card dg-wide"><h3>News</h3><div class="dg-news">${news || '<p class="dg-empty">No headlines.</p>'}</div></section>
    ${earnings ? `<section class="dg-card"><h3>Earnings this week</h3><ul class="dg-list">${earnings}</ul></section>` : ''}
    ${rem ? `<section class="dg-card"><h3>Reminders</h3><ul class="dg-list">${rem}</ul></section>` : ''}
  </div>
  <footer class="dg-foot">Made ${made.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })} · ${esc(d.edition === 'close' ? 'after the US close' : d.edition === 'morning' ? 'morning edition' : 'on demand')} · a read, not financial advice</footer>`;
}

export class Digest {
  constructor(button, panel, api) {
    this.button = button; this.panel = panel; this.api = api;
    button.innerHTML = `${MARK}<span>Summary</span><i class="dg-dot"></i>`;
    button.addEventListener('click', () => this.open());
    panel.addEventListener('click', (e) => this.click(e));
    panel.addEventListener('mousemove', (e) => this.hover(e));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && this.isOpen()) this.close(); });
    this.check();
  }
  isOpen() { return this.panel.classList.contains('on'); }
  async check() {
    const api = this.api(); if (!api?.digest) return;
    try { const d = await api.digest(); this.ready(d && d.made && !d.seen); } catch { /* not yet */ }
  }
  ready(on) { this.button.classList.toggle('ready', Boolean(on)); this.button.title = on ? 'Your summary is ready' : 'Your summary'; }
  async open() {
    const api = this.api();
    this.panel.innerHTML = '<div class="dg-sheet"><div class="dg-loading">Loading…</div></div>';
    this.panel.classList.add('on'); this.panel.setAttribute('aria-hidden', 'false');
    let d = null;
    try { d = api?.digest ? await api.digest() : null; } catch { /* shown as empty */ }
    this.show(d);
    this.ready(false);
    try { api?.digest_seen && api.digest_seen(); } catch { /* fine */ }
  }
  show(d) { this.panel.innerHTML = `<div class="dg-sheet">${markup(d)}</div>`; }
  close() { this.panel.classList.remove('on'); this.panel.setAttribute('aria-hidden', 'true'); }
  async click(e) {
    if (e.target === this.panel || e.target.closest('[data-act="close"]')) return this.close();
    if (e.target.closest('[data-act="refresh"]')) {
      const b = e.target.closest('button'); b.classList.add('spin');
      try { this.show(await this.api().digest_refresh()); } catch { b.classList.remove('spin'); }
      return;
    }
    const link = e.target.closest('[data-link]');
    if (link) { e.preventDefault(); const api = this.api(); if (link.dataset.link && api?.open_link) api.open_link(link.dataset.link); }
  }
  hover(e) {
    const svg = e.target.closest('.dg-area'); if (!svg) return;
    const pts = svg.dataset.points.split(',').map(Number);
    const r = svg.getBoundingClientRect();
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    const cross = svg.querySelector('.dg-cross');
    const vb = svg.viewBox.baseVal.width;
    cross.setAttribute('x1', f * vb); cross.setAttribute('x2', f * vb);
    svg.parentElement.title = String(pts[Math.round(f * (pts.length - 1))]);
  }
}
