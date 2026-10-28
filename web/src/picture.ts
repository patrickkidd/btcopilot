import { book } from "./case";
import { morph } from "./morph";
import { nameOnly } from "./caseview";
import { DateCertainty } from "./certainty";
import { called } from "./diagram";
import { closeX, esc, pan, still } from "./dom";
import { Shift } from "./marks";
// this line draws pills, dots and the wire
import {
  CH,
  PIC_H,
  ROWS,
  ROW_H,
  WIRE,
  X_PAD,
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
  EventKind,
  ItemKind,
  Spotlight,
  Touch,
  ViewKind,
  type Cluster,
  type Timeline,
  type TimelineEvent,
  type View,
} from "./types";
import { stronger, type Made } from "./turn";

/** Patrick, 2026-09-21: the undated shelf's "?" stays off until it explains itself. */
const HIDE_SHELF_MARK = true;

/** The pinned picture: the sentence spotlight the owner converged on
 * (OWNER_RULINGS 2026-09-02). A wire with a dot per moment; the moments the
 * coach's latest message names are drawn bright with their words above them,
 * tied to their dots, and everything else recedes to a dim dot. A tap on the
 * wire steps through the moments under the thumb and that moment writes itself
 * out in full. The people appear only while a play-by-play walks the moves. */

/** The picture region is ONE height for the whole line and a cluster open on
 * it, because a tap on the picture must never move a bubble; the play-by-play
 * is a drawer of its own over it (R-0570). */
/** The least space left between two cluster pills that would otherwise touch. */
const BOX_GAP = 6;
/** How far a pill reaches past the events it holds, at each end. */
const BOX_PAD = 10;
/** IBM Plex Mono's advance at the 10.5px the years under the line are written. */
const YEAR_CH = 6.3;
/** A dot on the line. */
const DOT_R = 4.5;
/** How tall a cluster's pill is drawn on the line. */
const PILL_H = 16;
/** A tap target on the line reaches from under the words' first row to the
 * bottom of the picture, so the thumb need not find the line itself (R-0544). */
const HIT_TOP = ROWS[1];
/** A tap target reaches no further than this either side of its mark's middle. */
const HIT_REACH = 60;
/** The baseline of the years under the line. */
const RULER_Y = 68;
/** The resting line is never drawn wider than this many screens: past it the
 * scale coarsens rather than the line reaching further (R-0381). */
const REACH = 2;
/** The least space between two dot centres inside a box for the two to read as
 * two rather than as one solid bar. */
const DOT_GAP = 11;

/** One mark on the line: a cluster as one pill over its years with nothing
 * drawn inside it, or an event no cluster claims as a dot (R-0543). */
export interface Pill {
  cluster: Cluster | null;
  event: TimelineEvent | null;
  left: number;
  right: number;
}

type Span = { left: number; right: number };

const middle = (mark: Span) => (mark.left + mark.right) / 2;

/** The marks on the line in order across it: a pill per cluster and a dot per
 * dated event no cluster claims. The clusters come in time order. A pill
 * reaches a little past the years it holds, and gives way where that would
 * touch the next pill or a dot beside it, leaving a gap, but never gives up
 * its own years. */
export function pills(
  clusters: Cluster[],
  dated: TimelineEvent[],
  at: (iso: string) => number,
): Pill[] {
  const bars: Pill[] = edges(clusters, at).map((edge, i) => ({
    cluster: clusters[i],
    event: null,
    ...edge,
  }));
  const dots: Pill[] = loose(dated, clusters).map((event) => {
    const x = at(event.dateTime as string);
    return { cluster: null, event, left: x - DOT_R, right: x + DOT_R };
  });
  for (const bar of bars) {
    const [start, end] = [at(bar.cluster!.start), at(bar.cluster!.end)];
    for (const dot of dots) {
      const x = middle(dot);
      if (x < start && dot.right + BOX_GAP > bar.left)
        bar.left = Math.min(start, dot.right + BOX_GAP);
      if (x > end && dot.left - BOX_GAP < bar.right)
        bar.right = Math.max(end, dot.left - BOX_GAP);
    }
  }
  return [...bars, ...dots].sort((a, b) => middle(a) - middle(b));
}

/** The one colour a pill takes for what the coach did to the events inside it
 * this turn: the strongest touch wins (R-0544). */
export function strongest(ids: number[], touched: Map<number, Touch>): Touch | null {
  return ids
    .map((id) => touched.get(id))
    .filter((one): one is Touch => !!one)
    .reduce<Touch | null>((a, b) => (a ? stronger(a, b) : b), null);
}

/** A cluster's years at a glance, two digits each, as the converged mockup
 * writes them: "93–97". One year when it starts and ends in the same one. */
function shortYears(start: string, end: string): string {
  const a = start.slice(2, 4);
  const b = end.slice(2, 4);
  return a === b ? a : `${a}\u2013${b}`;
}

/** Where each cluster reaches on the line: a little past the moments it holds,
 * and where two clusters a month apart would then touch, the two give way to
 * each other and leave a gap between them. */
function edges(clusters: { start: string; end: string }[], at: (iso: string) => number): Span[] {
  const spans = clusters.map((cluster) => ({
    left: at(cluster.start) - BOX_PAD,
    right: at(cluster.end) + BOX_PAD,
  }));
  for (let i = 1; i < spans.length; i += 1) {
    if (spans[i].left - spans[i - 1].right >= BOX_GAP) continue;
    const seam = (spans[i - 1].right + spans[i].left) / 2;
    spans[i - 1].right = seam - BOX_GAP / 2;
    spans[i].left = seam + BOX_GAP / 2;
  }
  return spans;
}

/** How wide the resting line is drawn, for a picture this many pixels wide.
 *
 * Wide enough that no two cluster boxes run into each other and every box keeps
 * room for the years written in it, and never more than two screens: on a
 * record too crowded for that the scale coarsens rather than the line reaching
 * further, so the whole history is always one or two swipes (R-0381). The
 * clusters come in time order; the dates are every dated moment, in order. */
