/* Q's fixes: a FIXES button beside the summary, and the page it opens - Q's
 * suggestions for the display (send one to Claude, or say it is not your
 * style), a fresh look on demand, and "point at it": click anything on the
 * display and say what is wrong with it. */

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const WRENCH = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.1L4 16.7 7.3 20l5.3-5.3a4 4 0 0 0 5.1-5.4l-2.4 2.4-2.6-.7-.7-2.6z"
  fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>`;

function selectorOf(el) {
  const parts = [];
  for (let n = el; n && n.nodeType === 1 && parts.length < 5; n = n.parentElement) {
    if (n.id) { parts.unshift(`#${n.id}`); break; }
    const cls = [...n.classList].slice(0, 2).map((c) => `.${c}`).join('');
    parts.unshift(n.tagName.toLowerCase() + cls);
  }
  return parts.join(' > ');
}

export class Fixes {
  constructor(button, panel, api) {
    this.button = button; this.panel = panel; this.api = api; this.picking = false;
    button.innerHTML = `${WRENCH}<span>Fixes</span><i class="dg-dot"></i>`;
    button.addEventListener('click', () => this.open());
    panel.addEventListener('click', (e) => this.click(e));
    this.pickMove = (e) => this.hover(e);
    this.pickClick = (e) => this.picked(e);
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      if (this.picking) this.stopPick(); else if (this.panel.classList.contains('on')) this.close();
    });
    this.check();
  }
  async check() {
    const api = this.api(); if (!api?.fixes) return;
    try { this.ready((await api.fixes()).new); } catch { /* not yet */ }
  }
  ready(n) { this.button.classList.toggle('ready', Boolean(n)); this.button.title = n ? `Q has ${n} new suggestions` : 'Q: fix the display'; }
  async open() {
    this.panel.classList.add('on'); this.panel.setAttribute('aria-hidden', 'false');
    this.show(null);
    try { this.show(await this.api().fixes()); } catch { this.show({ suggestions: [] }); }
  }
  close() { this.panel.classList.remove('on'); this.panel.setAttribute('aria-hidden', 'true'); }
  show(board, note = '') {
    const list = (board?.suggestions || []).map((s) => `
      <div class="fx-item ${esc(s.status)}" data-id="${esc(s.id)}">
        <div><em>${esc(s.area)}</em><h4>${esc(s.title)}</h4><p>${esc(s.detail)}</p></div>
        <div class="fx-acts">${s.status === 'new'
          ? '<button data-act="send" type="button">Send to Claude</button><button data-act="no" type="button" class="ghost">Not my style</button>'
          : s.status === 'sent' ? `<a href="#" data-link="${esc(s.issue || '')}">Sent ✓</a>` : '<span>Dropped</span>'}</div>
      </div>`).join('');
    this.panel.innerHTML = `<div class="dg-sheet fx-sheet">
      <header class="dg-head"><div><h2>Fixes</h2><p>Q looks at the display once a day and learns your style from what you send and drop.</p></div>
        <div class="dg-head-right">
          <button type="button" class="fx-btn" data-act="point">Point at something</button>
          <button type="button" class="fx-btn ghost" data-act="look">Look now</button>
          <button type="button" class="dg-close" data-act="close" aria-label="Close">✕</button></div></header>
      ${note ? `<p class="fx-note">${esc(note)}</p>` : ''}
      ${board == null ? '<div class="dg-loading">Loading…</div>'
        : list || '<p class="dg-empty">No suggestions yet - press Look now, or point at something.</p>'}
    </div>`;
  }
  async click(e) {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (e.target === this.panel || act === 'close') return this.close();
    const api = this.api();
    const link = e.target.closest('[data-link]');
    if (link) { e.preventDefault(); if (link.dataset.link && api?.open_link) api.open_link(link.dataset.link); return; }
    if (act === 'point') { this.close(); return this.startPick(); }
    if (act === 'look') {
      this.close();                                // Q looks at the display, not at this page
      await new Promise((r) => setTimeout(r, 450));
      const board = await api.fixes_look();
      this.open().then(() => this.show(board, board.ok ? 'Q took a fresh look.' : board.error));
      return;
    }
    const id = e.target.closest('[data-id]')?.dataset.id;
    if (!id) return;
    if (act === 'send') {
      const r = await api.fixes_send(id);
      this.show(await api.fixes(), r.ok ? `Sent to Claude as issue #${r.number}.` : r.error);
    } else if (act === 'no') {
      await api.fixes_no(id);
      this.show(await api.fixes(), 'Dropped - Q will remember you do not like that.');
    }
    this.check();
  }
  startPick() {
    this.picking = true;
    document.body.classList.add('fx-picking');
    this.ring = Object.assign(document.createElement('div'), { className: 'fx-ring' });
    this.tip = Object.assign(document.createElement('div'), { className: 'fx-tip', textContent: 'Click what needs fixing · Esc to cancel' });
    document.body.append(this.ring, this.tip);
    document.addEventListener('mousemove', this.pickMove, true);
    document.addEventListener('click', this.pickClick, true);
  }
  stopPick() {
    this.picking = false;
    document.body.classList.remove('fx-picking');
    this.ring?.remove(); this.tip?.remove(); this.ask?.remove();
    document.removeEventListener('mousemove', this.pickMove, true);
    document.removeEventListener('click', this.pickClick, true);
  }
  hover(e) {
    if (this.ask) return;
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el || el === this.ring || el === this.tip) return;
    const r = el.getBoundingClientRect();
    Object.assign(this.ring.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px` });
    this.target = el;
  }
  picked(e) {
    if (this.ask?.contains(e.target)) return;
    e.preventDefault(); e.stopPropagation();
    if (this.ask || !this.target) return;
    const r = this.target.getBoundingClientRect();
    this.element = { selector: selectorOf(this.target), text: (this.target.innerText || '').trim().slice(0, 200),
                     size: `${Math.round(r.width)}x${Math.round(r.height)} at ${Math.round(r.left)},${Math.round(r.top)}` };
    this.ask = Object.assign(document.createElement('form'), { className: 'fx-ask' });
    this.ask.innerHTML = `<label>What's wrong with this?</label><textarea rows="3" dir="auto" placeholder="e.g. the text is too small / this should be on the left"></textarea>
      <div><button type="submit">Send to Claude</button><button type="button" class="ghost">Cancel</button></div>`;
    Object.assign(this.ask.style, { left: `${Math.min(r.left, innerWidth - 380)}px`, top: `${Math.min(r.bottom + 10, innerHeight - 200)}px` });
    document.body.append(this.ask);
    this.ask.querySelector('textarea').focus();
    this.ask.querySelector('.ghost').addEventListener('click', () => this.stopPick());
    this.ask.addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const note = this.ask.querySelector('textarea').value;
      const r2 = await this.api().fixes_report(note, this.element);
      this.stopPick();
      this.open().then(async () => this.show(await this.api().fixes(), r2.ok ? `Sent to Claude as issue #${r2.number}.` : r2.error));
    });
  }
}
