import { esc } from "./dom";

/** The ratified move language (OWNER_RULINGS 2026-09-01, batches 1-3), drawn on
 * the people the play-by-play puts on stage. One green for every move mark;
 * amber is never used here, because amber only ever means the record asking.
 *
 * Built: toward, away, distance, cutoff, conflict, anxiety, symptom,
 * functioning up and down, defined self.
 * Not built yet: inside, outside, fusion, overfunctioning, underfunctioning —
 * they draw the person with no move rather than the wrong one. */

export enum Move {
  Toward = "toward",
  Away = "away",
  Distance = "distance",
  Cutoff = "cutoff",
  Conflict = "conflict",
  DefinedSelf = "defined-self",
}

export enum Shift {
  Up = "up",
  Down = "down",
  Same = "same",
}

export interface Figure {
  id: number;
  name: string;
  x: number;
  y: number;
}

export const R = 17;

const unit = (a: Figure, b: Figure) => {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy) || 1;
  return { x: dx / length, y: dy / length, length };
};

/** A person: the sharp outline that never leaves them, their initial, and their
 * name under it. */
export function figure(
  person: Figure,
  classes: string,
  ghost = false,
): string {
  const initial = person.name.trim().slice(0, 1).toUpperCase() || "?";
  return (
    `<g class="node ${classes}" data-person="${person.id}">` +
    (ghost
      ? `<circle class="ghost" cx="${person.x}" cy="${person.y}" r="${R}"/>`
      : "") +
    `<circle class="disc" cx="${person.x}" cy="${person.y}" r="${R}"/>` +
    `<text class="ini" x="${person.x}" y="${person.y + 4}" text-anchor="middle">${esc(initial)}</text>` +
    // clear of the outermost field ring, so a name is never drawn through one
    `<text class="nm" x="${person.x}" y="${person.y + R + 32}" text-anchor="middle">${esc(person.name)}</text>` +
    `</g>`
  );
}

/** The concentric rings that are a person's emotional field. */
export function field(person: Figure, rings = 2): string {
  return Array.from({ length: rings }, (_, i) =>
    `<circle class="fld" cx="${person.x}" cy="${person.y}" r="${R + 8 + i * 8}"/>`,
  ).join("");
}

/** An arrow whose tail travels with the mover: toward closes the gap, away
 * leads the way out. */
function arrow(from: Figure, to: Figure, away: boolean): string {
  const u = unit(from, to);
  const sign = away ? -1 : 1;
  const start = {
    x: from.x + sign * u.x * (R + 4),
    y: from.y + sign * u.y * (R + 4),
  };
  const end = away
    ? { x: from.x - u.x * (R + 46), y: from.y - u.y * (R + 46) }
    : { x: from.x + u.x * (u.length - R - 7), y: from.y + u.y * (u.length - R - 7) };
  return (
    `<path class="mv-arrow" marker-end="url(#tip)" ` +
    `d="M${start.x.toFixed(1)} ${start.y.toFixed(1)} L${end.x.toFixed(1)} ${end.y.toFixed(1)}"/>`
  );
}

/** Withdrawal: a wall between the two, the mover's field wrapping its ends but
 * never entering its shadow, and a dashed trace saying whose wall it is. */
function wall(from: Figure, to: Figure, struck: boolean): string {
  const u = unit(from, to);
  const mid = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 };
  const half = 26;
  const a = { x: mid.x - u.y * half, y: mid.y + u.x * half };
  const b = { x: mid.x + u.y * half, y: mid.y - u.x * half };
  const strike = struck
    ? `<path class="mv-strike" d="M${from.x} ${from.y} L${to.x} ${to.y}"/>`
    : "";
  return (
    `<path class="mv-trace" d="M${from.x} ${from.y} L${mid.x.toFixed(1)} ${mid.y.toFixed(1)}"/>` +
    strike +
    `<path class="mv-wall" d="M${a.x.toFixed(1)} ${a.y.toFixed(1)} L${b.x.toFixed(1)} ${b.y.toFixed(1)}"/>`
  );
}

/** Anxiety, in the one language it uses everywhere: a blurred shaking double
 * riding the sharp self, with spike static around it. */
function spikes(person: Figure): string {
  const n = 10;
  return Array.from({ length: n }, (_, i) => {
    const angle = (i / n) * Math.PI * 2;
    const from = { x: person.x + Math.cos(angle) * (R + 3), y: person.y + Math.sin(angle) * (R + 3) };
    const to = { x: person.x + Math.cos(angle) * (R + 10), y: person.y + Math.sin(angle) * (R + 10) };
    return `<path class="mv-spike" d="M${from.x.toFixed(1)} ${from.y.toFixed(1)} L${to.x.toFixed(1)} ${to.y.toFixed(1)}"/>`;
  }).join("");
}

