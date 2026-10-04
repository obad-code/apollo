/* Summary mode: the whole of Apollo on one calm page - what he would tell
 * you in a sentence, the markets with your stocks' calls and MONEYPENNY's
 * record, your projects and ideas with THEIA's notes, LYLA's Shorts, the
 * crew working live, and the only alerts that mattered. Everything is
 * real: the display's snapshot, the crew's board, the summary (digest.py)
 * and the alerts that were told. A rail down the left goes everywhere else. */

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const pct = (v) => `${v >= 0 ? '+' : '−'}${Math.abs(Number(v) || 0).toFixed(2)}%`;
const ago = (t) => { const s = Date.now() / 1000 - (t || 0); return s < 90 ? 'just now' : s < 3600 ? `${Math.round(s / 60)} min ago` : s < 86400 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`; };
const VCLASS = { 'STRONG BUY': 'sb', GOOD: 'gd', DECENT: 'dc', HOLD: 'hd', WEAK: 'wk', AVOID: 'av', BUY: 'gd' };
const EYES = '<svg viewBox="0 0 24 24"><circle cx="9" cy="11" r="1.8" fill="currentColor"/><circle cx="15" cy="11" r="1.8" fill="currentColor"/></svg>';
const ICON = {
  home: 'M4 11l8-7 8 7v9H4z', crew: 'M8 9a3 3 0 100-.01M16 9a3 3 0 100-.01M3 19c1-3 3-4 5-4s4 1 5 4M11 19c1-3 3-4 5-4s4 1 5 4',
  markets: 'M4 18l5-6 4 3 7-9', projects: 'M4 7h6l2 2h8v10H4z', ideas: 'M9 18h6M10 21h4M12 3a6 6 0 00-3.5 10.9V16h7v-2.1A6 6 0 0012 3z',
  shorts: 'M7 3h10v18H7zM11 10l3 2-3 2z', fixes: 'M14.7 6.3a4 4 0 00-5.4 5.1L4 16.7 7.3 20l5.3-5.3a4 4 0 005.1-5.4l-2.4 2.4-2.6-.7-.7-2.6z',
  idle: 'M3 5h18v12H3zM8 21h8', summary: 'M5 5h14v14H5zM8 9h8M8 13h5',
};
const CREW = {
  LYLA: { c: '#ffb000', bg: 'rgba(255,176,0,.15)' }, MONEYPENNY: { c: '#3ed8c8', bg: 'rgba(62,216,200,.15)' },
  THEIA: { c: '#b39bff', bg: 'rgba(179,155,255,.15)' }, Q: { c: '#e9e4da', bg: 'rgba(255,255,255,.08)' },
};

function spark(points, up) {
  if (!points || points.length < 2) return '';
  const lo = Math.min(...points), hi = Math.max(...points), w = 200, h = 46;
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${(i / (points.length - 1) * w).toFixed(1)},${(4 + (1 - (p - lo) / ((hi - lo) || 1)) * (h - 8)).toFixed(1)}`).join('');
  return `<svg class="sm-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path d="${d}L${w},${h}L0,${h}Z" fill="${up ? 'var(--up)' : 'var(--down)'}" opacity=".1"/>
    <path d="${d}" fill="none" stroke="${up ? 'var(--up)' : 'var(--down)'}" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`;
}

function greeting(d) {
  const h = new Date().getHours();
  const hello = h < 12 ? 'Good morning.' : h < 18 ? 'Good afternoon.' : 'Good evening.';
  const bits = [];
  const sp = (d.indices || [])[0];
  if (sp) bits.push(`the S&P is ${sp.change_pct >= 0 ? 'up' : 'down'} ${Math.abs(sp.change_pct).toFixed(1)}%`);
  const notes = (d.projects || []).filter((p) => p.theia && !p.theia.seen).length + (d.ideas || []).filter((i) => i.theia && !i.theia.seen).length;
  if (notes) bits.push(`THEIA has ${notes} new note${notes > 1 ? 's' : ''} for you`);
  const waiting = (d.shorts || []).find((s) => s.waiting);
  if (waiting) bits.push("LYLA's Short is waiting for your call");
  const busy = Object.entries(d.crew || {}).filter(([, a]) => a.working).map(([k]) => k);
  if (busy.length) bits.push(`${busy.join(' and ')} ${busy.length > 1 ? 'are' : 'is'} working`);
  if ((d.alerts || []).length && Date.now() / 1000 - d.alerts[0].when < 6 * 3600) bits.push(`one alert today: ${d.alerts[0].action} ${d.alerts[0].ticker}`);
  const text = bits.length ? bits.join(', ').replace(/^./, (c) => c.toUpperCase()) + '.' : 'All quiet - nothing needs you right now.';
  return `<b>${hello}</b> <span>${esc(text)}</span>`;
}

