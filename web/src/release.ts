import { Failed } from "./api";

/** How often a page that is due to reload looks again for a moment when
 * nothing would be lost. */
export const IDLE_POLL_MS = 1000;

/** A home-screen app keeps running the page it last loaded, so after a deploy
 * it would go on running the old release. Coming back to the front the page
 * asks which release is live and loads it, but never while that would lose the
 * reader's unsent words or a turn the coach is still writing. */
export class Release {
  private due = false;

  constructor(
    private readonly served: string,
    private readonly live: () => Promise<string>,
    private readonly busy: () => boolean,
    private readonly reload: () => void,
  ) {}

  async check(): Promise<void> {
    if (this.due) return;
    let live;
    try {
      live = await this.live();
    } catch (error) {
      // Offline or a server between releases is an ordinary state for an app
      // on a phone: which release is live is unknown, so the page stays.
      if (error instanceof Failed) return;
      throw error;
    }
    if (live === this.served) return;
    this.due = true;
    this.settle();
  }

  private settle(): void {
    if (this.busy()) setTimeout(() => this.settle(), IDLE_POLL_MS);
    else this.reload();
  }
}
