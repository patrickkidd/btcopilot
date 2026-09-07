import { esc } from "./dom";
import type { Chapter, Person, Timeline, TimelineEvent } from "./types";

/** The pinned picture: a horizontal time axis with each cluster drawn as one
 * blob. No words at rest (DRAWABILITY, at-rest vocabulary). Words arrive only
 * when a cluster is open, and the moves are drawn only while a play-by-play
 * steps through them. */

const REST_H = 66;
const OPEN_H = 148;
const REST_AXIS = 40;
const OPEN_AXIS = 116;
const STAGE_Y = 52;
const PAD = 24;

export interface PictureHandlers {
  onCluster(id: string): void;
}

const YEAR = 365.25 * 24 * 3600 * 1000;

function years(iso: string): number {
  return new Date(iso + "T00:00:00Z").getTime() / YEAR;
}

export class Picture {
  private data: Timeline | null = null;
  private open: string | null = null;
  private aimed = new Set<number>();
  private moving: TimelineEvent | null = null;
  private span: { min: number; max: number } = { min: 0, max: 1 };

  constructor(
    private host: HTMLElement,
    handlers: PictureHandlers,
  ) {
    window.addEventListener("resize", () => this.render());
    this.host.addEventListener("click", (e) => {
      const hit = (e.target as Element).closest<SVGElement>("[data-cluster]");
      if (hit?.dataset.cluster) handlers.onCluster(hit.dataset.cluster);
    });
  }

  setData(data: Timeline): void {
    this.data = data;
    const dates = data.chapters.flatMap((c) => [years(c.start), years(c.end)]);
    const min = dates.length ? Math.min(...dates) : 0;
    const max = dates.length ? Math.max(...dates) : 1;
    this.span = { min, max: max - min < 1 ? min + 1 : max };
    this.render();
  }

  setOpen(id: string | null): void {
    this.open = id;
    this.render();
  }

  /** Aim the picture at what a chip names — the coach pointing, or the user's
   * own tap coming back. */
  aim(eventIds: number[]): void {
    this.aimed = new Set(eventIds);
    this.moving = null;
    const chapter = this.chapterOf(eventIds[0]);
    if (chapter) this.open = chapter.id;
    this.render();
  }

  /** One step of a play-by-play: the event pulses and its move is drawn. */
  step(eventId: number): void {
    this.aimed = new Set([eventId]);
    this.moving = this.data?.events.find((e) => e.id === eventId) ?? null;
    const chapter = this.chapterOf(eventId);
    if (chapter) this.open = chapter.id;
    this.render();
  }

  clearAim(): void {
    this.aimed.clear();
    this.moving = null;
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
    return this.host.clientWidth || 400;
  }

  private get axisY(): number {
    return this.open ? OPEN_AXIS : REST_AXIS;
  }

  private x(iso: string): number {
    const { min, max } = this.span;
    return PAD + ((years(iso) - min) / (max - min)) * (this.width - 2 * PAD);
  }

  private person(id: number | null): Person | undefined {
    return id === null ? undefined : this.data?.people.find((p) => p.id === id);
  }

  private render(): void {
    if (!this.data) return;
    const height = this.open ? OPEN_H : REST_H;
    const w = this.width;
    this.host.innerHTML =
      `<svg viewBox="0 0 ${w} ${height}" width="${w}" height="${height}" ` +
      `role="img" aria-label="Your family over time">` +
      `<line class="axis" x1="${PAD}" y1="${this.axisY}" x2="${w - PAD}" y2="${this.axisY}"/>` +
      this.data.chapters.map((c) => this.blob(c)).join("") +
      this.stage() +
      `</svg>`;
  }

  private blob(chapter: Chapter): string {
    const a = this.x(chapter.start);
    const b = this.x(chapter.end);
    const mid = (a + b) / 2;
    const y = this.axisY;
    const rx = Math.max(8, (b - a) / 2 + 6);
    const ry = 6 + Math.min(8, chapter.count);
    const on = chapter.id === this.open;
    const lit = chapter.event_ids.some((id) => this.aimed.has(id));
    const dots = on
      ? chapter.event_ids
          .map((id) => this.data?.events.find((e) => e.id === id))
          .filter((e): e is TimelineEvent => !!e?.dateTime)
          .map(
            (e) =>
              `<circle class="ev${this.aimed.has(e.id) ? " lit" : ""}" ` +
              `cx="${this.x(e.dateTime as string)}" cy="${y}" r="3.5"/>`,
          )
          .join("")
      : "";
    return (
      `<g class="cl${on ? " on" : ""}${lit ? " lit" : ""}" data-cluster="${chapter.id}" ` +
      `role="button" tabindex="0" aria-label="${esc(chapter.label)}">` +
      `<ellipse class="hit" cx="${mid}" cy="${y}" rx="${rx + 10}" ry="22"/>` +
      `<ellipse class="body" cx="${mid}" cy="${y}" rx="${rx}" ry="${ry}"/>` +
      dots +
      `</g>`
    );
  }

  /** The move being played: the people it touches, an arrow to each target,
   * and an amber ring when anxiety moved. */
  private stage(): string {
    const event = this.moving;
    if (!event || !this.open) return "";
    const subject = this.person(event.child ?? event.person);
    const targets = [
      ...event.relationshipTargets,
      ...(event.spouse === null ? [] : [event.spouse]),
    ]
      .map((id) => this.person(id))
      .filter((p): p is Person => !!p);
    const cast = [subject, ...targets].filter((p): p is Person => !!p);
    if (!cast.length) return "";
    const gap = Math.min(130, (this.width - 2 * PAD) / (cast.length + 1));
    const left = this.width / 2 - (gap * (cast.length - 1)) / 2;
    const at = (i: number) => left + i * gap;
    const nodes = cast
      .map(
        (p, i) =>
          `<g class="pn${i === 0 && event.anxiety ? " anx" : ""}">` +
          `<circle class="sym" cx="${at(i)}" cy="${STAGE_Y}" r="14"/>` +
          (i === 0 && event.anxiety
            ? `<circle class="ring" cx="${at(i)}" cy="${STAGE_Y}" r="21"/>`
            : "") +
          `<text x="${at(i)}" y="${STAGE_Y + 38}" text-anchor="middle">${esc(p.name)}</text>` +
          `</g>`,
      )
      .join("");
    const arrows = targets
      .map((_, i) => {
        const from = at(0) + 16;
        const to = at(i + 1) - 18;
        return from < to
          ? `<path class="arrow" d="M${from} ${STAGE_Y} L${to} ${STAGE_Y}" marker-end="url(#tip)"/>`
          : `<path class="arrow" d="M${at(0) - 16} ${STAGE_Y} L${at(i + 1) + 18} ${STAGE_Y}" marker-end="url(#tip)"/>`;
      })
      .join("");
    return (
      `<defs><marker id="tip" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" ` +
      `markerHeight="6" orient="auto"><path d="M0 0 L8 4 L0 8 z" fill="currentColor"/></marker></defs>` +
      `<g class="cast">${arrows}${nodes}</g>`
    );
  }
}