export function markup(d) {
  const nav = (id, label, dot) => `<button type="button" class="sm-nav${id === 'summary' ? ' on' : ''}" data-go="${id}" title="${label}">
    <svg viewBox="0 0 24 24"><path d="${ICON[id]}"/></svg>${dot ? '<i></i>' : ''}</button>`;
  const stocks = (d.stocks || []).slice(0, 7);
  const most = Math.max(1, ...stocks.map((s) => Math.abs(s.change_pct || 0)));
  const acc = d.accuracy || {};
  const m7 = (acc.marks || {})[7] || {}, m30 = (acc.marks || {})[30] || {};
  const lesson = (acc.lessons || [])[0];
  const items = [
    ...(d.projects || []).slice(0, 3).map((p) => ({ kind: 'project', id: p.id, letter: p.name.slice(0, 1).toUpperCase(), title: p.name,
      sub: p.theia ? `THEIA: ${p.theia.summary}` : (p.about || 'No board notes yet'), theia: p.theia })),
    ...(d.ideas || []).slice(0, 3).map((i) => ({ kind: 'idea', id: i.id, letter: '💡', title: i.text,
      sub: i.theia ? `THEIA: ${i.theia.summary}` : 'THEIA is reading it…', theia: i.theia })),
  ].slice(0, 4);
  return `
  <nav class="sm-rail">
    <div class="sm-logo">A</div>
    ${nav('summary', 'Summary')}${nav('home', 'Normal')}${nav('crew', 'Agents', Object.values(d.crew || {}).some((a) => a.working))}
    ${nav('markets', 'Trading')}${nav('projects', 'Projects')}${nav('ideas', 'Ideas', (d.ideas || []).some((i) => i.theia && !i.theia.seen))}
    ${nav('shorts', 'Shorts', (d.shorts || []).some((s) => s.waiting))}
    <span class="sm-gap"></span>${nav('fixes', 'Fixes')}${nav('idle', 'Idle')}
  </nav>
  <section class="sm-hero sm-card">
    <div class="sm-orb"><svg viewBox="0 0 120 120"><ellipse cx="60" cy="60" rx="54" ry="34" fill="none" stroke="#f5e9cf" stroke-opacity=".7"/>
      <ellipse cx="60" cy="60" rx="22" ry="34" fill="none" stroke="#f5e9cf" stroke-opacity=".45"/><ellipse cx="60" cy="60" rx="40" ry="34" fill="none" stroke="#f5e9cf" stroke-opacity=".3"/>
      <path d="M60 44l4 12 12 4-12 4-4 12-4-12-12-4 12-4z" fill="#fff"/></svg></div>
    <div><p class="sm-say">${greeting(d)}</p>
      <div class="sm-ask"><span>“Read me the gist”</span><span>“Post the Short”</span><span dir="auto">“موني بيني حللي AMD”</span><span dir="auto">“افتح مشروع Nolock”</span></div></div>
    <div class="sm-mic" title="Hold Ctrl+Alt to talk"><svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/></svg><small>Ctrl+Alt</small></div>
  </section>
  <section class="sm-markets sm-card">
    <h3><b>Markets</b> · MONEYPENNY <button type="button" class="sm-more" data-go="markets">Open desk ›</button></h3>
    <div class="sm-idx">${(d.indices || []).map((q) => `<div><span>${esc(q.symbol === '^GSPC' ? 'S&P 500' : q.symbol === '^IXIC' ? 'Nasdaq' : q.symbol)}</span>
      <b>${Number(q.price || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}</b><em class="${q.change_pct >= 0 ? 'up' : 'down'}">${pct(q.change_pct)}</em>${spark(q.spark, q.change_pct >= 0)}</div>`).join('') || '<p class="sm-quiet">The market feed is not in yet.</p>'}</div>
    <div class="sm-rows">${stocks.map((s) => { const w = Math.abs(s.change_pct || 0) / most * 50; const up = (s.change_pct || 0) >= 0;
      return `<div class="sm-row"><b>${esc(s.symbol)}</b><span class="sm-bar"><i class="${up ? 'up' : 'down'}" style="${up ? 'left:50%' : `left:${50 - w}%`};width:${w}%"></i></span>
        <span class="${up ? 'up' : 'down'}">${pct(s.change_pct)}</span>${s.verdict ? `<span class="sm-v ${VCLASS[s.verdict] || 'hd'}">${esc(s.verdict)}</span>` : '<span></span>'}</div>`; }).join('')
      || '<p class="sm-quiet">Add stocks to your watchlist to see them here.</p>'}</div>
    <div class="sm-record"><div><b>${m7.rate == null ? '—' : `${m7.rate}%`}</b><span>right after 7 days</span></div><div><b>${m30.rate == null ? '—' : `${m30.rate}%`}</b><span>after 30 days</span></div>
      ${lesson ? `<p class="sm-lesson"><b>Lesson:</b> ${esc(lesson.lesson)}</p>` : `<p class="sm-lesson quiet">${acc.open ? `${acc.open} calls waiting to be graded` : 'Her record starts with her first graded call.'}</p>`}</div>
  </section>
  <section class="sm-theia sm-card">
    <h3><b>Projects &amp; Ideas</b> · THEIA <button type="button" class="sm-more" data-go="projects">All ›</button></h3>
    <div class="sm-list">${items.map((it) => `<button type="button" class="sm-item" data-open="${it.kind}" data-id="${esc(it.id)}">
        <span class="sm-thumb ${it.kind}">${esc(it.letter)}</span><span><b dir="auto">${esc(it.title)}</b><small dir="auto">${esc(it.sub)}</small></span>
        ${it.theia ? `<span class="sm-eye${it.theia.seen ? '' : ' new'}">${EYES}</span>` : '<span></span>'}</button>`).join('')
      || '<p class="sm-quiet">Add a project or say “فكرة” to Apollo - THEIA takes it from there.</p>'}</div>
    <div class="sm-three">${(d.theia || []).slice(0, 2).map((t) => `<div><em>${esc(t.kind)}</em><span dir="auto">${esc(t.text)}</span></div>`).join('')}</div>
  </section>
  <section class="sm-shorts sm-card">
    <h3><b>Shorts</b> · LYLA <button type="button" class="sm-more" data-go="shorts">Studio ›</button></h3>
    <div class="sm-reel">${(d.shorts || []).slice(0, 4).map((s, i) => `<button type="button" class="sm-short" data-short="${i}">
        ${s.previewSrc ? `<img src="${s.previewSrc}" alt="">` : ''}<b class="${s.waiting ? 'wait' : 'done'}">${s.waiting ? 'WAITING' : 'MADE'}</b><span dir="auto">${esc(s.title)}</span></button>`).join('')
      || '<p class="sm-quiet">Say “ليلى سوي مقطع” and it shows up here.</p>'}</div>
  </section>
  <aside class="sm-side">
    <section class="sm-card sm-crew">
      <h3><b>The crew</b> · live</h3>
      ${Object.keys(CREW).map((k) => { const a = (d.crew || {})[k] || {}; const last = (a.results || [])[0];
        return `<div class="sm-agent"><span class="sm-ava" style="background:${CREW[k].bg};color:${CREW[k].c}">${EYES}</span>
          <div><p>${k} <small>${a.working ? 'working' : 'standing by'}</small></p><div class="sm-hp"><i style="background:${CREW[k].c}"></i></div>
          <p class="sm-now" dir="auto">${esc(a.working || (last ? last.summary || last.task : 'Ready'))}</p></div></div>`; }).join('')}
    </section>
    <button type="button" class="sm-results" data-go="results">RESULTS · ${Object.values(d.crew || {}).reduce((n, a) => n + (a.results || []).length, 0)} ›</button>
    <section class="sm-card sm-alerts">
      <h3><b>Alerts</b> · only what matters</h3>
      ${(d.alerts || []).slice(0, 3).map((a) => `<a href="#" class="sm-alert ${a.action === 'BUY' ? 'buy' : 'sell'}" data-link="${esc(a.link || '')}">
        <span>${a.action === 'BUY' ? 'BUY!!' : a.action === 'SELL' ? 'PULL!!' : esc(a.action)}</span><p><b>${esc(a.ticker)}</b> ${esc(a.title)}<small>${esc(a.source)} · ${ago(a.when)}</small></p></a>`).join('')
        || '<p class="sm-quiet">No decisive news. Apollo stays quiet until something really moves.</p>'}
    </section>
  </aside>`;
}

export class SummaryMode {
  /* `data()` gathers what is on the page; `go(where)` and `open(kind, id)` act on clicks. */
  constructor(root, { data, go, open, short, link }) {
    this.root = root; this.data = data; this.go = go; this.open = open; this.short = short; this.link = link;
    root.addEventListener('click', (e) => {
      const go = e.target.closest('[data-go]'); if (go) return this.go(go.dataset.go);
      const it = e.target.closest('[data-open]'); if (it) return this.open(it.dataset.open, it.dataset.id);
      const s = e.target.closest('[data-short]'); if (s) return this.short(+s.dataset.short);
      const l = e.target.closest('[data-link]'); if (l) { e.preventDefault(); if (l.dataset.link) this.link(l.dataset.link); }
    });
  }
  async show() {
    this.on = true;
    const d = await this.data();
    if (this.on) this.root.innerHTML = markup(d);
    clearInterval(this.timer);
    this.timer = setInterval(() => this.refresh(), 30000);
  }
  async refresh() { if (!this.on) return; const d = await this.data(); if (this.on) this.root.innerHTML = markup(d); }
  hide() { this.on = false; clearInterval(this.timer); }
}
