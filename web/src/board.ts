import { esc } from "./dom";
import {
  BOARD_R,
  draw,
  figure,
  zigzag,
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

/** The ratified board drawing was 264px tall in a box proportioned for it. The
 * board now fits its content (owner review round 1, 2026-09-08), so this is the
 * most it may take rather than the height it always is. */
export const BOARD_H = 264;
/** The time axis under the people: the line, its ticks and its year labels. */
const AXIS_H = 40;
/** Room over a figure for the name written above it, and under it for the
 * figure alone. */
const ABOVE = BOARD_R + 22;
const BELOW = BOARD_R + 10;

export interface Step {
  event: TimelineEvent;
  /** Who moved, whoever the move reached, and the third point of a triangle. */
  cast: number[];
}

/** Which moments in a cluster are moves the board can draw. */
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

/** Everyone the whole cluster puts on the board, so the cast does not shuffle
 * between steps. */
export function castOfSteps(steps: Step[]): number[] {
  const seen: number[] = [];
  for (const step of steps)
    for (const id of step.cast) if (!seen.includes(id)) seen.push(id);
  return seen;
}

export interface Layout {
  figures: Figure[];
  /** What the drawing actually needs, which is what the board is given. */
  height: number;
}

/** The ratified board layout: people on an ellipse of x radius R*1.75 and
 * y radius R, the first at the top.
 *
 * The board leaves no space it is not using. The ellipse keeps its ratified
 * proportion and the frame limits it across; the height then follows from who
 * is standing on it, because with three people nobody stands at the bottom and
 * a fixed height would leave a band of nothing under them. Above, a figure
 * needs room for the name written over it; below, the figure alone. */
export function ellipse(people: Person[], width: number): Layout {
  const cx = width / 2;
  const n = people.length;
  const angleAt = (i: number) => -Math.PI / 2 + (i / n) * Math.PI * 2;
  const sines = people.map((_, i) => Math.sin(angleAt(i)));
  const rx = Math.max(60, Math.min(cx - 44, ((BOARD_H - ABOVE - BELOW) / 2) * 1.75));
  const ry = Math.min(110, Math.max(44, rx / 1.75));
  const top = n === 1 ? 0 : -Math.min(...sines, 0);
  const lowest = n === 1 ? 0 : Math.max(...sines, 0);
  const cy = ABOVE + ry * top;
  const height = Math.round(cy + ry * lowest + BELOW);
  return {
    height,
    figures: people.map((p, i) => {
      const angle = angleAt(i);
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
    }),
  };
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
  /** Where a mover has to stand for its whole walk to fit on the board. */
  place: Record<number, [number, number]>;
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
    place: {},
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
  out.place = drawn.place;
  out.classes.set(actor.id, `${drawn.actor} mover`);
  if (reached !== null && drawn.target) out.classes.set(reached, drawn.target);
  if (third !== null && drawn.third) out.classes.set(third, drawn.third);
  if (drawn.ghosts.actor) out.ghosts.set(actor.id, drawn.ghosts.actor);
  if (reached !== null && drawn.ghosts.target)
    out.ghosts.set(reached, drawn.ghosts.target);
  return out;
}

/** Earlier moves stay on the board behind the current gesture, so a cluster
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
  /** What the board takes, so the region above the chat is fitted to it. */
  height: number;
}

/** The board holding a closed triangle: the three the coach named, with the
 * heat drawn on all three sides. No mockup fixes this geometry; it uses the
 * ratified tension zigzag rather than inventing a mark. */
export function triangle(people: Person[], width: number): BoardView {
  const { figures, height } = ellipse(people, width);
  const heat = figures
    .map((f, i) => zigzag(f, figures[(i + 1) % figures.length]))
    .join("");
  return {
    svg:
      `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">` +
      `<g class="cast">${heat}` +
      figures.map((f) => figure(f, "")).join("") +
      `</g></svg>`,
    caption: people.map((p) => p.name).join(" · "),
    height,
  };
}

const YEAR_MS = 365.25 * 24 * 3600 * 1000;
const yearOf = (iso: string) => new Date(iso + "T00:00:00Z").getTime() / YEAR_MS;
/** The axis pads as pane A pads its own: wider on the left, where the first
 * year label is written. */
const AXIS_L = 30;
const AXIS_R = 16;

/** How near a decade label may come to the date under the selected dot before
 * the decade one is dropped: the two are the same size on the same line. */
const LABEL_GAP = 44;

/** The years under the people: the axis pane A puts on stage with them, its
 * decade ticks, one dot per move, a blob wherever moves bunch up, and the move
 * being drawn on top with its own date under it. */
