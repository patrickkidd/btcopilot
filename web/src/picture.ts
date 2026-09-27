import {
  board,
  castOfSteps,
  dateOf,
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
  rows,
  words,
  wrap2,
  zones,
} from "./spotlight";
import {
  ItemKind,
  Spotlight,
  Touch,
  ViewKind,
  type Cluster,
  type Person,
  type Question,
  type Timeline,
  type TimelineEvent,
  type View,
} from "./types";
import { stronger, type Made } from "./turn";

/** Patrick, 2026-09-21: the undated shelf's "?" stays off until it explains itself. */
const HIDE_SHELF_MARK = true;
/** The ratified hold: 1000ms after each move before the prose continues. */
const HOLD_MS = 1000;
const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** The pinned picture: the sentence spotlight the owner converged on
 * (OWNER_RULINGS 2026-09-02). A wire with a dot per moment; the moments the
 * coach's latest message names are drawn bright with their words above them,
 * tied to their dots, and everything else recedes to a dim dot. A tap on the
 * wire steps through the moments under the thumb and that moment writes itself
 * out in full. The people appear only while a play-by-play walks the moves. */

/** The picture region is ONE height for the whole line and a cluster open on
 * it, because a tap on the picture must never move a bubble; only entering the
 * moves board, which is a screen of its own, may change the layout. */
/** The least space left between two cluster boxes that would otherwise touch. */
const BOX_GAP = 6;
/** How far a box reaches past the moments it holds, at each end. */
const BOX_PAD = 10;
/** IBM Plex Mono's advance at the 10.5px the years inside a box are written. */
const YEAR_CH = 6.3;
/** The resting line is never drawn wider than this many screens: past it the
 * scale coarsens rather than the line reaching further (R-0381). */
const REACH = 2;

/** A cluster's box reaches from under the two rows of words above the line to
 * the year under a picked dot, so it never runs into either (R-0181). */
const BOX_Y = ROWS[1] + ROW_H;
const BOX_H = YEAR_TOP - BOX_Y;
/** A dot on the line. */
const DOT_R = 4.5;
/** The least space between two dot centres inside a box for the two to read as
 * two rather than as one solid bar. */
const DOT_GAP = 11;
/** A gap of this many years or more between clusters earns the amber question. */
const GAP_YEARS = 4;

/** A cluster's years at a glance, two digits each, as the converged mockup
 * writes them: "93–97". One year when it starts and ends in the same one. */
function shortYears(start: string, end: string): string {
  const a = start.slice(2, 4);
  const b = end.slice(2, 4);
  return a === b ? a : `${a}\u2013${b}`;
}

/** A cluster's years as the path names it: "2009–10", in full where the
 * century changes, one year when it starts and ends in the same one. */
