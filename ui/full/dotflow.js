/* The thinking state: a 7x7 dot matrix that plays a sequence, with the word
 * for what it is doing beside it.
 *
 * Ported from the React component in the brief. Everything it needed from
 * outside - GSAP for the label's transition, React for the frame counter - is
 * a few lines here, and this page has neither. The frame data is the brief's,
 * unchanged: each frame is the list of lit cells, 0 to 48, reading across.
 */

const SIZE = 49;          // seven by seven

export const FRAMES = {
  importing: [
    [0, 2, 4, 6, 20, 34, 48, 46, 44, 42, 28, 14, 8, 22, 36, 38, 40, 26, 12, 10, 16, 30, 24, 18, 32],
    [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45, 47],
    [8, 22, 36, 38, 40, 26, 12, 10, 16, 30, 24, 18, 32],
    [9, 11, 15, 17, 19, 23, 25, 29, 31, 33, 37, 39],
    [16, 30, 24, 18, 32],
    [17, 23, 31, 25],
    [24],
    [17, 23, 31, 25],
    [16, 30, 24, 18, 32],
    [9, 11, 15, 17, 19, 23, 25, 29, 31, 33, 37, 39],
    [8, 22, 36, 38, 40, 26, 12, 10, 16, 30, 24, 18, 32],
    [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45, 47],
    [0, 2, 4, 6, 20, 34, 48, 46, 44, 42, 28, 14, 8, 22, 36, 38, 40, 26, 12, 10, 16, 30, 24, 18, 32],
  ],
  syncing: [
    [45, 38, 31, 24, 17, 23, 25],
    [38, 31, 24, 17, 10, 16, 18],
    [31, 24, 17, 10, 3, 9, 11],
    [24, 17, 10, 3, 2, 4],
    [17, 10, 3],
    [10, 3],
    [3],
    [],
    [45],
    [45, 38, 44, 46],
    [45, 38, 31, 37, 39],
    [45, 38, 31, 24, 30, 32],
  ],
  searching: [
    [9, 16, 17, 15, 23],
    [10, 17, 18, 16, 24],
    [11, 18, 19, 17, 25],
    [18, 25, 26, 24, 32],
    [25, 32, 33, 31, 39],
    [32, 39, 40, 38, 46],
    [31, 38, 39, 37, 45],
    [30, 37, 38, 36, 44],
    [23, 30, 31, 29, 37],
    [31, 29, 37, 22, 24, 23, 38, 36],
    [16, 23, 24, 22, 30],
  ],
  heartbeat: [
    [],
    [3],
    [10, 2, 4, 3],
    [17, 9, 1, 11, 5, 10, 4, 3, 2],
    [24, 16, 8, 1, 3, 5, 18, 12, 17, 11, 4, 10, 9, 2],
    [31, 23, 15, 8, 10, 2, 4, 12, 25, 19, 24, 18, 11, 17, 16, 9],
    [38, 30, 22, 15, 17, 9, 11, 19, 32, 26, 31, 25, 18, 24, 23, 16],
    [38, 30, 22, 15, 17, 9, 11, 19, 32, 26, 31, 25, 18, 24, 23, 16],
    [38, 30, 22, 17, 9, 11, 19, 32, 26, 31, 25, 18, 24, 23, 16, 45, 37, 29, 21, 14, 8, 15, 12, 20, 27, 33, 39],
    [38, 30, 22, 17, 9, 11, 19, 32, 26, 31, 25, 18, 24, 23, 16, 45, 37, 29, 21, 14, 8, 15, 12, 20, 27, 33, 39],
    [38, 30, 22, 15, 17, 9, 11, 19, 32, 26, 31, 25, 18, 24, 23, 16],
    [39, 33, 37, 29, 17, 38, 30, 22, 15, 16, 23, 24, 31, 32, 25, 18, 26, 19],
    [17, 30, 16, 23, 24, 31, 32, 25, 18],
    [24],
  ],
};

export class DotFlow {
  /* `host` is an empty element. It gets the grid and the label; nothing else
   * on the page needs to know how either is built. */
  constructor(host, { dotSize = 6, gap = 3 } = {}) {
    this.host = host;
    this.items = [];
    this.item = 0;
    this.frame = 0;
    this.repeats = 0;
    this.timer = null;

    host.innerHTML = '';
    host.classList.add('dotflow');
    this.grid = document.createElement('div');
    this.grid.className = 'dotflow-grid';
    this.grid.style.gridTemplateColumns = `repeat(7, ${dotSize}px)`;
    this.grid.style.gap = `${gap}px`;
    for (let i = 0; i < SIZE; i++) {
      const dot = document.createElement('i');
      dot.style.width = dot.style.height = `${dotSize}px`;
      this.grid.appendChild(dot);
    }
    this.label = document.createElement('span');
    this.label.className = 'dotflow-label';
    host.append(this.grid, this.label);
    this.dots = [...this.grid.children];
  }

  /* `items` is [{title, frames, duration, repeatCount}], the brief's shape. */
  play(items) {
    this.items = items.filter((item) => item && item.frames && item.frames.length);
    if (!this.items.length) return this.stop();
    this.item = this.frame = this.repeats = 0;
    this.held = null;
    this._say(this.items[0].title);
    this._tick();
  }

  stop() {
    clearTimeout(this.timer);
    this.timer = null;
    for (const dot of this.dots) dot.classList.remove('on');
  }

  /* What Apollo is actually doing, when it knows: "fetching NVDA" rather than
   * "Thinking". The sequence carries on underneath. */
  say(text) {
    this.held = text;
    this._say(text);
  }

  _say(text) {
    // Down and out, then in from above - the label transition from the brief,
    // which is the only thing GSAP was doing there.
    this.label.style.animation = 'none';
    void this.label.offsetWidth;
    this.label.textContent = text || '';
    this.label.style.animation = '';
  }

  _tick() {
    const item = this.items[this.item];
    if (!item) return;
    const frame = item.frames[this.frame] || [];
    for (let i = 0; i < SIZE; i++) {
      this.dots[i].classList.toggle('on', frame.includes(i));
    }

    this.frame += 1;
    if (this.frame >= item.frames.length) {
      this.frame = 0;
      this.repeats += 1;
      if (this.repeats >= (item.repeatCount ?? 1)) {
        this.repeats = 0;
        this.item = (this.item + 1) % this.items.length;
        this._say(this.held || this.items[this.item].title);
      }
    }
    this.timer = setTimeout(() => this._tick(), item.duration ?? 150);
  }
}
