import { esc } from "./dom";
import { Sheet } from "./sheet";

/** What the server says a paste too long for one part costs and takes
 * (R-0897). */
export interface Projection {
  part_words: number;
  usd_per_1000_words: number;
  seconds_per_part: number;
}

/** Words as the page counts them: what whitespace separates. The server cuts
 * at paragraph breaks by its own rule, so the parts shown are an estimate. */
export const wordCount = (text: string): number => text.split(/\s+/).filter(Boolean).length;

export const partsOf = (words: number, at: Projection): number =>
  Math.max(1, Math.ceil(words / at.part_words));

const thousands = (n: number) => n.toLocaleString("en-US");

/** "About 12,000 words in 8 parts. Roughly $23.40 and 13 minutes." The
 * dollars to the nearest 5 cents, the minutes rounded up. */
export function costLine(words: number, at: Projection): string {
  const parts = partsOf(words, at);
  const dollars = Math.round((words / 1000) * at.usd_per_1000_words * 20) / 20;
  const minutes = Math.ceil((parts * at.seconds_per_part) / 60);
  return (
    `About ${thousands(words)} words in ${parts} parts. ` +
    `Roughly $${dollars.toFixed(2)} and ${minutes} minute${minutes === 1 ? "" : "s"}.`
  );
}

/** A text file the page can count before it is sent; a PDF or a photo is read
 * on the server and is not priced here. */
const counted = (file: File) => /\.(txt|md)$/i.test(file.name) || /^text\//.test(file.type);

/** Before notes too long for one part are sent, the person sees what they
 * cost and how long they take, and starts or cancels (R-0897). */
export class LongNotes {
  private sheet: Sheet;

  constructor(host: HTMLElement, private readonly at: Projection) {
    this.sheet = new Sheet(host, "ln");
  }

  /** True to send: the words fit one part, or the person chose Start. */
  async ask(text: string, file: File | null): Promise<boolean> {
    const words = wordCount(text) + (file && counted(file) ? wordCount(await file.text()) : 0);
    if (partsOf(words, this.at) < 2) return true;
    this.sheet.show(
      `<div class="cf-t">Long notes</div>` +
        `<p class="cf-p">${esc(costLine(words, this.at))}</p>` +
        `<div class="cf-btns">` +
        `<button class="cf-go" type="button" data-act="start">Start</button>` +
        `<button class="cf-no" type="button" data-act="cancel">Cancel</button>` +
        `</div>`,
    );
    return new Promise((answer) => {
      const panel = this.sheet.panel;
      const done = (start: boolean) => {
        panel.removeEventListener("click", onClick);
        panel.removeEventListener("keydown", onKey);
        this.sheet.lower();
        answer(start);
      };
      const onClick = (e: Event) => {
        const act = (e.target as Element).closest<HTMLElement>("[data-act]")?.dataset.act;
        if (act) done(act === "start");
      };
      const onKey = (e: KeyboardEvent) => {
        if (e.key === "Escape") done(false);
      };
      panel.addEventListener("click", onClick);
      panel.addEventListener("keydown", onKey);
    });
  }
}
