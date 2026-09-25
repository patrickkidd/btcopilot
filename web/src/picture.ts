import {
  board,
  castOfSteps,
  movesIn,
  triangle,
  type Step,
} from "./board";
import { esc } from "./dom";
// The drawability marks belong to the level with room to read them, which is
// the board; this line draws dots, the wire and the record's own question.
import { rangesTouch } from "./marks";
import {
  CH,
  PIC_H,
  ROWS,
  ROW_H,
  WIRE,
  X_PAD,
  YEAR_TOP,
  ZONE,
  baseOpacity,
  clip,
  cycle,
  dateText,
  sharedYears,
  dotRadius,
  rows,
  words,
  wrap2,
  zones,
} from "./spotlight";
import {
  DateCertainty,
  ItemKind,
  Spotlight,
  ViewKind,
  type Cluster,
  type Person,
  type Question,
  type Timeline,
  type TimelineEvent,
  type View,
} from "./types";

const YEAR_W = 60;
/** Patrick, 2026-09-21: the undated shelf's "?" stays off until it explains itself. */
const HIDE_SHELF_MARK = true;
/** The year sits centred under its dot, but never past the edges of what is on
 * screen: a dot at either end keeps its year inside the picture. */
const yearLeft = (x: number, from: number, to: number): string =>
  Math.max(from, Math.min(to - YEAR_W, x - YEAR_W / 2)).toFixed(1);

/** The ratified hold: 1000ms after each move before the prose continues. */
const HOLD_MS = 1000;
const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** The pinned picture: the sentence spotlight the owner converged on
 * (OWNER_RULINGS 2026-09-02). A wire with a dot per moment; the moments the
 * coach's latest message names are drawn bright with their words above them,
 * tied to their dots, and everything else recedes to a dim dot. A tap on the
 * wire steps through the moments under the thumb and that moment writes itself
 * out in full. The people appear only while a play-by-play walks the moves. */

/** The resting level: the whole line, one box per cluster (converged mockup,
 * crowded-cluster/timeline-converged.html renderRest).
 *
 * Its drawing is 78 tall, but the region it draws into is not. The picture
 * region is ONE height for both the resting wire and the open cluster, because
 * a tap on the picture must never move a bubble; only entering the moves board,
 * which is a screen of its own, may change the layout. So the resting drawing
 * is top-aligned inside the cluster's box and the rest of that box is empty. */
/** The resting band is the same 60 as the open one: one box per cluster on a
 * wire through the middle, and the years each box covers written inside it
 * (picked phone mockup, 2026-09-08). */
/** The least space left between two cluster boxes that would otherwise touch. */
const BOX_GAP = 6;
/** How far a box reaches past the moments it holds, at each end. */
const BOX_PAD = 10;
/** IBM Plex Mono's advance at the 10.5px the years inside a box are written. */
const YEAR_CH = 6.3;
/** The resting line is never drawn wider than this many screens: past it the
 * scale coarsens rather than the line reaching further (R-0381). */
const REACH = 2;

const REST_WIRE = 30;
/** A dot on the resting line. */
const DOT_R = 4.5;
/** The least space between two dot centres inside a box for the two to read as
 * two rather than as one solid bar. */
const DOT_GAP = 11;
/** A cluster of more than this many moments collapses to a ring and a count. */
const DENSE = 8;
/** A gap of this many years or more between clusters earns the amber question. */
const GAP_YEARS = 4;

/** A cluster's years at a glance, two digits each, as the converged mockup
 * writes them: "93–97". One year when it starts and ends in the same one. */
function shortYears(start: string, end: string): string {
  const a = start.slice(2, 4);
  const b = end.slice(2, 4);
  return a === b ? a : `${a}\u2013${b}`;
}

/** How wide the resting line is drawn, for a picture this many pixels wide.
 *
 * Wide enough that no two cluster boxes run into each other and every box keeps
 * room for the years written in it, and never more than two screens: on a
 * record too crowded for that the scale coarsens rather than the line reaching
 * further, so the whole history is always one or two swipes (R-0381). The
 * clusters come in time order; the dates are every dated moment, in order. */
export function restWidth(
  clusters: { start: string; end: string; count?: number }[],
  dates: string[],
  screen: number,
): number {
  if (dates.length < 2) return screen;
  const span = years(dates[dates.length - 1]) - years(dates[0]);
  if (span <= 0) return screen;
  let scale = (screen - 2 * X_PAD) / span;
  clusters.forEach((cluster, i) => {
    const dots = cluster.count && cluster.count <= DENSE ? cluster.count : 0;
    const room =
      Math.max(
        shortYears(cluster.start, cluster.end).length * YEAR_CH + 8,
        dots ? (dots - 1) * DOT_GAP + 2 * DOT_R : 0,
      ) -
      2 * BOX_PAD;
    const held = years(cluster.end) - years(cluster.start);
    if (held > 0 && room > 0) scale = Math.max(scale, room / held);
    // two clusters that already touch in time can never be pulled apart, and
    // the boxes give way to each other instead
    const apart = i ? years(cluster.start) - years(clusters[i - 1].end) : 0;
    if (apart > 0) scale = Math.max(scale, (2 * BOX_PAD + BOX_GAP) / apart);
  });
  return Math.round(Math.min(REACH * screen, 2 * X_PAD + scale * span));
}

/** Where a cluster's dots are drawn inside its box: where they fall in time,
 * unless that draws them over each other — a cluster held inside a few weeks
 * would be one solid bar — in which case they are spread evenly across the box
 * in the same order, and never outside it. */
export function dotXs(xs: number[], left: number, boxWidth: number): number[] {
  if (xs.every((x, i) => !i || x - xs[i - 1] >= DOT_GAP)) return xs;
  const from = left + DOT_R;
  const to = left + boxWidth - DOT_R;
  if (xs.length < 2) return [(from + to) / 2];
  return xs.map((_, i) => from + ((to - from) * i) / (xs.length - 1));
}

/** The second line of a label in the two-moments drawing: one row below the
 * first, since the shared rows stop at two and the drawing needs three. */
const PAIR_TWO = ROWS[1] + ROW_H;

/** Two moments side by side with the record's one asking mark between them.
 * No axis: a comparison is not a measurement. */
export function pairSvg(
  a: TimelineEvent,
  b: TimelineEvent,
  width: number,
): string {
  const mid = width / 2;
  const column = (event: TimelineEvent, left: number): string => {
    const wide = Math.floor((mid - X_PAD - 22) / CH);
    const [one, two] = wrap2(event.label, wide);
    const when = event.dateTime
      ? dateText(event.dateTime, event.dateCertainty)
      : "no date yet";
    return (
      `<text class="ss-w meta" x="${left}" y="${ROWS[0]}">${esc(when)}</text>` +
      `<text class="ss-w" x="${left}" y="${ROWS[1] + 6}">${esc(one)}</text>` +
      (two ? `<text class="ss-w" x="${left}" y="${PAIR_TWO + 6}">${esc(two)}</text>` : "")
    );
  };
  return (
    `<div class="ss">` +
    `<svg viewBox="0 0 ${width} ${PIC_H}" aria-hidden="true">` +
    column(a, X_PAD) +
    column(b, mid + 11) +
    `<line class="seam" x1="${mid}" y1="${ROWS[0] - 12}" x2="${mid}" y2="${PAIR_TWO + 12}"/>` +
    `<text class="qm" x="${mid}" y="${ROWS[1] + 6}" text-anchor="middle">?</text>` +
    `</svg></div>`
  );
}

/** The picture's levels. The middle "cluster drilldown" is CUT (R-0074): the
 * resting wire and the moves board are the two that survive. */
