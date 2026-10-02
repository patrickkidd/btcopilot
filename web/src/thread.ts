import * as api from "./api";
import type { Said } from "./api";
import { el, esc } from "./dom";
import { clockTime, dayKey, periodLabel, rowDate } from "./when";

/** The family's one thread: every sitting's words in the order they were said,
 * a light line with the day where one sitting ends and the next begins, and older pages
 * read in as the reader scrolls up. Nobody opens, starts or closes a sitting;
 * the server starts one when the family has been quiet a while. */

/** The server's page size: a shorter page is the thread's first. */
const PAGE = 50;
/** Read the next page back while the reader is this close to the top. */
const EDGE_PX = 600;
const DAY_WORDS = new Set(["Today", "Yesterday"]);

export class Thread {
  /** The oldest statement on screen, which the next page back is read from. */
  private oldest: number | null = null;
  private more = false;
  private reading: Promise<void> | null = null;

  constructor(
    private list: HTMLElement,
    /** Draws a page of words, and a line at each sitting's start, at the end
     * of the list. */
    private draw: (page: Said[]) => void,
  ) {
    list.addEventListener(
      "scroll",
      () => {
        if (list.scrollTop < EDGE_PX) void this.older();
      },
      { passive: true },
    );
  }

  /** The newest page, just drawn: older ones are read back from it. */
  start(page: Said[]): void {
    this.oldest = page[0]?.id ?? null;
    this.more = page.length === PAGE;
  }

  /** The next page back, put above what is on screen with the words the
   * reader is looking at held exactly where they are. */
  older(): Promise<void> {
    if (!this.more || this.oldest === null) return Promise.resolve();
    this.reading ??= this.readBack().finally(() => (this.reading = null));
    return this.reading;
  }

  /** Read back until the words `statementId` are on screen, or the thread
   * has no older words. */
  async reach(statementId: number): Promise<void> {
    while (!this.list.querySelector(`[data-statement="${statementId}"]`) && this.more)
      await this.older();
  }

  private async readBack(): Promise<void> {
    const page = await api.thread(this.oldest!);
    this.start(page);
    if (!page.length) return;
    const anchor = this.list.firstElementChild;
    const was = anchor?.getBoundingClientRect().top ?? 0;
    const end = this.list.lastChild;
    this.draw(page);
    const drawn: Node[] = [];
    for (let node = end ? end.nextSibling : this.list.firstChild; node; node = node.nextSibling)
      drawn.push(node);
    this.list.prepend(...drawn);
    if (anchor) this.list.scrollTop += anchor.getBoundingClientRect().top - was;
    // The chat pins itself to its newest words on every bubble it draws and
    // ignores the scroll that pinning causes; once its frame has passed, a
    // scroll it does notice tells it the reader is up here, not at the end.
    requestAnimationFrame(() => this.list.dispatchEvent(new Event("scroll")));
  }
}

/** The line where a sitting starts, with the day it started, and the time
 * as well when the sitting before it started that same day, so two lines in
 * a row never say the same thing. */
export function divider(when: string, previous: string | null): HTMLElement {
  const started = new Date(when);
  const now = new Date();
  const period = periodLabel(started, now);
  const day = DAY_WORDS.has(period) ? period : rowDate(started, now);
  const again = previous !== null && dayKey(new Date(previous)) === dayKey(started);
  const line = el("div", "sitting", esc(again ? `${day}, ${clockTime(started)}` : day));
  line.dataset.started = when;
  return line;
}