export function spanYears(start: string, end: string): string {
  const [a, b] = [start, end].map((iso) => iso.slice(0, 4));
  if (a === b) return a;
  return `${a}\u2013${a.slice(0, 2) === b.slice(0, 2) ? b.slice(2) : b}`;
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
    const dots = cluster.count ?? 0;
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

/** The picture's levels. The whole line and a cluster open on it are one
 * drawing (R-0538); the board, the about page and a comparison are modes of
 * the cluster level. */
export enum Level {
  /** Nothing named yet: the whole line at a glance, one box per cluster. */
  Rest = "rest",
  /** The same line with a cluster open, or what the coach named, lit. */
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

/** How many characters of a moment the path gives its last step. */
const TOLD_CH = 20;

/** A moment picked, as the path names it: the first name and what happened,
 * "Catherine died", and whatever of its words that leaves over, which the line
 * writes instead (R-0540). The path's words end on a whole word, and never on
 * a small one. */
export function told(who: string, label: string): [string, string] {
  const first = who.split(" ")[0];
  const all = (!first || label.startsWith(first) ? label : `${first} ${label}`).split(" ");
  let n = 1;
  while (n < all.length && all.slice(0, n + 1).join(" ").length <= TOLD_CH) n += 1;
  while (n > 1 && n < all.length && all[n - 1].length <= 2) n -= 1;
  return [all.slice(0, n).join(" "), all.slice(n).join(" ")];
}

/** What each mode inside a cluster is called in the path. */
const MODE: Partial<Record<Level, string>> = {
  [Level.Board]: "explain",
  [Level.About]: "about",
  [Level.Compare]: "compare",
};

/** The path over the line, from the whole timeline down to where the reader
 * is: the cluster open by its years, then the mode it is in or the moment
 * picked (R-0540). */
export function trail(
  level: Level,
  cluster: { start: string; end: string } | null,
  picked: string | null,
): string[] {
  const last = MODE[level] ?? picked;
  return [
    "Timeline",
    ...(cluster ? [spanYears(cluster.start, cluster.end)] : []),
    ...(last ? [last] : []),
  ];
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
 * top: the loose events' dots, then the cluster boxes, so a tap anywhere in a
 * box opens it, even on a loose event dated inside its years. */
export const restLayers = (boxes: Layer[], dots: Layer[]): Layer[] => [...dots, ...boxes];

/** A target as the button the thumb lands on, ZONE tall on the wire. */
const hitButton = (layer: Layer, wire: number): string =>
  `<button class="ss-hit" data-target="${layer.target}" data-index="${layer.index}" ` +
  `aria-label="${esc(layer.label)}" ` +
  `style="left:${layer.left.toFixed(1)}px;top:${wire - ZONE / 2}px;` +
  `width:${layer.width.toFixed(1)}px;height:${ZONE}px"></button>`;

/** The words over the line as one target, read by the row a tap lands on:
 * the words of the event picked lead to where it was said (R-0192), and blank
 * ground between them puts the picture down. */
const bandHit = (left: number, width: number): string =>
  `<button class="ss-hit" data-target="${Target.Band}" aria-label="what the coach named" ` +
  `style="left:${left.toFixed(1)}px;top:${ROWS[0] + 1}px;width:${width.toFixed(1)}px;height:${ZONE}px"></button>`;

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

/** How deep each level sits. Only something entirely new slides: the about
 * page and the board arrive over the line and go back off it. Picking a
 * cluster or a moment on the line, putting it down, and two moments face to
 * face change the line in place and slide nothing (R-0542). */
const DEPTH: Record<Level, number> = {
  [Level.Rest]: 0,
  [Level.Wire]: 0,
  [Level.Compare]: 0,
  [Level.Board]: 1,
  [Level.About]: 1,
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
const CONTROLS = "button, input, select, textarea, a[href]";

/** A control as a plain span that looks the same: its classes, its inline
 * style and what it says, nothing it does. */
function plain(control: Element): HTMLElement {
  const span = document.createElement("span");
  span.className = control.className;
  span.setAttribute("style", control.getAttribute("style") ?? "");
  span.innerHTML = control.innerHTML;
  return span;
}

function snapshot(region: HTMLElement, ...skip: Element[]): HTMLElement {
  const lay = document.createElement("div");
  lay.className = "slide-lay";
  // a picture of the level, not the level: nothing in it can be found, read
  // out or pressed, so the live controls are the only ones on the page
  lay.inert = true;
  lay.setAttribute("aria-hidden", "true");
  for (const child of [...region.children]) {
    if (skip.includes(child) || child.classList.contains("slide-lay")) continue;
    const copy = child.cloneNode(true) as HTMLElement;
    for (const el of [copy, ...copy.querySelectorAll("[id]")]) el.removeAttribute("id");
    for (const el of copy.querySelectorAll("[data-target]")) el.removeAttribute("data-target");
    for (const el of copy.querySelectorAll("[tabindex], [role]")) {
      el.removeAttribute("tabindex");
      el.removeAttribute("role");
    }
    // every control becomes a plain element drawn the same way, so the copy
    // holds nothing a reader, a screen reader or a test could take for one
    for (const el of copy.querySelectorAll(CONTROLS)) el.replaceWith(plain(el));
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

/** The events these ids name, as the play-by-play steps them: the dated ones
 * in date order, which is the record's own, and each undated one right after
 * the event stored before it, or first when it is stored first. */
export function inOrder(events: TimelineEvent[], ids: number[]): TimelineEvent[] {
  const named = events.filter((e) => ids.includes(e.id));
  const stored = ids.flatMap((id) => named.filter((e) => e.id === id));
  const out = named.filter((e) => dateOf(e) !== null);
  stored.forEach((e, i) => {
    if (dateOf(e) === null) out.splice(i ? out.indexOf(stored[i - 1]) + 1 : 0, 0, e);
  });
  return out;
}

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
 * cluster the cluster opens; outside every cluster it is picked on the whole
 * line, the clusters kept as they are drawn (R-0235, R-0538). The old chip
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
  /** What the coach's tool calls did to each event this turn, kept until the
   * next message (R-0539); the ones just touched flash as they land. */
  private touched = new Map<number, Touch>();
  private fresh = new Set<number>();
  /** Events removed this turn, drawn where they were until the next message. */
  private gone: TimelineEvent[] = [];
  private band: { start: string; end: string } | null = null;
  /** Where the resting line stands after the next draw, and the moment it goes
   * to when the coach's words name one. */
  private park = Park.Present;
  private aimed: number | null = null;
  private focus: Cluster | null = null;
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

  /** Colour what one line of what the coach did has just touched, at the
   * moment that line lands, on the line as it stands: nothing opens and
   * nothing moves but the line, to the first it wrote (R-0539). A person is
   * lit wherever people are drawn, which today is the board. `gone` is what
   * the line removed, as the record held it before. */
  light(made: Made[], gone: TimelineEvent[] = []): void {
    const moments = made.filter((one) => one.kind === ItemKind.Event);
    this.fresh = new Set(moments.map((one) => Number(one.id)));
    for (const one of moments) {
      const id = Number(one.id);
      const had = this.touched.get(id);
      this.touched.set(id, had ? stronger(had, one.touch) : one.touch);
    }
    this.gone.push(...gone);
    this.litPeople = made
      .filter((one) => one.kind === ItemKind.Person)
      .map((one) => Number(one.id));
    const wrote = moments.find((one) => one.touch !== Touch.Read);
    if (wrote) this.aim(Number(wrote.id));
    this.render();
    this.fresh.clear();
  }

  /** A read looked at these events. */
  read(ids: number[]): void {
    this.light(ids.map((id) => ({ kind: ItemKind.Event, id: String(id), touch: Touch.Read })));
  }

  /** The next message has arrived: what the last reply touched is drawn the
   * way the line draws it again. */
  untouch(): void {
    this.touched.clear();
    this.gone = [];
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
    this.render();
  }

  setData(data: Timeline): void {
    this.data = data;
    // the record has changed under the picture, which is what a reply leaves
    // behind: the line goes back to the present (R-0381)
    this.park = Park.Present;
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
    this.moves = movesIn(inOrder(this.data?.events ?? [], eventIds));
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
      if (!cluster || !this.openBoard(cluster.play_ids, clusterId)) return;
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
    return movesIn(inOrder(this.data?.events ?? [], eventIds)).length;
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

  /** The cluster the reader is in: the one open on the line, or the one the
   * board is showing. */
  private within(): Cluster | null {
    if (this.focus) return this.focus;
    const id = this.cluster;
    return id === null
      ? null
      : (this.data?.clusters.find((c) => c.id === id || c.cluster_ids.includes(id)) ?? null);
  }

  /** The path from the whole timeline to where the reader is (R-0540). */
  path(): string[] {
    const picked = this.level === Level.Rest || this.level === Level.Wire ? this.event(this.selected) : null;
    return trail(
      this.level,
      this.level === Level.Rest ? null : this.within(),
      picked && told(picked.person_name, picked.label)[0],
    );
  }

  /** Back to one step of the path: the whole timeline, or the cluster with
   * nothing picked and no mode open. */
  back(step: number): void {
    const open = this.within();
    if (!step || !open) {
      this.dismiss();
      return;
    }
    this.moves = [];
    this.cast = [];
    this.at = 0;
    this.spotlight(open.event_ids);
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
    this.level = Level.Rest;
    this.moves = [];
    this.at = 0;
    this.pair = null;
    this.touched.clear();
    this.gone = [];
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

  private dated(): TimelineEvent[] {
    return (this.data?.events ?? []).filter((e) => !!dateOf(e));
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

  /** A mode of the cluster, as a card laid over the chat from the top of the
   * picture: as tall as what it holds, while the picture and the header keep
   * their height and the bubbles stay where they are under it (R-0460). */
  private card(markup: string): void {
    this.laid = { zones: [], rows: [] };
    this.pin(PIC_H);
    this.host.innerHTML = `<div class="card">${markup}</div>`;
  }

  /** The picture region owns its level's height, so the chat below it only ever
   * moves on a deliberate level change and never on a tap (LAYOUT CONTRACT). */
  private pin(height: number): void {
    this.host.style.height = `${height}px`;
  }

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
    this.card(
      `<div class="ss about">` +
        (why ? `<p class="ab-why">${esc(why)}</p>` : "") +
        `<p class="ab-span">${esc(fullYears(cluster.start, cluster.end))} · ` +
        `${moments.length} event${moments.length === 1 ? "" : "s"}</p>` +
        `<ul class="ab-list">${rows}</ul></div>`,
    );
  }

  /** The line: one drawing for the whole timeline and a cluster open on it
   * (R-0538). One box per cluster on a wire that never moves, its years in
   * it and its moments as dots; the moments no cluster claims are dots of
   * their own; the amber question where the record has a long gap it cannot
   * account for. What the reader opened or the coach named is lit and the
   * rest is dimmed, never taken away. A moment picked writes itself out above
   * the line with its year under its dot, and what the coach touched this
   * turn keeps its colour (R-0539). A tap on a box opens its cluster; the
   * open cluster's dots and the loose ones pick. Converged mockup:
   * crowded-cluster/timeline-converged.html renderRest. */
  private renderLine(): void {
    const screen = this.width;
    const dated = this.dated();
    this.laid = { zones: [], rows: [] };
    this.pin(PIC_H);

    // What has no date exists at every level: it is the one thing on the
    // picture the record is still asking about.
    const shelf = this.shelfHit(screen - X_PAD, WIRE);

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
    const first = years(dated[0].dateTime as string);
    const last = years(dated[dated.length - 1].dateTime as string);
    const span = last - first || 1;
    const at = (iso: string) =>
      dated.length === 1
        ? (x0 + x1) / 2
        : x0 + ((years(iso) - first) / span) * (x1 - x0);
    const open = this.level === Level.Wire ? this.focus : null;
    const lit = new Set(this.named);
    if (this.selected !== null) lit.add(this.selected);
    const dim = ` opacity="${baseOpacity(dated.length, lit.size)}"`;

    let svg =
      `<svg viewBox="0 0 ${width} ${PIC_H}" height="${PIC_H}" preserveAspectRatio="xMinYMin meet">` +
      this.bandMark(at) +
      `<line class="wire" x1="${x0}" y1="${WIRE}" x2="${x1}" y2="${WIRE}"/>`;
    // The moment picked is drawn last, so it is on top of whatever crowds it
    // (picked mockup Q1).
    let onTop = "";
    // A dot takes the colour of what the coach did to it this turn; a read is
    // left to the box when the read took in the whole cluster.
    const dot = (id: number | null, x: number, boxRead = false): void => {
      const touch = id === null ? undefined : this.touched.get(id);
      const shown = touch === Touch.Read && boxRead ? undefined : touch;
      const on = id !== null && id === this.selected;
      const named = !on && id !== null && this.named.includes(id);
      const cls = ["dot", on && "on", named && "lit", shown, shown && this.fresh.has(id as number) && "flash"]
        .filter(Boolean)
        .join(" ");
      const faded = lit.size && !shown && (id === null || !lit.has(id)) ? dim : "";
      const drawn =
        `<circle class="${cls}"${id === null ? "" : ` data-event="${id}"`} ` +
        `cx="${x.toFixed(1)}" cy="${WIRE}" r="${on ? 7 : DOT_R}"${faded}/>`;
      if (on) onTop += drawn;
      else svg += drawn;
    };
    const marks: Mark[] = [];
    const picks: Mark[] = [];
    const boxes: Layer[] = [];
    let openX: number | null = null;
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
      const opened = cluster.id === open?.id;
      if (opened) openX = left + boxWidth / 2;
      // a read that took in every moment in the cluster greys the box rather
      // than every dot in it (R-0539)
      const read =
        cluster.event_ids.every((id) => this.touched.has(id)) &&
        cluster.event_ids.some((id) => this.touched.get(id) === Touch.Read);
      const state = [
        opened ? "open" : lit.size ? "dim" : "",
        read ? "read" : "",
        read && cluster.event_ids.some((id) => this.fresh.has(id)) ? "flash" : "",
      ]
        .filter(Boolean)
        .map((one) => ` ${one}`)
        .join("");
      svg +=
        `<g class="ep-g${state}">` +
        `<rect class="ep" x="${left.toFixed(1)}" y="${BOX_Y}" ` +
        `width="${boxWidth.toFixed(1)}" height="${BOX_H}" rx="8"/>` +
        `<rect class="ep-edge" x="${left.toFixed(1)}" y="${BOX_Y}" ` +
        `width="${boxWidth.toFixed(1)}" height="${BOX_H}" rx="8"/>` +
        // the open cluster's years are the path's, and a figure is written
        // once on a screen
        (opened
          ? ""
          : `<text class="ep-yrs" x="${middle.toFixed(1)}" y="${WIRE - 7}" text-anchor="middle">` +
            `${esc(shortYears(cluster.start, cluster.end))}</text>`) +
        `</g>`;
      // every event in the box is a dot, however many there are: a crowded
      // box carries no count (R-0376)
      const inBox = dated.filter((e) => cluster.event_ids.includes(e.id));
      const whole = inBox.length === cluster.count;
      const when = whole
        ? inBox.map((e) => at(e.dateTime as string))
        : Array.from({ length: cluster.count }, (_, j) =>
            cluster.count > 1 ? a + ((b - a) * j) / (cluster.count - 1) : middle,
          );
      dotXs(when, left, boxWidth).forEach((x, j) => {
        const event = whole ? inBox[j] : null;
        dot(event?.id ?? null, x, read);
        if (!event) return;
        marks.push({ event, x });
        if (opened) picks.push({ event, x });
      });

      const next = clusters[i + 1];
      if (next && years(next.start) - years(cluster.end) >= GAP_YEARS) {
        const gap = (at(next.start) + b) / 2;
        svg +=
          `<text class="qm small" x="${gap.toFixed(1)}" y="${WIRE + 4}" ` +
          `text-anchor="middle">?</text>`;
      }

      // the open cluster's own dots pick; every other box opens its cluster,
      // and a box may be narrower than a thumb, so the target is grown to the
      // floor
      if (opened) return;
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
    for (const event of loose(dated, clusters)) {
      const x = at(event.dateTime as string);
      dot(event.id, x);
      marks.push({ event, x });
      picks.push({ event, x });
    }
    // what this turn removed stays where it was, in its colour, until the next
    // message
    const kept = new Set(dated.map((e) => e.id));
    for (const event of this.gone)
      if (!kept.has(event.id) && dateOf(event)) dot(event.id, at(event.dateTime as string));
    svg += this.questions(at, kept) + onTop + `</svg>`;

    const zoned = zones(picks, width);
    this.laid.zones = zoned.map((zone) => zone.marks);
    const hits = restLayers(boxes, dotLayers(zoned))
      .map((layer) => hitButton(layer, WIRE))
      .join("");

    const aimed = marks.find((m) => m.event.id === this.aimed);
    // the line goes to what was named: the open cluster's box when the moment
    // is in it, otherwise the moment itself
    const onX = aimed ? (open?.event_ids.includes(aimed.event.id) ? openX : aimed.x) : null;
    // where the line comes to rest, so the words of a picked moment are
    // written across the stretch the reader will be looking at
    const shows = this.stands({ width, screen }, held, onX);
    const said = this.labels(marks, shows + X_PAD, shows + screen - X_PAD, WIRE);
    this.laid.rows = said.rowsLaid;
    const chosen = marks.find((m) => m.event.id === this.selected);
    // With a cluster open and nothing picked, the words over the line are the
    // cluster's own name, so the reader can find what is open (R-0538).
    // It stands on the picture rather than the line that slides under it, so
    // it is always inside the picture whichever cluster is open.
    const title =
      !said.text && open && !chosen
        ? `<div class="ss-t ss-name" style="left:${X_PAD}px;top:${ROWS[0]}px;` +
          `width:${screen - 2 * X_PAD}px">${esc(open.title || open.label)}</div>`
        : "";
    // The band lies over the words and under the dots' own targets.
    const words = said.text ? said.text + bandHit(shows + X_PAD, screen - 2 * X_PAD) : "";

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
    // again as it slides. They belong to a line long enough to slide, and give
    // way to the year of a moment picked.
    const ends =
      width > screen
        ? `<div class="ss-yrs"><span></span><span></span></div>`
        : "";

    this.host.innerHTML =
      `<div class="ss"><div class="ss-scroll"><div class="ss-line" style="width:${width.toFixed(1)}px">` +
      `${svg}${words}${hits}${snaps}</div></div>${ends}${title}${shelf}</div>`;
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

  /** The cluster a resting tap landed on. */
  clusterAt(index: number): Cluster | undefined {
    return this.restClusters()[index];
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
    this.card(
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
        : ""),
    );
    for (const id of this.litPeople)
      this.host.querySelector(`.node[data-person="${id}"]`)?.classList.add("lit");
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
    this.renderLine();
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
      // the path already says who and what happened: the line says only what
      // it leaves out, the date first (no word twice)
      const said = [
        dateText(event.dateTime as string, event.dateCertainty),
        told(event.person_name, event.label)[1],
      ]
        .filter(Boolean)
        .join(" \u00b7 ");
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
  private bandMark(at: (iso: string) => number): string {
    if (!this.band) return "";
    const a = at(this.band.start);
    const b = at(this.band.end);
    return (
      `<rect class="span" x="${Math.min(a, b).toFixed(1)}" y="${WIRE - 14}" ` +
      `width="${Math.max(4, Math.abs(b - a)).toFixed(1)}" height="28" rx="6"/>`
    );
  }

  /** The one amber treatment: the record asking which of two things came first.
   *
   * It asks only where the two guess ranges touch. Where they do not, the
   * record knows the order and the dots' own places on the line say it, so
   * nothing is asked (DRAWABILITY rule 4). */
  private questions(at: (iso: string) => number, shown: Set<number>): string {
    if (this.selected !== null || this.named.length) return "";
    return (this.data?.questions ?? [])
      .filter((q: Question) => shown.has(q.event_id) && this.ordered(q))
      .map((q: Question, i, all) => {
        const x = at(q.date);
        if (all.slice(0, i).some((other) => Math.abs(at(other.date) - x) < 16))
          return "";
        return `<text class="qm small" x="${x.toFixed(1)}" y="${WIRE - 16}" text-anchor="middle">?</text>`;
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