export enum Level {
  /** Nothing named yet: the whole line at a glance, one box per cluster. */
  Rest = "rest",
  Wire = "wire",
  Board = "board",
  /** What the open cluster is: the coach's reason, its span, its moments. A
   * level of its own behind the small i beside the title (owner, 2026-09-09). */
  About = "about",
  /** Two moments face to face, which is how the record asks a question about
   * a pair. No mockup fixes this drawing; it is built from the approved
   * "Pairs, face to face" concept and the at-rest vocabulary. */
  Compare = "compare",
}

/** A label the thumb can land on: which moment it names, which of the three
 * rows it is written on, and where it sits across the picture. */
interface LabelRow {
  id: number;
  row: number;
  left: number;
  width: number;
}

/** How far beside a label's words still counts as the label. */
const LABEL_SLOP = 6;
/** How far above and below its own line a row of words still answers. */
const ROW_SLOP = 3;

export enum Target {
  Zone = "zone",
  /** A cluster box on the resting level. */
  Cluster = "cluster",
  Band = "band",
  Question = "question",
  Shelf = "shelf",
  /** The board's own controls, which the picture answers itself. */
  /** Anywhere on the picture that is not a moment, a label or a control. */
  Ground = "ground",
  Prev = "prev",
  Next = "next",
  /** Ask the coach to talk through the cluster the board is showing. */
  Explain = "explain",
}

const OWN = new Set<string>([Target.Prev, Target.Next]);

/** One invisible tap target along the line. */
export interface Layer {
  target: Target;
  index: number;
  left: number;
  width: number;
  label: string;
}

/** The resting line's tap targets in the order they are laid, the last on
 * top: the cluster boxes, then the loose events' dots, so a loose event dated
 * inside a cluster's years is reached by a tap on its dot and the box by a tap
 * anywhere else on it. */
export const restLayers = (boxes: Layer[], dots: Layer[]): Layer[] => [...boxes, ...dots];

/** A target as the button the thumb lands on, ZONE tall on the wire. */
const hitButton = (layer: Layer, wire: number): string =>
  `<button class="ss-hit" data-target="${layer.target}" data-index="${layer.index}" ` +
  `aria-label="${esc(layer.label)}" ` +
  `style="left:${layer.left.toFixed(1)}px;top:${wire - ZONE / 2}px;` +
  `width:${layer.width.toFixed(1)}px;height:${ZONE}px"></button>`;

/** The loose events' targets: one per dot, or per dots drawn over one another. */
export const dotLayers = (zoned: { left: number; width: number; marks: Mark[] }[]): Layer[] =>
  zoned.map((zone, index) => ({
    target: Target.Zone,
    index,
    left: zone.left,
    width: zone.width,
    label: zone.marks[0].event.label,
  }));

/** How long one level takes to slide over the one it came from. */
const SLIDE_MS = 320;

/** How deep each level sits. Drilling in slides the arriving view over the one
 * it came from; coming back slides the current one off it. Two moments face to
 * face is a level of the same depth as an open cluster: the coach puts it up
 * in place of one. */
const DEPTH: Record<Level, number> = {
  [Level.Rest]: 0,
  [Level.Wire]: 1,
  [Level.Compare]: 1,
  [Level.Board]: 2,
  [Level.About]: 2,
};

const still = (): boolean =>
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/** Where the resting line sits once it has been drawn again. */
enum Park {
  /** The present at the right end: at load, and when the record changes. */
  Present = "present",
  /** Where the reader left it. */
  Held = "held",
  /** On the moment the coach's words, or a chip in them, just named. */
  Named = "named",
}

const SCROLLER = ".ss-scroll";

/** A still picture of the region as it is now, laid over it: the live rows
 * are cloned without their ids so nothing on the page can find the copies.
 * How far the line was scrolled is carried across, because a clone starts at
 * the left end and the copy has to stand where the reader left it. */
function snapshot(region: HTMLElement, ...skip: Element[]): HTMLElement {
  const lay = document.createElement("div");
  lay.className = "slide-lay";
  for (const child of [...region.children]) {
    if (skip.includes(child) || child.classList.contains("slide-lay")) continue;
    const copy = child.cloneNode(true) as HTMLElement;
    for (const el of [copy, ...copy.querySelectorAll("[id]")]) el.removeAttribute("id");
    const live = [...child.querySelectorAll<HTMLElement>(SCROLLER)];
    copy.querySelectorAll<HTMLElement>(SCROLLER).forEach((el, i) => {
      el.dataset.left = String(live[i]?.scrollLeft ?? 0);
    });
    lay.append(copy);
  }
  return lay;
}

/** Stand a snapshot's lines where the live ones were, once it is on the page. */
function keepScroll(lay: HTMLElement): void {
  for (const el of lay.querySelectorAll<HTMLElement>(SCROLLER))
    el.scrollLeft = Number(el.dataset.left ?? 0);
}

export interface Tap {
  target: Target;
  /** For a zone, which one. */
  index: number;
  /** Where the thumb landed on the picture. */
  x: number;
  y: number;
}

export interface PictureHandlers {
  onTap(tap: Tap): void;
  /** Whether the board may ask the coach to talk the cluster through. A coding
   * has no coach turn, so its board carries only the two step arrows. */
  canExplain?: boolean;
}

const YEAR = 365.25 * 24 * 3600 * 1000;

export function years(iso: string): number {
  return new Date(iso + "T00:00:00Z").getTime() / YEAR;
}

/** The calendar year a point on the line falls in. years() counts from 1970,
 * so the way back to a year is through the date that point stands for. */
export function yearAt(at: number): number {
  return new Date(at * YEAR).getUTCFullYear();
}

interface Mark {
  event: TimelineEvent;
  x: number;
}

/** "2006", or "2004–2006": the span in full years, for a page with room. */
function fullYears(start: string, end: string): string {
  const a = yearAt(years(start));
  const b = yearAt(years(end));
  return a === b ? String(a) : `${a}\u2013${b}`;
}

/** The dated moments no cluster claims. */
function loose(dated: TimelineEvent[], clusters: { event_ids: number[] }[]): TimelineEvent[] {
  const claimed = new Set(clusters.flatMap((cluster) => cluster.event_ids));
  return dated.filter((event) => !claimed.has(event.id));
}

/** Which way in to an event the reader touched. */
export enum Via {
  Chip = "chip",
  Dot = "dot",
}

/** What the picture shows, as far as picking an event changes it. */
export interface Look {
  level: Level;
  focus: Cluster | null;
  named: number[];
  selected: number | null;
}

/** The picture after one event is picked. A chip naming it and its dot do one
 * thing (R-0168): the event is picked and everything else recedes. Inside a
 * cluster the cluster opens; outside every cluster it is picked on the resting
 * line, the clusters kept as brackets under it (R-0235). The old chip
 * spotlight, kept behind a per-person setting: a chip put the event on the
 * wire with the whole record and no clusters, and a dot only picked it. */
export function picked(
  look: Look,
  id: number,
  named: number[],
  clusters: Cluster[],
  spot: Spotlight,
  via: Via,
): Look {
  const focus = clusters.find((c) => c.event_ids.includes(id)) ?? null;
  if (spot === Spotlight.Unified)
    return { level: focus ? Level.Wire : Level.Rest, focus, named, selected: id };
  if (via === Via.Dot) return { ...look, selected: id };
  return { level: Level.Wire, focus, named, selected: id };
}

/** The whole resting line is drawn, clusters as boxes, or as brackets under
 * the line while an event no cluster holds is picked. */
export const resting = (look: Look): boolean =>
  look.level === Level.Rest && (look.selected === null || !look.focus);

/** Where the line runs: high on the resting line with nothing picked, and
 * lower wherever an event is picked, to leave its words room above it. */
export const wireOf = (look: Look): number =>
  resting(look) && look.selected === null ? REST_WIRE : WIRE;

