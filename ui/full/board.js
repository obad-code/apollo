/* A project's board, full screen - a free canvas like Apple's Freeform.
 *
 * Pen and marker, lines and arrows, boxes and circles, sticky notes, text,
 * pictures (pick, paste or drop) and files; select to move, resize or
 * delete; pan with the hand, the space bar or the middle button; zoom with
 * Ctrl+wheel. Everything is SVG over an endless dotted grid, saved as you go
 * (myprojects.py). Ask THEIA and she looks at the board and leaves notes. */

const NS = 'http://www.w3.org/2000/svg';
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const uid = () => Math.random().toString(36).slice(2, 10);
const COLORS = ['#f5f1e8', '#ffd166', '#ff6b7a', '#5fe39a', '#6ab7ff', '#c49bff'];
const NOTE_COLORS = ['#fff3b0', '#ffd6e0', '#c9f2d8', '#cfe6ff', '#e6dcff', '#ffe0c2'];
const TOOLS = [
  ['select', 'V', 'M5 3l12 8-5 1.5L9.5 18z'], ['hand', 'H', 'M8 11V5.5a1.5 1.5 0 013 0V10m0-1V4.5a1.5 1.5 0 013 0V10m0-.5V6a1.5 1.5 0 013 0v7c0 4-2.5 7-6.5 7S5 17.5 4 15l-1.2-3a1.4 1.4 0 012.4-1.3L8 13'],
  ['pen', 'P', 'M4 20l4-1 11-11-3-3L5 16zM14 7l3 3'], ['marker', 'M', 'M5 19h6M7 17l9-9 3 3-9 9H7z'],
  ['line', 'L', 'M5 19L19 5'], ['arrow', 'A', 'M5 19L19 5M11 5h8v8'], ['rect', 'R', 'M4 6h16v12H4z'], ['ellipse', 'O', 'M12 5a8 7 0 100 14 8 7 0 000-14z'],
  ['note', 'N', 'M5 4h14v11l-5 5H5zM14 20v-5h5'], ['text', 'T', 'M6 6h12M12 6v13'], ['image', 'I', 'M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M15 9.5a1.5 1.5 0 100-.01'],
  ['file', 'F', 'M7 3h7l4 4v14H7zM14 3v4h4'], ['eraser', 'E', 'M8 20h12M5 15l8-8 6 6-5 5H8z'],
];

function bounds(it) {
  if (it.pts) {
    const xs = it.pts.map((p) => p[0]), ys = it.pts.map((p) => p[1]);
    return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) };
  }
  return { x: it.x, y: it.y, w: it.w || 10, h: it.h || 10 };
}

function inkPath(pts) {
  if (!pts.length) return '';
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2;
    d += `Q${pts[i][0]},${pts[i][1]} ${mx},${my}`;
  }
  if (pts.length > 1) d += `L${pts[pts.length - 1][0]},${pts[pts.length - 1][1]}`;
  return d;
}

