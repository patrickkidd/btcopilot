import { DateCertainty, type TimelineEvent } from "./types";

/** The drawability marks: what the picture draws beside a dot once there are
 * words on it to say what the mark means (DRAWABILITY.md rules 1-5).
 *
 * At rest only a line, dots and the amber question mark exist. Everything here
 * belongs to the level where the coach has named something and its words are
 * written beside it, which is the only place a band or a tick can be read.
 *
 * Pure, so the rules can be checked without a browser. */

/** A moment's direction, if it has one. Relationship moves are categorical and
 * carry none: they are marks, not points on a trend. */
export enum Shift {
  Up = "up",
  Down = "down",
  Same = "same",
}

/** The three variable lanes a moment can carry a direction on. */
export enum Lane {
  Symptom = "symptom",
  Anxiety = "anxiety",
  Functioning = "functioning",
}

const LANES = [Lane.Symptom, Lane.Anxiety, Lane.Functioning];

/** A moment's lane and direction. A moment carrying more than one keeps the
 * first, because one wire can only draw one trend. */
export function shiftOf(
  event: TimelineEvent,
): { lane: Lane; shift: Shift } | null {
  for (const lane of LANES) {
    const value = event[lane];
    if (value) return { lane, shift: value as Shift };
  }
  return null;
}

export interface Mark {
  event: TimelineEvent;
  x: number;
}

/** How wide a guessed date is: a year either side, which is what the record's
 * one approximate grade means (±365 days). */
export const GUESS_YEARS = 1;

/** A guessed date is a band as wide as the guess, so it is noticeable and
 * correctable and never reads as firm as a certain one (rule 2).
 *
 * A short record scales a year to most of the wire, where a band a whole year
 * wide would swallow the line rather than mark one guess on it, so the band is
 * held to an eighth of the wire however few years are on it. */
export function bands(
  marks: Mark[],
  perYear: number,
  wire: number,
  span: number,
): string {
  return marks
    .filter((m) => m.event.dateCertainty === DateCertainty.Approximate)
    .map((m) => {
      const half = Math.min(span / 8, Math.max(6, perYear * GUESS_YEARS));
      return (
        `<rect class="band" x="${(m.x - half).toFixed(1)}" y="${wire - 7}" ` +
        `width="${(half * 2).toFixed(1)}" height="14" rx="3"/>`
      );
    })
    .join("");
}

/** What a moment that lasted covers: quiet horizontal bands beneath the main
 * wire, each starting and ending where the record dates it. Added because a
 * record's relationships carry start and end dates ("The Generalization Test").
 * They stack so two overlapping spans can both be seen. */
export function spans(
  marks: Mark[],
  wire: number,
  at: (iso: string) => number,
): string {
  const ranged = marks
    .filter((m) => !!m.event.endDateTime)
    .sort((a, b) => a.x - b.x);
  const ends: number[] = [];
  return ranged
    .map((m) => {
      const right = at(m.event.endDateTime as string);
      // a row is free once nothing on it reaches this far
      let row = ends.findIndex((edge) => edge < m.x - 2);
      if (row < 0) row = ends.length;
      ends[row] = right;
      return (
        `<line class="lane" x1="${m.x.toFixed(1)}" y1="${wire + 12 + row * 6}" ` +
        `x2="${Math.max(right, m.x + 3).toFixed(1)}" y2="${wire + 12 + row * 6}"/>`
      );
    })
    .join("");
}

/** Silence is dotted and never flat: a stretch with nothing recorded must not
 * read as a stretch where nothing changed (rule 3). */
export function silence(
  marks: Mark[],
  wire: number,
  gapYears: number,
  perYear: number,
): string {
  const sorted = [...marks].sort((a, b) => a.x - b.x);
  let out = "";
  for (let i = 1; i < sorted.length; i += 1) {
    const a = sorted[i - 1].x;
    const b = sorted[i].x;
    if (b - a < gapYears * perYear) continue;
    out +=
      `<line class="gap" x1="${(a + 9).toFixed(1)}" y1="${wire}" ` +
      `x2="${(b - 9).toFixed(1)}" y2="${wire}"/>`;
  }
  return out;
}

