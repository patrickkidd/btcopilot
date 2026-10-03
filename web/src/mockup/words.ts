import type { PageFile } from "./casefile";

/** Page words. The page speaks plain words (Patrick, 2026-10-01: no theory
 * vocabulary). The case files' texts are not edited: the page picks. A theory
 * word inside a quote is replaced with plain words in square brackets, the way
 * an editor marks words that are not the speaker's, and a sentence that says
 * what caused what is left out, by one rule on every page. Which words and
 * which sentences is in each case's page file (reword, cut), never here; the
 * verdict file (fd336/verdict.md) lists them too. */

/** The words the page may not carry (Patrick, 2026-10-01). */
export const FORBIDDEN = /\b(differentiat\w*|triangl\w*|triangulat\w*|fusion|cut[- ]?off|anxiety|anxious|nuclear|projection|because)\b/gi;

/** Words this page once coined and may not use: Patrick's word for a set of
 * events on the line is "cluster" (ruled 2026-09-22; never "span" or
 * "stretch"), a thing that happened is an "event" (never "moment"), and he said
 * "chalkboard", never "board" on its own. */
export const COINED = /\b(spans?|stretch(es)?|moments?|board)\b/gi;

export function scan(text: string, re: RegExp = FORBIDDEN): string[] {
  return [...new Set((text.match(re) ?? []).map((w) => w.toLowerCase()))];
}

/** One case's wording: its page file's cuts and rewordings, applied to any
 * text of its case file, and the record of which ones matched. */
export class Wording {
  private readonly fired = new Set<string>();

  constructor(private readonly page: PageFile) {}

  /** A case file's words as the page shows them. */
  plain(text: string): string {
    let out = text;
    for (const { from } of this.page.cut) {
      if (!out.includes(from)) continue;
      out = out.split(from).join("");
      this.fired.add(from);
    }
    for (const [from, to] of this.page.reword) {
      if (!out.includes(from)) continue;
      out = out.split(from).join(to);
      this.fired.add(from);
    }
    return out;
  }

  /** Replacements and cuts that matched nothing: the case file drifted from
   * what its page file was written against. */
  unfired(): string[] {
    return [...this.page.reword.map(([from]) => from), ...this.page.cut.map((c) => c.from)].filter((from) => !this.fired.has(from));
  }
}