export class Picture {
  private data: Timeline | null = null;
  /** The moments the coach's latest message named — the spotlight. */
  private named: number[] = [];
  private selected: number | null = null;
  private cast: number[] = [];
  private level = Level.Rest;
  private moves: Step[] = [];
  /** The cluster the board is currently showing, so a chip already on its own
   * board steps it rather than reopening it. */
  private cluster: string | null = null;
  private at = 0;
  private pair: [number, number] | null = null;
  private entering = false;
  /** True while the coach is still answering the last "explain", so the control
   * that asked cannot be asked again until the words land or fail. */
  private explaining = false;
  /** Set once the reader steps the board themselves. */
  private steered = false;
  /** Who the coach has just put in the record. They stay lit the way a
   * spotlit moment does: until the next thing is aimed at or picked. */
  private litPeople: number[] = [];
  private band: { start: string; end: string } | null = null;
  /** Where the resting line stands after the next draw, and the moment it goes
   * to when the coach's words name one. */
  private park = Park.Present;
  private aimed: number | null = null;
  private focus: Cluster | null = null;
  private range = { min: 0, max: 1 };
  private laid: { zones: Mark[][]; rows: LabelRow[] } = {
    zones: [],
    rows: [],
  };
  /** How deep the view on screen is, so a render that changes levels knows
   * which way it is travelling. */
  private depth = DEPTH[Level.Rest];
  private flight: Animation | null = null;
  /** What is left to do once the slide is over, held so a render arriving
   * mid-flight can finish it early rather than stack a second pair of layers. */
  private landing: (() => void) | null = null;

  constructor(
    private host: HTMLElement,
    private handlers: PictureHandlers,
    private spot = Spotlight.Unified,
  ) {
    window.addEventListener("resize", () => this.render());
    this.host.addEventListener("click", (e) => {
      const hit = (e.target as Element).closest<HTMLElement>("[data-target]");
      // Empty ground. Nothing on the picture is under the thumb, so the tap is
      // the reader putting the picture down; the board has its own way back.
      if (!hit) {
        if (this.level !== Level.Board)
          this.handlers.onTap(this.tapAt(Target.Ground, e));
        return;
      }
      e.preventDefault();
      if (OWN.has(hit.dataset.target as string)) {
        this.control(hit.dataset.target as Target);
        return;
      }
      const tap = this.tapAt(
        hit.dataset.target as Target,
        e,
        Number(hit.dataset.index ?? -1),
      );
      // The words are written over the wire, and the wire's own targets are 44
      // tall so a thumb can find a dot — tall enough to cover the second line
      // of a label. Where a tap lands on a line of words, the words answer it:
      // the reader touched the label, not the dot underneath it.
      const on =
        tap.target === Target.Zone && this.rowAt(tap.x, tap.y) !== null
          ? { ...tap, target: Target.Band }
          : tap;
      this.handlers.onTap(on);
    });
  }

  private tapAt(target: Target, e: Event, index = -1): Tap {
    const box = this.host.getBoundingClientRect();
    // the marks and the words sit on the line, which slides under the picture,
    // so where the thumb landed is read in the line's own places
    const slid = this.host.querySelector<HTMLElement>(SCROLLER)?.scrollLeft ?? 0;
    return {
      target,
      index,
      x: (e as MouseEvent).clientX - box.left + slid,
      y: (e as MouseEvent).clientY - box.top,
    };
  }

  /** Light what one line of what the coach did has just put in the record, at
   * the moment that line lands: a moment as a dot on the wire, a person
   * wherever people are drawn, which today is the board. */
  light(made: { kind: ItemKind; id: string }[]): void {
    const moments = made
      .filter((one) => one.kind === ItemKind.Event)
      .map((one) => Number(one.id))
      .filter((id) => (this.data?.events ?? []).some((e) => e.id === id));
    const people = made
      .filter((one) => one.kind === ItemKind.Person)
      .map((one) => Number(one.id));
    // the spotlight clears the last lighting before this one takes its place,
    // so who this line made is set after it, not before
    if (moments.length) this.spotlight(moments);
    this.litPeople = people;
    this.render();
  }

  /** Put the picture down: nothing selected, nothing named, the whole line at
   * a glance again. */
  dismiss(): void {
    this.named = [];
    this.selected = null;
    this.litPeople = [];
    this.park = Park.Present;
    this.focus = null;
    this.cluster = null;
    this.level = Level.Rest;
    this.rescale();
    this.render();
  }

  setData(data: Timeline): void {
    this.data = data;
    // the record has changed under the picture, which is what a reply leaves
    // behind: the line goes back to the present (R-0381)
    this.park = Park.Present;
    this.rescale();
    this.render();
  }

  /** What the coach's latest message named. Everything else recedes. */
  spotlight(eventIds: number[]): void {
    this.named = eventIds;
    this.selected = null;
    this.litPeople = [];
    this.aim(eventIds[0] ?? null);
    // naming something opens the cluster it belongs to; naming nothing leaves
    // the picture at rest, showing the whole line
    this.level = eventIds.length ? Level.Wire : Level.Rest;
    this.cluster = null;
    this.focus = this.clusterOf(eventIds[0]);
    this.rescale();
    this.render();
  }

  /** One event picked, from its dot or from a chip naming it; a chip also
   * takes the line to it, since it may be off screen. */
  pick(id: number, named: number[], via: Via): void {
    ({
      level: this.level,
      focus: this.focus,
      named: this.named,
      selected: this.selected,
    } = picked(this.look(), id, named, this.data?.clusters ?? [], this.spot, via));
    this.litPeople = [];
    if (via === Via.Chip) {
      this.aim(id);
      this.cluster = null;
    }
    this.rescale();
    this.render();
  }

  private look(): Look {
    return {
      level: this.level,
      focus: this.focus,
      named: this.named,
      selected: this.selected,
    };
  }

  select(eventId: number | null): void {
    this.selected = eventId;
    this.litPeople = [];
    // a tap moves nothing: the reader is already looking at what they touched
    this.render();
  }

  /** The line goes to the moment the coach's words, or a chip in them, just
   * named, and stays where it is when they name nothing. */
  private aim(eventId: number | null): void {
    this.aimed = eventId;
    this.park = eventId === null ? Park.Held : Park.Named;
  }

  selection(): number | null {
    return this.selected;
  }

  /** The moments under one tap zone, in time order. */
  inZone(index: number): number[] {
    return (this.laid.zones[index] ?? []).map((mark) => mark.event.id);
  }

  /** Which label the thumb landed on, for a tap in the label band. The band is
   * one 44px target and the row nearest the tap wins it, which is the
   * converged mockup's rule; across, the tap has to be on the words themselves,
   * because the space beside them is ground and belongs to putting the picture
   * down. */
  rowAt(x: number, y: number): number | null {
    let best: number | null = null;
    let distance = Infinity;
    for (const row of this.laid.rows) {
      if (x < row.left - LABEL_SLOP || x > row.left + row.width + LABEL_SLOP)
        continue;
      const top = ROWS[row.row];
      // A line of words answers for the line it is written on and no further.
      // Without this every point in the band belonged to the nearest row, so a
      // tap on the wire below the words named a moment nobody touched.
      if (y < top - ROW_SLOP || y > top + ROW_H + ROW_SLOP) continue;
      const d = Math.abs(top + ROW_H / 2 - y);
      if (d < distance) {
        distance = d;
        best = row.id;
      }
    }
    return best;
  }

  step(eventId: number): void {
    // while the board is open a named moment steps the board rather than
    // off the board it only picks the moment out on the wire, because a move
    // with people on stage is drawn on the board and nowhere else (ruled)
    const on = this.moves.findIndex((m) => m.event.id === eventId);
    if (this.level === Level.Board && on >= 0) {
      // once the reader has taken the controls the play-through stops moving
      // the board under them
      if (this.steered) return;
      this.at = on;
      this.render();
      return;
    }
    this.selected = eventId;
    this.aim(eventId);
    this.render();
  }

