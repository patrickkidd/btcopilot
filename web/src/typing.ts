/** Whether the keyboard has handed a message box all its words. A phrase
 * still being composed (on an iPhone, the last phrase dictation is still
 * hearing) belongs to the keyboard: a box emptied under it gets the phrase
 * back the moment the keyboard lets go of it. So a send ends the composition
 * by taking the focus away, and reads and empties the box only once the
 * composition has ended. */
export class Typing {
  private composing = false;
  private ended: (() => void) | null = null;

  constructor(private box: HTMLElement) {
    box.addEventListener("compositionstart", () => (this.composing = true));
    box.addEventListener("compositionend", () => {
      this.composing = false;
      this.ended?.();
      this.ended = null;
    });
  }

  /** True once the box holds every word, so this send may read and empty
   * it; false for a second send while the first still waits for the
   * keyboard, as only one of them may send. */
  async free(): Promise<boolean> {
    if (!this.composing) return true;
    if (this.ended) return false;
    const ended = new Promise<void>((go) => (this.ended = go));
    this.box.blur();
    await ended;
    return true;
  }
}