/* One item as SVG. `live` makes notes and text editable. */
export function itemSvg(it, live = false) {
  const g = (inner) => `<g data-id="${it.id}" class="bd-item bd-${it.type}">${inner}</g>`;
  switch (it.type) {
    case 'ink':
      return g(`<path d="${inkPath(it.pts)}" fill="none" stroke="${it.color}" stroke-width="${it.w}" stroke-linecap="round" stroke-linejoin="round" opacity="${it.op || 1}"/>
        <path d="${inkPath(it.pts)}" fill="none" stroke="transparent" stroke-width="${Math.max(14, it.w + 10)}"/>`);
    case 'line': case 'arrow': {
      const [[x1, y1], [x2, y2]] = it.pts;
      const a = Math.atan2(y2 - y1, x2 - x1), s = 10 + it.w * 2;
      const head = it.type === 'arrow' ? `<path d="M${x2 - s * Math.cos(a - 0.45)},${y2 - s * Math.sin(a - 0.45)}L${x2},${y2}L${x2 - s * Math.cos(a + 0.45)},${y2 - s * Math.sin(a + 0.45)}" fill="none" stroke="${it.color}" stroke-width="${it.w}" stroke-linecap="round" stroke-linejoin="round"/>` : '';
      return g(`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${it.color}" stroke-width="${it.w}" stroke-linecap="round"/>${head}
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="transparent" stroke-width="16"/>`);
    }
    case 'rect': return g(`<rect x="${it.x}" y="${it.y}" width="${it.w}" height="${it.h}" rx="10" fill="${it.fill || 'transparent'}" stroke="${it.color}" stroke-width="${it.sw || 3}"/>`);
    case 'ellipse': return g(`<ellipse cx="${it.x + it.w / 2}" cy="${it.y + it.h / 2}" rx="${it.w / 2}" ry="${it.h / 2}" fill="${it.fill || 'transparent'}" stroke="${it.color}" stroke-width="${it.sw || 3}"/>`);
    case 'note':
      return g(`<foreignObject x="${it.x}" y="${it.y}" width="${it.w}" height="${it.h}"><div xmlns="http://www.w3.org/1999/xhtml" class="bd-note" dir="auto"
        style="background:${it.color}" ${live ? 'contenteditable="true"' : ''}>${esc(it.text)}</div></foreignObject>`);
    case 'text':
      return g(`<foreignObject x="${it.x}" y="${it.y}" width="${it.w}" height="${it.h}"><div xmlns="http://www.w3.org/1999/xhtml" class="bd-text" dir="auto"
        style="color:${it.color};font-size:${it.size}px" ${live ? 'contenteditable="true"' : ''}>${esc(it.text)}</div></foreignObject>`);
    case 'image': return g(`<image href="${it.src}" x="${it.x}" y="${it.y}" width="${it.w}" height="${it.h}" preserveAspectRatio="xMidYMid slice"/>`);
    case 'file':
      return g(`<rect x="${it.x}" y="${it.y}" width="${it.w}" height="${it.h}" rx="12" fill="#1d1c22" stroke="#3a3842"/>
        <path transform="translate(${it.x + 14},${it.y + 16})" d="M2 0h11l6 6v20H2zM13 0v6h6" fill="none" stroke="#ffd166" stroke-width="1.6"/>
        <text x="${it.x + 44}" y="${it.y + 30}" fill="#f5f1e8" font-size="14" font-family="Inter, sans-serif">${esc(it.name.slice(0, 26))}</text>
        <text x="${it.x + 44}" y="${it.y + 48}" fill="#8f8a80" font-size="11" font-family="Inter, sans-serif">double-click to open</text>`);
    default: return '';
  }
}

export class Board {
  constructor(root, api) {
    this.root = root; this.api = api;
    this.items = []; this.view = { x: 0, y: 0, k: 1 };
    this.tool = 'pen'; this.color = COLORS[0]; this.noteColor = NOTE_COLORS[0]; this.width = 3;
    this.sel = null; this.undo = []; this.redo = []; this.dirty = false; this.changed = false;
    root.innerHTML = `
      <svg class="bd-svg"><defs><pattern id="bd-dots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="rgba(255,255,255,.09)"/></pattern></defs>
        <rect class="bd-grid" width="100%" height="100%" fill="url(#bd-dots)"/><g class="bd-world"><g class="bd-items"></g><g class="bd-draft"></g><g class="bd-sel"></g></g></svg>
      <header class="bd-top"><div><b class="bd-name"></b><span class="bd-state">Saved</span></div>
        <div class="bd-top-r"><button type="button" data-act="theia" class="bd-theia-btn">THEIA, take a look</button>
        <button type="button" data-act="fit" title="Fit everything">Fit</button><button type="button" data-act="close" class="bd-close" title="Close (Esc)">Done</button></div></header>
      <nav class="bd-tools">${TOOLS.map(([t, k, d]) => `<button type="button" data-tool="${t}" title="${t} (${k})"><svg viewBox="0 0 24 24"><path d="${d}"/></svg></button>`).join('')}
        <i></i><button type="button" data-act="undo" title="Undo (Ctrl+Z)"><svg viewBox="0 0 24 24"><path d="M9 14L4 9l5-5M4 9h10a6 6 0 010 12h-3"/></svg></button>
        <button type="button" data-act="redo" title="Redo (Ctrl+Y)"><svg viewBox="0 0 24 24"><path d="M15 14l5-5-5-5M20 9H10a6 6 0 000 12h3"/></svg></button></nav>
      <div class="bd-props"><div class="bd-colors">${COLORS.map((c) => `<button type="button" data-color="${c}" style="--c:${c}"></button>`).join('')}</div>
        <div class="bd-notes">${NOTE_COLORS.map((c) => `<button type="button" data-note="${c}" style="--c:${c}"></button>`).join('')}</div>
        <div class="bd-widths">${[2, 4, 8].map((w) => `<button type="button" data-width="${w}"><i style="height:${w}px"></i></button>`).join('')}</div></div>
      <aside class="bd-side" hidden><header><b>THEIA</b><button type="button" data-act="side">✕</button></header><div class="bd-side-body"></div></aside>
      <input type="file" class="bd-pick-image" accept="image/*" multiple hidden><input type="file" class="bd-pick-file" multiple hidden>`;
    this.svg = root.querySelector('.bd-svg');
    this.world = root.querySelector('.bd-world');
    this.layer = root.querySelector('.bd-items');
    this.draft = root.querySelector('.bd-draft');
    this.selLayer = root.querySelector('.bd-sel');
    this.bind();
  }