  /** Enter the board: the moves of one cluster, numbered, on the people they
   * happened between. The level below it is CUT, so this comes straight from
   * the chat. */
  openBoard(eventIds: number[], cluster: string | null = null): number {
    const events = (this.data?.events ?? []).filter((e) =>
      eventIds.includes(e.id),
    );
    this.moves = movesIn(events);
    if (!this.moves.length) return 0;
    this.cluster = cluster;
    this.level = Level.Board;
    this.entering = true;
    this.steered = false;
    this.at = 0;
    this.cast = [];
    this.render();
    return this.moves.length;
  }

  /** A chip in a play-by-play steps the board and never goes back to the wire
   * (owner review round 1). The board opens on the cluster the walk narrates if
   * it is not already up, then goes to the move the chip names — or, when the
   * chip names no move of its own, to the nth move of the walk. */
  playStep(clusterId: string, eventIds: number[], ordinal: number): void {
    if (this.level !== Level.Board || this.cluster !== clusterId) {
      const cluster =
        this.clusterOf(eventIds[0]) ??
        this.data?.clusters.find(
          (c) => c.id === clusterId || c.cluster_ids.includes(clusterId),
        );
      if (!cluster || !this.openBoard(cluster.event_ids, clusterId)) return;
    }
    // the reader stepping the board themselves outranks a play-through still
    // running, which is what steering already means here
    this.steered = true;
    const named = this.moves.findIndex((m) => eventIds.includes(m.event.id));
    this.at =
      named >= 0
        ? named
        : Math.min(this.moves.length - 1, Math.max(0, ordinal));
    this.render();
  }

  /** How many moves a cluster would put on the board, for the entry button. */
  countMoves(eventIds: number[]): number {
    return movesIn(
      (this.data?.events ?? []).filter((e) => eventIds.includes(e.id)),
    ).length;
  }

  onBoard(): boolean {
    return this.level === Level.Board;
  }

  /** Whether the picture is showing one cluster rather than the whole line. */
  opened(): boolean {
    return this.level === Level.Wire && this.focus !== null;
  }

  /** The cluster the picture is showing, if it is showing one. */
  openCluster(): Cluster | null {
    return this.opened() ? this.focus : null;
  }

  /** The cluster the board is showing, which is what "explain" asks about. */
  showing(): string | null {
    return this.cluster;
  }

  /** The coach is answering, or has finished answering, an explain. */
  explains(busy: boolean): void {
    this.explaining = busy;
    if (this.level === Level.Board) this.render();
  }

  private control(target: Target): void {
    // the reader taking the controls outranks a play-through still running:
    // from here the board is theirs to step
    this.steered = true;
    if (target === Target.Next)
      this.at = Math.min(this.moves.length - 1, this.at + 1);
    else if (target === Target.Prev) this.at = Math.max(0, this.at - 1);
    this.render();
  }

  /** The name of the view the reader is in: the cluster the board is showing,
   * or the cluster open on the wire. Null at rest, where the picture is the
   * whole line and has no name but its own. */
  title(): string | null {
    const open =
      this.focus ??
      (this.cluster
        ? this.data?.clusters.find(
            (c) => c.id === this.cluster || c.cluster_ids.includes(this.cluster as string),
          ) ?? null
        : null);
    return this.level === Level.Rest || !open ? null : open.title || open.label;
  }

  /** A view below the whole line is open, so there is somewhere to go up to. */
  deep(): boolean {
    return this.level === Level.Board || this.level === Level.About || this.opened();
  }

  /** The open cluster's own page, a level in from the cluster. */
  about(): void {
    if (!this.opened()) return;
    this.level = Level.About;
    this.render();
  }

  aboutOpen(): boolean {
    return this.level === Level.About;
  }

  /** Nothing dated on the record yet: the picture is one sentence, and the
   * row under it has nothing to point at. */
  empty(): boolean {
    return this.dated().length === 0;
  }

  /** Up exactly one level: the board to the cluster it is showing, an open
   * cluster to the whole line. The title row is the only way up (owner ruling
   * 2026-09-08), so the board carries no corner arrow of its own. */
  up(): void {
    if (this.level === Level.About) {
      this.level = Level.Wire;
      this.render();
      return;
    }
    if (this.level !== Level.Board) {
      // The arrow always closes the cluster, picked moment or not (Patrick,
      // 2026-09-22: putting the moment down first was tap-for-tap logical and
      // felt wrong). Putting a moment down is a tap on empty ground.
      this.dismiss();
      return;
    }
    this.level = Level.Wire;
    this.moves = [];
    this.cluster = null;
    this.cast = [];
    this.at = 0;
    this.render();
  }

  async show(view: View): Promise<void> {
    this.band = null;
    this.cast = [];
    // every view starts from the resting wire; the ones that are a level of
    // their own say so below
    this.level = Level.Wire;
    this.moves = [];
    this.cluster = null;
    switch (view.kind) {
      case ViewKind.Triangle:
        // people on stage draw only on the board, which is a level of its own
        this.cast = view.persons;
        this.level = Level.Board;
        this.entering = true;
        this.render();
        return;
      case ViewKind.Span:
        this.band = { start: view.start, end: view.end };
        this.render();
        return;
      case ViewKind.Compare:
        // two moments face to face, a question mark between them, no axis
        this.pair = [view.event_a, view.event_b];
        this.level = Level.Compare;
        this.render();
        return;
      case ViewKind.Sequence: {
        // a sequence is the moves board, stepped in order, and it stays up
        // afterwards so the reader can hold on any one move
        const n = this.openBoard(view.events);
        if (!n) return;
        for (let i = 1; i < n; i += 1) {
          await pause(HOLD_MS);
          // a tap on back, or another view, ends the walk through
          if ((this.level as Level) !== Level.Board) return;
          this.at = i;
          this.render();
        }
        return;
      }
      case ViewKind.Cluster: {
        const cluster = this.data?.clusters.find(
          (c) => c.id === view.cluster || c.cluster_ids.includes(view.cluster),
        );
        if (cluster) {
          this.focus = cluster;
          this.spotlight(cluster.event_ids);
        }
        return;
      }
    }
  }

  clear(): void {
    this.named = [];
    this.selected = null;
    this.park = Park.Present;
    this.cast = [];
    this.band = null;
    this.focus = null;
    this.level = Level.Wire;
    this.moves = [];
    this.at = 0;
    this.pair = null;
    this.rescale();
    this.render();
  }

  private yearOf = (event: TimelineEvent) => (event.dateTime as string).slice(0, 4);

  private event(id: number | null): TimelineEvent | null {
    return id === null
      ? null
      : (this.data?.events.find((e) => e.id === id) ?? null);
  }

  private clusterOf(eventId: number | undefined): Cluster | null {
    if (eventId === undefined || !this.data) return null;
    return this.data.clusters.find((c) => c.event_ids.includes(eventId)) ?? null;
  }

  /** The coach drives the picture: when it names moments inside one cluster,
   * the wire zooms to that cluster; otherwise the whole record is on it. */
  private rescale(): void {
    const shown = this.shown();
    const dates = shown.map((e) => years(e.dateTime as string));
    if (!dates.length) {
      this.range = { min: 0, max: 1 };
      return;
    }
    const min = Math.min(...dates);
    const max = Math.max(...dates);
    const pad = Math.max(0.3, (max - min) * 0.06);
    this.range = { min: min - pad, max: max + pad };
  }

  /** The moments on the wire: the focused cluster when the coach aimed at one,
   * otherwise every dated moment in the record. */
  private shown(): TimelineEvent[] {
    const dated = this.dated();
    if (!this.focus) return dated;
    const ids = new Set(this.focus.event_ids);
    // whatever is picked is always on the wire, or its words would describe a
    // moment the picture is not showing
    if (this.selected !== null) ids.add(this.selected);
    const inFocus = dated.filter((e) => ids.has(e.id));
    return inFocus.length ? inFocus : dated;
  }

