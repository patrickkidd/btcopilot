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

/** A chip with nothing to do is dimmed rather than missing. */
export const tok = (
  id: string,
  kind: string,
  mark: string,
  word: string,
  live: boolean,
) =>
  `<button type="button" class="tok ${kind}${live ? "" : " dim"}" id="${id}"` +
  `${live ? "" : " disabled"}>${mark}${word}</button>`;

/** The way into the two lists, at the end of the row (owner review round 3). */
export const LIST_BUTTON =
  `<button class="listglyph" id="menu-open" type="button" ` +
  `aria-label="open the timeline list">` +
  `<svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">` +
  `<path d="M1 1h14M1 6h14M1 11h14" stroke="currentColor" stroke-width="1.6" ` +
  `stroke-linecap="round" fill="none"/></svg></button>`;
