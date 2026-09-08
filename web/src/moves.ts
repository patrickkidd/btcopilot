import { esc } from "./dom";

/** The ratified move language (OWNER_RULINGS 2026-09-01, batches 1-3), drawn on
 * the people the play-by-play puts on stage. One green for every move mark;
 * amber is never used here, because amber only ever means the record asking.
 *
 * All twelve relationship moves and the three variable shifts are drawn. */

export enum Move {
  Toward = "toward",
  Away = "away",
  Distance = "distance",
  Cutoff = "cutoff",
  Conflict = "conflict",
  DefinedSelf = "defined-self",
  Inside = "inside",
  Outside = "outside",
  Fusion = "fusion",
  Overfunctioning = "overfunctioning",
  Underfunctioning = "underfunctioning",
  Projection = "projection",
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

/** How far along the line between two people a move carries someone. */
function toward(from: Figure, to: Figure, distance: number): [number, number] {
  const u = unit(from, to);
  return [u.x * distance, u.y * distance];
}

/** A person: the sharp outline that never leaves them, their initial, and their
 * name under it. */
export function figure(
  person: Figure,
  classes: string,
  ghost = false,
  step: [number, number] = [0, 0],
): string {
  const initial = person.name.trim().slice(0, 1).toUpperCase() || "?";
  const moved =
    step[0] || step[1]
      ? ` transform="translate(${step[0].toFixed(1)} ${step[1].toFixed(1)})"`
      : "";
  return (
    `<g class="node ${classes}" data-person="${person.id}"${moved}>` +
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

/** Fusion, as Bowen drew it: three bands holding the pair the whole way. */
function bands(a: Figure, b: Figure): string {
  const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  const rx = Math.abs(b.x - a.x) / 2 + R + 10;
  const ry = R + 14;
  return [0, 5, 10]
    .map(
      (grow) =>
        `<ellipse class="mv-band" cx="${mid.x.toFixed(1)}" cy="${mid.y.toFixed(1)}" ` +
        `rx="${(rx + grow).toFixed(1)}" ry="${(ry + grow).toFixed(1)}"/>`,
    )
    .join("");
}

/** The app-spec flank arrow, about two thirds the size of a person: up beside
 * whoever rises, down beside whoever sinks, in lockstep. */
function flank(person: Figure, up: boolean): string {
  const x = person.x + R + 12;
  const top = person.y - 11;
  const bottom = person.y + 11;
  const head = up
    ? `M${x - 4} ${top + 5} L${x} ${top} L${x + 4} ${top + 5}`
    : `M${x - 4} ${bottom - 5} L${x} ${bottom} L${x + 4} ${bottom - 5}`;
  return `<path class="mv-flank" d="M${x} ${top} L${x} ${bottom} ${head}"/>`;
}

/** The tension in a triangle: a line from the mover to each of the others. */
function tension(from: Figure, others: Figure[]): string {
  return others
    .map(
      (other) =>
        `<path class="mv-tension" d="M${from.x.toFixed(1)} ${from.y.toFixed(1)} ` +
        `L${other.x.toFixed(1)} ${other.y.toFixed(1)}"/>`,
    )
    .join("");
}

/** Projection: the parent's agitation drains off along the arrow's own dashes
 * and settles on the child, who inherits the identical shake. */
function flow(from: Figure, to: Figure): string {
  return (
    `<path class="mv-flow" d="M${from.x.toFixed(1)} ${from.y.toFixed(1)} ` +
    `L${to.x.toFixed(1)} ${to.y.toFixed(1)}"/>`
  );
}

export interface Drawn {
  /** Extra classes for the mover's own figure. */
  actor: string;
  /** Extra classes for whoever the move reaches. */
  target: string;
  /** Extra classes for the third person in a triangle. */
  third: string;
  /** Everything drawn around and between them. */
  marks: string;
  /** How far the move actually moves someone, by person id. A move is a move:
   * the person travels, as they do in the approved play-by-play. */
  steps: Record<number, [number, number]>;
}

const NONE: Drawn = { actor: "", target: "", third: "", marks: "", steps: {} };

/** One move, in the ratified language. `third` is the other point of a
 * triangle, which inside and outside both need. */
export function draw(
  kind: string | null,
  actor: Figure,
  target: Figure | null,
  shifts: { symptom: string | null; anxiety: string | null; functioning: string | null },
  third: Figure | null = null,
): Drawn {
  if (shifts.anxiety)
    return {
      ...NONE,
      actor: "anx shake",
      marks: field(actor) + spikes(actor),
    };
  if (shifts.symptom)
    return { ...NONE, marks: cross(actor, shifts.symptom as Shift) };
  if (shifts.functioning)
    return {
      ...NONE,
      actor: shifts.functioning === Shift.Down ? "f-down" : "f-up",
      marks: ""
    };
  switch (kind) {
    case Move.Toward:
      return target
        ? {
            ...NONE,
            marks: arrow(actor, target, false),
            steps: { [actor.id]: toward(actor, target, 9) },
          }
        : NONE;
    case Move.Away:
      return target
        ? {
            ...NONE,
            marks: arrow(actor, target, true),
            steps: { [actor.id]: toward(actor, target, -11) },
          }
        : NONE;
    case Move.Distance:
      return target
        ? { ...NONE, actor: "still", marks: field(actor) + wall(actor, target, false) }
        : NONE;
    case Move.Cutoff:
      return target
        ? {
            ...NONE,
            actor: "still faded",
            target: "faded",
            marks: field(actor) + wall(actor, target, true),
          }
        : NONE;
    case Move.Conflict:
      return target
        ? { ...NONE, actor: "shake", target: "shake", marks: sparks(actor, target) }
        : NONE;
    case Move.DefinedSelf:
      return {
        ...NONE,
        actor: "self",
        marks: `<circle class="mv-clear" cx="${actor.x}" cy="${actor.y}" r="${R + 12}"/>`,
      };
    case Move.Fusion:
      // three bands hold the pair the whole way, and their fields are shared
      return target
        ? { ...NONE, actor: "fused", target: "fused", marks: bands(actor, target) }
        : NONE;
    case Move.Inside:
      // the mover closes on the one they want; the same motion pushes the old
      // insider out
      return target
        ? {
            ...NONE,
            marks: arrow(actor, target, false),
            steps: {
              [actor.id]: toward(actor, target, 14),
              ...(third ? { [third.id]: toward(target, third, 16) } : {}),
            },
          }
        : NONE;
    case Move.Outside:
      // the heat is between the mover and both of them, and it ends with the
      // walk: no tension is drawn once they have gone
      return target
        ? {
            ...NONE,
            marks:
              tension(actor, third ? [target, third] : [target]) +
              arrow(actor, target, true),
            steps: { [actor.id]: toward(actor, target, -13) },
          }
        : NONE;
    case Move.Overfunctioning:
      return target
        ? { ...NONE, actor: "f-up", marks: flank(actor, true) + flank(target, false) }
        : { ...NONE, actor: "f-up", marks: flank(actor, true) };
    case Move.Underfunctioning:
      return target
        ? { ...NONE, actor: "f-down", marks: flank(actor, false) + flank(target, true) }
        : { ...NONE, actor: "f-down", marks: flank(actor, false) };
    case Move.Projection:
      // anxiety uses one language everywhere: it drains off the parent and
      // settles on the child, who inherits the identical shake
      return target
        ? {
            ...NONE,
            actor: "anx shake",
            target: "anx shake",
            marks: spikes(actor) + flow(actor, target) + spikes(target),
          }
        : { ...NONE, actor: "anx shake", marks: field(actor) + spikes(actor) };
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
