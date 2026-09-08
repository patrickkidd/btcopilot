import { esc } from "./dom";
import { MarkKind, merge, span, type Mark, type Slot } from "./layout";
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

const SEQUENCE_MS = 1100;
const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** The pinned picture: a time line with a dot per dated event, the stretches
 * drawn as groupings behind them, and the amber question mark where the record
 * has a question. No words at rest beyond the two end years, which are what
 * make it read as time rather than a shape (DRAWABILITY, at-rest vocabulary).
 * Words arrive in the caption when a mark is tapped; the people are drawn only
 * while a play-by-play or a view puts them on stage. */

const REST_H = 88;
const STAGE_H = 168;
const REST_AXIS = 44;
const STAGE_AXIS = 136;
const STAGE_Y = 56;
const PAD = 26;
const DOT_R = 4;
/** Question marks are wider than dots, so they need more room before they read
 * as two separate questions rather than one smudge. */
const QUESTION_GAP = 15;

export enum Target {
  Cluster = "cluster",
  Event = "event",
  Count = "count",
  Question = "question",
  Shelf = "shelf",
}

export interface Tap {
  target: Target;
  id: string;
  ids: number[];
}

export interface PictureHandlers {
  onTap(tap: Tap): void;
}

const YEAR = 365.25 * 24 * 3600 * 1000;

export function years(iso: string): number {
  return new Date(iso + "T00:00:00Z").getTime() / YEAR;
}

const yearOf = (iso: string): string => iso.slice(0, 4);

export class Picture {
  private data: Timeline | null = null;
  private open: string | null = null;
  private openIds: number[] = [];
  private aimed = new Set<number>();
  private moving: TimelineEvent | null = null;
  private cast: number[] = [];
  private closed = false;
  private band: { start: string; end: string } | null = null;
  private range = { min: 0, max: 1 };

  constructor(
    private host: HTMLElement,
    handlers: PictureHandlers,
  ) {
    window.addEventListener("resize", () => this.render());
    const tap = (e: Event) => {
      const hit = (e.target as Element).closest<SVGElement>("[data-target]");
      if (!hit?.dataset.target) return;
      e.preventDefault();
      handlers.onTap({
        target: hit.dataset.target as Target,
        id: hit.dataset.id ?? "",
        ids: (hit.dataset.ids ?? "")
          .split(",")
          .filter(Boolean)
          .map((part) => Number(part)),
      });
    };
    this.host.addEventListener("click", tap);
  }

  setData(data: Timeline): void {
    this.data = data;
    this.range = span(this.dated().map((e) => years(e.dateTime as string)));
    this.render();
  }

  /** What the caption is about: a stretch, or the events a mark stands for. */
  select(id: string | null, ids: number[] = []): void {
    this.open = id;
    this.openIds = ids;
    this.render();
  }

  /** Aim the picture at what a chip names — the coach pointing, or the user's
   * own tap coming back. */
  aim(eventIds: number[]): void {
    this.aimed = new Set(eventIds);
    this.moving = null;
    const chapter = this.chapterOf(eventIds[0]);
    if (chapter) {
      this.open = chapter.id;
      this.openIds = [];
    }
    this.render();
  }

  /** One step of a play-by-play: the event pulses and its move is drawn. */
  step(eventId: number): void {
    this.aimed = new Set([eventId]);
    this.cast = [];
    this.closed = false;
    this.moving = this.data?.events.find((e) => e.id === eventId) ?? null;
    const chapter = this.chapterOf(eventId);
    if (chapter) {
      this.open = chapter.id;
      this.openIds = [];
    }
    this.render();
  }

  /** Draw one view the coach asked for. The set is closed (R-0075): a triangle
   * over three people, a span of time, two moments compared, a sequence of
   * moves, or one cluster. */
  async show(view: View): Promise<void> {
    this.band = null;
    this.cast = [];
    switch (view.kind) {
      case ViewKind.Triangle:
        this.cast = view.persons;
        this.closed = true;
        this.moving = null;
        this.aimed.clear();
        this.render();
        return;
      case ViewKind.Span:
        this.band = { start: view.start, end: view.end };
        this.moving = null;
        this.render();
        return;
      case ViewKind.Compare:
        this.aim([view.event_a, view.event_b]);
        return;
      case ViewKind.Sequence:
        for (const id of view.events) {
          this.step(id);
          await pause(SEQUENCE_MS);
        }
        return;
      case ViewKind.Cluster: {
        const chapter = this.data?.chapters.find(
          (c) => c.id === view.cluster || c.cluster_ids.includes(view.cluster),
        );
        if (chapter) this.select(chapter.id);
        return;
      }
    }
  }

