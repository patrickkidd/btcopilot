import * as api from "./api";
import { Feature, tap } from "./track";
import { toast } from "./toast";
import type { Cut } from "./types";

/** Selecting a cut inside the chat, on someone else's diagram (R-0629).
 *
 * A cut is a first and a last line, in one sitting or across several. The
 * first tap rings its first line, the second its last and every line between,
 * and a third starts over. A line inside a cut the room already ratified is
 * refused. The amber line under the read-only line says what to tap and,
 * once both ends are in, what the cut spans; the foot bar places it.
 */

export interface CutHandlers {
  /** Selecting turned on or off: the page swaps the message bar for the
   * foot bar. */
  onSelecting(on: boolean): void;
  /** The cut is saved: Next meeting takes over. */
  onPlaced(): void;
}

const month = (d: Date): string =>
  d.toLocaleDateString(undefined, { month: "short" });

/** The days a cut spans and how many sittings it crosses, the way the amber
 * line says it ("10 to 17 Mar, 2 sittings") and the agenda row with the year
 * ("10 to 17 Mar 2026 · 2 sittings"). */
export function spanWords(
  first: Date,
  last: Date,
  sittings: number,
  year = false,
): string {
  const end = `${last.getDate()} ${month(last)}${year ? ` ${last.getFullYear()}` : ""}`;
  const sameMonth =
    first.getMonth() === last.getMonth() &&
    first.getFullYear() === last.getFullYear();
  const start = sameMonth
    ? String(first.getDate())
    : `${first.getDate()} ${month(first)}`;
  const days =
    first.toDateString() === last.toDateString() ? end : `${start} to ${end}`;
  return `${days}${year ? " ·" : ","} ${sittings} sitting${sittings === 1 ? "" : "s"}`;
}

export class CutSelect {
  private on = false;
  private first: HTMLElement | null = null;
  private last: HTMLElement | null = null;
  /** The last line of the newest cut the room ratified, which no new end may
   * fall at or before. */
  private ratified: number | null = null;
  /** A cut already on the agenda, opened to move its lines. */
  private editing: Cut | null = null;
  /** The meeting a new cut joins. */
  private day: string | null = null;

  constructor(
    private list: HTMLElement,
    private strip: HTMLElement,
    private say: HTMLElement,
    private bar: HTMLElement,
    private handlers: CutHandlers,
  ) {
    this.list.addEventListener(
      "click",
      (e) => {
        if (!this.on) return;
        const bubble = (e.target as Element).closest<HTMLElement>(
          ".bub[data-statement]",
        );
        if (!bubble) return;
        e.stopPropagation();
        e.preventDefault();
        this.pick(bubble);
      },
      true,
    );
    this.strip
      .querySelector(".cs-cancel")!
      .addEventListener("click", () => this.stop());
    this.bar.addEventListener("click", (e) => {
      if ((e.target as Element).closest(".ct-go:not([disabled])"))
        void this.place();
    });
  }

  selecting(): boolean {
    return this.on;
  }

  /** Turn selecting on for a diagram, with its cuts read for the ratified
   * line and, when given, one cut already on the agenda lit where it stands. */
  async start(
    diagramId: number,
    day: string | null,
    editing: Cut | null = null,
  ): Promise<void> {
    const cuts = await api.diagramCuts(diagramId);
    const done = cuts.filter((cut) => cut.ratified_at !== null).at(-1);
    this.ratified = done?.end_statement_id ?? null;
    this.day = day;
    this.editing = editing;
    this.first = editing ? this.bubble(editing.start_statement_id) : null;
    this.last = editing ? this.bubble(editing.end_statement_id) : null;
    this.on = true;
    this.strip.hidden = false;
    this.bar.hidden = false;
    this.handlers.onSelecting(true);
    this.paint();
  }

  stop(): void {
    if (!this.on) return;
    this.on = false;
    this.first = this.last = null;
    this.editing = null;
    this.strip.hidden = true;
    this.bar.hidden = true;
    this.paint();
    this.handlers.onSelecting(false);
  }

  /** Lit lines and dividers are redrawn once older pages are read in. */
  repaint(): void {
    if (this.on) this.paint();
  }

  private bubble(statementId: number): HTMLElement | null {
    return this.list.querySelector<HTMLElement>(
      `.bub[data-statement="${statementId}"]`,
    );
  }

  private lines(): HTMLElement[] {
    return [...this.list.querySelectorAll<HTMLElement>(".bub[data-statement]")];
  }

  /** At or before the last ratified line, which is on screen whenever a line
   * after it is: the thread reads back in order. */
  private refused(bubble: HTMLElement): boolean {
    if (this.ratified === null) return false;
    const line = this.bubble(this.ratified);
    if (!line) return false;
    return !(
      line.compareDocumentPosition(bubble) & Node.DOCUMENT_POSITION_FOLLOWING
    );
  }

  private pick(bubble: HTMLElement): void {
    if (this.refused(bubble)) {
      toast("That part was already ratified");
      return;
    }
    tap(Feature.CutLine);
    if (!this.first || this.last) {
      this.first = bubble;
      this.last = null;
    } else if (
      bubble.compareDocumentPosition(this.first) &
      Node.DOCUMENT_POSITION_FOLLOWING
    ) {
      this.last = this.first;
      this.first = bubble;
    } else this.last = bubble;
    this.paint();
  }

  /** The sitting divider a line falls under. */
  private sitting(bubble: HTMLElement): HTMLElement {
    let node = bubble.previousElementSibling;
    while (node && !node.classList.contains("sitting"))
      node = node.previousElementSibling;
    return node as HTMLElement;
  }

  private span(): string {
    const top = this.sitting(this.first!);
    const end = this.sitting(this.last!);
    let count = 1;
    for (
      let node = top.nextElementSibling;
      node && node !== end.nextElementSibling;
      node = node.nextElementSibling
    )
      if (node.classList.contains("sitting")) count += 1;
    return spanWords(
      new Date(top.dataset.started!),
      new Date(end.dataset.started!),
      count,
    );
  }

  private paint(): void {
    const lines = this.lines();
    const from = this.first ? lines.indexOf(this.first) : -1;
    const to = this.last ? lines.indexOf(this.last) : from;
    lines.forEach((bubble, at) => {
      const inside = this.on && from >= 0 && from <= at && at <= to;
      bubble.classList.toggle("lit", inside);
      bubble.classList.toggle("after", this.on && !!this.last && at > to);
    });
    this.say.textContent = `Selecting a cut · ${
      this.first && this.last
        ? this.span()
        : this.first
          ? "now tap the last line"
          : "tap the first line, then the last"
    }`;
    this.bar.innerHTML =
      `<button class="btn ct-go${this.first && this.last ? " go" : ""}" type="button"` +
      `${this.first && this.last ? "" : " disabled"}>Place this cut</button>`;
  }

  private async place(): Promise<void> {
    if (!this.first || !this.last) return;
    tap(Feature.CutConfirm);
    const start = Number(this.first.dataset.statement);
    const end = Number(this.last.dataset.statement);
    try {
      if (this.editing) await api.moveCut(this.editing.id, start, end);
      else await api.putOnAgenda(start, end, this.day);
    } catch (error) {
      if (!(error instanceof api.Failed) || error.status !== 400) throw error;
      toast("That cut overlaps one already placed");
      return;
    }
    this.stop();
    this.handlers.onPlaced();
  }
}