  /* -- opening, saving ----------------------------------------------------------------- */
  async open(project) {
    this.project = project;
    this.root.querySelector('.bd-name').textContent = project.name;
    const data = (await this.api().project_board(project.id)) || {};
    this.items = data.items || []; this.view = data.view || { x: innerWidth / 2 - 400, y: innerHeight / 2 - 260, k: 1 };
    this.undo = []; this.redo = []; this.changed = false; this.sel = null;
    this.root.classList.add('on'); this.root.setAttribute('aria-hidden', 'false');
    this.setTool(this.items.length ? 'select' : 'pen');
    this.render();
    if (project.theia) this.showTheia(project.theia, false);
    else this.root.querySelector('.bd-side').hidden = true;
  }

  async close() {
    clearTimeout(this.saveTimer);
    await this.save(true);
    this.root.classList.remove('on'); this.root.setAttribute('aria-hidden', 'true');
    // A changed board goes to THEIA on its own, at most every half an hour.
    const p = this.project;
    if (this.changed && this.items.length && (!p.reviewed_at || Date.now() / 1000 - p.reviewed_at > 1800)) {
      this.png().then((png) => this.api().project_theia(p.id, png)).catch(() => {});
    }
    this.onClose && this.onClose();
  }

  touch() {
    this.dirty = true; this.changed = true;
    this.root.querySelector('.bd-state').textContent = 'Saving…';
    clearTimeout(this.saveTimer);
    this.saveTimer = setTimeout(() => this.save(), 1200);
  }

  async save(withPreview = false) {
    if (!this.dirty && !withPreview) return;
    const preview = withPreview && this.items.length ? await this.png(560).catch(() => '') : '';
    const r = await this.api().project_save(this.project.id, { items: this.items, view: this.view }, preview);
    this.dirty = false;
    this.root.querySelector('.bd-state').textContent = r && r.ok === false ? r.error : 'Saved';
  }

  remember() { this.undo.push(JSON.stringify(this.items)); if (this.undo.length > 60) this.undo.shift(); this.redo = []; }
  stepBack(from, to) {
    if (!from.length) return;
    to.push(JSON.stringify(this.items));
    this.items = JSON.parse(from.pop()); this.sel = null; this.render(); this.touch();
  }

  /* -- drawing ------------------------------------------------------------------------- */
  render() {
    const editing = this.editing;
    this.layer.innerHTML = this.items.map((it) => itemSvg(it, true)).join('');
    this.world.setAttribute('transform', `translate(${this.view.x},${this.view.y}) scale(${this.view.k})`);
    this.svg.querySelector('.bd-grid').setAttribute('transform', `translate(${this.view.x % (24 * this.view.k)},${this.view.y % (24 * this.view.k)}) scale(${this.view.k})`);
    this.drawSel();
    if (editing) this.focusEdit(editing);
  }

  drawSel() {
    const it = this.items.find((i) => i.id === this.sel);
    if (!it) { this.selLayer.innerHTML = ''; return; }
    const b = bounds(it), p = 6 / this.view.k;
    const handle = ['note', 'text', 'image', 'rect', 'ellipse', 'file'].includes(it.type)
      ? `<rect class="bd-handle" x="${b.x + b.w - p}" y="${b.y + b.h - p}" width="${p * 2.4}" height="${p * 2.4}" rx="${p / 2}"/>` : '';
    this.selLayer.innerHTML = `<rect class="bd-selbox" x="${b.x - p}" y="${b.y - p}" width="${b.w + p * 2}" height="${b.h + p * 2}" rx="${p}" stroke-width="${1.5 / this.view.k}"/>${handle}`;
  }