  clearAim(): void {
    this.aimed.clear();
    this.moving = null;
    this.cast = [];
    this.band = null;
    this.closed = false;
    this.render();
  }

  openChapter(): Chapter | null {
    return this.data?.chapters.find((c) => c.id === this.open) ?? null;
  }

  private chapterOf(eventId: number | undefined): Chapter | null {
    if (eventId === undefined || !this.data) return null;
    return this.data.chapters.find((c) => c.event_ids.includes(eventId)) ?? null;
  }

  /** The viewBox is sized in real pixels so nothing is stretched: the time axis
   * has to span the full width, and a person has to stay round. */
  private get width(): number {
    return this.host.clientWidth || 360;
  }

  /** People are only drawn while a move or a view puts them on stage, and only
   * then does the picture need the extra height. */
  private get staged(): boolean {
    return this.cast.length > 0 || this.moving !== null;
  }

  private get axisY(): number {
    return this.staged ? STAGE_AXIS : REST_AXIS;
  }

  private x(iso: string): number {
    const { min, max } = this.range;
    return PAD + ((years(iso) - min) / (max - min)) * (this.right - PAD);
  }

  /** The axis stops short of the shelf mark so the two never sit on top of
   * each other on a phone. */
  private get right(): number {
    return this.width - (this.hasShelf ? PAD + 20 : PAD);
  }

  private get hasShelf(): boolean {
    return !!this.data?.shelf.length;
  }

  private person(id: number | null): Person | undefined {
    return id === null ? undefined : this.data?.people.find((p) => p.id === id);
  }

  /** What the line can carry: a date the record is at least approximately sure
   * of. Anything else is on the shelf and must not also appear on the line. */
  private dated(): TimelineEvent[] {
    return (this.data?.events ?? []).filter(
      (e) => !!e.dateTime && e.dateCertainty !== DateCertainty.Unknown,
    );
  }

  private render(): void {
    if (!this.data) return;
    const height = this.staged ? STAGE_H : REST_H;
    const w = this.width;
    const empty = !this.dated().length;
    this.host.innerHTML =
      `<svg viewBox="0 0 ${w} ${height}" width="${w}" height="${height}" ` +
      `role="img" aria-label="Your family over time">` +
      (empty
        ? this.nothing()
        : `<line class="axis" x1="${PAD}" y1="${this.axisY}" x2="${this.right}" y2="${this.axisY}"/>` +
          this.band_() +
          this.data.chapters.map((c) => this.group(c)).join("") +
          this.marks() +
          this.questions() +
          this.ends() +
          this.shelf()) +
      this.stage() +
      `</svg>`;
  }

  /** Nothing has a date yet: one amber question mark, which is the whole
   * at-rest vocabulary a record this empty has earned. */
  private nothing(): string {
    const y = this.axisY;
    return (
      `<line class="axis empty" x1="${PAD}" y1="${y}" x2="${this.width - PAD}" y2="${y}"/>` +
      `<g class="ask q" data-target="${Target.Shelf}" data-id="none" ` +
      `role="button" tabindex="0" aria-label="Nothing has a date yet">` +
      `<circle class="hit" cx="${this.width / 2}" cy="${y}" r="26"/>` +
      `<text class="qm" x="${this.width / 2}" y="${y + 8}" text-anchor="middle">?</text>` +
      `</g>`
    );
  }

  /** The two end years. Without them the strip is a shape; with them it is a
   * span of time, and they are the only words the resting picture carries. */
  private ends(): string {
    const dates = this.dated().map((e) => e.dateTime as string);
    const first = yearOf(dates[0]);
    const last = yearOf(dates[dates.length - 1]);
    const y = this.axisY + 20;
    const label = (x: number, text: string, anchor: string) =>
      `<text class="yr" x="${x}" y="${y}" text-anchor="${anchor}">${esc(text)}</text>`;
    return first === last
      ? label(this.width / 2, first, "middle")
      : label(PAD, first, "start") + label(this.right, last, "end");
  }