  private dated(): TimelineEvent[] {
    return (this.data?.events ?? []).filter(
      (e) => !!e.dateTime && e.dateCertainty !== DateCertainty.Unknown,
    );
  }

  private person(id: number | null): Person | undefined {
    return id === null ? undefined : this.data?.people.find((p) => p.id === id);
  }

  private get width(): number {
    return this.host.clientWidth || 360;
  }

  /** Where a tap target of this size sits when it is meant to be centred on a
   * point: a target for a thumb is wider than the gap at the ends of the wire,
   * so one near an end is slid inside rather than left hanging off the edge. */
  private hitLeft(middle: number, size: number, width = this.width): string {
    return Math.min(Math.max(middle - size / 2, 0), width - size).toFixed(1);
  }

  private x(iso: string): number {
    const { min, max } = this.range;
    const x1 = this.width - X_PAD;
    return X_PAD + ((years(iso) - min) / (max - min)) * (x1 - X_PAD);
  }

  /** The picture region owns its level's height, so the chat below it only ever
   * moves on a deliberate level change and never on a tap (LAYOUT CONTRACT). */
  private pin(height: number): void {
    this.host.style.height = `${height}px`;
  }

  /** The board is a level of its own: its own height, its own nav, its own
   * step controls, and a caption saying which move of how many this is. */
  /** The whole line at a glance: one box per cluster, its years above it, its
   * moments as dots inside it, and the amber question where the record has a
   * long gap it cannot account for. A tap opens a cluster. Converged mockup:
   * crowded-cluster/timeline-converged.html renderRest. */
  /** Everything the record and the coach can say about one cluster, as words:
   * the reason it is one episode, its span, and each moment with its year. The
   * page takes the height its words need. */
  private renderAbout(cluster: Cluster): void {
    this.laid = { zones: [], rows: [] };
    const why = (cluster.reason ?? cluster.summary ?? "").trim();
    const moments = (this.data?.events ?? [])
      .filter((e) => cluster.event_ids.includes(e.id))
      .sort((a, b) => (a.dateTime ?? "").localeCompare(b.dateTime ?? ""));
    const rows = moments
      .map(
        (e) =>
          `<li><span class="ab-yr">${esc(this.yearOf(e))}</span>` +
          `<span class="ab-what">${esc(e.label)}</span></li>`,
      )
      .join("");
    this.host.innerHTML =
      `<div class="ss about">` +
      (why ? `<p class="ab-why">${esc(why)}</p>` : "") +
      `<p class="ab-span">${esc(fullYears(cluster.start, cluster.end))} · ` +
      `${moments.length} event${moments.length === 1 ? "" : "s"}</p>` +
      `<ul class="ab-list">${rows}</ul></div>`;
    this.pin(this.host.scrollHeight);
  }

  private renderRest(): void {
    const screen = this.width;
    const dated = this.dated();
    this.laid = { zones: [], rows: [] };
    this.pin(PIC_H);

    // What has no date exists at every level: it is the one thing on the
    // picture the record is still asking about.
    const shelf = this.shelfHit(screen - X_PAD, REST_WIRE);

    if (!dated.length) {
      this.host.innerHTML =
        `<div class="ss"><p class="ss-empty">` +
        `The timeline draws itself here as you talk.</p>${shelf}</div>`;
      return;
    }

    const clusters = this.restClusters();
    // The line is drawn wider than the screen and slides sideways under it, so
    // a crowded record reads at a scale a thumb can pick from (R-0381).
    const width = restWidth(
      clusters,
      dated.map((e) => e.dateTime as string),
      screen,
    );
    const held = this.host.querySelector<HTMLElement>(SCROLLER)?.scrollLeft ?? null;
    const x0 = X_PAD;
    const x1 = width - X_PAD;
    // A picked loose moment gets the words, dot and year the open cluster gives
    // one — the same two lines above the wire — so the wire drops to where the
    // words leave room and the boxes, which live where the words go, become
    // brackets under the wire until the moment is put down (owner, option A,
    // 2026-09-09).
    const picked = this.selected !== null && loose(dated, clusters).some((e) => e.id === this.selected);
    // what an event picked leaves out recedes, as it does on the open wire
    const faded = (id: number | null) =>
      this.named.length && (id === null || !this.named.includes(id))
        ? ` opacity="${baseOpacity(dated.length, this.named.length)}"`
        : "";
    const wireY = wireOf(this.look());
    const first = years(dated[0].dateTime as string);
    const last = years(dated[dated.length - 1].dateTime as string);
    const span = last - first || 1;
    const at = (iso: string) =>
      dated.length === 1
        ? (x0 + x1) / 2
        : x0 + ((years(iso) - first) / span) * (x1 - x0);
    const aimed = dated.find((e) => e.id === this.aimed);
    const onX = aimed ? at(aimed.dateTime as string) : null;
    // where the line comes to rest, so the words of a picked moment are
    // written across the stretch the reader will be looking at
    const shows = this.stands({ width, screen }, held, onX);

    let svg =
      `<svg viewBox="0 0 ${width} ${PIC_H}" height="${PIC_H}" preserveAspectRatio="xMinYMin meet">` +
      (picked
        ? `<defs><linearGradient id="epfade" gradientUnits="userSpaceOnUse" ` +
          `x1="0" x2="0" y1="${wireY + 20}" y2="${wireY - 20}">` +
          `<stop offset="0" class="epfade-in"/><stop offset="0.45" class="epfade-in"/>` +
          `<stop offset="1" class="epfade-out"/></linearGradient></defs>`
        : "") +
      `<line class="wire" x1="${x0}" y1="${wireY}" x2="${x1}" y2="${wireY}"/>`;
    const boxes: Layer[] = [];
    // A box reaches a little past the moments it holds, and two clusters a
    // month apart would then draw over one another. Where that happens the two
    // boxes give way to each other and leave a gap between them.
    const edges = clusters.map((cluster) => ({
      left: at(cluster.start) - BOX_PAD,
      right: at(cluster.end) + BOX_PAD,
    }));
    for (let i = 1; i < edges.length; i += 1) {
      const gap = edges[i].left - edges[i - 1].right;
      if (gap >= BOX_GAP) continue;
      const middle = (edges[i - 1].right + edges[i].left) / 2;
      edges[i - 1].right = middle - BOX_GAP / 2;
      edges[i].left = middle + BOX_GAP / 2;
    }

    clusters.forEach((cluster, i) => {
      const a = at(cluster.start);
      const b = at(cluster.end);
      const left = edges[i].left;
      const boxWidth = Math.max(6, edges[i].right - edges[i].left);
      const middle = (a + b) / 2;
      // The box rides the wire wherever the wire is. While a moment is picked
      // the box fades to nothing going up, so it never reaches the words above
      // (owner, 2026-09-09).
      const boxY = wireY - 20;
      const fade = picked ? ` style="fill:url(#epfade)"` : "";
      const fadeEdge = picked ? ` style="stroke:url(#epfade)"` : "";
      svg +=
        `<rect class="ep" x="${left.toFixed(1)}" y="${boxY}" ` +
        `width="${boxWidth.toFixed(1)}" height="40" rx="8"${fade}/>` +
        `<rect class="ep-edge" x="${left.toFixed(1)}" y="${boxY}" ` +
        `width="${boxWidth.toFixed(1)}" height="40" rx="8"${fadeEdge}/>`;
      if (cluster.count > DENSE)
        svg +=
          `<circle class="ep-many" cx="${middle.toFixed(1)}" cy="${wireY}" r="11"/>` +
          `<text class="ep-count" x="${middle.toFixed(1)}" y="${wireY + 4}" ` +
          `text-anchor="middle">${cluster.count}</text>`;
      else {
        const inBox = dated.filter((e) => cluster.event_ids.includes(e.id));
        const when =
          inBox.length === cluster.count
            ? inBox.map((e) => at(e.dateTime as string))
            : Array.from({ length: cluster.count }, (_, j) =>
                cluster.count > 1 ? a + ((b - a) * j) / (cluster.count - 1) : middle,
              );
        for (const cx of dotXs(when, left, boxWidth))
          svg += `<circle class="dot" cx="${cx.toFixed(1)}" cy="${wireY}" r="${DOT_R}"${faded(null)}/>`;
      }
      if (!picked)
        svg +=
          `<text class="ep-yrs" x="${middle.toFixed(1)}" y="21" text-anchor="middle">` +
          `${esc(shortYears(cluster.start, cluster.end))}</text>`;

      const next = clusters[i + 1];
      if (next && years(next.start) - years(cluster.end) >= GAP_YEARS) {
        const gap = (at(next.start) + b) / 2;
        svg +=
          `<text class="qm small" x="${gap.toFixed(1)}" y="${wireY + 4}" ` +
          `text-anchor="middle">?</text>`;
      }

      // the box may be narrower than a thumb, so the target is grown to the floor
      const target = Math.max(ZONE, boxWidth);
      boxes.push({
        target: Target.Cluster,
        index: i,
        left: Number(this.hitLeft(middle, target, width)),
        width: target,
        label: cluster.title || shortYears(cluster.start, cluster.end),
      });
    });
    // A moment no cluster claims is drawn as itself: a dot on the wire where it
    // happened, with no box around it and nothing else bundled into it.
    const marks: Mark[] = loose(dated, clusters).map((event) => ({
      event,
      x: at(event.dateTime as string),
    }));
    for (const { event, x } of marks) {
      const on = event.id === this.selected ? " on" : "";
      svg += `<circle class="dot${on}" cx="${x.toFixed(1)}" cy="${wireY}" r="${on ? 7 : DOT_R}"${faded(event.id)}/>`;
    }
    const zoned = zones(marks, width);
    this.laid.zones = zoned.map((zone) => zone.marks);
    const hits = restLayers(boxes, dotLayers(zoned))
      .map((layer) => hitButton(layer, wireY))
      .join("");

    svg += `</svg>`;

    let words = "";
    if (picked) {
      // the words are written across the stretch on screen and travel with
      // their own mark from there
      const laid = this.labels(marks, shows + X_PAD, shows + screen - X_PAD, wireY);
      this.laid.rows = laid.rowsLaid;
      const mark = marks.find((m) => m.event.id === this.selected) as Mark;
      words =
        laid.text +
        `<div class="ss-yr on" style="left:${yearLeft(mark.x, shows, shows + screen)}px;` +
        `top:${YEAR_TOP}px;width:${YEAR_W}px;text-align:center">${esc(this.yearOf(mark.event))}</div>`;
    }

    // Where the line settles after a swipe: at a box's near edge, so a cluster
    // is never cut in half, and at the present.
    const stops = new Set<string>();
    for (const edge of edges) {
      stops.add(Math.max(0, edge.left - X_PAD).toFixed(1));
      stops.add(Math.max(0, edge.right + X_PAD - screen).toFixed(1));
    }
    stops.add(Math.max(0, width - screen).toFixed(1));
    const snaps = [...stops]
      .map((left) => `<i class="ss-snap" style="left:${left}px"></i>`)
      .join("");
    // The years say which stretch of the record is on screen, and are written
    // again as it slides. They belong to a line long enough to slide.
    const ends =
      width > screen && !picked
        ? `<div class="ss-yrs"><span></span><span></span></div>`
        : "";

    this.host.innerHTML =
      `<div class="ss"><div class="ss-scroll"><div class="ss-line" style="width:${width.toFixed(1)}px">` +
      `${svg}${words}${hits}${snaps}</div></div>${ends}${shelf}</div>`;
    this.settle({ width, screen, first, span }, held, onX);
  }

