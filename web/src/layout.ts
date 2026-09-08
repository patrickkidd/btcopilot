/** How the resting strip decides what to draw. Pure so the sparse and dense
 * cases can be checked without a browser: one dot per dated event until dots
 * would touch, then a run of them merges into one count mark that says its own
 * words on tap (DRAWABILITY, at-rest vocabulary = line, dots, question mark;
 * within-lane density merges to worded count chips at scale). */

export const MIN_GAP = 11;
/** A count mark that stretches across the picture says nothing about when its
 * moments happened, so a run breaks once it is this wide and the dense stretch
 * becomes several counts along the line instead of one. */
export const MAX_RUN = 56;
/** A record whose events all fall on one day still needs a line to sit on. */
export const MIN_SPAN_YEARS = 1;
const EDGE = 0.06;

export enum MarkKind {
  Dot = "dot",
  Count = "count",
}

export interface Mark {
  id: number;
  x: number;
}

export type Slot =
  | { kind: MarkKind.Dot; x: number; ids: number[] }
  | { kind: MarkKind.Count; x: number; ids: number[]; from: number; to: number };

/** Pad the ends so a single stretch never runs edge to edge and read as a
 * shape rather than a span of time. */
export function span(
  values: number[],
  minSpan = MIN_SPAN_YEARS,
): { min: number; max: number } {
  if (!values.length) return { min: 0, max: minSpan };
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (max - min < minSpan) {
    const mid = (min + max) / 2;
    min = mid - minSpan / 2;
    max = mid + minSpan / 2;
  }
  const pad = (max - min) * EDGE;
  return { min: min - pad, max: max + pad };
}

/** Marks close enough to overlap become one count mark. A run of one stays a
 * dot: merging a lone event would hide it behind a number. */
export function merge(
  marks: Mark[],
  minGap = MIN_GAP,
  maxRun = MAX_RUN,
): Slot[] {
  const sorted = [...marks].sort((a, b) => a.x - b.x);
  const runs: Mark[][] = [];
  for (const mark of sorted) {
    const run = runs.at(-1);
    const near = run && mark.x - (run.at(-1) as Mark).x < minGap;
    const room = run && mark.x - run[0].x <= maxRun;
    if (near && room) run.push(mark);
    else runs.push([mark]);
  }
  return runs.map((run) =>
    run.length === 1
      ? { kind: MarkKind.Dot as const, x: run[0].x, ids: [run[0].id] }
      : {
          kind: MarkKind.Count as const,
          x: (run[0].x + (run.at(-1) as Mark).x) / 2,
          ids: run.map((m) => m.id),
          from: run[0].x,
          to: (run.at(-1) as Mark).x,
        },
  );
}

export function countWords(n: number, first: string, last: string): string {
  const when = first === last ? first : `${first}–${last}`;
  return `${n} moments, ${when}`;
}
