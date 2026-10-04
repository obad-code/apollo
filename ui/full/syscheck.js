/* System Check: a SYSTEM button beside Fixes, and the page it opens - the
 * whole of Apollo looked over (syscheck.py): the boot checks, the crew's
 * brains, Gemini's quota, every agent, today's errors - and the safe fixes it
 * made by itself. Nothing leaves this PC. */

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const SHIELD = `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6z M8.5 12l2.5 2.5 4.5-5"
  fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>`;
const WORD = { ok: 'OK', warn: 'WATCH', fail: 'BROKEN' };

export class SystemCheck {
  constructor(button, panel, api) {
    this.button = button; this.panel = panel; this.api = api; this.running = false;
    button.innerHTML = `${SHIELD}<span>System</span><i class="dg-dot"></i>`;
    button.addEventListener('click', () => this.open(false));
    panel.addEventListener('click', (e) => this.click(e));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && this.panel.classList.contains('on')) this.close(); });
    window.addEventListener('pywebviewready', () => this.check());
  }
  async check() {
    const api = this.api(); if (!api?.system_check_last) return;
    try { this.mark(await api.system_check_last()); } catch { /* not yet */ }
  }
  mark(r) {
    const bad = r ? (r.fail || 0) : 0;
    this.button.classList.toggle('ready', bad > 0);
    this.button.title = r ? `Last check: ${r.fail || 0} broken, ${r.warn || 0} to watch` : 'Check the whole of Apollo';
  }
  async open(runNow) {
    this.panel.classList.add('on'); this.panel.setAttribute('aria-hidden', 'false');
    let last = null;
    try { last = await this.api()?.system_check_last?.(); } catch { /* none yet */ }
    if (runNow || !last) return this.run();
    this.show(last);
  }
  close() { this.panel.classList.remove('on'); this.panel.setAttribute('aria-hidden', 'true'); }
  async run() {
    if (this.running) return;
    this.running = true; this.show(null);
    let r;
    try { r = await this.api().system_check(); } catch (e) { r = { ok_run: false, error: String(e) }; }
    this.running = false;
    if (r && r.ok_run === false) return this.show({ rows: [] }, r.error || 'The check could not run.');
    this.mark(r); this.show(r);
  }
  show(r, note = '') {
    const rows = (r?.rows || []).slice().sort((a, b) => ({ fail: 0, warn: 1, ok: 2 }[a.status] - { fail: 0, warn: 1, ok: 2 }[b.status]));
    const when = r?.at ? new Date(r.at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
    const list = rows.map((x) => `
      <div class="sc-row ${esc(x.status)}${x.fixed ? ' fixed' : ''}">
        <b>${x.fixed ? 'FIXED' : WORD[x.status] || esc(x.status)}</b>
        <div><em>${esc(x.label)}</em><p>${esc(x.detail)}</p></div>
      </div>`).join('');
    const sum = r?.rows ? `<div class="sc-sum"><span class="fail">${r.fail || 0} broken</span><span class="warn">${r.warn || 0} to watch</span>
      <span class="fixed">${r.fixed || 0} fixed</span><span class="ok">${r.ok || 0} ok</span>${when ? `<i>checked ${esc(when)}</i>` : ''}</div>` : '';
    this.panel.innerHTML = `<div class="dg-sheet fx-sheet">
      <header class="dg-head"><div><h2>System Check</h2><p>The whole of Apollo looked over, and what is safe to fix, fixed. Only Apollo's own files - nothing of yours is read, and nothing leaves this PC.</p></div>
        <div class="dg-head-right">
          <button type="button" class="fx-btn" data-act="run"${this.running ? ' disabled' : ''}>Check now</button>
          <button type="button" class="dg-close" data-act="close" aria-label="Close">✕</button></div></header>
      ${note ? `<p class="fx-note">${esc(note)}</p>` : ''}
      ${r == null ? '<div class="dg-loading">Checking everything… (up to half a minute)</div>' : sum + (list || '<p class="dg-empty">Nothing checked yet.</p>')}
    </div>`;
  }
  click(e) {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (e.target === this.panel || act === 'close') return this.close();
    if (act === 'run') this.run();
  }
}
