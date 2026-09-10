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
  whoText,
  words,
  wrap2,
  zones,
} from "./spotlight";
import {
  DateCertainty,
  ItemKind,
  ViewKind,
  type Cluster,
  type Person,
  type Question,
  type Timeline,
  type TimelineEvent,
  type View,
} from "./types";

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

const REST_H = 60;
const REST_WIRE = 30;
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

/** The picture's levels. The middle "cluster drilldown" is CUT (R-0074): the
 * resting wire and the moves board are the two that survive. */
enum Level {
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

const STILL = window.matchMedia("(prefers-reduced-motion: reduce)");

/** A still picture of the region as it is now, laid over it: the live rows
 * are cloned without their ids so nothing on the page can find the copies. */
function snapshot(region: HTMLElement, ...skip: Element[]): HTMLElement {
  const lay = document.createElement("div");
  lay.className = "slide-lay";
  for (const child of [...region.children]) {
    if (skip.includes(child) || child.classList.contains("slide-lay")) continue;
    const copy = child.cloneNode(true) as HTMLElement;
    for (const el of [copy, ...copy.querySelectorAll("[id]")]) el.removeAttribute("id");
    lay.append(copy);
  }
  return lay;
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
}

const YEAR = 365.25 * 24 * 3600 * 1000;

export function years(iso: string): number {
  return new Date(iso + "T00:00:00Z").getTime() / YEAR;
}

interface Mark {
  event: TimelineEvent;
  x: number;
}

/** "2006", or "2004–2006": the span in full years, for a page with room. */
function fullYears(start: string, end: string): string {
  const a = Math.floor(years(start));
  const b = Math.floor(years(end));
  return a === b ? String(a) : `${a}\u2013${b}`;
}

/** The dated moments no cluster claims. */
function loose(dated: TimelineEvent[], clusters: { event_ids: number[] }[]): TimelineEvent[] {
  const claimed = new Set(clusters.flatMap((cluster) => cluster.event_ids));
  return dated.filter((event) => !claimed.has(event.id));
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
  private band: { start: string; end: string } | null = null;
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
    return {
      target,
      index,
      x: (e as MouseEvent).clientX - box.left,
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
    this.focus = null;
    this.cluster = null;
    this.level = Level.Rest;
    this.rescale();
    this.render();
  }

  setData(data: Timeline): void {
    this.data = data;
    this.rescale();
    this.render();
  }

  /** What the coach's latest message named. Everything else recedes. */
  spotlight(eventIds: number[]): void {
    this.named = eventIds;
    this.selected = null;
    this.litPeople = [];
    // naming something opens the cluster it belongs to; naming nothing leaves
    // the picture at rest, showing the whole line
    this.level = eventIds.length ? Level.Wire : Level.Rest;
    this.cluster = null;
    this.focus = this.clusterOf(eventIds[0]);
    this.rescale();
    this.render();
  }

  select(eventId: number | null): void {
    this.selected = eventId;
    this.litPeople = [];
    this.render();
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
      `${moments.length} moment${moments.length === 1 ? "" : "s"}</p>` +
      `<ul class="ab-list">${rows}</ul></div>`;
    this.pin(this.host.scrollHeight);
  }

  private renderRest(): void {
    const width = this.width;
    const x0 = X_PAD;
    const x1 = width - X_PAD;
    const dated = this.dated();
    this.laid = { zones: [], rows: [] };
    this.pin(PIC_H);

    // What has no date exists at every level: it is the one thing on the
    // picture the record is still asking about.
    const shelf = this.shelfHit(x1, REST_WIRE);

    if (!dated.length) {
      this.host.innerHTML =
        `<div class="ss"><p class="ss-empty">` +
        `Nothing on your line yet — it draws itself as you talk.</p>${shelf}</div>`;
      return;
    }

    const clusters = this.restClusters();
    // A picked loose moment gets the words, dot and year the open cluster gives
    // one — the same two lines above the wire — so the wire drops to where the
    // words leave room and the boxes, which live where the words go, become
    // brackets under the wire until the moment is put down (owner, option A,
    // 2026-09-09).
    const picked = this.selected !== null && loose(dated, clusters).some((e) => e.id === this.selected);
    const wireY = picked ? WIRE : REST_WIRE;
    const first = years(dated[0].dateTime as string);
    const last = years(dated[dated.length - 1].dateTime as string);
    const span = last - first || 1;
    const at = (iso: string) =>
      dated.length === 1
        ? (x0 + x1) / 2
        : x0 + ((years(iso) - first) / span) * (x1 - x0);

    let svg =
      `<svg viewBox="0 0 ${width} ${REST_H}" height="${REST_H}" preserveAspectRatio="xMinYMin meet">` +
      (picked
        ? `<defs><linearGradient id="epfade" gradientUnits="userSpaceOnUse" ` +
          `x1="0" x2="0" y1="${wireY + 20}" y2="${wireY - 20}">` +
          `<stop offset="0" class="epfade-in"/><stop offset="0.45" class="epfade-in"/>` +
          `<stop offset="1" class="epfade-out"/></linearGradient></defs>`
        : "") +
      `<line class="wire" x1="${x0}" y1="${wireY}" x2="${x1}" y2="${wireY}"/>`;
    let hits = "";
    let clusterHits = "";
    // A box reaches a little past the moments it holds, and two clusters a
    // month apart would then draw over one another. Where that happens the two
    // boxes give way to each other and leave a gap between them.
    const edges = clusters.map((cluster) => ({
      left: at(cluster.start) - 10,
      right: at(cluster.end) + 10,
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
      else
        for (let j = 0; j < cluster.count; j += 1) {
          const spread = cluster.count > 1 ? j / (cluster.count - 1) : 0.5;
          svg +=
            `<circle class="dot" cx="${(a + (b - a) * spread).toFixed(1)}" ` +
            `cy="${wireY}" r="4.5"/>`;
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
      clusterHits +=
        `<button class="ss-hit" data-target="${Target.Cluster}" data-index="${i}" ` +
        `aria-label="${esc(cluster.title || shortYears(cluster.start, cluster.end))}" ` +
        `style="left:${(middle - target / 2).toFixed(1)}px;top:${wireY - ZONE / 2}px;` +
        `width:${target.toFixed(1)}px;height:${ZONE}px"></button>`;
    });
    // A moment no cluster claims is drawn as itself: a dot on the wire where it
    // happened, with no box around it and nothing else bundled into it.
    const marks: Mark[] = loose(dated, clusters).map((event) => ({
      event,
      x: at(event.dateTime as string),
    }));
    this.laid.zones = marks.map((mark) => [mark]);
    marks.forEach(({ event, x }, i) => {
      const on = event.id === this.selected ? " on" : "";
      svg += `<circle class="dot${on}" cx="${x.toFixed(1)}" cy="${wireY}" r="${on ? 7 : 4.5}"/>`;
      hits +=
        `<button class="ss-hit" data-target="${Target.Zone}" data-index="${i}" ` +
        `aria-label="${esc(event.label)}" ` +
        `style="left:${(x - ZONE / 2).toFixed(1)}px;top:${wireY - ZONE / 2}px;` +
        `width:${ZONE}px;height:${ZONE}px"></button>`;
    });

    svg += `</svg>`;

    let words = "";
    if (picked) {
      const laid = this.labels(marks, x0, x1, wireY);
      this.laid.rows = laid.rowsLaid;
      const mark = marks.find((m) => m.event.id === this.selected) as Mark;
      words =
        laid.text +
        `<div class="ss-yr on" style="left:${(mark.x - 30).toFixed(1)}px;` +
        `top:${YEAR_TOP}px;width:60px;text-align:center">${esc(this.yearOf(mark.event))}</div>`;
    }

    // A cluster's target goes down last so it wins where a loose moment's
    // thumb-sized target reaches over its box: a tap on a box opens the box.
    this.host.innerHTML = `<div class="ss">${svg}${words}${hits}${clusterHits}${shelf}</div>`;
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
          `<button type="button" class="btn primary" data-target="${Target.Explain}" ` +
          `${this.explaining ? "disabled" : ""}>&#9654; explain</button>` +
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
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches)
      this.host.querySelector("svg")?.pauseAnimations();
  }

  /** Two moments side by side with the record's one asking mark between them.
   * No axis: a comparison is not a measurement. */
  private renderPair(): string | null {
    const [a, b] = (this.pair ?? [0, 0]).map((id) => this.event(id));
    if (!a || !b) return null;
    const width = this.width;
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
        (two
          ? `<text class="ss-w" x="${left}" y="${ROWS[2] + 6}">${esc(two)}</text>`
          : "")
      );
    };
    this.pin(PIC_H);
    return (
      `<div class="ss">` +
      `<svg viewBox="0 0 ${width} ${PIC_H}" aria-hidden="true">` +
      column(a, X_PAD) +
      column(b, mid + 11) +
      `<line class="seam" x1="${mid}" y1="${ROWS[0] - 12}" x2="${mid}" y2="${ROWS[2] + 12}"/>` +
      `<text class="qm" x="${mid}" y="${ROWS[1] + 6}" text-anchor="middle">?</text>` +
      `</svg></div>`
    );
  }