  /** Where the line comes to rest after this draw: on the moment just named,
   * where the reader left it, or parked at the present. */
  private stands(
    view: { width: number; screen: number },
    held: number | null,
    onX: number | null,
  ): number {
    const end = Math.max(0, view.width - view.screen);
    if (this.park === Park.Named && onX !== null)
      return Math.max(0, Math.min(end, onX - view.screen / 2));
    if (this.park === Park.Held && held !== null) return Math.min(end, held);
    return end;
  }

  /** Where the line stands once it has been drawn: parked at the present, on
   * the moment just named, or where the reader left it. The years under it are
   * written from the stretch on screen, and again on every slide. */
  private settle(
    view: { width: number; screen: number; first: number; span: number },
    held: number | null,
    onX: number | null,
  ): void {
    const scroll = this.host.querySelector<HTMLElement>(SCROLLER);
    if (!scroll) return;
    const reach = view.width - 2 * X_PAD;
    const ends = [...this.host.querySelectorAll<HTMLElement>(".ss-yrs span")];
    const write = () => {
      if (ends.length !== 2) return;
      const year = (x: number) =>
        String(
          yearAt(
            view.first +
              ((Math.max(X_PAD, Math.min(view.width - X_PAD, x)) - X_PAD) / reach) *
                view.span,
          ),
        );
      ends[0].textContent = year(scroll.scrollLeft);
      ends[1].textContent = year(scroll.scrollLeft + view.screen);
    };
    scroll.addEventListener("scroll", write);
    const named = this.park === Park.Named && onX !== null;
    const to = this.stands(view, held, onX);
    this.park = Park.Held;
    this.aimed = null;
    // the line travelling to what was named is the picture answering the
    // coach's words; every other draw puts it down where it belongs at once
    if (named && held !== null && !still())
      scroll.scrollTo({ left: to, behavior: "smooth" });
    else scroll.scrollLeft = to;
    write();
  }

  /** The clusters the resting level draws, in time order. They are the ones
   * the record holds; a record with none draws none, and its moments are dots
   * on the wire. */
  private restClusters(): Cluster[] {
    return [...(this.data?.clusters ?? [])]
      .filter((c) => c.event_ids.length)
      .sort((a, b) => years(a.start) - years(b.start));
  }

  /** The moments in the cluster a resting tap landed on. */
  inCluster(index: number): number[] {
    return this.restClusters()[index]?.event_ids ?? [];
  }

  private renderBoard(): void {
    const ids = this.moves.length ? castOfSteps(this.moves) : this.cast;
    const people = ids
      .map((id) => this.person(id))
      .filter((p): p is Person => !!p);
    const { svg, caption, height } = this.moves.length
      ? board(this.moves, this.at, people, this.data?.events ?? [], this.width)
      : triangle(people, this.width);
    const last = this.moves.length - 1;
    // people pop in when the board opens, and only then: a step through the
    // cluster must not restage everyone on every move
    const zoom = this.entering ? " in" : "";
    this.entering = false;
    this.host.innerHTML =
      `<div class="ss board${zoom}" style="height:${height}px">${svg}</div>` +
      `<div class="bcap">${esc(caption)}</div>` +
      // a cast the coach put on the board has nothing to step through
      (this.moves.length
        ? `<div class="pctl">` +
          `<button type="button" class="btn" data-target="${Target.Prev}" ` +
          `${this.at === 0 ? "disabled" : ""} aria-label="the move before">&#9664;</button>` +
          // One row, whichever way the board was opened. Explain is dead only
          // while the coach is still answering the last one.
          (this.handlers.canExplain === false
            ? ""
            : `<button type="button" class="btn primary" data-target="${Target.Explain}" ` +
              `${this.explaining ? "disabled" : ""}>&#9654; explain</button>`) +
          `<button type="button" class="btn" data-target="${Target.Next}" ` +
          `${this.at >= last ? "disabled" : ""} aria-label="the move after">&#9654;</button>` +
          `</div>`
        : "");
    for (const id of this.litPeople)
      this.host.querySelector(`.node[data-person="${id}"]`)?.classList.add("lit");
    // The board is as tall as what it holds — the drawing, its caption and its
    // controls — rather than a fixed number with an empty band under it.
    this.pin(
      [...this.host.children].reduce(
        (total, node) => total + node.getBoundingClientRect().height,
        0,
      ),
    );
    if (still())
      this.host.querySelector("svg")?.pauseAnimations();
  }