/** What one moment is drawn as when the coach has not named it. A directed
 * moment is a point on a trend and stays a dot; a recorded no-change is a solid
 * flat mark, told apart from silence at every zoom (rule 3); a moment with no
 * direction at all is a fact stamped where it happened. */
export enum MarkKind {
  Dot = "dot",
  Flat = "flat",
  Tick = "tick",
}

export function markOf(event: TimelineEvent): MarkKind {
  const shift = shiftOf(event);
  if (!shift) return MarkKind.Tick;
  return shift.shift === Shift.Same ? MarkKind.Flat : MarkKind.Dot;
}

/** The line needs three directed points, and it spans only where they are: a
 * two-point line invents a trend and there is no extension to now or to birth
 * (rule 1). The lane with the most directed points is the one drawn, because
 * one wire can carry one trend. */
export function trend(marks: Mark[], wire: number): string {
  const line = trendPoints(marks);
  if (!line) return "";
  const at = (m: Mark) =>
    `${m.x.toFixed(1)},${(wire + (shiftOf(m.event)?.shift === Shift.Up ? -6 : 6)).toFixed(1)}`;
  return `<polyline class="step" points="${line.points.map(at).join(" ")}"/>`;
}

/** The directed points a trend would be drawn through, and the lane they are
 * on. Null below the three-point floor. */
export function trendPoints(marks: Mark[]): { lane: Lane; points: Mark[] } | null {
  let best: { lane: Lane; points: Mark[] } | null = null;
  for (const lane of LANES) {
    const points = marks
      .filter((m) => {
        const shift = shiftOf(m.event);
        return (
          shift?.lane === lane &&
          (shift.shift === Shift.Up || shift.shift === Shift.Down)
        );
      })
      .sort((a, b) => a.x - b.x);
    if (points.length >= 3 && (!best || points.length > best.points.length))
      best = { lane, points };
  }
  return best;
}

/** An open-ended state fades after its last confirmation rather than stopping
 * dead, because the record does not know it ended (rule 5). It is drawn for the
 * trend's own lane, whose last point is the last confirmation on it. */
export function fade(marks: Mark[], wire: number, x1: number): string {
  const line = trendPoints(marks);
  if (!line) return "";
  const last = line.points[line.points.length - 1];
  if (last.event.endDateTime) return "";
  if (x1 - last.x < 12) return "";
  const shift = shiftOf(last.event)?.shift;
  const y = wire + (shift === Shift.Up ? -6 : 6);
  return (
    `<defs><linearGradient id="openfade" x1="0" x2="1">` +
    `<stop offset="0" stop-color="var(--data)" stop-opacity=".5"/>` +
    `<stop offset="1" stop-color="var(--data)" stop-opacity="0"/>` +
    `</linearGradient></defs>` +
    `<line class="fade" x1="${last.x.toFixed(1)}" y1="${y}" ` +
    `x2="${x1.toFixed(1)}" y2="${y}"/>`
  );
}

/** Order is shown only when the two guess ranges do not touch; where they
 * overlap the record asks instead, which is the one amber treatment (rule 4).
 * Where they do not touch, the dots' own places on the line say which came
 * first and nothing is asked. */
export function rangesTouch(
  a: { date: string; certainty: string | null },
  b: { date: string; certainty: string | null },
): boolean {
  const span = (one: { date: string; certainty: string | null }) => {
    const at = Number(one.date.slice(0, 4)) + Number(one.date.slice(5, 7)) / 12;
    const half =
      one.certainty === DateCertainty.Approximate ? GUESS_YEARS : 1 / 12;
    return [at - half, at + half];
  };
  const [aMin, aMax] = span(a);
  const [bMin, bMax] = span(b);
  return aMin <= bMax && bMin <= aMax;
}