  private render(): void {
    if (!this.data) return;
    const to = DEPTH[this.level];
    const from = this.depth;
    this.depth = to;
    this.land();
    if (to === from || !this.host.firstChild || STILL.matches) {
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
    requestAnimationFrame(() => {
      const arriving = snapshot(region, leaving);
      region.append(dir === 1 ? arriving : leaving);
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
    // A tap on a loose moment picks it where it is: the clusters stay, the
    // dot reads as picked (owner, 2026-09-09). The spotlight below is for
    // what the coach's words name, not for a tap.
    if (this.level === Level.Rest && (this.selected === null || !this.focus)) {
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
    const wire = WIRE;

    if (!shown.length) {
      this.laid = { zones: [], rows: [] };
      this.pin(PIC_H);
      this.host.innerHTML =
        `<div class="ss">` +
        `<svg viewBox="0 0 ${width} ${PIC_H}" aria-hidden="true">` +
        `<line class="wire empty" x1="${x0}" y1="${WIRE}" x2="${x1}" y2="${WIRE}"/>` +
        `<text class="qm" x="${width / 2}" y="${WIRE + 6}" text-anchor="middle">?</text>` +
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
    const zoned = zones(marks, x0, x1);
    this.laid.zones = zoned.map((zone) => zone.marks);
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
      ? `<div class="ss-yr on" style="left:${(picked.x - 30).toFixed(1)}px;` +
        `top:${YEAR_TOP}px;width:60px;text-align:center">` +
        `${esc(this.yearOf(picked.event))}</div>`
      : "";

    let hits =
      `<button class="ss-hit" data-target="${Target.Band}" aria-label="what the coach named" ` +
      `style="left:${x0}px;top:${ROWS[0] + 1}px;width:${x1 - x0}px;height:${ZONE}px"></button>`;
    zoned.forEach((zone, i) => {
      hits +=
        `<button class="ss-hit" data-target="${Target.Zone}" data-index="${i}" ` +
        `aria-label="moments around ${this.yearOf(zone.marks[0].event)}" ` +
        `style="left:${zone.left.toFixed(1)}px;top:${wire - ZONE / 2}px;` +
        `width:${zone.width.toFixed(1)}px;height:${ZONE}px"></button>`;
    });
    hits += this.shelfHit(x1, wire);

    this.pin(height);
    this.host.innerHTML = `<div class="ss">${svg}${text}${html}${hits}</div>`;
    // CSS cannot reach the move language's SVG animations, so reduced motion
    // holds them on their first frame the same way it stops the rest
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches)
      this.host.querySelector("svg")?.pauseAnimations();
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
      const said = whoText(event.person_name, this.protagonist());
      const who = said ? `${said} · ` : "";
      const lines = wrap2(
        clip(who + event.label.trim(), Math.min(88, wide * ROWS.length)),
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
          this.protagonist(),
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

  private protagonist(): string {
    return this.data?.people.find((p) => p.primary)?.name ?? "";
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