  /** Two moments side by side with the record's one asking mark between them.
   * No axis: a comparison is not a measurement. */
  private renderPair(): string | null {
    const [a, b] = (this.pair ?? [0, 0]).map((id) => this.event(id));
    if (!a || !b) return null;
    this.pin(PIC_H);
    return pairSvg(a, b, this.width);
  }

  private render(): void {
    if (!this.data) return;
    const to = DEPTH[this.level];
    const from = this.depth;
    this.depth = to;
    this.land();
    if (to === from || !this.host.firstChild || still()) {
      this.draw();
      return;
    }
    this.slide(to > from ? 1 : -1);
  }

  /** One level in or one level out. Drilling down, the arriving view slides in
   * from the right over the one it came from; going back, the view being left
   * slides out to the right and uncovers it. Both stand at the height the
   * region already had, so nothing under the picture moves while they travel;
   * a level with a height of its own takes it once the slide is over
   * (owner ruling 2026-09-08). */
  private slide(dir: 1 | -1): void {
    // The card is the whole picture region — title line, drawing and the row
    // of chips — not the drawing alone (owner, 2026-09-09). The level that is
    // leaving is photographed now; the one arriving is photographed once the
    // page has written its title and chips, a frame later; the two pictures
    // travel over the live region, which is already showing the new level.
    const region = this.host.parentElement as HTMLElement;
    const leaving = snapshot(region);
    this.draw();
    region.classList.add("sliding");
    region.append(leaving);
    keepScroll(leaving);
    requestAnimationFrame(() => {
      const arriving = snapshot(region, leaving);
      region.append(dir === 1 ? arriving : leaving);
      keepScroll(arriving);
      const mover = dir === 1 ? arriving : leaving;
      const off = { transform: "translateX(100%)" };
      const on = { transform: "translateX(0)" };
      this.flight = mover.animate(dir === 1 ? [off, on] : [on, off], {
        duration: SLIDE_MS,
        easing: "ease",
      });
      this.landing = () => {
        leaving.remove();
        arriving.remove();
        region.classList.remove("sliding");
      };
      this.flight.finished.then(
        () => this.land(),
        () => undefined,
      );
    });
  }

  /** Put the arriving view down where it belongs, whether the slide finished
   * or was overtaken. */
  private land(): void {
    const finish = this.landing;
    if (!finish) return;
    this.landing = null;
    this.flight?.cancel();
    this.flight = null;
    finish();
  }

  private draw(): void {
    if (this.level === Level.About && this.focus) {
      this.renderAbout(this.focus);
      return;
    }
    if (this.level === Level.Board && (this.moves.length || this.cast.length)) {
      this.renderBoard();
      return;
    }
    if (this.level === Level.Compare) {
      const markup = this.renderPair();
      if (markup) {
        this.host.innerHTML = markup;
        return;
      }
    }
    // A loose event picked, by its dot or by a chip, is picked where it is:
    // the clusters stay, the dot reads as picked (Patrick, 2026-09-09; R-0168).
    // The spotlight below is for a cluster open, or what the coach's words
    // name as a whole.
    if (resting(this.look())) {
      this.renderRest();
      return;
    }
    const width = this.width;
    const x0 = X_PAD;
    const x1 = width - X_PAD;
    const shown = this.shown();
    // the resting picture is one fixed height, whatever it is showing: people
    // on stage belong to the board, which is a level of its own (ruled)
    const height = PIC_H;
    const wire = wireOf(this.look());

    if (!shown.length) {
      this.laid = { zones: [], rows: [] };
      this.pin(PIC_H);
      this.host.innerHTML =
        `<div class="ss">` +
        `<svg viewBox="0 0 ${width} ${PIC_H}" aria-hidden="true">` +
        `<line class="wire empty" x1="${x0}" y1="${WIRE}" x2="${x1}" y2="${WIRE}"/>` +
        // The "?" in the middle of an empty wire was the question language
        // (DRAWABILITY): "the record is still asking". Hidden on Patrick's word,
        // 2026-09-21: distracting before anyone knows what it means. The rule
        // stands; the glyph waits for a first-time explanation. To restore:
        // `<text class="qm" x="${width / 2}" y="${WIRE + 6}" text-anchor="middle">?</text>`
        `</svg>` +
        `<button class="ss-hit" data-target="${Target.Shelf}" ` +
        `aria-label="Nothing has a date yet" ` +
        `style="left:${x0}px;top:${WIRE - 22}px;width:${x1 - x0}px;height:${ZONE}px"></button>` +
        `</div>`;
      return;
    }

    const marks: Mark[] = shown.map((event) => ({
      event,
      x: this.x(event.dateTime as string),
    }));
    const named = new Set(this.named);
    const opacity = baseOpacity(marks.length, this.named.length);
    const radius = dotRadius(marks.length);
    // the words are laid out first: where they land decides whether there is
    // room for the bracket over the cluster
    const { text, rowsLaid } = this.labels(marks, x0, x1, wire);
    this.laid.rows = rowsLaid;

    let svg =
      `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">` +
      `<defs><marker id="tip" viewBox="0 0 10 10" refX="8.5" refY="5" ` +
      `markerWidth="5.5" markerHeight="5.5" orient="auto">` +
      `<path d="M0 0 L10 5 L0 10 Z" class="tipfill"/></marker></defs>` +
      this.bandMark(wire) +
      `<line class="wire" x1="${x0}" y1="${wire}" x2="${x1}" y2="${wire}"/>`;

    // one dot per moment; moments sharing a date stack instead of merging
    const byDate = new Map<string, Mark[]>();
    for (const mark of marks) {
      const key = mark.event.dateTime as string;
      byDate.set(key, [...(byDate.get(key) ?? []), mark]);
    }
    // The moment picked is drawn last, so it is on top of whatever crowds it
    // (picked mockup Q1).
    let onTop = "";
    for (const group of byDate.values()) {
      const x = group[0].x.toFixed(1);
      const lit = group.filter((m) => named.has(m.event.id));
      const keep = (mark: Mark, drawn: string) => {
        if (mark.event.id === this.selected) onTop += drawn;
        else svg += drawn;
      };
      if (lit.length) {
        if (group.length > lit.length)
          svg += `<circle class="halo" cx="${x}" cy="${wire}" r="7"/>`;
        lit.forEach((mark, i) => {
          const cy = i === 0 ? (lit.length > 1 ? wire + 5 : wire) : i === 1 ? wire - 5 : wire + 5 + 10 * (i - 1);
          keep(mark, this.dot(mark, x, cy, 1, radius, true));
        });
      } else {
        if (group.length > 1)
          svg += `<circle class="halo" cx="${x}" cy="${wire}" r="7" opacity="${opacity}"/>`;
        keep(group[0], this.dot(group[0], x, wire, opacity, radius, false));
      }
    }
    svg += onTop;

    svg += this.questions(wire);
    svg += `</svg>`;

    // The year is written once, under the moment picked, and nowhere else: the
    // words carry no date and the ends of the line carry none either (picked
    // mockup, A).
    const picked = marks.find((m) => m.event.id === this.selected);
    const html = picked
      ? `<div class="ss-yr on" style="left:${yearLeft(picked.x, 0, width)}px;` +
        `top:${YEAR_TOP}px;width:${YEAR_W}px;text-align:center">` +
        `${esc(this.yearOf(picked.event))}</div>`
      : "";

    let hits =
      `<button class="ss-hit" data-target="${Target.Band}" aria-label="what the coach named" ` +
      `style="left:${x0}px;top:${ROWS[0] + 1}px;width:${x1 - x0}px;height:${ZONE}px"></button>`;
    hits += this.zoneHits(marks, width, wire);
    hits += this.shelfHit(x1, wire);

    this.pin(height);
    this.host.innerHTML = `<div class="ss">${svg}${text}${html}${hits}</div>`;
    // CSS cannot reach the move language's SVG animations, so reduced motion
    // holds them on their first frame the same way it stops the rest
    if (still())
      this.host.querySelector("svg")?.pauseAnimations();
  }