  at(e) {
    const r = this.svg.getBoundingClientRect();
    return [(e.clientX - r.left - this.view.x) / this.view.k, (e.clientY - r.top - this.view.y) / this.view.k];
  }

  setTool(t) {
    this.tool = t;
    this.root.querySelectorAll('[data-tool]').forEach((b) => b.classList.toggle('on', b.dataset.tool === t));
    this.root.dataset.tool = t;
    if (t === 'image') { this.root.querySelector('.bd-pick-image').click(); this.setTool('select'); }
    if (t === 'file') { this.root.querySelector('.bd-pick-file').click(); this.setTool('select'); }
  }

  add(it) { this.remember(); this.items.push(it); this.sel = it.id; this.render(); this.touch(); return it; }

  focusEdit(id) {
    const div = this.layer.querySelector(`[data-id="${id}"] [contenteditable]`);
    if (!div) return;
    div.focus();
    const range = document.createRange(); range.selectNodeContents(div); range.collapse(false);
    const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
  }

  /* -- pictures and files -------------------------------------------------------------- */
  async addImage(file, where) {
    const url = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsDataURL(file); });
    const img = await new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.src = url; });
    const scale = Math.min(1, 1600 / Math.max(img.width, img.height));
    const c = Object.assign(document.createElement('canvas'), { width: Math.round(img.width * scale), height: Math.round(img.height * scale) });
    c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
    const src = c.toDataURL(file.type === 'image/png' ? 'image/png' : 'image/jpeg', 0.86);
    const w = Math.min(520, c.width), h = w * c.height / c.width;
    const [x, y] = where || this.centre();
    this.add({ id: uid(), type: 'image', src, x: x - w / 2, y: y - h / 2, w, h });
  }

  async addFile(file, where) {
    if (file.type.startsWith('image/')) return this.addImage(file, where);
    if (file.size > 25 * 1024 * 1024) { this.say('That file is over 25 MB - keep it in a folder and drop a note instead.'); return; }
    const url = await new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsDataURL(file); });
    const path = await this.api().project_file(this.project.id, file.name, url);
    const [x, y] = where || this.centre();
    this.add({ id: uid(), type: 'file', name: file.name, path, x: x - 120, y: y - 32, w: 240, h: 64 });
  }

  centre() { const r = this.svg.getBoundingClientRect(); return [(r.width / 2 - this.view.x) / this.view.k, (r.height / 2 - this.view.y) / this.view.k]; }
  say(text) { this.root.querySelector('.bd-state').textContent = text; }

  fit() {
    if (!this.items.length) return;
    const bs = this.items.map(bounds);
    const x0 = Math.min(...bs.map((b) => b.x)), y0 = Math.min(...bs.map((b) => b.y));
    const x1 = Math.max(...bs.map((b) => b.x + b.w)), y1 = Math.max(...bs.map((b) => b.y + b.h));
    const r = this.svg.getBoundingClientRect();
    const k = Math.min(2, Math.max(0.1, Math.min((r.width - 240) / (x1 - x0 || 1), (r.height - 220) / (y1 - y0 || 1))));
    this.view = { k, x: r.width / 2 - (x0 + x1) / 2 * k, y: r.height / 2 - (y0 + y1) / 2 * k + 20 };
    this.render(); this.touch();
  }

  /* The whole board as a PNG, for THEIA and the project card. */
  async png(most = 1600) {
    const bs = this.items.map(bounds);
    if (!bs.length) return '';
    const pad = 40;
    const x0 = Math.min(...bs.map((b) => b.x)) - pad, y0 = Math.min(...bs.map((b) => b.y)) - pad;
    const w = Math.max(...bs.map((b) => b.x + b.w)) + pad - x0, h = Math.max(...bs.map((b) => b.y + b.h)) + pad - y0;
    const k = Math.min(1, most / Math.max(w, h));
    const css = '.bd-note{width:100%;height:100%;box-sizing:border-box;padding:14px;border-radius:6px;color:#1b1a17;font:500 16px/1.4 Inter,sans-serif;white-space:pre-wrap;overflow:hidden}.bd-text{white-space:pre-wrap;font-family:Inter,sans-serif;font-weight:600}';
    const svg = `<svg xmlns="${NS}" width="${Math.round(w * k)}" height="${Math.round(h * k)}" viewBox="${x0} ${y0} ${w} ${h}"><style>${css}</style>
      <rect x="${x0}" y="${y0}" width="${w}" height="${h}" fill="#141317"/>${this.items.map((it) => itemSvg(it)).join('')}</svg>`;
    const img = await new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej;
      i.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`; });
    const c = Object.assign(document.createElement('canvas'), { width: img.width, height: img.height });
    c.getContext('2d').drawImage(img, 0, 0);
    return c.toDataURL('image/png');
  }

  async askTheia() {
    const side = this.root.querySelector('.bd-side');
    side.hidden = false;
    side.querySelector('.bd-side-body').innerHTML = '<p class="bd-wait">THEIA is looking at your board…</p>';
    await this.save();
    const r = await this.api().project_theia(this.project.id, await this.png().catch(() => ''));
    if (r && r.ok) { this.project.theia = r.theia; this.project.reviewed_at = Date.now() / 1000; this.showTheia(r.theia, true); }
    else side.querySelector('.bd-side-body').innerHTML = `<p class="bd-wait">${esc((r && r.error) || 'THEIA could not look just now.')}</p>`;
  }

  showTheia(notes, fresh) {
    const side = this.root.querySelector('.bd-side');
    side.hidden = false;
    const html = esc(notes.notes || '').replace(/^(SUMMARY|WHAT I SEE|NEXT|MISSING|QUESTION):/gm, '<h5>$1</h5>')
      .replace(/^\s*[-•*]\s+(.*)$/gm, '<li>$1</li>').replace(/\n{2,}/g, '<br>');
    side.querySelector('.bd-side-body').innerHTML = `<div dir="auto">${html}</div><small>${fresh ? 'just now' : new Date(notes.at * 1000).toLocaleString('en-GB')}</small>`;
    if (!notes.seen) this.api().project_seen(this.project.id);
  }

  /* -- input ----------------------------------------------------------------------------- */
  bind() {
    const root = this.root;
    root.addEventListener('click', (e) => {
      const b = e.target.closest('button'); if (!b) return;
      if (b.dataset.tool) this.setTool(b.dataset.tool);
      if (b.dataset.color) { this.color = b.dataset.color; this.recolor('color', b.dataset.color); }
      if (b.dataset.note) { this.noteColor = b.dataset.note; this.recolor('note', b.dataset.note); }
      if (b.dataset.width) this.width = Number(b.dataset.width);
      const act = b.dataset.act;
      if (act === 'close') this.close();
      if (act === 'undo') this.stepBack(this.undo, this.redo);
      if (act === 'redo') this.stepBack(this.redo, this.undo);
      if (act === 'fit') this.fit();
      if (act === 'theia') this.askTheia();
      if (act === 'side') root.querySelector('.bd-side').hidden = true;
      root.querySelectorAll('[data-color]').forEach((x) => x.classList.toggle('on', x.dataset.color === this.color));
      root.querySelectorAll('[data-note]').forEach((x) => x.classList.toggle('on', x.dataset.note === this.noteColor));
      root.querySelectorAll('[data-width]').forEach((x) => x.classList.toggle('on', Number(x.dataset.width) === this.width));
    });
    root.querySelector('.bd-pick-image').addEventListener('change', async (e) => { for (const f of e.target.files) await this.addImage(f); e.target.value = ''; });
    root.querySelector('.bd-pick-file').addEventListener('change', async (e) => { for (const f of e.target.files) await this.addFile(f); e.target.value = ''; });
    this.svg.addEventListener('pointerdown', (e) => this.down(e));
    this.svg.addEventListener('pointermove', (e) => this.move(e));
    this.svg.addEventListener('pointerup', (e) => this.up(e));
    this.svg.addEventListener('dblclick', (e) => this.dbl(e));
    this.svg.addEventListener('wheel', (e) => {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        const r = this.svg.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
        const k = Math.min(4, Math.max(0.1, this.view.k * Math.exp(-e.deltaY * 0.0022)));
        this.view.x = mx - (mx - this.view.x) * k / this.view.k; this.view.y = my - (my - this.view.y) * k / this.view.k; this.view.k = k;
      } else { this.view.x -= e.deltaX; this.view.y -= e.deltaY; }
      this.render(); this.dirty = true;
    }, { passive: false });
    this.layer.addEventListener('input', (e) => {
      const id = e.target.closest('[data-id]')?.dataset.id, it = this.items.find((i) => i.id === id);
      if (!it) return;
      it.text = e.target.innerText;
      if (it.type === 'text') {                  // the box grows with what is typed, in either direction of script
        it.w = Math.max(40, e.target.scrollWidth + 30); it.h = Math.max(it.size * 1.4, e.target.scrollHeight + 4);
        const fo = e.target.closest('foreignObject'); fo.setAttribute('width', it.w); fo.setAttribute('height', it.h);
      }
      this.touch();
    });
    this.layer.addEventListener('focusout', (e) => {
      const id = e.target.closest('[data-id]')?.dataset.id;
      this.editing = null;
      const it = this.items.find((i) => i.id === id);
      if (it && it.type === 'text' && !it.text.trim()) { this.items = this.items.filter((i) => i !== it); this.render(); this.touch(); }
    });
    root.addEventListener('dragover', (e) => e.preventDefault());
    root.addEventListener('drop', async (e) => { e.preventDefault(); const at = this.at(e); for (const f of e.dataTransfer.files) await this.addFile(f, at); });
    document.addEventListener('paste', async (e) => {
      if (!root.classList.contains('on') || this.editing) return;
      for (const item of e.clipboardData.items) if (item.kind === 'file') await this.addFile(item.getAsFile());
    });
    // First, and only ours while the board is up: the display's own shortcuts never see these keys.
    document.addEventListener('keydown', (e) => { if (this.root.classList.contains('on')) { e.stopImmediatePropagation(); this.key(e, true); } }, true);
    document.addEventListener('keyup', (e) => { if (this.root.classList.contains('on')) { e.stopImmediatePropagation(); this.key(e, false); } }, true);
  }

  recolor(kind, c) {
    const it = this.items.find((i) => i.id === this.sel); if (!it) return;
    if (kind === 'note' && it.type === 'note') { this.remember(); it.color = c; }
    else if (kind === 'color' && it.type !== 'note' && it.type !== 'image' && it.type !== 'file') { this.remember(); it.color = c; }
    else return;
    this.render(); this.touch();
  }

  key(e, down) {
    if (!this.root.classList.contains('on')) return;
    if (e.key === ' ' && !this.editing) { this.spaceHeld = down; this.root.classList.toggle('panning', down); e.preventDefault(); return; }
    if (!down || this.editing) { if (down && e.key === 'Escape') document.activeElement.blur(); return; }
    if (e.key === 'Escape') { if (this.sel) { this.sel = null; this.drawSel(); } else this.close(); return; }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); this.stepBack(e.shiftKey ? this.redo : this.undo, e.shiftKey ? this.undo : this.redo); return; }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') { e.preventDefault(); this.stepBack(this.redo, this.undo); return; }
    if ((e.key === 'Delete' || e.key === 'Backspace') && this.sel) { this.remember(); this.items = this.items.filter((i) => i.id !== this.sel); this.sel = null; this.render(); this.touch(); return; }
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const t = TOOLS.find(([, k]) => k === e.key.toUpperCase());
    if (t) this.setTool(t[0]);
  }

  down(e) {
    if (this.editing && e.target.closest('[contenteditable]')) return;
    this.svg.setPointerCapture(e.pointerId);
    const p = this.at(e);
    if (e.button === 1 || this.tool === 'hand' || this.spaceHeld) { this.op = { kind: 'pan', sx: e.clientX, sy: e.clientY, vx: this.view.x, vy: this.view.y }; return; }
    const hit = e.target.closest('[data-id]')?.dataset.id;
    const t = this.tool;
    if (t === 'eraser') { this.op = { kind: 'erase' }; this.erase(hit); return; }
    if (t === 'select') {
      if (e.target.classList.contains('bd-handle')) {
        const it = this.items.find((i) => i.id === this.sel);
        this.remember(); this.op = { kind: 'resize', it, sx: p[0], sy: p[1], w: it.w, h: it.h, ratio: it.type === 'image' ? it.h / it.w : 0 };
        return;
      }
      this.sel = hit || null; this.drawSel();
      if (hit) { this.remember(); this.op = { kind: 'drag', it: this.items.find((i) => i.id === hit), last: p, moved: false }; }
      return;
    }
    if (t === 'pen' || t === 'marker') {
      this.op = { kind: 'ink', it: { id: uid(), type: 'ink', pts: [p], color: this.color, w: t === 'marker' ? this.width * 4 : this.width, op: t === 'marker' ? 0.4 : 1 } };
      return;
    }
    if (['line', 'arrow', 'rect', 'ellipse'].includes(t)) { this.op = { kind: 'shape', t, from: p, to: p }; return; }
    if (t === 'note' || t === 'text') e.preventDefault();
    if (t === 'note') { const it = this.add({ id: uid(), type: 'note', x: p[0] - 100, y: p[1] - 80, w: 200, h: 160, text: '', color: this.noteColor }); this.edit(it.id); this.setTool('select'); return; }
    if (t === 'text') { const it = this.add({ id: uid(), type: 'text', x: p[0], y: p[1] - 18, w: 600, h: 40, text: '', size: 26, color: this.color }); this.edit(it.id); this.setTool('select'); }
  }

  move(e) {
    const op = this.op; if (!op) return;
    const p = this.at(e);
    if (op.kind === 'pan') { this.view.x = op.vx + e.clientX - op.sx; this.view.y = op.vy + e.clientY - op.sy; this.render(); return; }
    if (op.kind === 'erase') { const id = document.elementFromPoint(e.clientX, e.clientY)?.closest('[data-id]')?.dataset.id; this.erase(id); return; }
    if (op.kind === 'ink') { op.it.pts.push([Math.round(p[0] * 10) / 10, Math.round(p[1] * 10) / 10]); this.draft.innerHTML = itemSvg(op.it); return; }
    if (op.kind === 'shape') { op.to = p; this.draft.innerHTML = itemSvg(this.shape(op)); return; }
    if (op.kind === 'drag') {
      const dx = p[0] - op.last[0], dy = p[1] - op.last[1]; op.last = p; op.moved = true;
      const it = op.it;
      if (it.pts) it.pts = it.pts.map(([x, y]) => [x + dx, y + dy]); else { it.x += dx; it.y += dy; }
      this.render(); return;
    }
    if (op.kind === 'resize') {
      const it = op.it;
      it.w = Math.max(40, op.w + p[0] - op.sx);
      it.h = op.ratio ? it.w * op.ratio : Math.max(30, op.h + p[1] - op.sy);
      this.render();
    }
  }

  up() {
    if (this.editing) this.focusEdit(this.editing);
    const op = this.op; this.op = null; this.draft.innerHTML = '';
    if (!op) return;
    if (op.kind === 'ink' && op.it.pts.length > 1) this.add(op.it);
    if (op.kind === 'shape') { const it = this.shape(op); const b = bounds(it); if (b.w + b.h > 6) this.add(it); }
    if (op.kind === 'drag') { if (op.moved) this.touch(); else this.undo.pop(); }
    if (op.kind === 'resize') this.touch();
    if (op.kind === 'pan') this.dirty = true;
  }

  shape(op) {
    const [x1, y1] = op.from, [x2, y2] = op.to;
    if (op.t === 'line' || op.t === 'arrow') return { id: op.id || (op.id = uid()), type: op.t, pts: [[x1, y1], [x2, y2]], color: this.color, w: this.width };
    return { id: op.id || (op.id = uid()), type: op.t, x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1), color: this.color, sw: this.width };
  }

  erase(id) {
    if (!id) return;
    this.remember();
    this.items = this.items.filter((i) => i.id !== id);
    this.render(); this.touch();
  }

  edit(id) { this.editing = id; this.focusEdit(id); setTimeout(() => this.editing === id && this.focusEdit(id), 30); }

  dbl(e) {
    const id = e.target.closest('[data-id]')?.dataset.id, it = this.items.find((i) => i.id === id);
    if (!it) return;
    if (it.type === 'note' || it.type === 'text') this.edit(id);
    if (it.type === 'file') this.api().project_open_file(it.path);
  }
}
