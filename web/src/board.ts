import { esc } from "./dom";
import {
  BOARD_R,
  draw,
  figure,
  type Figure,
  type Walk,
} from "./moves";
import { dateText } from "./spotlight";
import type { Person, TimelineEvent } from "./types";

/** The moves board: Bowen's chalkboard, the third and deepest level of the one
 * picture. Numbered moves on a subset of the real diagram, stepped one at a
 * time, in the same move language the resting wire and the play-by-play use.
 *
 * The middle "cluster drilldown" level is CUT (R-0074): the board is entered
 * straight from the chat, and the words about it live in the chat. */

/** The ratified board: 264px tall, people on an ellipse around its centre. */
export const BOARD_H = 264;
const REF_W = 380;
const RING = 82;

export interface Step {
  event: TimelineEvent;
  /** Who moved, whoever the move reached, and the third point of a triangle. */
  cast: number[];
}

/** Which moments in a stretch are moves the board can draw. */
export function movesIn(events: TimelineEvent[]): Step[] {
  return events
    .filter(
      (e) =>
        !!e.relationship || !!e.symptom || !!e.anxiety || !!e.functioning,
    )
    .map((event) => ({ event, cast: castOf(event) }));
}

function castOf(event: TimelineEvent): number[] {
  const subject = event.child ?? event.person;
  const reached = [
    ...event.relationshipTargets,
    ...(event.spouse === null ? [] : [event.spouse]),
    ...event.relationshipTriangles,
  ];
  return [...new Set([...(subject === null ? [] : [subject]), ...reached])];
}

/** Everyone the whole stretch puts on the board, so the cast does not shuffle
 * between steps. */
export function castOfSteps(steps: Step[]): number[] {
  const seen: number[] = [];
  for (const step of steps)
    for (const id of step.cast) if (!seen.includes(id)) seen.push(id);
  return seen;
}

/** The ratified board layout: centre of the board, people on an ellipse of
 * x radius R*1.75 and y radius R, the first at the top. */
export function ellipse(
  people: Person[],
  width: number,
  height = BOARD_H,
): Figure[] {
  const cx = width / 2;
  const cy = height / 2;
  const rx = Math.min(cx - 44, (RING * 1.75 * width) / REF_W);
  const ry = Math.min(cy - 46, RING);
  const n = people.length;
  return people.map((p, i) => {
    const angle = -Math.PI / 2 + (i / n) * Math.PI * 2;
    return {
      id: p.id,
      name: p.name,
      gender: p.gender,
      r: BOARD_R,
      above: true,
      x: n === 1 ? cx : cx + Math.cos(angle) * rx,
      y: n === 1 ? cy : cy + Math.sin(angle) * ry,
      mirror: n > 1 && Math.cos(angle) > 0,
      stage: { w: width, h: height },
    };
  });
}

/** The pair bonds the record actually holds, drawn first and beneath
 * everything. */
export function bonds(
  figures: Figure[],
  events: TimelineEvent[],
  steps: Record<number, Walk> = {},
): string {
  const drawn = new Set<string>();
  const lines: string[] = [];
  for (const event of events) {
    if (event.spouse === null || event.person === null) continue;
    const key = [event.person, event.spouse].sort((a, b) => a - b).join("-");
    if (drawn.has(key)) continue;
    drawn.add(key);
    const a = figures.find((f) => f.id === event.person);
    const b = figures.find((f) => f.id === event.spouse);
    if (!a || !b) continue;
    // a bond holds whoever it ties, so its end travels with a person who walks
    const ends =
      end(a, steps[a.id], "1") +
      end(b, steps[b.id], "2");
    lines.push(
      `<line class="bond" x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" ` +
        `x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}">${ends}</line>`,
    );
  }
  return lines.join("");
}

function end(who: Figure, step: Walk | undefined, n: "1" | "2"): string {
  if (!step) return "";
  const offsets = step.values.split(";").map((pair) => pair.split(" ").map(Number));
  const on = (axis: 0 | 1, base: number) =>
    `<animate attributeName="${axis ? "y" : "x"}${n}" ` +
    `values="${offsets.map(([dx, dy]) => (base + (axis ? dy : dx)).toFixed(1)).join(";")}" ` +
    `keyTimes="${step.keyTimes}" dur="${step.dur}" repeatCount="indefinite" fill="freeze"/>`;
  return on(0, who.x) + on(1, who.y);
}