export function restWidth(
  clusters: { start: string; end: string; event_ids?: number[] }[],
  dates: string[],
  screen: number,
): number {
  if (dates.length < 2) return screen;
  const span = years(dates[dates.length - 1]) - years(dates[0]);
  if (span <= 0) return screen;
  let scale = (screen - 2 * X_PAD) / span;
  clusters.forEach((cluster, i) => {
    // room for the dots drawn, which are its dated events only
    const dots = cluster.event_ids?.length ?? 0;
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

/** How far each mark's tap target reaches across the line: halfway to its
 * neighbours and no further than HIT_REACH from its middle, but always over
 * the whole mark, so a tap anywhere on a pill opens it (R-0537, R-0544). */
export function reach(marks: Span[], width: number): Span[] {
  return marks.map((mark, i) => {
    const c = middle(mark);
    const before = i ? (c + middle(marks[i - 1])) / 2 : 0;
    const after = i < marks.length - 1 ? (c + middle(marks[i + 1])) / 2 : width;
    return {
      left: Math.max(0, Math.min(mark.left, Math.max(before, c - HIT_REACH))),
      right: Math.min(width, Math.max(mark.right, Math.min(after, c + HIT_REACH))),
    };
  });
}

/** Where a year sits under its tick, as the SVG text-anchor takes it. */
enum Anchor {
  Start = "start",
  Middle = "middle",
  End = "end",
}

/** One year written under the line. */
export interface Tick {
  year: number;
  x: number;
  anchor: Anchor;
}

/** The years under the line: the first and last at its two ends, and the
 * decades between them, or every second decade where ten years is too narrow
 * to write, each left off where it would touch another (R-0543). */
export function ruler(
  y0: number,
  y1: number,
  at: (iso: string) => number,
  x0: number,
  x1: number,
): Tick[] {
  if (y0 === y1) return [{ year: y0, x: (x0 + x1) / 2, anchor: Anchor.Middle }];
  const wide = 4 * YEAR_CH;
  const ticks: Tick[] = [
    { year: y0, x: x0, anchor: Anchor.Start },
    { year: y1, x: x1, anchor: Anchor.End },
  ];
  const span = (t: Tick) => {
    const left =
      t.anchor === Anchor.Start ? t.x : t.anchor === Anchor.End ? t.x - wide : t.x - wide / 2;
    return [left - 4, left + wide + 4];
  };
  const step = at(`${y0 + 10}-01-01`) - at(`${y0}-01-01`) >= 62 ? 10 : 20;
  for (let year = Math.ceil((y0 + 1) / step) * step; year < y1; year += step) {
    const tick: Tick = { year, x: at(`${year}-01-01`), anchor: Anchor.Middle };
    const [l, r] = span(tick);
    if (ticks.some((t) => l < span(t)[1] && r > span(t)[0])) continue;
    ticks.push(tick);
  }
  return ticks.sort((a, b) => a.x - b.x);
}

/** A cluster's years as the path names it: "2009–10", in full where the
 * century changes, one year when it starts and ends in the same one. */
export function spanYears(start: string, end: string): string {
  const [a, b] = [start, end].map((iso) => iso.slice(0, 4));
  if (a === b) return a;
  return `${a}\u2013${a.slice(0, 2) === b.slice(0, 2) ? b.slice(2) : b}`;
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
      ? dateText(event.dateTime, event.dateCertainty, event.datePrecision)
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
 * drawing (R-0538); the about page and a comparison are modes of the cluster
 * level. The play-by-play is its own drawer (R-0570). */
export enum Level {
  /** Nothing named yet: the whole line at a glance, one box per cluster. */
  Rest = "rest",
  /** The same line with a cluster open, or what the coach named, lit. */
  Wire = "wire",
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
/** What stands between the parts of a moment's words. */
const SEP = "·";

/** A moment picked, as the path names it: the first name and what happened,
 * "Delphine died" or, from the title "Stopped calling", "Ben stopped calling",
 * and whatever of its words that leaves over, which the line
 * writes instead (R-0540). A title that starts with someone else's name in
 * the family gets the name, a colon, then the title as written: "Ben: Marcus
 * moved out" (R-0730). The path's words end on a whole word, and never on a
 * small one. */
export function told(who: string, label: string, family: string[] = []): [string, string] {
  const first = who.split(" ")[0];
  // a title reads on its own (R-0681); after a name it runs on as one sentence
  const run = /^[A-Z][a-z]/.test(label) ? label.charAt(0).toLowerCase() + label.slice(1) : label;
  const lead = label.split(" ")[0].replace(/[^\p{L}'-]/gu, "");
  const named = family.includes(lead) ? `${first}: ${label}` : `${first} ${run}`;
  const all = (!first || label.startsWith(first) ? label : named).split(" ");
  let n = 1;
  while (n < all.length && all.slice(0, n + 1).join(" ").length <= TOLD_CH) n += 1;
  while (n > 1 && n < all.length && all[n - 1].length <= 2) n -= 1;
  // a separator in the words is dropped where they are cut, so the line's
  // own separator before the rest is never doubled: "2011 · of lung cancer"
  const rest = all.slice(n);
  while (rest[0] === SEP) rest.shift();
  return [all.slice(0, n).join(" "), rest.join(" ")];
}

/** What each mode inside a cluster is called in the path. */
const MODE: Partial<Record<Level, string>> = {
  [Level.About]: "about",
  [Level.Compare]: "compare",
};

type Named = { title: string; label?: string; start: string; end: string };

/** The open cluster's name, or its years for a cluster with no name of its own. */
export const clusterName = (c: Named) => nameOnly(c) || (c.label ?? spanYears(c.start, c.end));

/** The open cluster as the path names it: its name and years, "Every mark \u00b7
 * 1972\u201399", the years written once for a cluster with no name (R-0767). */
export const clusterStep = (c: Named) => {
  const years = c.label ?? spanYears(c.start, c.end);
  const name = clusterName(c);
  return name === years ? years : `${name} \u00b7 ${years}`;
};

/** The path over the line, from the whole timeline down to where the reader
 * is: the cluster open by its name and years, then the mode it is in or the event
 * picked (R-0540, R-0767). */
export function trail(level: Level, cluster: Named | null, picked: string | null): string[] {
  const last = MODE[level] ?? picked;
  return [
    "Timeline",
    ...(cluster ? [clusterStep(cluster)] : []),
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
  /** The about page's close button, which goes where the path's cluster step
   * goes. */
  Close = "close",
  /** Anywhere on the picture that is not a moment or a label. */
  Ground = "ground",
  /** A dot on a cluster's page; its index is the event's id. */
  Dot = "dot",
}

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

/** A target as the button the thumb lands on, from under the path to the
 * bottom of the picture (R-0544). */
const hitButton = (layer: Layer): string =>
  `<button class="ss-hit" data-target="${layer.target}" data-index="${layer.index}" ` +
  `aria-label="${esc(layer.label)}" ` +
  `style="left:${layer.left.toFixed(1)}px;top:${HIT_TOP}px;` +
  `width:${layer.width.toFixed(1)}px;height:${PIC_H - HIT_TOP - 1}px"></button>`;

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
 * page arrives over the line and goes back off it. Picking a
 * cluster or a moment on the line, putting it down, and two moments face to
 * face change the line in place and slide nothing (R-0542). */
const DEPTH: Record<Level, number> = {
  [Level.Rest]: 0,
  [Level.Wire]: 0,
  [Level.Compare]: 0,
  [Level.About]: 1,
};

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

/** A reader's hand moving the line; a tap only touches it. */
const HANDS = ["touchmove", "wheel"];

/** A redraw moves the line's resting places, and a browser slides a line
 * resting near one onto it; so while the line is drawn again and put where
 * it stood its snapping is off, and it comes back the moment the reader's
 * hand next moves the line, so a swipe still comes to rest and a tap moves
 * nothing (R-0937, R-0953). */
function steady(scroll: HTMLElement): void {
  scroll.style.scrollSnapType = "none";
  if (scroll.dataset.steady) return;
  scroll.dataset.steady = "1";
  const back = () => {
    scroll.style.scrollSnapType = "";
    delete scroll.dataset.steady;
    for (const kind of HANDS) scroll.removeEventListener(kind, back);
  };
  for (const kind of HANDS) scroll.addEventListener(kind, back, { passive: true });
}
/** What is laid over a screen and answers its own taps. */
const OVER = ".slideover, .pbp, .fs-sheet, .fs-scrim, [role=dialog]";

/** A still picture of the region as it is now, laid over it: the live rows
 * are cloned without their ids so nothing on the page can find the copies.
 * How far the line was scrolled is carried across, because a clone starts at
 * the left end and the copy has to stand where the reader left it. */
const CONTROLS = "button, input, select, textarea, a[href]";

/** A control as a plain span that looks the same: its classes, its inline
 * style, the box the live control is laid out as (a button is a block in the
 * line, a span is not, so its margins would be lost and the copy come out
 * shorter than the level it stands for) and what it says, nothing it does. */
/** What a control's box and words are laid out by that a plain element does
 * not take from the same classes: the browser's own button padding, border and
 * font, and its centring of what it holds. */
const LAID = [
  "boxSizing",
  "fontSize",
  "fontWeight",
  "fontStyle",
  "lineHeight",
  "letterSpacing",
  "textAlign",
  "paddingTop",
  "paddingRight",
  "paddingBottom",
  "paddingLeft",
  "borderTopWidth",
  "borderRightWidth",
  "borderBottomWidth",
  "borderLeftWidth",
  "borderTopStyle",
  "borderRightStyle",
  "borderBottomStyle",
  "borderLeftStyle",
] as const;
type Laid = Partial<Record<(typeof LAID)[number] | "display" | "alignItems" | "justifyContent", string>>;

const ALONG: Record<string, string> = { left: "flex-start", start: "flex-start", right: "flex-end", end: "flex-end" };

/** How a live control is laid out, for its stand-in in a snapshot. A button
 * centres what it holds up and down, and across by its text-align, which a
 * plain element does only as a flex box. */
function laidOf(control: Element): Laid {
  const css = getComputedStyle(control);
  const out: Laid = { display: css.display };
  for (const name of LAID) out[name] = css[name];
  if (control instanceof HTMLButtonElement && !/flex|grid/.test(css.display)) {
    out.display = css.display.startsWith("inline") ? "inline-flex" : "flex";
    out.alignItems = "center";
    out.justifyContent = ALONG[css.textAlign] ?? "center";
  }
  return out;
}

function plain(control: Element, laid: Laid): HTMLElement {
  const span = document.createElement("span");
  span.className = control.className;
  span.setAttribute("style", control.getAttribute("style") ?? "");
  Object.assign(span.style, laid);
  span.innerHTML = control.innerHTML;
  return span;
}

function snapshot(region: HTMLElement): HTMLElement {
  const lay = document.createElement("div");
  lay.className = "slide-lay";
  // the region's own height: the copy travels in a clipping box taller than
  // the region (theme.css .slide-clip), so it cannot take its height from that
  lay.style.height = `${region.offsetHeight}px`;
  // a picture of the level, not the level: nothing in it can be found, read
  // out or pressed, so the live controls are the only ones on the page
  lay.inert = true;
  lay.setAttribute("aria-hidden", "true");
  for (const child of [...region.children]) {
    if (child.classList.contains("slide-clip")) continue;
    const copy = child.cloneNode(true) as HTMLElement;
    for (const el of [copy, ...copy.querySelectorAll("[id]")]) el.removeAttribute("id");
    for (const el of copy.querySelectorAll("[data-target]")) el.removeAttribute("data-target");
    for (const el of copy.querySelectorAll("[tabindex], [role]")) {
      el.removeAttribute("tabindex");
      el.removeAttribute("role");
    }
    // every control becomes a plain element drawn the same way, so the copy
    // holds nothing a reader, a screen reader or a test could take for one
    const laid = [...child.querySelectorAll(CONTROLS)].map(laidOf);
    copy.querySelectorAll(CONTROLS).forEach((el, i) => el.replaceWith(plain(el, laid[i])));
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
  /** A tap on the book button of the page behind a cluster's i, which raises
   * the passages behind what a cluster is (R-0691; Patrick, 2026-10-08). */
  onBook?(button: HTMLElement): void;
  /** The cluster's drawing switched between one row and one lane per person. */
  onView?(view: ClusterView): void;
  /** A long press on an event's row or dot on a cluster's page: its details. */
  onHold?(eventId: number): void;
}

/** How the page behind a cluster's i draws its events: one row, or one lane
 * per person (Patrick, 2026-10-13: option A by default, a button for B). */
export enum ClusterView {
  Row = "row",
  Lanes = "lanes",
}

export const VIEW_KEY = "cluster-view";

/** The reader's last choice in this browser; one row when the browser keeps nothing. */
export function storedView(): ClusterView {
  try {
    return localStorage.getItem(VIEW_KEY) === ClusterView.Lanes ? ClusterView.Lanes : ClusterView.Row;
  } catch {
    return ClusterView.Row;
  }
}

export function storeView(view: ClusterView): void {
  try {
    localStorage.setItem(VIEW_KEY, view);
  } catch {
    // a browser that keeps nothing keeps the choice for this page only
  }
}

/** A shift's dot takes the colour of what moved, the strongest first; any
 * other event is drawn in ink. */
const SHIFT_COLOURS: [keyof TimelineEvent, string][] = [
  ["symptom", "var(--remove)"],
  ["anxiety", "var(--ask)"],
  ["functioning", "var(--move)"],
  ["relationship", "var(--data)"],
];
const INK = "var(--ink)";

export const colourOf = (event: TimelineEvent) =>
  (event.kind === EventKind.Shift && SHIFT_COLOURS.find(([field]) => event[field])?.[1]) || INK;

/** The word under the drawing for each colour that appears in it. */
const COLOUR_WORDS = new Map<string, string>([
  ...SHIFT_COLOURS.map(([field, colour]): [string, string] => [colour, field]),
  [INK, "other events"],
]);

/** What a line through a cluster's drawing stands at: a death, solid; an
 * illness found in someone other than the diagram's own person, dashed; the
 * opening event the cluster stores, dashed, when it is neither (R-0862). */
export enum Key {
  Death = "death",
  Illness = "illness",
  Opening = "opening",
}

/** The events a cluster's events cluster around, each with its line's kind and
 * its short label, by the first deaths-and-periods mockup's rule (R-0862). */
export function keysOf(
  events: TimelineEvent[],
  opening: number | null,
  you: number | null,
  people: Map<number, string>,
): { event: TimelineEvent; key: Key; label: string }[] {
  const first = (e: TimelineEvent) => {
    const name = (e.person !== null && people.get(e.person)) || e.person_name || "";
    return called({ n: name }).n;
  };
  const whose = (e: TimelineEvent) => (/['’]s$/.test(first(e)) ? first(e) : `${first(e)}'s`);
  return events.flatMap((e): { event: TimelineEvent; key: Key; label: string }[] => {
    if (e.kind === EventKind.Death)
      return [{ event: e, key: Key.Death, label: first(e) ? `${whose(e)} death` : e.label }];
    if (e.kind === EventKind.Shift && e.symptom === Shift.Up && e.person !== you)
      return [{ event: e, key: Key.Illness, label: first(e) ? `${first(e)}: ${e.label}` : e.label }];
    if (e.id === opening) return [{ event: e, key: Key.Opening, label: e.label }];
    return [];
  });
}

/** Whose lane an event sits in: its first person, the child for a birth. */
const laneOf = (e: TimelineEvent) =>
  (e.kind === EventKind.Birth || e.kind === EventKind.Adopted ? (e.child ?? e.person) : (e.person ?? e.child)) ?? -1;

/** How long a press is held before it opens the event, as in the sessions list. */
const HOLD_MS = 500;
const LANE_H = 30;
const NAME_W = 64;
/** How wide one letter of a line's label is drawn, and how far apart two rows of labels stand. */
const LETTER = 6.6;
const KEY_ROW = 11;
/** How far apart up the row events on the same date stand, the row staying one row. */
const STACK = 8;
/** How far a dot's target reaches past it where no other dot is near. */
const THUMB = 12;
const TOP = 22;
const SHORT = 22;

const cut = (text: string, n: number) => (text.length > n ? text.slice(0, n - 1) + "\u2026" : text);

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Each dot's own target: a thumb's reach around it, cut halfway to any dot
 * nearer than that, along the way the two stand furthest apart, so no target
 * covers another dot and every dot answers its own tap (R-0168). */
export function targets(dots: { x: number; y: number }[]): Box[] {
  return dots.map((d) => {
    let [l, r, t, b] = [d.x - THUMB, d.x + THUMB, d.y - THUMB, d.y + THUMB];
    for (const o of dots) {
      const [dx, dy] = [o.x - d.x, o.y - d.y];
      if (o === d || Math.abs(dx) >= 2 * THUMB || Math.abs(dy) >= 2 * THUMB) continue;
      if (Math.abs(dx) >= Math.abs(dy)) {
        if (dx > 0) r = Math.min(r, d.x + dx / 2);
        else l = Math.max(l, d.x + dx / 2);
      } else if (dy > 0) b = Math.min(b, d.y + dy / 2);
      else t = Math.max(t, d.y + dy / 2);
    }
    return { x: l, y: t, w: r - l, h: b - t };
  });
}

/** A key event's line, its label on the row of labels it was stood on. */
export interface KeyLine {
  id: number;
  key: Key;
  x: number;
  label: string;
  row: number;
  /** Where the label's words start and end along the drawing. */
  from: number;
  to: number;
}

/** Each line's label on the highest row where it touches no other label and
 * no other line crosses it, cut shorter only when no row is clear, so no two
 * labels ever overlap (R-0862). */
export function stand(lines: { id: number; key: Key; x: number; label: string }[], width: number): KeyLine[] {
  const laid: KeyLine[] = [];
  const span = (x: number, label: string) => {
    const w = label.length * LETTER;
    return x + 3 + w <= width ? [x + 3, x + 3 + w] : [x - 3 - w, x - 3];
  };
  const clear = (c: KeyLine) =>
    laid.every(
      (o) =>
        !(o.row === c.row && c.from < o.to + 4 && o.from < c.to + 4) &&
        !(o.row < c.row && o.x >= c.from && o.x <= c.to) &&
        !(c.row < o.row && c.x >= o.from && c.x <= o.to),
    );
  for (const line of [...lines].sort((a, b) => a.x - b.x)) {
    let found: KeyLine | null = null;
    for (let n = Math.min(line.label.length, SHORT); !found && n >= 4; n--) {
      const label = cut(line.label, n);
      const [from, to] = span(line.x, label);
      for (let row = 0; !found && row <= laid.length; row++) {
        const c = { ...line, label, row, from, to };
        if (clear(c)) found = c;
      }
    }
    if (found) laid.push(found);
  }
  return laid;
}

export interface Placed {
  dots: { id: number; x: number; y: number; colour: string; hollow: boolean; hit: Box }[];
  keys: KeyLine[];
  /** Where the dots start under the rows of labels. */
  top: number;
  lanes: { name: string; y: number }[];
  /** Where each lane's line is drawn, the one row's alone in the one-row view. */
  lines: number[];
  years: [string, string];
  height: number;
}

/** Where each event of a cluster with a date on it lands in a drawing `width`
 * wide; a date the diagram is unsure of, or does not know, is drawn hollow
 * where it is stored, as the approved gallery does. `people` names the lanes. */
export function place(
  events: TimelineEvent[],
  view: ClusterView,
  width: number,
  opening: number | null,
  people: Map<number, string> = new Map(),
  you: number | null = null,
): Placed {
  const dated = events.filter((e) => e.dateTime).sort((a, b) => a.dateTime!.localeCompare(b.dateTime!));
  const lanes = view === ClusterView.Lanes ? [...new Set(dated.map(laneOf))] : [-1];
  const left = (view === ClusterView.Lanes ? NAME_W : 0) + 8;
  const right = width - 8;
  const a = years(dated[0].dateTime!.slice(0, 10));
  const span = years(dated[dated.length - 1].dateTime!.slice(0, 10)) - a || 1;
  const x = (e: TimelineEvent) => left + ((years(e.dateTime!.slice(0, 10)) - a) / span) * (right - left);
  const keys = stand(
    keysOf(dated, opening, you, people).map((k) => ({ id: k.event.id, key: k.key, x: x(k.event), label: k.label })),
    width,
  );
  const top = TOP + KEY_ROW * Math.max(0, ...keys.map((k) => k.row));
  const laneAt = (e: TimelineEvent) => (view === ClusterView.Lanes ? lanes.indexOf(laneOf(e)) : 0);
  const slotOf = (e: TimelineEvent) => `${laneAt(e)}:${e.dateTime!.slice(0, 10)}`;
  const counts = new Map<string, number>();
  for (const e of dated) counts.set(slotOf(e), (counts.get(slotOf(e)) ?? 0) + 1);
  // A lane is as tall as its largest stack of same-date dots needs, so the top
  // dot stays under the labels and the lane above.
  const bands = lanes.map((_, i) => {
    const most = Math.max(...dated.filter((e) => laneAt(e) === i).map((e) => counts.get(slotOf(e))!));
    return LANE_H + Math.max(0, (most - 1) * STACK + 5 - (LANE_H - 8));
  });
  const laneY = (i: number) => top + bands.slice(0, i + 1).reduce((a, b) => a + b, 0) - 8;
  const stacked = new Map<string, number>();
  const dots = dated.map((e) => {
    const lane = laneAt(e);
    const slot = slotOf(e);
    const n = stacked.get(slot) ?? 0;
    stacked.set(slot, n + 1);
    return {
      id: e.id,
      x: x(e),
      y: laneY(lane) - n * STACK,
      colour: colourOf(e),
      hollow: e.dateCertainty !== DateCertainty.Certain,
    };
  });
  const hits = targets(dots);
  return {
    dots: dots.map((d, i) => ({ ...d, hit: hits[i] })),
    keys,
    top,
    lanes:
      view === ClusterView.Lanes
        ? lanes.map((id, i) => ({ name: cut(people.get(id) ?? "", 9), y: laneY(i) }))
        : [],
    lines: lanes.map((_, i) => laneY(i)),
    years: [dated[0].dateTime!.slice(0, 4), dated[dated.length - 1].dateTime!.slice(0, 4)],
    height: laneY(lanes.length - 1) + 26,
  };
}

/** The baseline of a row of line labels. */
const keyY = (row: number) => TOP - 10 + KEY_ROW * row;

/** The cluster's events as dots by date, a line through them at each event
 * they cluster around, the years at the ends, and the button that swaps one
 * row for lanes. */
export function drawing(
  events: TimelineEvent[],
  view: ClusterView,
  width: number,
  opening: number | null,
  people: Map<number, string> = new Map(),
  you: number | null = null,
): string {
  if (!events.some((e) => e.dateTime)) return "";
  const p = place(events, view, width, opening, people, you);
  const f = (n: number) => n.toFixed(1);
  const marks =
    p.lanes
      .map((l) => `<text class="ab-name" x="0" y="${f(l.y + 4)}">${esc(l.name)}</text>`)
      .join("") +
    p.lines
      .map((y) => `<line class="ab-lane" x1="${f(p.lanes.length ? NAME_W + 8 : 8)}" x2="${f(width - 8)}" y1="${f(y)}" y2="${f(y)}"/>`)
      .join("") +
    p.keys
      .map(
        (k) =>
          `<line class="ab-key ab-${k.key}" x1="${f(k.x)}" x2="${f(k.x)}" y1="${f(keyY(k.row) + 3)}" y2="${f(p.height - 16)}"/>` +
          `<text class="ab-keyname ab-${k.key}" x="${f(k.from)}" y="${f(keyY(k.row))}">${esc(k.label)}</text>`,
      )
      .join("") +
    p.dots
      .map(
        (d) =>
          `<circle class="ab-dot" data-event="${d.id}" cx="${f(d.x)}" cy="${f(d.y)}" r="5" stroke="${d.colour}" fill="${d.hollow ? "var(--panel)" : d.colour}"/>` +
          `<rect class="ab-hit" data-target="${Target.Dot}" data-index="${d.id}" x="${f(d.hit.x)}" y="${f(d.hit.y)}" width="${f(d.hit.w)}" height="${f(d.hit.h)}"/>`,
      )
      .join("") +
    `<text class="ab-end" x="${p.lanes.length ? NAME_W + 8 : 8}" y="${f(p.height - 4)}">${p.years[0]}</text>` +
    `<text class="ab-end" x="${width - 8}" y="${f(p.height - 4)}" text-anchor="end">${p.years[1]}</text>`;
  const shown = new Set(p.dots.map((d) => d.colour));
  const legend =
    [...COLOUR_WORDS]
      .filter(([colour]) => shown.has(colour))
      .map(([colour, word]) => `<span class="ab-swatch" style="background:${colour}"></span>${word}`)
      .join(" ") +
    (p.dots.some((d) => d.hollow) ? ` <span class="ab-swatch ab-hollow"></span>hollow: approximate date` : "") +
    (p.keys.some((k) => k.key === Key.Death) ? ` <span class="ab-swatch ab-line ab-death"></span>death` : "") +
    (p.keys.some((k) => k.key === Key.Illness) ? ` <span class="ab-swatch ab-line ab-illness"></span>illness found` : "");
  const other = view === ClusterView.Row ? ClusterView.Lanes : ClusterView.Row;
  return (
    `<svg class="ab-draw" data-view="${view}" viewBox="0 0 ${width} ${f(p.height)}" width="${width}" height="${f(p.height)}">${marks}</svg>` +
    `<p class="ab-span ab-legend">${legend}</p>` +
    `<button type="button" class="ab-view" data-view="${other}">${other === ClusterView.Lanes ? "By person" : "One row"}</button>`
  );
}

/** The key the cluster's book raises in the passages file, and the sheet's title. */
export const CLUSTER_BOOK = "cluster";
export const CLUSTER_BOOK_TITLE = "What a cluster is";

/** A cluster's page: every event of the cluster in the list, the undated
 * ones too, and the drawing of those with a date on them (R-0850). */
export function clusterPage(
  cluster: Cluster,
  all: TimelineEvent[],
  people: { id: number; name: string; primary?: boolean }[],
  view: ClusterView,
  width: number,
): string {
  const why = (cluster.reason ?? cluster.summary ?? "").trim();
  const events = membersOf(cluster, all);
  const moments = events.map((e) => ({ id: e.id, year: e.dateTime?.slice(0, 4) ?? "", label: e.label }));
  const names = new Map(people.map((p) => [p.id, p.name]));
  const you = people.find((p) => p.primary)?.id ?? null;
  const draw = drawing(events, view, width, cluster.openingEventId ?? null, names, you);
  return aboutMarkup(why, cluster.label, moments, draw);
}

/** Every event of a cluster, the undated ones too, by date. */
export const membersOf = (cluster: Cluster, all: TimelineEvent[]) =>
  all.filter((e) => cluster.play_ids.includes(e.id)).sort((a, b) => (a.dateTime ?? "").localeCompare(b.dateTime ?? ""));

/** What a tap on a cluster's page leaves selected: a row, that one event; a
 * dot, every event on its date; the same again, nothing. It only relates the
 * list to the drawing and opens nothing (R-0861). */
export function chosen(now: number[], id: number, via: Via, events: TimelineEvent[]): number[] {
  const day = events.find((e) => e.id === id)?.dateTime?.slice(0, 10);
  const next =
    via === Via.Dot && day ? events.filter((e) => e.dateTime?.slice(0, 10) === day).map((e) => e.id) : [id];
  return next.length === now.length && next.every((n) => now.includes(n)) ? [] : next;
}

/** The page behind a cluster's i, as markup: the coach's reason, the years and
 * the count, each moment with its year, and the app's book button, which
 * opens the passages behind what a cluster is (R-0213, R-0691; Patrick,
 * 2026-10-08: the info button for a cluster has the book button). The passages
 * live only behind the book, never in the coach's words (R-0688). */
export function aboutMarkup(
  why: string,
  span: string,
  moments: { id?: number; year: string; label: string }[],
  draw = "",
): string {
  const rows = moments
    .map((m) => `<li${m.id === undefined ? "" : ` data-event="${m.id}"`}><span class="ab-yr">${esc(m.year)}</span><span class="ab-what">${esc(m.label)}</span></li>`)
    .join("");
  return (
    `<div class="ss about">` +
    (why ? `<p class="ab-why">${esc(why)}</p>` : "") +
    `<p class="ab-span">${esc(span)} · ${moments.length} event${moments.length === 1 ? "" : "s"}</p>` +
    draw +
    `<ul class="ab-list">${rows}</ul>` +
    book(CLUSTER_BOOK, CLUSTER_BOOK_TITLE) +
    `</div>` +
    closeX(` data-target="${Target.Close}"`)
  );
}

const YEAR = 365.25 * 24 * 3600 * 1000;

/** When a moment happened, or nothing when the record cannot say. */
export const dateOf = (event: TimelineEvent) =>
  event.dateCertainty === DateCertainty.Unknown ? null : event.dateTime;

export function years(iso: string): number {
  return new Date(iso + "T00:00:00Z").getTime() / YEAR;
}

/** Where a line `width` wide slides to so a point `x` on it stands in the
 * middle of a `screen`, as near as its ends allow. */
export const centredOn = (x: number, width: number, screen: number) =>
  Math.max(0, Math.min(width - screen, x - screen / 2));

/** Where the line slides so a span of it is in sight: nowhere when it is in
 * sight already, else centred on it, or from its start when it is wider than
 * the screen; centred when where the line stands is not known (Patrick,
 * 2026-10-15). */
export function into(span: Span, left: number | null, width: number, screen: number): number {
  const wide = span.right - span.left > screen - 2 * X_PAD;
  if (left !== null) {
    const seen = wide
      ? span.left <= left + X_PAD && span.right >= left + screen - X_PAD
      : inSight(span.left, left, screen) && inSight(span.right, left, screen);
    if (seen) return left;
  }
  if (!wide) return centredOn(middle(span), width, screen);
  return Math.max(0, Math.min(width - screen, span.left - X_PAD));
}

/** Whether a point `x` on the line is in sight, the line slid to `left`,
 * clear of the picture's side margins. */
export const inSight = (x: number, left: number, screen: number) =>
  x >= left + X_PAD && x <= left + screen - X_PAD;

/** The calendar year a point on the line falls in. years() counts from 1970,
 * so the way back to a year is through the date that point stands for. */
export function yearAt(at: number): number {
  return new Date(at * YEAR).getUTCFullYear();
}

interface Mark {
  event: TimelineEvent;
  x: number;
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
  /** A row of the list on a cluster's page. */
  Row = "row",
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
  private level = Level.Rest;
  private pair: [number, number] | null = null;
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
  /** Where the line was last slid to, while something else stands in its place. */
  private left: number | null = null;
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
  private landed: () => void = () => undefined;
  /** Kept once the about page has finished sliding in or out. */
  settled: Promise<void> = Promise.resolve();
  /** The events selected on the cluster's page, in its list and on its drawing alike (R-0861). */
  private chosen: number[] = [];
  /** A long press has just opened an event, so the tap that ends it selects nothing. */
  private held = false;

  constructor(
    private host: HTMLElement,
    private handlers: PictureHandlers,
    private spot = Spotlight.Unified,
    /** The Family view steps through events one by one, so the event picked
     * inside a cluster is drawn on it too (R-0796). */
    private stepping = false,
  ) {
    window.addEventListener("resize", () => this.render());
    document.addEventListener("click", (e) => this.under(e), true);
    this.host.addEventListener("click", (e) => {
      // The book on the page behind the i raises its passages and touches
      // nothing on the picture.
      const bookButton = (e.target as Element).closest<HTMLElement>(".book[data-book]");
      if (bookButton) {
        e.preventDefault();
        this.handlers.onBook?.(bookButton);
        return;
      }
      const one = this.aboutEvent(e.target as Element);
      if (one !== null) {
        e.preventDefault();
        if (this.held) this.held = false;
        else this.choose(one.id, one.via);
        return;
      }
      const swap = (e.target as Element).closest<HTMLElement>(".ab-view[data-view]");
      if (swap) {
        e.preventDefault();
        const view = swap.dataset.view as ClusterView;
        storeView(view);
        this.render();
        this.handlers.onView?.(view);
        return;
      }
      const hit = (e.target as Element).closest<HTMLElement>("[data-target]");
      // Empty ground. Nothing on the picture is under the thumb, so the tap is
      // the reader putting the picture down; on a cluster's page it is a tap
      // on the page, which only its close button puts away (Patrick, 2026-10-22).
      if (!hit) {
        if (this.level !== Level.About) this.handlers.onTap(this.tapAt(Target.Ground, e));
        return;
      }
      e.preventDefault();
      const tap = this.tapAt(
        hit.dataset.target as Target,
        e,
        Number(hit.dataset.index ?? -1),
      );
      // The words are written over the wire, and the wire's own targets reach
      // up the strip so a thumb can find a dot or a pill — far enough to cover
      // the second line of a label. Where a tap lands on a line of words, the
      // words answer it: the reader touched the label, not the mark under it.
      const on =
        (tap.target === Target.Zone || tap.target === Target.Cluster) &&
        this.rowAt(tap.x, tap.y) !== null
          ? { ...tap, target: Target.Band }
          : tap;
      this.handlers.onTap(on);
    });
    this.holds();
  }

  /** With a cluster's view open, a tap on what lies under it, below the
   * picture on the same screen, puts the view away and reaches nothing there,
   * so no second view opens over the first (Patrick, 2026-10-15). What is laid
   * over the screen, a sheet or a drawer, keeps its own taps. */
  private under(e: MouseEvent): void {
    if (this.level !== Level.About) return;
    const region = this.host.parentElement as HTMLElement;
    const at = e.target as Element;
    if (region.contains(at) || at.closest(OVER) || !region.parentElement?.contains(at)) return;
    if (!(region.compareDocumentPosition(at) & Node.DOCUMENT_POSITION_FOLLOWING)) return;
    e.preventDefault();
    e.stopPropagation();
    this.handlers.onTap(this.tapAt(Target.Close, e));
  }

  /** A long press on an event of a cluster's page opens its details, as a
   * long press on a row opens it for editing in the sessions list. */
  private holds(): void {
    let timer = 0;
    const cancel = () => window.clearTimeout(timer);
    this.host.addEventListener("pointerdown", (e) => {
      this.held = false;
      const one = this.aboutEvent(e.target as Element);
      if (one === null) return;
      timer = window.setTimeout(() => {
        this.held = true;
        this.handlers.onHold?.(one.id);
      }, HOLD_MS);
    });
    for (const kind of ["pointerup", "pointercancel", "pointermove"]) this.host.addEventListener(kind, cancel);
  }

  /** The event under a tap on the cluster's page, by its row or its dot. */
  private aboutEvent(el: Element): { id: number; via: Via } | null {
    if (this.level !== Level.About) return null;
    const row = el.closest<HTMLElement>(".ab-list li[data-event]");
    if (row) return { id: Number(row.dataset.event), via: Via.Row };
    const dot = el.closest<HTMLElement>(`.ab-draw [data-target="${Target.Dot}"]`);
    return dot ? { id: Number(dot.dataset.index), via: Via.Dot } : null;
  }

  private choose(id: number, via: Via): void {
    this.chosen = chosen(this.chosen, id, via, this.focus ? membersOf(this.focus, this.data?.events ?? []) : []);
    this.mark();
  }

  /** The selection drawn in place on the list and the drawing, so the page
   * keeps where it was scrolled to. */
  private mark(): void {
    const on = new Set(this.chosen);
    for (const el of this.host.querySelectorAll<HTMLElement | SVGElement>(".about [data-event]")) {
      const lit = on.has(Number(el.dataset.event));
      el.classList.toggle("on", lit);
      if (el.tagName === "circle") el.setAttribute("r", lit ? "7" : "5");
    }
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
   * nothing moves but the line, to the first it wrote (R-0539). `gone` is
   * what the line removed, as the record held it before. */
  light(made: Made[], gone: TimelineEvent[] = []): void {
    const moments = made.filter((one) => one.kind === ItemKind.Event);
    this.fresh = new Set(moments.map((one) => Number(one.id)));
    for (const one of moments) {
      const id = Number(one.id);
      const had = this.touched.get(id);
      this.touched.set(id, had ? stronger(had, one.touch) : one.touch);
    }
    this.gone.push(...gone);
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
    this.park = Park.Present;
    this.focus = null;
    this.level = Level.Rest;
    this.render();
  }

  setData(data: Timeline): void {
    this.data = data;
    // a change to the record, from a reply here or a write anywhere, leaves
    // the line where the reader slid it (R-0577); a diagram just opened is
    // parked at the present by the clear before it
    this.render();
  }

  /** What the coach's latest message named. Everything else recedes, and the
   * line travels to the first of it. */
  spotlight(eventIds: number[]): void {
    this.aim(eventIds[0] ?? null);
    this.name(eventIds);
  }

  /** A cluster the reader opened: the line travels to it when it is out of
   * sight, and stays where it is when it is in sight (Patrick, 2026-10-15). */
  open(eventIds: number[]): void {
    this.aim(eventIds[0] ?? null);
    this.name(eventIds);
  }

  private name(eventIds: number[]): void {
    this.named = eventIds;
    this.selected = null;
    // naming something opens the cluster it belongs to; naming nothing leaves
    // the picture at rest, showing the whole line
    this.level = eventIds.length ? Level.Wire : Level.Rest;
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
    if (via === Via.Chip) this.aim(id);
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

  /** The Family view's step: its event picked as a chip picks it, or, for a
   * step the line draws nothing of, nothing picked and the line left where it
   * stands, never sent to the present. */
  step(eventId: number | null): void {
    if (eventId !== null) {
      this.pick(eventId, [], Via.Chip);
      return;
    }
    this.named = [];
    this.selected = null;
    this.focus = null;
    this.level = Level.Rest;
    this.aim(null);
    this.render();
  }

  /** How many dated moments a cluster has, which is what explain can tell. */
  countDated(eventIds: number[]): number {
    return (this.data?.events ?? []).filter((e) => eventIds.includes(e.id) && dateOf(e)).length;
  }

  /** Whether the picture is showing one cluster rather than the whole line. */
  opened(): boolean {
    return this.level === Level.Wire && this.focus !== null;
  }

  /** The cluster the picture is showing, if it is showing one. */
  openCluster(): Cluster | null {
    return this.opened() ? this.focus : null;
  }


  /** The event the path ends on, when one is picked and no mode is open. */
  private shown(): TimelineEvent | null {
    return this.level === Level.Rest || this.level === Level.Wire ? this.event(this.selected) : null;
  }

  /** Whether the path ends on a picked event. */
  picked(): boolean {
    return this.shown() !== null;
  }

  /** Everyone's first name in the record, which a title may start with (R-0730). */
  private firstNames(): string[] {
    return (this.data?.people ?? []).map((p) => p.name.split(" ")[0]);
  }

  /** The path from the whole timeline to where the reader is (R-0540). */
  path(): string[] {
    const picked = this.shown();
    return trail(
      this.level,
      this.level === Level.Rest ? null : this.focus,
      picked && told(picked.person_name, picked.label, this.firstNames())[0],
    );
  }

  /** Back to one step of the path: the whole timeline, or the cluster with
   * nothing picked and no mode open. */
  back(step: number): void {
    const open = this.focus;
    if (!step || !open) {
      this.dismiss();
      return;
    }
    this.open(open.event_ids);
  }

  /** The open cluster's own page, a level in from the cluster. */
  about(): void {
    if (!this.opened()) return;
    this.level = Level.About;
    this.chosen = [];
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

  /** A view the coach aimed at. A triangle or a sequence has people and moves
   * to draw, so the play-by-play drawer tells it instead (R-0570). */
  show(view: View): void {
    this.band = null;
    // every view starts from the resting wire; the ones that are a level of
    // their own say so below
    this.level = Level.Wire;
    switch (view.kind) {
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
    this.scale = null;
    this.named = [];
    this.selected = null;
    this.park = Park.Present;
    this.band = null;
    this.focus = null;
    this.level = Level.Rest;
    this.pair = null;
    this.touched.clear();
    this.gone = [];
    this.render();
  }

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

  /** What the line draws: the dated events, and the one picked when it holds
   * a date the record is unsure of, since a chip showing a date goes there
   * (Patrick, 2026-10-15). */
  private onLine(): TimelineEvent[] {
    const dated = this.dated();
    const picked = this.event(this.selected);
    if (!picked?.dateTime || dated.includes(picked)) return dated;
    return [...dated, picked].sort((a, b) => years(a.dateTime as string) - years(b.dateTime as string));
  }

  private get width(): number {
    return this.host.clientWidth || 360;
  }

  /** A mode of the cluster, as a card laid over the chat from the top of the
   * picture: as tall as what it holds, while the picture and the header keep
   * their height and the bubbles stay where they are under it (R-0460), on
   * the case report as on the chat. It stops at the bottom of the screen and
   * scrolls inside itself when it holds more. */
  private card(markup: string): void {
    this.laid = { zones: [], rows: [] };
    this.pin(PIC_H);
    // a card already up is drawn in place, keeping where it was scrolled
    const up = this.host.querySelector<HTMLElement>(":scope > .card");
    if (up && this.host.childElementCount === 1) morph(up, markup);
    else this.host.innerHTML = `<div class="card">${markup}</div>`;
    const card = this.host.firstElementChild as HTMLElement;
    card.style.maxHeight = `${window.innerHeight - this.host.getBoundingClientRect().top}px`;
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
    // the page's words sit between its 16px left and its 52px right, clear of the cross
    this.card(clusterPage(cluster, this.data?.events ?? [], this.data?.people ?? [], storedView(), this.width - 68));
    this.mark();
  }


  /** The line: one drawing for the whole timeline and a cluster open on it
   * (R-0538), wider than the screen when the record needs it and swiped
   * sideways under it, at most two screens (R-0381). One pill per cluster
   * with nothing drawn inside it, and a dot for each event no cluster claims
   * (R-0543); the years under it as a ruler. What the reader opened or the
   * coach named is lit and the rest is dimmed, never taken away. A picked event writes itself out
   * above the line, and a pill or dot the coach touched this turn takes that
   * colour, the strongest touch winning (R-0539, R-0544). Only a pill and a
   * loose dot answer a tap, each across the strip's height to halfway to its
   * neighbours; a tap on the open pill is ground, which puts it down. */
  private renderLine(): void {
    const screen = this.width;
    const dated = this.onLine();
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
    // where the reader left the line, kept while a cluster's view stood in its
    // place; a line resting at its end, the present, stays at its end however
    // much wider or narrower it is drawn now, as when clusters come in (R-0937)
    const scroller = this.host.querySelector<HTMLElement>(SCROLLER);
    const atEnd = scroller !== null && scroller.scrollLeft >= scroller.scrollWidth - scroller.clientWidth - 1;
    let held = atEnd ? null : (scroller?.scrollLeft ?? this.left);
    const x0 = X_PAD;
    const x1 = width - X_PAD;
    const first = years(dated[0].dateTime as string);
    const last = years(dated[dated.length - 1].dateTime as string);
    const span = last - first || 1;
    const at = (iso: string) =>
      dated.length === 1
        ? (x0 + x1) / 2
        : x0 + ((years(iso) - first) / span) * (x1 - x0);
    // a line slid in and drawn at a new width keeps the date that was under
    // the middle of the screen under the middle of the screen (R-0937)
    const was = this.scale;
    if (held !== null && was) {
      const middle = was.first + ((held + screen / 2 - was.x0) / (was.x1 - was.x0)) * was.span;
      held = Math.max(0, Math.round(x0 + ((middle - first) / span) * (x1 - x0) - screen / 2));
    }
    this.scale = { first, span, x0, x1 };
    const open = this.level === Level.Wire ? this.focus : null;
    const lit = new Set(this.named);
    if (this.selected !== null) lit.add(this.selected);
    const dim = ` opacity="${baseOpacity(dated.length, lit.size)}"`;

    let svg =
      `<svg viewBox="0 0 ${width} ${PIC_H}" height="${PIC_H}" preserveAspectRatio="xMinYMin meet">` +
      this.bandMark(at) +
      `<line class="wire" x1="${x0}" y1="${WIRE}" x2="${x1}" y2="${WIRE}"/>`;
    // The event picked is drawn last, so it is on top of whatever crowds it
    // (picked mockup Q1).
    let onTop = "";
    // A dot takes the colour of what the coach did to it this turn.
    const dot = (id: number, x: number): void => {
      const touch = this.touched.get(id);
      const on = id === this.selected;
      const named = !on && this.named.includes(id);
      const cls = ["dot", on && "on", named && "lit", touch, touch && this.fresh.has(id) && "flash"]
        .filter(Boolean)
        .join(" ");
      const faded = lit.size && !touch && !lit.has(id) ? dim : "";
      const drawn =
        `<circle class="${cls}" data-event="${id}" ` +
        `cx="${x.toFixed(1)}" cy="${WIRE}" r="${on ? 7 : DOT_R}"${faded}/>`;
      if (on) onTop += drawn;
      else svg += drawn;
    };
    const marks: Mark[] = [];
    const boxes: Layer[] = [];
    const laid = pills(clusters, dated, at);
    const hits = reach(laid, width);
    laid.forEach((pill, i) => {
      if (pill.event) {
        const x = at(pill.event.dateTime as string);
        dot(pill.event.id, x);
        marks.push({ event: pill.event, x });
        return;
      }
      const cluster = pill.cluster as Cluster;
      const ids = cluster.event_ids;
      const opened = cluster.id === open?.id;
      const touch = strongest(ids, this.touched);
      const shown = opened || ids.some((id) => lit.has(id));
      const cls = [
        "pill",
        shown ? "on" : lit.size && !touch ? "dim" : "",
        touch,
        touch && ids.some((id) => this.fresh.has(id)) ? "flash" : "",
      ]
        .filter(Boolean)
        .join(" ");
      const wide = Math.max(PILL_H, pill.right - pill.left);
      svg +=
        `<rect class="${cls}" data-cluster="${cluster.id}" ` +
        `x="${(middle(pill) - wide / 2).toFixed(1)}" y="${WIRE - PILL_H / 2}" ` +
        `width="${wide.toFixed(1)}" height="${PILL_H}" rx="${PILL_H / 2}"/>`;
      // a second tap on the open pill is ground, which puts it down
      if (opened) return;
      boxes.push({
        target: Target.Cluster,
        index: clusters.indexOf(cluster),
        left: hits[i].left,
        width: hits[i].right - hits[i].left,
        label: cluster.title,
      });
    });
    // what this turn removed stays where it was, in its colour, until the next
    // message, unless a pill already carries its colour
    const kept = new Set(dated.map((e) => e.id));
    const claimed = new Set(clusters.flatMap((c) => c.event_ids));
    for (const event of this.gone)
      if (!kept.has(event.id) && !claimed.has(event.id) && dateOf(event))
        dot(event.id, at(event.dateTime as string));
    // stepping event by event, the step's event is drawn and named over its
    // cluster's pill as well (Patrick, 2026-10-07)
    const inside = this.stepping ? dated.find((e) => e.id === this.selected && claimed.has(e.id)) : undefined;
    if (inside) {
      const x = at(inside.dateTime as string);
      dot(inside.id, x);
      marks.push({ event: inside, x });
    }
    for (const tick of ruler(yearAt(first), yearAt(last), at, x0, x1))
      svg +=
        `<text class="ep-yrs" x="${tick.x.toFixed(1)}" y="${RULER_Y}" ` +
        `text-anchor="${tick.anchor}">${tick.year}</text>`;
    svg += onTop + `</svg>`;

    const zoned = zones(marks, width);
    this.laid.zones = zoned.map((zone) => zone.marks);

    const aimed = marks.find((m) => m.event.id === this.aimed);
    // stepping event by event, a draw that would leave the step's dot out of
    // sight, as one that lands mid-travel does, goes to it again (Patrick, 2026-10-07)
    const step = this.stepping && !aimed ? marks.find((m) => m.event.id === this.selected) : undefined;
    if (step && !inSight(step.x, held ?? Math.max(0, width - screen), screen)) this.park = Park.Named;
    const mark = aimed ?? step;
    // an event drawn inside its cluster's pill is gone to by the pill
    const pill = mark || this.aimed === null ? undefined : laid.find((p) => p.cluster?.event_ids.includes(this.aimed!));
    const on = mark ? { left: mark.x, right: mark.x } : (pill ?? null);
    // where the line comes to rest, so the words of a picked event are
    // written across the stretch the reader will be looking at
    const shows = this.stands({ width, screen }, held, on);
    const said = this.labels(marks, shows + X_PAD, shows + screen - X_PAD, WIRE);
    this.laid.rows = said.rowsLaid;
    const chosen = marks.find((m) => m.event.id === this.selected);
    // With a cluster open and nothing picked, the words over the line are the
    // cluster's name with how many events it holds (R-0538, R-0583, R-0767).
    const title =
      !said.text && open && !chosen
        ? `<div class="ss-t ss-name" style="left:${X_PAD}px;top:${ROWS[0]}px;` +
          `width:${screen - 2 * X_PAD}px"><span>${esc(clusterName(open))}</span> <span class="ct">(${open.count})</span></div>`
        : "";
    // The band lies over the words and under the marks' own targets.
    const words = said.text ? said.text + bandHit(shows + X_PAD, screen - 2 * X_PAD) : "";
    const targets = restLayers(boxes, dotLayers(zoned)).map(hitButton).join("");
    // Where the line settles after a swipe: at a box's near edge, so a cluster
    // is never cut in half.
    const stops = new Set<number>();
    for (const edge of edges(clusters, at)) {
      stops.add(Math.max(0, edge.left - X_PAD));
      stops.add(Math.max(0, edge.right + X_PAD - screen));
    }
    // and at both ends, so the first moment is reachable as the last is
    stops.add(0);
    stops.add(Math.max(0, width - screen));
    // whole pixels, or a redraw lands the line a pixel off where it stood (R-0542)
    const snaps = [...new Set([...stops].map(Math.round))]
      .map((left) => `<i class="ss-snap" style="left:${left}px"></i>`)
      .join("");

    this.lay(`${width.toFixed(1)}px`, `${svg}${words}${targets}${snaps}`, `${title}${shelf}`);
    this.settle({ width, screen }, held, on);
  }

  /** Where the line last put its years, to keep a date in place when it is
   * drawn at another width. */
  private scale: { first: number; span: number; x0: number; x1: number } | null = null;

  /** What the line last drew, to change only what differs. */
  private drawn: { strip: HTMLElement; width: string; line: string; after: string } | null = null;

  /** The line put on screen. A redraw while the line is up keeps its frame and
   * its scroller, so it neither flashes nor loses where the reader slid it,
   * and changes only the parts whose drawing differs. */
  private lay(width: string, line: string, after: string): void {
    const frame = this.host.querySelector<HTMLElement>(":scope > .ss");
    const scroll = frame?.querySelector<HTMLElement>(`:scope > ${SCROLLER}`);
    const strip = scroll?.querySelector<HTMLElement>(":scope > .ss-line");
    // anything else drawn here since, and the line is drawn whole again
    if (!scroll || !strip || this.drawn?.strip !== strip) {
      this.host.innerHTML =
        `<div class="ss"><div class="ss-scroll"><div class="ss-line" style="width:${width}">${line}</div></div>${after}</div>`;
      this.drawn = { strip: this.host.querySelector<HTMLElement>(".ss-line")!, width, line, after };
      return;
    }
    steady(scroll);
    if (width !== this.drawn.width) strip.style.width = width;
    if (line !== this.drawn.line) morph(strip, line);
    if (after !== this.drawn.after) {
      while (scroll.nextSibling) scroll.nextSibling.remove();
      scroll.insertAdjacentHTML("afterend", after);
    }
    this.drawn = { strip, width, line, after };
  }

  /** Where the line comes to rest after this draw: on what was just named
   * when it is out of sight, where the reader left it, or parked at the
   * present. */
  private stands(
    view: { width: number; screen: number },
    held: number | null,
    on: Span | null,
  ): number {
    const end = Math.max(0, view.width - view.screen);
    const left = held === null ? null : Math.min(end, held);
    // a line resting at the present has no held place, but is in sight there
    if (this.park === Park.Named && on) return into(on, left ?? end, view.width, view.screen);
    if (this.park !== Park.Present && left !== null) return left;
    return end;
  }

  /** Where the line stands once it has been drawn: parked at the present, on
   * the moment just named, or where the reader left it. */
  private settle(
    view: { width: number; screen: number },
    held: number | null,
    on: Span | null,
  ): void {
    const scroll = this.host.querySelector<HTMLElement>(SCROLLER);
    if (!scroll) return;
    const named = this.park === Park.Named && on !== null;
    const to = this.stands(view, held, on);
    this.park = Park.Held;
    this.aimed = null;
    // the line travelling to what was named is the picture answering the
    // coach's words; every other draw puts it down where it belongs at once.
    // The line is drawn anew at its left end, so a travel sets out from where
    // the reader left it. It travels frame by frame: Safari leaves the
    // browser's own smooth scroll, set out on a line just drawn, where it began.
    const glide = named && held !== null && !still();
    if (glide) scroll.scrollLeft = held;
    pan(scroll, to, glide);
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
    this.left = this.host.querySelector<HTMLElement>(SCROLLER)?.scrollLeft ?? this.left;
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

  /** One level in or one level out. Drilling down, the arriving view comes down
   * from the top over the one it came from, like a drawer; going back, the view
   * being left goes back up and uncovers it (R-0768). The region keeps its height, so
   * nothing under the picture moves while they travel (owner ruling
   * 2026-09-08), and the about page travels at its full height over the chat,
   * never let out to it after landing (Patrick, 2026-10-02). */
  private slide(dir: 1 | -1): void {
    this.landed();
    this.settled = new Promise((done) => (this.landed = done));
    // The card is the whole picture region — title line, drawing and the row
    // of chips — not the drawing alone (owner, 2026-09-09). The level that is
    // leaving is photographed now; the one arriving is photographed once the
    // page has written its title and chips, a frame later; the two pictures
    // travel over the live region, which is already showing the new level, in
    // a clipping box of their own that is cut at the region's top and sides
    // and reaches well below it (theme.css .slide-clip), so the about page
    // hangs over the chat whole on every frame.
    const region = this.host.parentElement as HTMLElement;
    const leaving = snapshot(region);
    this.draw();
    region.classList.add("sliding");
    const clip = document.createElement("div");
    clip.className = "slide-clip";
    clip.append(leaving);
    region.append(clip);
    keepScroll(leaving);
    // A render that arrives before the first frame lands this slide there and
    // then, so a cluster's view opened over another never leaves a dead copy
    // over the live one, its cross answering nothing (Patrick, 2026-10-15).
    const frame = requestAnimationFrame(() => {
      const arriving = snapshot(region);
      clip.append(dir === 1 ? arriving : leaving);
      keepScroll(arriving);
      const mover = dir === 1 ? arriving : leaving;
      // the about page hangs below the region, so it starts as far up as its own foot
      const top = mover.getBoundingClientRect().top;
      const foot = Math.max(mover.offsetHeight, ...[...mover.querySelectorAll(".card")].map((c) => c.getBoundingClientRect().bottom - top));
      const off = { transform: `translateY(${-Math.ceil(foot)}px)` };
      const on = { transform: "translateY(0)" };
      this.flight = mover.animate(dir === 1 ? [off, on] : [on, off], {
        duration: SLIDE_MS,
        easing: "ease",
      });
      this.flight.finished.then(
        () => this.land(),
        () => undefined,
      );
    });
    this.landing = () => {
      cancelAnimationFrame(frame);
      clip.remove();
      region.classList.remove("sliding");
    };
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
    this.landed();
  }

  private draw(): void {
    if (this.level === Level.About && this.focus) {
      this.renderAbout(this.focus);
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
        dateText(event.dateTime as string, event.dateCertainty, event.datePrecision),
        told(event.person_name, event.label, this.firstNames())[1],
      ]
        .filter(Boolean)
        .join(` ${SEP} `);
      const lines = wrap2(
        clip(said, Math.min(88, wide * ROWS.length)),
        wide,
      );
      // stepping event by event, the words stand over their dot, kept inside
      // the line, so the step's dot is the one they name (Patrick, 2026-10-07)
      const at = (line: string) => {
        if (!this.stepping) return { left: x0, width: x1 - x0 };
        const width = Math.min(x1 - x0, Math.ceil(line.length * CH) + 2);
        return { left: Math.min(Math.max(chosen.x - width / 2, x0), x1 - width), width };
      };
      const text = lines
        .map((line, i) => {
          if (!line) return "";
          const { left, width } = at(line);
          return `<div class="ss-t on" style="left:${left.toFixed(1)}px;top:${ROWS[i]}px;width:${width.toFixed(1)}px">${esc(line)}</div>`;
        })
        .join("");
      // the words of the moment already picked are its label, so a tap on them
      // is a tap on it and picks it again rather than putting the picture down
      return {
        text,
        rowsLaid: lines
          .map((line, row) => ({ id: event.id, row, ...at(line), line }))
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