  /** One stretch, drawn only as wide as its own events: a grouping behind the
   * dots, never a shape that stands in for them. Two stretches never overlap —
   * overlapping groupings read as one shape, which is the whole problem. */
  private group(chapter: Chapter): string {
    const a = this.x(chapter.start);
    const b = this.x(chapter.end);
    const y = this.axisY;
    const mid = (a + b) / 2;
    const chapters = this.data?.chapters ?? [];
    const at = chapters.indexOf(chapter);
    const before = chapters[at - 1];
    const after = chapters[at + 1];
    const room = Math.min(
      before ? (a - this.x(before.end)) / 2 : Infinity,
      after ? (this.x(after.start) - b) / 2 : Infinity,
    );
    const half = Math.max(
      3,
      Math.min(
        Math.max(9, (b - a) / 2 + 7),
        (b - a) / 2 + Math.max(room - 1, 0),
        // never past the ends of the line, where the years are written
        mid - PAD + 2,
        this.right - mid + 2,
      ),
    );
    const on = chapter.id === this.open;
    const lit = chapter.event_ids.some((id) => this.aimed.has(id));
    return (
      `<g class="cl${on ? " on" : ""}${lit ? " lit" : ""}" ` +
      `data-target="${Target.Cluster}" data-id="${esc(chapter.id)}" ` +
      `data-ids="${chapter.event_ids.join(",")}" ` +
      `role="button" tabindex="0" aria-label="${esc(chapter.title)}">` +
      `<rect class="hit" x="${mid - half - 6}" y="${y - 22}" ` +
      `width="${half * 2 + 12}" height="44" rx="8"/>` +
      `<rect class="body" x="${mid - half}" y="${y - 13}" ` +
      `width="${half * 2}" height="26" rx="13"/>` +
      `</g>`
    );
  }

  /** A dot per dated event, and a count mark wherever dots would collide. The
   * merging happens inside a stretch, so a count never stands for moments from
   * two different stretches. */
  private marks(): string {
    const events = this.dated();
    const byId = new Map(events.map((e) => [e.id, e]));
    const runs = new Map<string, Mark[]>();
    for (const event of events) {
      const key = this.chapterOf(event.id)?.id ?? "";
      const mark = { id: event.id, x: this.x(event.dateTime as string) };
      runs.set(key, [...(runs.get(key) ?? []), mark]);
    }
    return [...runs.values()]
      .flatMap((marks) => merge(marks))
      .map((slot) => this.mark(slot, byId))
      .join("");
  }

  private mark(slot: Slot, byId: Map<number, TimelineEvent>): string {
    const y = this.axisY;
    const lit = slot.ids.some((id) => this.aimed.has(id));
    const on = slot.ids.every((id) => this.openIds.includes(id)) && !!this.openIds.length;
    const cls = `${lit ? " lit" : ""}${on ? " on" : ""}`;
    const data =
      `data-id="${slot.ids.join(",")}" data-ids="${slot.ids.join(",")}"`;
    if (slot.kind === MarkKind.Dot) {
      const label = byId.get(slot.ids[0])?.label ?? "A moment";
      return (
        `<g class="ev${cls}" data-target="${Target.Event}" ${data} ` +
        `role="button" tabindex="0" aria-label="${esc(label)}">` +
        `<circle class="hit" cx="${slot.x}" cy="${y}" r="15"/>` +
        `<circle class="dot" cx="${slot.x}" cy="${y}" r="${DOT_R}"/></g>`
      );
    }
    const n = String(slot.ids.length);
    const w = 16 + n.length * 7;
    return (
      `<g class="ct${cls}" data-target="${Target.Count}" ${data} ` +
      `role="button" tabindex="0" aria-label="${n} moments">` +
      `<rect class="hit" x="${slot.x - w / 2 - 6}" y="${y - 15}" ` +
      `width="${w + 12}" height="30" rx="8"/>` +
      `<rect class="pill" x="${slot.x - w / 2}" y="${y - 9}" ` +
      `width="${w}" height="18" rx="9"/>` +
      `<text class="n" x="${slot.x}" y="${y + 4}" text-anchor="middle">${n}</text></g>`
    );
  }

