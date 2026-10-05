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
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && this.sheet.up) this.sheet.lower();
    });
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

  /** A tap on a book raises its passages, and one on the sheet's cross or
   * scrim lowers it; false when the tap was on neither. */
  tap(target: Element): boolean {
    if (target.closest(".fs-sheet.bk .cardx, .fs-scrim.bk")) {
      this.sheet.lower();
      return true;
    }
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
