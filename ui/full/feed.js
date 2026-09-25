/* The feed's rows, fuller: what a story shows beside its title. A picture -
 * its own, or where it came without one, its source's initials on a tile
 * tinted for what it is about - a two-line gist, and what it is about where
 * the chip over the list does not already say. And a line over the list:
 * how many stories, from how many places, and how new the newest is.
 * app.js builds the markup; this is the part node can check
 * (tests/test_feed_rows.py). */

/* A source's initials: the first letters of its first two words; one word
 * in capitals (GameGPU) gives its capitals, any other one word its first
 * two letters. An apostrophe does not break a word. */
export function initials(source) {
  const words = String(source || '').replace(/['’]/g, '').match(/[\p{L}\p{N}]+/gu) || [];
  if (!words.length) return '';
  if (words.length > 1) return (words[0][0] + words[1][0]).toUpperCase();
  const capitals = words[0].match(/\p{Lu}/gu) || [];
  if (capitals.length >= 2) return capitals.slice(0, 2).join('');
  return words[0].slice(0, 2).toUpperCase();
}

/* What a story is about, on its row - only under "all": under its own chip
 * the chip says it. A post is a post; Private Eye's finds are flagged as
 * such already. */
export function topicTag(topic, chosen) {
  if (chosen !== 'all' || topic === 'private eye') return '';
  return topic === 'posts' ? 'post' : String(topic || '');
}

/* The line over the list, for stories newest first. */
export function summaryLine(items) {
  if (!items || !items.length) return '';
  const sources = new Set(items.map((item) => String(item.source || '').trim().toLowerCase()).filter(Boolean));
  const n = items.length, m = sources.size;
  return `${n} ${n === 1 ? 'story' : 'stories'} · ${m} ${m === 1 ? 'source' : 'sources'}`
       + ` · newest ${items[0].age}`;
}
