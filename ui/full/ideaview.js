/* One idea, the whole screen: the idea itself, THEIA's read of it laid out
 * section by section, and a conversation with her down the side - ask her
 * anything about it, and she answers with her analysis in mind. */

const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const EYES = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" stroke-width="1.4"/><circle cx="9" cy="11" r="1.7" fill="currentColor"/><circle cx="15" cy="11" r="1.7" fill="currentColor"/></svg>';

/* THEIA's report, as cards: each "1. ANALYSIS" / "## Heading" / "VERDICT:" starts one. */
function sections(report) {
  const out = [];
  let cur = null;
  for (const raw of String(report || '').split('\n')) {
    const line = raw.trim();
    const head = line.match(/^(?:#{1,4}\s*)?(?:\d+[.)]\s*)?\**([A-Z][A-Z &'-]{2,40}|[^:]{2,40}?)\**\s*[:\-–]\s*(.*)$/);
    const isHead = /^#{1,4}\s/.test(line) || (head && head[1] === head[1].toUpperCase() && /[A-Z]/.test(head[1]));
    if (isHead) {
      const title = (line.replace(/^#{1,4}\s*/, '').match(/^(?:\d+[.)]\s*)?\**([^:*]+)/) || [])[1] || line;
      cur = { title: title.trim(), lines: [] };
      out.push(cur);
      const rest = head && head[2];
      if (rest && !/^#{1,4}\s/.test(line)) cur.lines.push(rest);
    } else if (line) {
      if (!cur) { cur = { title: '', lines: [] }; out.push(cur); }
      cur.lines.push(line);
    }
  }
  return out;
}

function lines(ls) {
  let html = '', list = false;
  for (const l of ls) {
    const bullet = l.match(/^[-•*]\s+(.*)$/) || l.match(/^\d+[.)]\s+(.*)$/);
    const text = esc(bullet ? bullet[1] : l).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
    if (bullet && !list) { html += '<ul>'; list = true; }
    if (!bullet && list) { html += '</ul>'; list = false; }
    html += bullet ? `<li>${text}</li>` : `<p>${text}</p>`;
  }
  return html + (list ? '</ul>' : '');
}

const TONES = { analysis: 'blue', critique: 'red', 'the best way': 'green', 'best way': 'green', verdict: 'amber', confidence: 'amber' };

export class IdeaView {
  constructor(root, api) {
    this.root = root; this.api = api;
    root.addEventListener('click', (e) => this.click(e));
    root.addEventListener('submit', (e) => { e.preventDefault(); this.send(); });
    root.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && e.target.matches('textarea')) { e.preventDefault(); this.send(); }
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && this.isOpen() && !e.target.matches('textarea')) this.close(); });
  }
  isOpen() { return this.root.classList.contains('on'); }
  async open(id) {
    this.id = id;
    this.root.classList.add('on'); this.root.setAttribute('aria-hidden', 'false');
    this.root.innerHTML = '<div class="iv-sheet"><div class="iv-wait">Opening…</div></div>';
    this.idea = await this.api().idea(id);
    this.render();
    const api = this.api(); if (api && api.ideas_seen) api.ideas_seen();
  }
  close() { this.root.classList.remove('on'); this.root.setAttribute('aria-hidden', 'true'); this.onClose && this.onClose(); }

  render(busy = false) {
    const idea = this.idea;
    if (!idea) { this.root.innerHTML = '<div class="iv-sheet"><div class="iv-wait">That idea is gone.</div></div>'; return; }
    const read = idea.theia;
    const cards = read ? sections(read.report).map((s) => {
      const tone = TONES[s.title.toLowerCase()] || '';
      return `<section class="iv-card ${tone}">${s.title ? `<h3>${esc(s.title)}</h3>` : ''}${lines(s.lines)}</section>`;
    }).join('') : '';
    const talk = (idea.chat || []).map((m) => `<div class="iv-msg ${m.who === 'you' ? 'you' : 'her'}" dir="auto">${
      m.who === 'you' ? '' : `<i>${EYES}</i>`}<p>${esc(m.text).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>')}</p></div>`).join('');
    this.root.innerHTML = `<div class="iv-sheet">
      <header class="iv-head">
        <button type="button" class="iv-back" data-act="close">‹ Ideas</button>
        <div class="iv-title"><em>Idea · ${esc(new Date((idea.at || 0) * 1000).toLocaleDateString('en-GB', { day: 'numeric', month: 'long' }))}</em>
          <h1 dir="auto">${esc(idea.text)}</h1></div>
      </header>
      <div class="iv-body">
        <main class="iv-read">
          ${read ? `<div class="iv-summary"><span>${EYES} THEIA's read</span><p dir="auto">${esc(read.summary)}</p></div>
            <div class="iv-cards" dir="auto">${cards}</div>`
            : `<div class="iv-empty">${EYES}<p>THEIA hasn't read this one yet.</p>
               <button type="button" data-act="analyse" ${busy ? 'disabled' : ''}>${busy ? 'THEIA is reading it…' : 'Ask THEIA to read it now'}</button></div>`}
        </main>
        <aside class="iv-chat">
          <header>${EYES}<b>Talk to THEIA</b><small>about this idea</small></header>
          <div class="iv-msgs">${talk || '<p class="iv-hint">Ask her anything - "is this worth it?", "what would you do first?", "what am I missing?"</p>'}</div>
          <form class="iv-say"><textarea rows="2" dir="auto" placeholder="Write to THEIA…"></textarea><button type="submit">Send</button></form>
        </aside>
      </div></div>`;
    const msgs = this.root.querySelector('.iv-msgs'); msgs.scrollTop = msgs.scrollHeight;
  }

  async click(e) {
    const act = e.target.closest('[data-act]')?.dataset.act;
    if (act === 'close' || e.target === this.root) return this.close();
    if (act === 'analyse') {
      this.render(true);
      const r = await this.api().idea_analyse(this.id);
      if (r && r.ok) this.idea = r.idea;
      this.render();
    }
  }

  async send() {
    const box = this.root.querySelector('.iv-say textarea');
    const text = box.value.trim(); if (!text) return;
    box.value = '';
    this.idea.chat = [...(this.idea.chat || []), { who: 'you', text }, { who: 'theia', text: '…' }];
    this.render();
    const r = await this.api().idea_chat(this.id, text);
    this.idea.chat[this.idea.chat.length - 1].text = r && r.ok ? r.reply : `(${(r && r.error) || 'THEIA could not answer just now'})`;
    this.render();
    this.root.querySelector('.iv-say textarea').focus();
  }
}
