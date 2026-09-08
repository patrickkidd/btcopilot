import {
  BOARD_H,
  board,
  castOfSteps,
  movesIn,
  triangle,
  type Step,
} from "./board";
import { esc } from "./dom";
import {
  CH,
  PIC_H,
  ROWS,
  WIRE,
  X_PAD,
  YEAR_TOP,
  ZONE,
  baseOpacity,
  clip,
  cycle,
  dateText,
  dotRadius,
  rows,
  words,
  wrap2,
  zones,
} from "./spotlight";
import {
  DateCertainty,
  ViewKind,
  type Chapter,
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

const NODAL = new Set(["cutoff", "defined-self", "fusion"]);

/** The resting level: the whole line, one box per chapter (converged mockup,
 * crowded-chapter/timeline-converged.html renderRest).
 *
 * Its drawing is 78 tall, but the region it draws into is not. The picture
 * region is ONE height for both the resting wire and the open chapter, because
 * a tap on the picture must never move a bubble; only entering the moves board,
 * which is a screen of its own, may change the layout. So the resting drawing
 * is top-aligned inside the chapter's box and the rest of that box is empty. */
const REST_H = 78;
const REST_WIRE = 46;
/** A chapter of more than this many moments collapses to a ring and a count. */
const DENSE = 8;
/** A gap of this many years or more between chapters earns the amber question. */
const GAP_YEARS = 4;

/** A chapter's years at a glance, two digits each, as the converged mockup
 * writes them: "93–97". One year when it starts and ends in the same one. */
function shortYears(start: string, end: string): string {
  const a = start.slice(2, 4);
  const b = end.slice(2, 4);
  return a === b ? a : `${a}\u2013${b}`;
}

/** The picture's levels. The middle "cluster drilldown" is CUT (R-0074): the
 * resting wire and the moves board are the two that survive. */
enum Level {
  /** Nothing named yet: the whole line at a glance, one box per chapter. */
  Rest = "rest",
  Wire = "wire",
  Board = "board",
  /** Two moments face to face, which is how the record asks a question about
   * a pair. No mockup fixes this drawing; it is built from the approved
   * "Pairs, face to face" concept and the at-rest vocabulary. */
  Compare = "compare",
}

export enum Target {
  Zone = "zone",
  /** A chapter box on the resting level. */
  Chapter = "chapter",
  Band = "band",
  Question = "question",
  Shelf = "shelf",
  /** The board's own controls, which the picture answers itself. */
  Back = "back",
  Prev = "prev",
  Next = "next",
}

const OWN = new Set<string>([Target.Back, Target.Prev, Target.Next]);

export interface Tap {
  target: Target;
  /** For a zone, which one; for the band, the y the thumb landed at. */
  index: number;
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

export class Picture {
  private data: Timeline | null = null;
  /** The moments the coach's latest message named — the spotlight. */
  private named: number[] = [];
  private selected: number | null = null;
  private cast: number[] = [];
  private level = Level.Rest;
  private moves: Step[] = [];
  private at = 0;
  private pair: [number, number] | null = null;
  private entering = false;
  private band: { start: string; end: string } | null = null;
  private focus: Chapter | null = null;
  private range = { min: 0, max: 1 };
  private laid: { zones: Mark[][]; rows: { id: number; row: number }[] } = {
    zones: [],
    rows: [],
  };

  constructor(
    private host: HTMLElement,
    private handlers: PictureHandlers,
  ) {
    window.addEventListener("resize", () => this.render());
    this.host.addEventListener("click", (e) => {
      const hit = (e.target as Element).closest<HTMLElement>("[data-target]");
      if (!hit) return;
      e.preventDefault();
      if (OWN.has(hit.dataset.target as string)) {
        this.control(hit.dataset.target as Target);
        return;
      }
      const box = this.host.getBoundingClientRect();
      this.handlers.onTap({
        target: hit.dataset.target as Target,
        index: Number(hit.dataset.index ?? -1),
        y: (e as MouseEvent).clientY - box.top,
      });
    });
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
    // naming something opens the chapter it belongs to; naming nothing leaves
    // the picture at rest, showing the whole line
    this.level = eventIds.length ? Level.Wire : Level.Rest;
    this.focus = this.chapterOf(eventIds[0]);
    this.rescale();
    this.render();
  }

  select(eventId: number | null): void {
    this.selected = eventId;
    this.render();
  }

  selection(): number | null {
    return this.selected;
  }

  /** The moments under one tap zone, in time order. */
  inZone(index: number): number[] {
    return (this.laid.zones[index] ?? []).map((mark) => mark.event.id);
  }

  /** Which labelled row the thumb landed nearest, for a tap on the label band. */
  rowAt(y: number): number | null {
    let best: number | null = null;
    let distance = Infinity;
    for (const row of this.laid.rows) {
      const d = Math.abs(ROWS[row.row] + 7.5 - y);
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
      this.at = on;
      this.render();
      return;
    }
    this.selected = eventId;
    this.render();
  }

  /** Enter the board: the moves of one stretch, numbered, on the people they
   * happened between. The level below it is CUT, so this comes straight from
   * the chat. */
  openBoard(eventIds: number[]): number {
    const events = (this.data?.events ?? []).filter((e) =>
      eventIds.includes(e.id),
    );
    this.moves = movesIn(events);
    if (!this.moves.length) return 0;
    this.level = Level.Board;
    this.entering = true;
    this.at = 0;
    this.cast = [];
    this.render();
    return this.moves.length;
  }

  /** How many moves a stretch would put on the board, for the entry button. */
  countMoves(eventIds: number[]): number {
    return movesIn(
      (this.data?.events ?? []).filter((e) => eventIds.includes(e.id)),
    ).length;
  }

  onBoard(): boolean {
    return this.level === Level.Board;
  }

  private control(target: Target): void {
    if (target === Target.Back) {
      this.level = Level.Wire;
      this.moves = [];
      this.cast = [];
      this.at = 0;
    } else if (target === Target.Next)
      this.at = Math.min(this.moves.length - 1, this.at + 1);
    else if (target === Target.Prev) this.at = Math.max(0, this.at - 1);
    this.render();
  }

  async show(view: View): Promise<void> {
    this.band = null;
    this.cast = [];
    // every view starts from the resting wire; the ones that are a level of
    // their own say so below
    this.level = Level.Wire;
    this.moves = [];
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
        const chapter = this.data?.chapters.find(
          (c) => c.id === view.cluster || c.cluster_ids.includes(view.cluster),
        );
        if (chapter) {
          this.focus = chapter;
          this.spotlight(chapter.event_ids);
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

  /** What the readout beside the picture says the picture is showing. */
  state(): string {
    const event = this.event(this.selected);
    if (event?.dateTime)
      return `${dateText(event.dateTime, event.dateCertainty)} · ${clip(event.label, 30)}`;
    if (this.focus) return this.focus.label;
    const dated = this.dated();
    if (!dated.length) return "nothing dated yet";
    return `${this.yearOf(dated[0])}–${this.yearOf(dated[dated.length - 1])}`;
  }

  private yearOf = (event: TimelineEvent) => (event.dateTime as string).slice(0, 4);

  private event(id: number | null): TimelineEvent | null {
    return id === null
      ? null
      : (this.data?.events.find((e) => e.id === id) ?? null);
  }

  private chapterOf(eventId: number | undefined): Chapter | null {
    if (eventId === undefined || !this.data) return null;
    return this.data.chapters.find((c) => c.event_ids.includes(eventId)) ?? null;
  }

  /** The coach drives the picture: when it names moments inside one stretch,
   * the wire zooms to that stretch; otherwise the whole record is on it. */
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

  /** The moments on the wire: the focused stretch when the coach aimed at one,
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
  /** The whole line at a glance: one box per chapter, its years above it, its
   * moments as dots inside it, and the amber question where the record has a
   * long gap it cannot account for. A tap opens a chapter. Converged mockup:
   * crowded-chapter/timeline-converged.html renderRest. */
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

    const chapters = this.restChapters();
    const first = years(dated[0].dateTime as string);
    const last = years(dated[dated.length - 1].dateTime as string);
    const span = last - first || 1;
    const at = (iso: string) =>
      dated.length === 1
        ? (x0 + x1) / 2
        : x0 + ((years(iso) - first) / span) * (x1 - x0);

    let svg =
      `<svg viewBox="0 0 ${width} ${REST_H}" height="${REST_H}" preserveAspectRatio="xMinYMin meet">` +
      `<line class="wire" x1="${x0}" y1="${REST_WIRE}" x2="${x1}" y2="${REST_WIRE}"/>`;
    let hits = "";
    chapters.forEach((chapter, i) => {
      const a = at(chapter.start);
      const b = at(chapter.end);
      const left = a - 10;
      const boxWidth = b - a + 20;
      const middle = (a + b) / 2;
      svg +=
        `<rect class="ep" x="${left.toFixed(1)}" y="12" ` +
        `width="${boxWidth.toFixed(1)}" height="52" rx="8"/>` +
        `<rect class="ep-edge" x="${left.toFixed(1)}" y="12" ` +
        `width="${boxWidth.toFixed(1)}" height="52" rx="8"/>`;
      if (chapter.count > DENSE)
        svg +=
          `<circle class="ep-many" cx="${middle.toFixed(1)}" cy="${REST_WIRE}" r="11"/>` +
          `<text class="ep-count" x="${middle.toFixed(1)}" y="${REST_WIRE + 4}" ` +
          `text-anchor="middle">${chapter.count}</text>`;
      else
        for (let j = 0; j < chapter.count; j += 1) {
          const spread = chapter.count > 1 ? j / (chapter.count - 1) : 0.5;
          svg +=
            `<circle class="dot" cx="${(a + (b - a) * spread).toFixed(1)}" ` +
            `cy="${REST_WIRE}" r="4.5"/>`;
        }
      svg +=
        `<text class="ep-yrs" x="${middle.toFixed(1)}" y="26" text-anchor="middle">` +
        `${esc(shortYears(chapter.start, chapter.end))}</text>`;

      const next = chapters[i + 1];
      if (next && years(next.start) - years(chapter.end) >= GAP_YEARS) {
        const gap = (at(next.start) + b) / 2;
        svg +=
          `<text class="qm small" x="${gap.toFixed(1)}" y="${REST_WIRE + 4}" ` +
          `text-anchor="middle">?</text>`;
      }

      // the box may be narrower than a thumb, so the target is grown to the floor
      const target = Math.max(ZONE, boxWidth);
      hits +=
        `<button class="ss-hit" data-target="${Target.Chapter}" data-index="${i}" ` +
        `aria-label="${esc(chapter.title || shortYears(chapter.start, chapter.end))}" ` +
        `style="left:${(middle - target / 2).toFixed(1)}px;top:${REST_WIRE - ZONE / 2}px;` +
        `width:${target.toFixed(1)}px;height:${ZONE}px"></button>`;
    });
    svg += `<text class="ss-hint" x="${x0}" y="74">tap a chapter</text></svg>`;

    this.host.innerHTML = `<div class="ss">${svg}${hits}${shelf}</div>`;
  }

  /** The chapters the resting level draws, in time order. A record with no
   * chapters of its own is one chapter: everything on it. */
  private restChapters(): Chapter[] {
    const chapters = (this.data?.chapters ?? []).filter((c) => c.event_ids.length);
    if (chapters.length)
      return [...chapters].sort((a, b) => years(a.start) - years(b.start));
    const dated = this.dated();
    if (!dated.length) return [];
    return [
      {
        id: "all",
        label: "",
        title: "",
        summary: null,
        cluster_ids: [],
        start: dated[0].dateTime as string,
        end: dated[dated.length - 1].dateTime as string,
        event_ids: dated.map((e) => e.id),
        count: dated.length,
      },
    ];
  }

  /** The moments in the chapter a resting tap landed on. */
  inChapter(index: number): number[] {
    return this.restChapters()[index]?.event_ids ?? [];
  }

  private renderBoard(): void {
    const ids = this.moves.length ? castOfSteps(this.moves) : this.cast;
    const people = ids
      .map((id) => this.person(id))
      .filter((p): p is Person => !!p);
    const { svg, caption } = this.moves.length
      ? board(this.moves, this.at, people, this.data?.events ?? [], this.width)
      : triangle(people, this.width);
    const last = this.moves.length - 1;
    this.pin(BOARD_H + 84);
    const zoom = this.entering ? " in" : "";
    this.entering = false;
    this.host.innerHTML =
      `<div class="ss board${zoom}" style="height:${BOARD_H}px">${svg}` +
      `<button class="corner l ss-hit" data-target="${Target.Back}" ` +
      `aria-label="back to the time line">&#8592;</button></div>` +
      `<div class="bcap">${esc(caption)}</div>` +
      // a cast the coach put on the board has nothing to step through
      (this.moves.length
        ? `<div class="pctl">` +
          `<button type="button" class="btn" data-target="${Target.Prev}" ` +
          `${this.at === 0 ? "disabled" : ""} aria-label="the move before">&#9664;</button>` +
          `<button type="button" class="btn primary" data-target="${Target.Next}" ` +
          `${this.at >= last ? "disabled" : ""}>&#9654; next move</button>` +
          `</div>`
        : "");
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
    if (this.level === Level.Rest && this.selected === null) {
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
    // room for the bracket over the stretch
    const { text, rowsLaid } = this.labels(marks, x0, x1, wire);
    this.laid.rows = rowsLaid;

    let svg =
      `<svg viewBox="0 0 ${width} ${height}" aria-hidden="true">` +
      `<defs><marker id="tip" viewBox="0 0 10 10" refX="8.5" refY="5" ` +
      `markerWidth="5.5" markerHeight="5.5" orient="auto">` +
      `<path d="M0 0 L10 5 L0 10 Z" class="tipfill"/></marker></defs>` +
      this.bandMark(wire) +
      `<line class="wire" x1="${x0}" y1="${wire}" x2="${x1}" y2="${wire}"/>` +
      this.bracket(wire, x0, x1);

    // one dot per moment; moments sharing a date stack instead of merging
    const byDate = new Map<string, Mark[]>();
    for (const mark of marks) {
      const key = mark.event.dateTime as string;
      byDate.set(key, [...(byDate.get(key) ?? []), mark]);
    }
    for (const group of byDate.values()) {
      const x = group[0].x.toFixed(1);
      const lit = group.filter((m) => named.has(m.event.id));
      if (lit.length) {
        if (group.length > lit.length)
          svg += `<circle class="halo" cx="${x}" cy="${wire}" r="7"/>`;
        lit.forEach((mark, i) => {
          const cy = i === 0 ? (lit.length > 1 ? wire + 5 : wire) : i === 1 ? wire - 5 : wire + 5 + 10 * (i - 1);
          svg += this.dot(mark, x, cy, 1, radius, true);
        });
      } else {
        if (group.length > 1)
          svg += `<circle class="halo" cx="${x}" cy="${wire}" r="7" opacity="${opacity}"/>`;
        svg += this.dot(group[0], x, wire, opacity, radius, false);
      }
    }

    svg += this.questions(wire);
    svg += `</svg>`;

    const first = this.yearOf(shown[0]);
    const last = this.yearOf(shown[shown.length - 1]);
    const yearTop = YEAR_TOP;
    let html =
      `<div class="ss-yr" style="left:${x0}px;top:${yearTop}px">${first}</div>`;
    if (last !== first)
      html += `<div class="ss-yr" style="right:${x0}px;top:${yearTop}px">${last}</div>`;

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
    const chosen = mark.event.id === this.selected;
    if (chosen) return `<circle class="dot on" cx="${x}" cy="${cy}" r="7"/>`;
    if (NODAL.has(mark.event.relationship ?? "") || mark.event.relationshipTargets.length >= 2)
      return (
        `<circle class="dot nodal" cx="${x}" cy="${cy}" r="6.5" opacity="${opacity}"/>` +
        `<circle class="dot core" cx="${x}" cy="${cy}" r="2" opacity="${opacity}"/>`
      );
    return `<circle class="dot${lit ? " lit" : ""}" cx="${x}" cy="${cy}" r="${lit ? 5 : radius}" opacity="${opacity}"/>`;
  }

  /** The words. A chosen moment says itself in full over three rows; otherwise
   * the moments the coach named take a row each, tied to their dots. */
  private labels(
    marks: Mark[],
    x0: number,
    x1: number,
    wire: number,
  ): { text: string; rowsLaid: { id: number; row: number }[] } {
    const chosen = marks.find((m) => m.event.id === this.selected);
    const wide = Math.floor((x1 - x0) / CH);
    if (chosen) {
      const event = chosen.event;
      const meta =
        dateText(event.dateTime as string, event.dateCertainty) +
        (event.person_name && event.person_name !== this.protagonist()
          ? ` · ${event.person_name}`
          : "");
      const lines = wrap2(clip(event.label.trim(), Math.min(88, wide * 2)), wide);
      const text = [meta, lines[0], lines[1]]
        .map((line, i) =>
          line
            ? `<div class="ss-t ${i ? "on" : "meta"}" ` +
              `style="left:${x0}px;top:${ROWS[i]}px;width:${x1 - x0}px">${esc(line)}</div>`
            : "",
        )
        .join("");
      return { text, rowsLaid: [] };
    }
    const spotlit = marks.filter((m) => this.named.includes(m.event.id));
    if (!spotlit.length) return { text: "", rowsLaid: [] };
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
      rowsLaid: laid.filter((r) => r.text).map((r) => ({ id: r.id, row: r.row })),
    };
  }

  private protagonist(): string {
    return this.data?.people.find((p) => p.primary)?.name ?? "";
  }

  /** The bracket over the stretch the coach aimed at. It is only drawn when no
   * words are on the picture, because the words sit where it would go. */
  private bracket(wire: number, x0: number, x1: number): string {
    if (!this.focus || this.selected !== null || this.laid.rows.length) return "";
    const a = Math.max(x0, this.x(this.focus.start) - 5);
    const b = Math.min(x1, this.x(this.focus.end) + 5);
    const top = wire - 12;
    // a bracket with no label says a stretch is there but not which one
    const years = `${this.focus.start.slice(0, 4)}–${this.focus.end.slice(0, 4)}`;
    return (
      `<path class="brk" d="M${a.toFixed(1)} ${wire - 8} L${a.toFixed(1)} ${top} ` +
      `L${b.toFixed(1)} ${top} L${b.toFixed(1)} ${wire - 8}"/>` +
      `<text class="brkl" x="${((a + b) / 2).toFixed(1)}" y="${top - 5}" ` +
      `text-anchor="middle">${esc(years)}</text>`
    );
  }

  private bandMark(wire: number): string {
    if (!this.band) return "";
    const a = this.x(this.band.start);
    const b = this.x(this.band.end);
    return (
      `<rect class="span" x="${Math.min(a, b).toFixed(1)}" y="${wire - 14}" ` +
      `width="${Math.max(4, Math.abs(b - a)).toFixed(1)}" height="28" rx="6"/>`
    );
  }

  /** The one amber treatment: the record asking which of two things came first. */
  private questions(wire: number): string {
    if (this.selected !== null || this.named.length) return "";
    const shown = new Set(this.shown().map((e) => e.id));
    return (this.data?.questions ?? [])
      .filter((q: Question) => shown.has(q.event_id))
      .map((q: Question, i, all) => {
        const x = this.x(q.date);
        if (all.slice(0, i).some((other) => Math.abs(this.x(other.date) - x) < 16))
          return "";
        return `<text class="qm small" x="${x.toFixed(1)}" y="${wire - 16}" text-anchor="middle">?</text>`;
      })
      .join("");
  }

  /** The amber question past the right end of the line, for what has no date.
   * It sits above the wire where there is room for it and on the wire where
   * there is not, which is the case at the resting level. */
  private shelfHit(x1: number, wire: number): string {
    if (!this.data?.shelf.length) return "";
    const above = wire - ZONE - 4;
    const top = above >= 0 ? above : wire - ZONE / 2;
    return (
      `<button class="ss-hit shelf" data-target="${Target.Shelf}" ` +
      `aria-label="things with no date yet" ` +
      `style="left:${x1 - 26}px;top:${top}px;width:${ZONE}px;height:${ZONE}px">?</button>`
    );
  }

  /** The next moment a tap on a zone lands on. */
  next(index: number, current: number | null): number | null {
    return cycle(this.inZone(index), current);
  }
}