function axis(steps: Step[], at: number, width: number, top: number): string {
  const dated = steps
    .map((step, i) => ({ i, iso: step.event.dateTime }))
    .filter((s): s is { i: number; iso: string } => !!s.iso);
  if (!dated.length) return "";
  const years = dated.map((s) => yearOf(s.iso));
  const first = Math.min(...years);
  const last = Math.max(...years);
  const span = Math.max(1, last - first);
  const x0 = AXIS_L;
  const x1 = width - AXIS_R;
  const y = top + 18;
  const at_ = (iso: string) =>
    x0 + ((yearOf(iso) - first) / span) * (x1 - x0);

  const now = dated.find((s) => s.i === at);
  const nowX = now ? at_(now.iso) : null;

  let out = `<line class="ax" x1="${x0}" y1="${y}" x2="${x1}" y2="${y}"/>`;
  // decade ticks, as pane A rules its axis by decades
  const decade = Math.ceil((first + 1970) / 10) * 10;
  for (let year = decade; ; year += 10) {
    const x = x0 + ((year - 1970 - first) / span) * (x1 - x0);
    if (x > x1) break;
    if (x < x0) continue;
    // the date under the selected dot is the one that must be readable, so a
    // decade label close enough to run into it keeps its tick and loses its year
    const crowded = nowX !== null && Math.abs(x - nowX) < LABEL_GAP;
    out +=
      `<line class="ax-tick" x1="${x.toFixed(1)}" y1="${y - 4}" ` +
      `x2="${x.toFixed(1)}" y2="${y + 4}"/>` +
      (crowded
        ? ""
        : `<text class="ax-yr" x="${x.toFixed(1)}" y="${y + 18}" ` +
          `text-anchor="middle">${year}</text>`);
  }

  // where moves bunch up, a blob says so before anything is opened
  const blobs = new Map<number, number>();
  for (const s of dated) {
    const key = Math.round(at_(s.iso) / 18);
    blobs.set(key, (blobs.get(key) ?? 0) + 1);
  }
  for (const [key, count] of blobs) {
    if (count < 2) continue;
    const rx = 6 + count;
    out +=
      `<ellipse class="ax-blob" cx="${(key * 18).toFixed(1)}" cy="${y}" ` +
      `rx="${rx}" ry="${(rx * 0.68).toFixed(1)}"/>`;
  }

  // a move's dot fills in as it is played, so the axis carries how far along
  // the cluster the board is
  for (const s of dated) {
    const played = s.i <= at;
    out +=
      `<circle class="ax-dot${played ? " played" : ""}" ` +
      `cx="${at_(s.iso).toFixed(1)}" cy="${y}" r="${played ? 4.6 : 3.4}"/>`;
  }

  // The move being drawn is the last thing on the axis, so it is on top of the
  // dots beside it however close they are. Nothing is drawn behind it: a shape
  // wide enough to sit under three dots cannot say which of the three it means.
  if (now !== undefined && nowX !== null) {
    const when = dateText(now.iso, steps[at].event.dateCertainty);
    out +=
      `<circle class="ax-now" cx="${nowX.toFixed(1)}" cy="${y}" r="7"/>` +
      // the date is written once, here, under the dot it belongs to
      `<text class="ax-yr on" x="${nowX.toFixed(1)}" y="${y + 18}" ` +
      `text-anchor="middle">${esc(when)}</text>`;
  }
  return `<g class="axis">${out}</g>`;
}

/** The whole board at one step. */
export function board(
  steps: Step[],
  at: number,
  people: Person[],
  events: TimelineEvent[],
  width: number,
): BoardView {
  const { figures: laid, height: stage } = ellipse(people, width);
  const dated = steps.some((step) => !!step.event.dateTime);
  const height = dated ? stage + AXIS_H : stage;
  const now = steps[at];
  const g: Gesture = now
    ? gesture(now, laid)
    : {
        marks: "",
        classes: new Map(),
        ghosts: new Map(),
        steps: {},
        place: {},
      };
  // a mover whose walk would not fit stands further in, and everything that
  // points at them is drawn from where they now stand
  const figures = laid.map((f) => {
    const shift = g.place[f.id];
    return shift ? { ...f, x: f.x + shift[0], y: f.y + shift[1] } : f;
  });
  const svg =
    `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">` +
    `<defs><filter id="glow" x="-30%" y="-30%" width="160%" height="160%">` +
    `<feGaussianBlur stdDeviation="1.1"/></filter></defs>` +
    bonds(figures, events, g.steps) +
    history(steps, at, laid) +
    `<g class="cast">${g.marks}` +
    figures
      .map((f) =>
        figure(f, g.classes.get(f.id) ?? "", g.ghosts.get(f.id) ?? "", g.steps[f.id]),
      )
      .join("") +
    `</g>` +
    (dated ? axis(steps, at, width, stage) : "") +
    `</svg>`;
  return { svg, caption: caption(steps, at, people), height };
}

/** Who the move is about and what they said happened, in their own words.
 *
 * No count and no clinical term: the reader is told a person and a thing that
 * happened, never "15/17" or "symptom down". The date is written once, under
 * the dot on the years line. */
function caption(steps: Step[], at: number, people: Person[]): string {
  const step = steps[at];
  if (!step) return "";
  const event = step.event;
  const who =
    people.find((p) => p.id === (event.child ?? event.person))?.name ??
    event.person_name;
  // the description is the person's own words; the label is the record talking
  // about itself, so it is only the fallback
  const words = event.description?.trim() || event.label;
  return who ? `${who} · ${words}` : words;
}