  /** One invisible target per dot, or per dots drawn over one another, laid
   * where the line's taps read them. */
  private zoneHits(marks: Mark[], width: number, wire: number): string {
    const zoned = zones(marks, width);
    this.laid.zones = zoned.map((zone) => zone.marks);
    return dotLayers(zoned)
      .map((layer) => hitButton(layer, wire))
      .join("");
  }

  private dot(
    mark: Mark,
    x: string,
    cy: number,
    opacity: number,
    radius: number,
    lit: boolean,
  ): string {
    // Every moment on this line is a dot (ruled 2026-09-08). What kind of
    // moment it is — a guess at a date, a no-change, a direction, a nodal
    // moment — is drawn where there is room to read it, which is the board.
    const chosen = mark.event.id === this.selected;
    if (chosen) return `<circle class="dot on" cx="${x}" cy="${cy}" r="7"/>`;
    return `<circle class="dot${lit ? " lit" : ""}" cx="${x}" cy="${cy}" r="${lit ? 5 : radius}" opacity="${opacity}"/>`;
  }

  /** The words. A chosen moment says itself in full over three rows; otherwise
   * the moments the coach named take a row each, tied to their dots. */
  private labels(
    marks: Mark[],
    x0: number,
    x1: number,
    wire: number,
  ): { text: string; rowsLaid: LabelRow[] } {
    const chosen = marks.find((m) => m.event.id === this.selected);
    const wide = Math.floor((x1 - x0) / CH);
    if (chosen) {
      const event = chosen.event;
      const said = words(
        event.dateTime as string,
        event.dateCertainty,
        event.person_name,
        event.label,
      );
      const lines = wrap2(
        clip(said, Math.min(88, wide * ROWS.length)),
        wide,
      );
      const text = lines
        .map((line, i) =>
          line
            ? `<div class="ss-t on" ` +
              `style="left:${x0}px;top:${ROWS[i]}px;width:${x1 - x0}px">${esc(line)}</div>`
            : "",
        )
        .join("");
      // the words of the moment already picked are its label, so a tap on them
      // is a tap on it and picks it again rather than putting the picture down
      return {
        text,
        rowsLaid: lines
          .map((line, row) => ({ id: event.id, row, left: x0, width: x1 - x0, line }))
          .filter((r) => r.line)
          .map(({ id, row, left, width }) => ({ id, row, left, width })),
      };
    }
    // One cluster open and nothing picked in it: no words on the drawing. The
    // cluster's name is the title of the view, and its reason is behind the i
    // beside it (owner, 2026-09-09).
    if (this.focus) return { text: "", rowsLaid: [] };
    const spotlit = marks.filter((m) => this.named.includes(m.event.id));
    if (!spotlit.length) return { text: "", rowsLaid: [] };
    // A line says which month it was only where it has to: where two of the
    // moments being named fall in the same year and nothing else tells them
    // apart (picked mockup, A with C).
    const clash = sharedYears(spotlit.map((m) => m.event.dateTime as string));
    const laid = rows(
      spotlit.map((m) => ({
        id: m.event.id,
        x: m.x,
        text: words(
          m.event.dateTime as string,
          m.event.dateCertainty,
          m.event.person_name,
          m.event.label,
          clash.has((m.event.dateTime as string).slice(0, 4)),
        ),
      })),
      x0,
      x1,
    );
    const leaders = new Set<string>();
    let text = "";
    for (const row of laid) {
      const key = row.x.toFixed(1);
      if (!leaders.has(key)) {
        leaders.add(key);
        text += `<div class="ss-lead" style="left:${key}px;top:${ROWS[row.row] + 15}px;height:${wire - ROWS[row.row] - 15}px"></div>`;
      }
      if (!row.text) continue;
      text +=
        `<div class="ss-t on" style="left:${row.left.toFixed(1)}px;top:${ROWS[row.row]}px;` +
        `width:${row.width.toFixed(1)}px;text-align:${row.align}">${esc(row.text)}</div>`;
    }
    // A row with no room for words is not a row the thumb can pick.
    return {
      text,
      rowsLaid: laid
        .filter((r) => r.text)
        .map((r) => ({ id: r.id, row: r.row, left: r.left, width: r.width })),
    };
  }

  /** The bracket over the cluster the coach aimed at. It is only drawn when no
   * words are on the picture, because the words sit where it would go. */
  private bandMark(wire: number): string {
    if (!this.band) return "";
    const a = this.x(this.band.start);
    const b = this.x(this.band.end);
    return (
      `<rect class="span" x="${Math.min(a, b).toFixed(1)}" y="${wire - 14}" ` +
      `width="${Math.max(4, Math.abs(b - a)).toFixed(1)}" height="28" rx="6"/>`
    );
  }

  /** The one amber treatment: the record asking which of two things came first.
   *
   * It asks only where the two guess ranges touch. Where they do not, the
   * record knows the order and the dots' own places on the line say it, so
   * nothing is asked (DRAWABILITY rule 4). */
  private questions(wire: number): string {
    if (this.selected !== null || this.named.length) return "";
    const shown = new Set(this.shown().map((e) => e.id));
    return (this.data?.questions ?? [])
      .filter((q: Question) => shown.has(q.event_id) && this.ordered(q))
      .map((q: Question, i, all) => {
        const x = this.x(q.date);
        if (all.slice(0, i).some((other) => Math.abs(this.x(other.date) - x) < 16))
          return "";
        return `<text class="qm small" x="${x.toFixed(1)}" y="${wire - 16}" text-anchor="middle">?</text>`;
      })
      .join("");
  }

  /** Whether the record still has to ask about this pair: it does only while
   * the two guess ranges touch. */
  private ordered(q: Question): boolean {
    const one = this.event(q.event_id);
    const other = this.event(q.other_event_id);
    if (!one?.dateTime || !other?.dateTime) return true;
    return rangesTouch(
      { date: one.dateTime, certainty: one.dateCertainty },
      { date: other.dateTime, certainty: other.dateCertainty },
    );
  }

  /** The amber question past the right end of the line, for what has no date.
   * It sits above the wire where there is room for it and on the wire where
   * there is not, which is the case at the resting level. */
  private shelfHit(x1: number, wire: number): string {
    // The "?" past the end of the line is the undated shelf: facts the record
    // holds but cannot place (DRAWABILITY, R-0047). Hidden on Patrick's word,
    // 2026-09-21, because nothing tells a first-time reader what it means; the
    // shelf itself stays, reached from the events list. Drop the next line to
    // bring the marker back.
    if (HIDE_SHELF_MARK) return "";
    if (!this.data?.shelf.length) return "";
    const above = wire - ZONE - 4;
    const top = above >= 0 ? above : wire - ZONE / 2;
    // The target is 44 wide and sits past the end of the line, so it has to be
    // held inside the frame: a hair over the edge and tapping it scrolls the
    // whole page sideways to reveal it.
    const left = Math.min(x1 - 26, this.width - ZONE);
    return (
      `<button class="ss-hit shelf" data-target="${Target.Shelf}" ` +
      `aria-label="things with no date yet" ` +
      `style="left:${left}px;top:${top}px;width:${ZONE}px;height:${ZONE}px">?</button>`
    );
  }

  /** The next moment a tap on a zone lands on. */
  next(index: number, current: number | null): number | null {
    return cycle(this.inZone(index), current);
  }
}
