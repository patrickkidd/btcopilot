import { passages } from "./case";
import { Sheet } from "./sheet";
import type { Passages } from "./types";

/** The book buttons and the sheet of passages they raise (R-0691, R-0692),
 * one for each screen that has books: the passages are read once, asked for
 * again at the next tap when a read failed. */
export class Books {
  private all: Promise<Passages | null> | null = null;
  private readonly sheet: Sheet;

  constructor(
    root: HTMLElement,
    private readonly read: () => Promise<Passages | null>,
  ) {
    this.sheet = new Sheet(root, "bk");
    // its cross, the dimmed page above it and Escape all put it away
    root.addEventListener("click", (e) => {
      if ((e.target as Element).closest(".fs-sheet.bk .cardx, .fs-scrim.bk")) this.sheet.lower();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.sheet.up) {
        this.sheet.lower();
        // the key put the passages away and nothing else: the page behind a
        // cluster's i, which Escape also closes, stays where it was
        e.stopImmediatePropagation();
      }
    });
  }

  /** Whether the passages are up. */
  get up(): boolean {
    return this.sheet.up;
  }

  /** Read again at the next ask, as when another family is opened. */
  forget(): void {
    this.all = null;
  }

  /** The passages, read once. */
  ask(): Promise<Passages | null> {
    this.all ??= this.read().catch((error) => {
      this.all = null;
      throw error;
    });
    return this.all;
  }

  /** A tap on a book raises its passages; false when the tap was not on one. */
  tap(target: Element): boolean {
    const book = target.closest<HTMLElement>(".book[data-book]");
    if (!book) return false;
    void this.open(book);
    return true;
  }

  private async open(book: HTMLElement): Promise<void> {
    const all = await this.ask();
    if (all) this.sheet.show(passages(all, book.dataset.book!, book.dataset.title!));
  }
}
