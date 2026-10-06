/** The row under the picture: one mark and one word per chip, drawn as the
 * chip the coach writes into the messages below, so the row and the thread are
 * plainly the same object (picked plate F).
 *
 * The chat screen and the coding screen both draw this row, from here, so the
 * two cannot drift apart. Which chips each screen offers is its own: there is
 * no coach turn in a coding, so that screen shows only the play mark. */

export const ASK_MARK =
  `<svg width="15" height="15" viewBox="0 0 18 18" aria-hidden="true">` +
  `<rect x="1.3" y="7" width="15.4" height="9" rx="4.5" fill="none" ` +
  `stroke="currentColor" stroke-width="1.4"/>` +
  `<rect x="4" y="9.8" width="7" height="3.4" rx="1.7" fill="currentColor"/>` +
  `<path d="M9 1v3.6M9 4.9 7.2 3.1M9 4.9l1.8-1.8" fill="none" ` +
  `stroke="currentColor" stroke-width="1.4" stroke-linecap="round" ` +
  `stroke-linejoin="round"/></svg>`;

export const PLAY_MARK =
  `<svg width="12" height="12" viewBox="0 0 18 18" aria-hidden="true">` +
  `<path d="M4.8 2.6 15.2 9 4.8 15.4Z" fill="currentColor"/></svg>`;

export const IN_CHAT_MARK =
  `<svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true">` +
  `<rect x="1.6" y="2.4" width="14.8" height="10.2" rx="3" fill="none" ` +
  `stroke="currentColor" stroke-width="1.5"/>` +
  `<path d="M5.6 12.6 4.6 16.2 8.6 12.6" fill="none" stroke="currentColor" ` +
  `stroke-width="1.5" stroke-linejoin="round"/></svg>`;

/** A couple and their child, the mark of the whole family (R-0742). */
export const FAMILY_MARK =
  `<svg width="15" height="15" viewBox="0 0 18 18" aria-hidden="true">` +
  `<g fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round">` +
  `<rect x="1.5" y="1.5" width="5.5" height="5.5"/><circle cx="13.75" cy="4.25" r="2.75"/>` +
  `<path d="M4.25 7v3h9.5V7M9 10v3.5"/><circle cx="9" cy="15.2" r="1.8"/></g></svg>`;

/** A chip with nothing to do is dimmed rather than missing. */
/** The one back arrow every screen draws (R-0223). */
export const BACK =
  `<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">` +
  `<path d="M13.5 4.5 7 11l6.5 6.5" stroke="currentColor" stroke-width="2" ` +
  `stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>`;

export const tok = (
  id: string,
  kind: string,
  mark: string,
  word: string,
  live: boolean,
) =>
  `<button type="button" class="tok ${kind}${live ? "" : " dim"}" id="${id}"` +
  `${live ? "" : " disabled"}>${mark}${word}</button>`;

/** The way into the two lists, at the end of the row (owner review round 3).
 * The chat and the coding screen each have their own, so the id is given. */
export const listButton = (id: string) =>
  `<button class="listglyph" id="${id}" type="button" ` +
  `aria-label="open the timeline list">` +
  `<svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">` +
  `<path d="M1 1h14M1 6h14M1 11h14" stroke="currentColor" stroke-width="1.6" ` +
  `stroke-linecap="round" fill="none"/></svg></button>`;
