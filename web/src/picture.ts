import { esc } from "./dom";
import { draw, figure, ring, type Figure } from "./moves";
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

const SEQUENCE_MS = 1100;
const pause = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** The pinned picture: the sentence spotlight the owner converged on
 * (OWNER_RULINGS 2026-09-02). A wire with a dot per moment; the moments the
 * coach's latest message names are drawn bright with their words above them,
 * tied to their dots, and everything else recedes to a dim dot. A tap on the
 * wire steps through the moments under the thumb and that moment writes itself
 * out in full. The people appear only while a play-by-play walks the moves. */

/** While a move plays the picture grows just enough to stand the people above
 * the wire; any more and the move floats in an empty box. */
const STAGE_H = 252;
const STAGE_GAP = 96;
const NODAL = new Set(["cutoff", "defined-self", "fusion"]);

export enum Target {
  Zone = "zone",
  Band = "band",
  Question = "question",
  Shelf = "shelf",
}

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
  private moving: TimelineEvent | null = null;
  private cast: number[] = [];
  private closed = false;
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
    this.moving = this.data?.events.find((e) => e.id === eventId) ?? null;
    this.selected = eventId;
    this.render();
  }

  async show(view: View): Promise<void> {
    this.band = null;
    this.cast = [];
    switch (view.kind) {
      case ViewKind.Triangle:
        this.cast = view.persons;
        this.closed = true;
        this.moving = null;
        this.render();
        return;
      case ViewKind.Span:
        this.band = { start: view.start, end: view.end };
        this.moving = null;
        this.render();
        return;
      case ViewKind.Compare:
        this.spotlight([view.event_a, view.event_b]);
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
    this.moving = null;
    this.cast = [];
    this.band = null;
    this.focus = null;
    this.closed = false;
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

  private get staged(): boolean {
    return this.cast.length > 0 || this.moving !== null;
  }

  private x(iso: string): number {
    const { min, max } = this.range;
    const x1 = this.width - X_PAD;
    return X_PAD + ((years(iso) - min) / (max - min)) * (x1 - X_PAD);
  }

  private render(): void {
    if (!this.data) return;
    const width = this.width;
    const x0 = X_PAD;
    const x1 = width - X_PAD;
    const shown = this.shown();
    const height = this.staged ? STAGE_H : PIC_H;
    const wire = this.staged ? STAGE_H - 59 : WIRE;

    if (!shown.length) {
      this.laid = { zones: [], rows: [] };
      this.host.innerHTML =
        `<div class="ss" style="height:${PIC_H}px">` +
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
    svg += this.stage(width, wire);
    svg += `</svg>`;

    const first = this.yearOf(shown[0]);
    const last = this.yearOf(shown[shown.length - 1]);
    const yearTop = this.staged ? height - 22 : YEAR_TOP;
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

    this.host.innerHTML = `<div class="ss" style="height:${height}px">${svg}${text}${html}${hits}</div>`;
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
      text +=
        `<div class="ss-t on" style="left:${row.left.toFixed(1)}px;top:${ROWS[row.row]}px;` +
        `width:${row.width.toFixed(1)}px;text-align:${row.align}">${esc(row.text)}</div>`;
    }
    return { text, rowsLaid: laid.map((r) => ({ id: r.id, row: r.row })) };
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
    return (
      `<path class="brk" d="M${a.toFixed(1)} ${wire - 8} L${a.toFixed(1)} ${top} ` +
      `L${b.toFixed(1)} ${top} L${b.toFixed(1)} ${wire - 8}"/>`
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

  private shelfHit(x1: number, wire: number): string {
    if (!this.data?.shelf.length) return "";
    return (
      `<button class="ss-hit shelf" data-target="${Target.Shelf}" ` +
      `aria-label="things with no date yet" ` +
      `style="left:${x1 - 26}px;top:${wire - ZONE - 4}px;width:${ZONE}px;height:${ZONE}px">?</button>`
    );
  }

  /** The people, only while a move or a view puts them on stage. The simple
   * circular layout the 2026-09-02 ruling asked to keep for now. */
  private stage(width: number, _wire: number): string {
    const ids = this.cast.length ? this.cast : this.castOfMove();
    const people = ids
      .map((id) => this.person(id))
      .filter((p): p is Person => !!p)
      .map((p) => ({ id: p.id, name: p.name }));
    if (!people.length) return "";
    const figures: Figure[] = ring(people, width, STAGE_H - 59 - STAGE_GAP);
    const event = this.moving;
    const at = (id: number) => figures.find((f) => f.id === id) ?? null;
    let marks = "";
    const classes = new Map<number, string>();
    if (event) {
      const subject = event.child ?? event.person;
      const reached = event.relationshipTargets[0] ?? event.spouse ?? null;
      const actor = at(subject ?? -1);
      if (actor) {
        const drawn = draw(event.relationship, actor, at(reached ?? -1), {
          symptom: event.symptom,
          anxiety: event.anxiety,
          functioning: event.functioning,
        });
        marks = drawn.marks;
        classes.set(actor.id, drawn.actor);
        if (reached !== null && drawn.target) classes.set(reached, drawn.target);
      }
    } else if (this.closed && figures.length === 3) {
      marks = figures
        .map((f, i) => {
          const next = figures[(i + 1) % figures.length];
          return `<path class="mv-tri" d="M${f.x.toFixed(1)} ${f.y.toFixed(1)} L${next.x.toFixed(1)} ${next.y.toFixed(1)}"/>`;
        })
        .join("");
    }
    return (
      `<g class="cast">${marks}` +
      figures.map((f) => figure(f, classes.get(f.id) ?? "", (classes.get(f.id) ?? "").includes("anx"))).join("") +
      `</g>`
    );
  }

  private castOfMove(): number[] {
    const event = this.moving;
    if (!event) return [];
    const subject = event.child ?? event.person;
    const reached = [
      ...event.relationshipTargets,
      ...(event.spouse === null ? [] : [event.spouse]),
    ];
    return [...(subject === null ? [] : [subject]), ...reached];
  }

  /** The next moment a tap on a zone lands on. */
  next(index: number, current: number | null): number | null {
    return cycle(this.inZone(index), current);
  }
}