  /** The amber question mark where the record cannot tell the order of two
   * things that happened at about the same time (DRAWABILITY). Questions about
   * the same years merge into one mark rather than stacking on each other. */
  private questions(): string {
    const y = this.axisY;
    const all = this.data?.questions ?? [];
    const marks: Mark[] = all.map((q: Question, i) => ({
      id: i,
      x: this.x(q.date),
    }));
    return merge(marks, QUESTION_GAP)
      .map((slot) => {
        const asked = slot.ids.map((i) => all[i]);
        const ids = [
          ...new Set(asked.flatMap((q) => [q.event_id, q.other_event_id])),
        ];
        return (
          `<g class="ask q" data-target="${Target.Question}" ` +
          `data-id="${ids.join(",")}" data-ids="${ids.join(",")}" ` +
          `role="button" tabindex="0" aria-label="An unanswered question">` +
          `<circle class="hit" cx="${slot.x}" cy="${y - 17}" r="13"/>` +
          `<text class="qm" x="${slot.x}" y="${y - 13}" text-anchor="middle">?</text></g>`
        );
      })
      .join("");
  }

  /** What has no date at all sits past the end of the line, never positioned
   * on it (DRAWABILITY, the undated shelf). */
  private shelf(): string {
    if (!this.hasShelf) return "";
    const x = this.width - PAD + 6;
    const y = this.axisY;
    return (
      `<g class="ask shelf" data-target="${Target.Shelf}" data-id="shelf" ` +
      `role="button" tabindex="0" aria-label="Things with no date yet">` +
      `<circle class="hit" cx="${x}" cy="${y}" r="16"/>` +
      `<circle class="ring" cx="${x}" cy="${y}" r="11"/>` +
      `<text class="qm" x="${x}" y="${y + 5}" text-anchor="middle">?</text></g>`
    );
  }

  /** A span of time the coach named, drawn on the axis itself. */
  private band_(): string {
    if (!this.band) return "";
    const a = this.x(this.band.start);
    const b = this.x(this.band.end);
    return (
      `<rect class="band" x="${Math.min(a, b)}" y="${this.axisY - 17}" ` +
      `width="${Math.max(4, Math.abs(b - a))}" height="34" rx="6"/>`
    );
  }

  /** The people a view or a move puts on stage: a move draws the subject and
   * whoever it reaches, a triangle draws its three and closes the loop. */
  private stage(): string {
    if (this.cast.length) return this.figures(this.cast, this.closed, null);
    const event = this.moving;
    if (!event) return "";
    const reached = [
      ...event.relationshipTargets,
      ...(event.spouse === null ? [] : [event.spouse]),
    ];
    const subject = event.child ?? event.person;
    if (subject === null && !reached.length) return "";
    return this.figures(
      [...(subject === null ? [] : [subject]), ...reached],
      false,
      event.anxiety ? 0 : null,
    );
  }

  /** People on a line, an arrow from the first to each of the others, closed
   * into a loop for a triangle, and an amber ring on whoever is anxious. */
  private figures(ids: number[], closed: boolean, ring: number | null): string {
    const cast = ids
      .map((id) => this.person(id))
      .filter((p): p is Person => !!p);
    if (!cast.length) return "";
    const gap = Math.min(130, (this.width - 2 * PAD) / (cast.length + 1));
    const left = this.width / 2 - (gap * (cast.length - 1)) / 2;
    const at = (i: number) => left + i * gap;
    const nodes = cast
      .map(
        (p, i) =>
          `<g class="pn${ring === i ? " anx" : ""}">` +
          `<circle class="sym" cx="${at(i)}" cy="${STAGE_Y}" r="14"/>` +
          (ring === i
            ? `<circle class="ring" cx="${at(i)}" cy="${STAGE_Y}" r="21"/>`
            : "") +
          `<text x="${at(i)}" y="${STAGE_Y + 38}" text-anchor="middle">${esc(p.name)}</text>` +
          `</g>`,
      )
      .join("");
    const link = (a: number, b: number) => {
      const forward = at(a) < at(b);
      const from = at(a) + (forward ? 16 : -16);
      const to = at(b) + (forward ? -18 : 18);
      return `<path class="arrow" d="M${from} ${STAGE_Y} L${to} ${STAGE_Y}" marker-end="url(#tip)"/>`;
    };
    const pairs = cast.slice(1).map((_, i) => link(0, i + 1));
    if (closed && cast.length === 3)
      pairs.push(
        `<path class="arrow tri" d="M${at(1)} ${STAGE_Y + 16} Q${(at(1) + at(2)) / 2} ${
          STAGE_Y + 46
        } ${at(2)} ${STAGE_Y + 16}"/>`,
      );
    return (
      `<defs><marker id="tip" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" ` +
      `markerHeight="6" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="currentColor"/></marker></defs>` +
      `<g class="cast">${pairs.join("")}${nodes}</g>`
    );
  }
}