interface Gesture {
  marks: string;
  classes: Map<number, string>;
  ghosts: Map<number, "out" | "in" | "solo">;
  steps: Record<number, Walk>;
}

/** One step's drawing: the marks around the people and what each of them does. */
function gesture(step: Step, figures: Figure[]): Gesture {
  const at = (id: number | null | undefined) =>
    id === null || id === undefined
      ? null
      : (figures.find((f) => f.id === id) ?? null);
  const event = step.event;
  const actor = at(event.child ?? event.person);
  const out: Gesture = {
    marks: "",
    classes: new Map(),
    ghosts: new Map(),
    steps: {},
  };
  if (!actor) return out;
  const reached = event.relationshipTargets[0] ?? event.spouse ?? null;
  const third =
    event.relationshipTriangles[0] ?? event.relationshipTargets[1] ?? null;
  const drawn = draw(
    event.relationship,
    actor,
    at(reached),
    {
      symptom: event.symptom,
      anxiety: event.anxiety,
      functioning: event.functioning,
    },
    at(third),
  );
  out.marks = drawn.marks;
  out.steps = drawn.steps;
  out.classes.set(actor.id, `${drawn.actor} mover`);
  if (reached !== null && drawn.target) out.classes.set(reached, drawn.target);
  if (third !== null && drawn.third) out.classes.set(third, drawn.third);
  if (drawn.ghosts.actor) out.ghosts.set(actor.id, drawn.ghosts.actor);
  if (reached !== null && drawn.ghosts.target)
    out.ghosts.set(reached, drawn.ghosts.target);
  return out;
}

/** Earlier moves stay on the board behind the current gesture, so a stretch
 * accumulates into one picture instead of flashing past. */
function history(steps: Step[], upTo: number, figures: Figure[]): string {
  if (upTo <= 0) return "";
  const marks = steps
    .slice(0, upTo)
    .map((step) => gesture(step, figures).marks)
    .join("")
    // history is residue, not a second thing moving: what a move left behind
    // stays, and what only existed while it played does not
    .replace(/<animate[^>]*\/>/g, "");
  return marks ? `<g class="hist">${marks}</g>` : "";
}

export interface BoardView {
  svg: string;
  caption: string;
}

/** The whole board at one step. */
export function board(
  steps: Step[],
  at: number,
  people: Person[],
  events: TimelineEvent[],
  width: number,
): BoardView {
  const figures = ellipse(people, width);
  const now = steps[at];
  const g: Gesture = now
    ? gesture(now, figures)
    : { marks: "", classes: new Map(), ghosts: new Map(), steps: {} };
  const svg =
    `<svg viewBox="0 0 ${width} ${BOARD_H}" aria-hidden="true">` +
    `<defs><filter id="glow" x="-30%" y="-30%" width="160%" height="160%">` +
    `<feGaussianBlur stdDeviation="1.1"/></filter></defs>` +
    bonds(figures, events, g.steps) +
    history(steps, at, figures) +
    `<g class="cast">${g.marks}` +
    figures
      .map((f) =>
        figure(f, g.classes.get(f.id) ?? "", g.ghosts.get(f.id) ?? "", g.steps[f.id]),
      )
      .join("") +
    `</g></svg>`;
  return { svg, caption: caption(steps, at, people) };
}

/** `step/total · year — from → to · label`, as the board draws it. */
function caption(steps: Step[], at: number, people: Person[]): string {
  const step = steps[at];
  if (!step) return "";
  const name = (id: number | null) =>
    people.find((p) => p.id === id)?.name ?? "someone";
  const event = step.event;
  const when = event.dateTime
    ? dateText(event.dateTime, event.dateCertainty)
    : "no date yet";
  const from = name(event.child ?? event.person);
  const to = event.relationshipTargets
    .concat(event.spouse === null ? [] : [event.spouse])
    .map(name)
    .join(", ");
  const who = to ? `${from} → ${to}` : from;
  return `${at + 1}/${steps.length} · ${when} · ${who} · ${esc(event.label)}`;
}
