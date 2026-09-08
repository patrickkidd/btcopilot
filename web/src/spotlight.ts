/** The words the picture writes about a moment, and how they are cut to fit.
 * Pure, so the sentence spotlight's decisions can be checked without a browser.
 * Geometry and wording follow the converged mockup (crowded-chapter,
 * concept-sentence-spotlight, ruled 2026-09-02): one mono line per row, cut at a
 * space, three rows at most. */

/** IBM Plex Mono advance at the 13px floor. */
export const CH = 7.8;
export const ROWS = [44, 59, 74];
export const WIRE = 99;
export const YEAR_TOP = 136;
export const PIC_H = 158;
export const X_PAD = 16;
/** UI_STANDARDS: no tap target below 44. */
export const ZONE = 44;

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export enum Certainty {
  Unknown = "unknown",
  Approximate = "approximate",
  Certain = "certain",
}

/** A date the record is only approximately sure of says its year and no more;
 * a date it is sure of says the month too. */
export function dateText(iso: string, certainty: string | null): string {
  const year = iso.slice(0, 4);
  if (certainty === Certainty.Approximate) return year;
  const month = Number(iso.slice(5, 7));
  return `${MONTHS[Math.min(11, Math.max(0, month - 1))]} ${year}`;
}

export const clip = (text: string, n: number): string =>
  text.length > n ? text.slice(0, Math.max(0, n - 1)) + "…" : text;

/** Two rows of a label, cut at a space unless that would throw most of it away. */
export function wrap2(text: string, wide: number): [string, string] {
  if (text.length <= wide) return [text, ""];
  let cut = text.lastIndexOf(" ", wide);
  if (cut < Math.floor(wide * 0.6)) cut = wide;
  const rest = text.slice(cut).trim();
  return [
    text.slice(0, cut).trim(),
    rest.length <= wide ? rest : rest.slice(0, wide - 1) + "…",
  ];
}

/** What a moment's row says: when, who it is about when that is not the person
 * whose record this is, and its own words. */
export function words(
  date: string,
  certainty: string | null,
  who: string,
  protagonist: string,
  label: string,
): string {
  const person = who && who !== protagonist ? `${who} · ` : "";
  return `${dateText(date, certainty)} · ${person}${label.trim()}`;
}

/** How big a dot is at this density (the converged mockup's four steps). */
export function dotRadius(n: number): number {
  return n <= 12 ? 4.5 : n <= 30 ? 3.5 : n <= 60 ? 2.6 : 1.8;
}

/** How faint the moments the coach did not name are. When it has named some,
 * everything else recedes; when it has named none, a short record stays solid. */
export function baseOpacity(n: number, named: number): number {
  return named ? 0.35 : n <= 24 ? 1 : 0.6;
}

export interface Row {
  id: number;
  row: number;
  left: number;
  width: number;
  align: "left" | "right";
  text: string;
  x: number;
}

/** Lay the named moments' words out in up to three rows: to the right of the
 * dot where there is room, otherwise to its left, and never over the one before.
 *
 * A moment with no room left for even one character keeps its row with empty
 * text: the leader line is drawn from the row down to the dot whatever the
 * words do, so a crowded picture still shows which dots the coach named
 * (ratified: the leader is emitted before the alignment and budget branch). */
/** Which of the named moments get words. Three or fewer all do; past that it is
 * the first, the middle and the last, so the words span the stretch rather than
 * crowding into its opening (ruled). */
export function pick<T>(sorted: T[]): T[] {
  if (sorted.length <= ROWS.length) return sorted;
  return [
    sorted[0],
    sorted[Math.floor((sorted.length - 1) / 2)],
    sorted[sorted.length - 1],
  ];
}

export function rows(
  named: { id: number; x: number; text: string }[],
  x0: number,
  x1: number,
): Row[] {
  const sorted = pick([...named].sort((a, b) => a.x - b.x));
  const out: Row[] = [];
  sorted.forEach((mark, i) => {
    const previous = i ? sorted[i - 1].x : null;
    let budget = Math.min(44, Math.floor((x1 - mark.x - 4) / CH));
    let left = mark.x + 4;
    let width = x1 - left;
    let align: "left" | "right" = "left";
    if (budget < 12) {
      const limit = previous === null ? x0 : previous + 4;
      width = mark.x - 4 - limit;
      budget = Math.min(44, Math.floor(width / CH));
      left = limit;
      align = "right";
    }
    out.push({
      id: mark.id,
      row: i,
      left,
      width: Math.max(0, width),
      align,
      text: budget < 1 ? "" : clip(mark.text, budget),
      x: mark.x,
    });
  });
  return out;
}

/** Tap zones across the wire, each at least the 44px floor. A zone holds the
 * moments under it and a tap cycles through them. */
export function zones<T extends { x: number }>(
  marks: T[],
  x0: number,
  x1: number,
): { left: number; width: number; marks: T[] }[] {
  const count = Math.max(1, Math.floor((x1 - x0) / ZONE));
  const width = (x1 - x0) / count;
  const out = Array.from({ length: count }, (_, i) => ({
    left: x0 + i * width,
    width,
    marks: [] as T[],
  }));
  for (const mark of marks) {
    const i = Math.min(count - 1, Math.max(0, Math.floor((mark.x - x0) / width)));
    out[i].marks.push(mark);
  }
  return out.filter((zone) => zone.marks.length > 0);
}

/** The next moment a tap on a zone selects: the first, then each in turn, then
 * nothing (the converged mockup's cycle). */
export function cycle<T>(inZone: T[], current: T | null): T | null {
  const at = current === null ? -1 : inZone.indexOf(current);
  return at < 0 ? (inZone[0] ?? null) : (inZone[at + 1] ?? null);
}