/** The symptom cross, obviously worsening or improving. */
function cross(person: Figure, direction: Shift): string {
  const x = person.x + 15;
  const y = person.y - 15;
  const glyph =
    direction === Shift.Down
      ? `<path class="mv-dir" d="M${x + 11} ${y - 5} L${x + 11} ${y + 5} M${x + 8} ${y + 2} L${x + 11} ${y + 5} L${x + 14} ${y + 2}"/>`
      : direction === Shift.Up
        ? `<path class="mv-dir" d="M${x + 11} ${y + 5} L${x + 11} ${y - 5} M${x + 8} ${y - 2} L${x + 11} ${y - 5} L${x + 14} ${y - 2}"/>`
        : "";
  return (
    `<g class="mv-sym">` +
    `<circle class="sym-bg" cx="${x}" cy="${y}" r="9"/>` +
    `<path class="sym-x" d="M${x - 4} ${y} L${x + 4} ${y} M${x} ${y - 4} L${x} ${y + 4}"/>` +
    glyph +
    `</g>`
  );
}

export interface Drawn {
  /** Extra classes for the mover's own figure. */
  actor: string;
  /** Extra classes for whoever the move reaches. */
  target: string;
  /** Everything drawn around and between them. */
  marks: string;
}

const NONE: Drawn = { actor: "", target: "", marks: "" };

/** One move, in the ratified language. */
export function draw(
  kind: string | null,
  actor: Figure,
  target: Figure | null,
  shifts: { symptom: string | null; anxiety: string | null; functioning: string | null },
): Drawn {
  if (shifts.anxiety)
    return { actor: "anx shake", target: "", marks: field(actor) + spikes(actor) };
  if (shifts.symptom)
    return { actor: "", target: "", marks: cross(actor, shifts.symptom as Shift) };
  if (shifts.functioning)
    return {
      actor: shifts.functioning === Shift.Down ? "f-down" : "f-up",
      target: "",
      marks: "",
    };
  switch (kind) {
    case Move.Toward:
      return target
        ? { actor: "step-to", target: "", marks: arrow(actor, target, false) }
        : NONE;
    case Move.Away:
      return target
        ? { actor: "step-off", target: "", marks: arrow(actor, target, true) }
        : NONE;
    case Move.Distance:
      return target
        ? { actor: "still", target: "", marks: field(actor) + wall(actor, target, false) }
        : NONE;
    case Move.Cutoff:
      return target
        ? {
            actor: "still faded",
            target: "faded",
            marks: field(actor) + wall(actor, target, true),
          }
        : NONE;
    case Move.Conflict:
      return target
        ? { actor: "shake", target: "shake", marks: sparks(actor, target) }
        : NONE;
    case Move.DefinedSelf:
      return { actor: "self", target: "", marks: `<circle class="mv-clear" cx="${actor.x}" cy="${actor.y}" r="${R + 12}"/>` };
    default:
      return NONE;
  }
}

/** Conflict: both vibrate and sparks fly between them. */
function sparks(a: Figure, b: Figure): string {
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  return Array.from({ length: 4 }, (_, i) => {
    const off = (i - 1.5) * 9;
    return (
      `<path class="mv-spark" d="M${(mid.x + off).toFixed(1)} ${mid.y - 9} ` +
      `L${(mid.x + off + 4).toFixed(1)} ${mid.y} L${(mid.x + off - 2).toFixed(1)} ${mid.y + 9}"/>`
    );
  }).join("");
}

/** Where the people stand while a move plays: a ring, which is the simple
 * circular layout the 2026-09-02 ruling asked to keep for now. */
export function ring(
  people: { id: number; name: string }[],
  width: number,
  cy: number,
): Figure[] {
  const radius = Math.min(78, Math.max(46, width / 2 - 74));
  if (people.length === 1) return [{ ...people[0], x: width / 2, y: cy }];
  if (people.length === 2)
    return people.map((p, i) => ({
      ...p,
      x: width / 2 + (i === 0 ? -radius : radius),
      y: cy,
    }));
  return people.map((p, i) => {
    const angle = -Math.PI / 2 + (i / people.length) * Math.PI * 2;
    return {
      ...p,
      x: width / 2 + Math.cos(angle) * radius,
      y: cy + Math.sin(angle) * radius * 0.62,
    };
  });
}
