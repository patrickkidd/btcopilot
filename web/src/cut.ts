import * as api from "./api";
import { Feature, tap } from "./track";
import { el, esc, type Title } from "./dom";
import { dragScroll } from "./drag";
import { divider } from "./thread";
import { toast } from "./toast";
import { rowDate } from "./when";
import type { SessionTurn, SessionTurns } from "./types";

/** Placing the cut: the family's whole thread read-only in one scroll, with
 * the same line between sittings the chat shows, a row of its sittings that
 * jumps to each, and the one button that puts the cut on the agenda (R-0267).
 *
 * A cut is a first and a last line, in one sitting or across several. Taps
 * take turns: the first sets where the cut starts, the next where it ends.
 * The lines inside it are lit and the rest dimmed, and no end can be placed
 * at or before the last point already ratified.
 */

export interface CutHandlers {
  /** The cut is on the agenda: the agenda screen takes over. */
  onPlaced(): void;
  /** What the screen is called, which the title row shows. */
  onTitle(title: string | Title): void;
}

enum End {
  First = "first",
  Last = "last",
}

export class Cut {
  private read: SessionTurns | null = null;
  private first: number | null = null;
  private last: number | null = null;
  /** Which end the next tap places. */
  private next = End.First;
  /** The meeting a cut newly put on the agenda joins. */
  private day: string | null = null;
  /** The sitting the screen opens at, once it is on screen. */
  private opening = 0;

  constructor(
    private jump: HTMLElement,
    private list: HTMLElement,
    private bar: HTMLElement,
    private handlers: CutHandlers,
  ) {
    this.list.addEventListener("click", (e) => {
      const bubble = (e.target as Element).closest<HTMLElement>(".bub.line");
      if (bubble) this.move(Number(bubble.dataset.turn));
    });
    this.jump.addEventListener("click", (e) => {
      const to = (e.target as Element).closest<HTMLElement>(".ct-to");
      if (to) this.reach(Number(to.dataset.sitting));
    });
    this.bar.addEventListener("click", (e) => {
      if ((e.target as Element).closest(".ct-go")) void this.place();
    });
    dragScroll(this.list);
  }

  /** Open the thread of one sitting's family at that sitting. A cut already
   * on the agenda opens lit where it stands; a new one starts as the
   * sitting's lines not yet ratified, and joins the meeting on `day`. */
  async open(discussionId: number, day: string | null): Promise<void> {
    this.day = day;
    const read = (this.read = await api.sessionTurns(discussionId));
    const open = read.turns.filter((t) => !this.ratified(t));
    const here = open.filter((t) => t.sitting_id === read.sitting_id);
    this.first = read.on_agenda?.start_statement_id ?? here[0]?.id ?? open[0]?.id ?? null;
    this.last = read.on_agenda?.statement_id ?? here[here.length - 1]?.id ?? this.first;
    this.next = End.First;
    this.handlers.onTitle(read.session);
    this.opening = read.on_agenda ? this.turn(this.first)!.sitting_id : read.sitting_id;
    this.draw();
  }

  /** The screen is showing: scroll to the sitting it opened at. */
  land(): void {
    this.reach(this.opening);
  }

  private turn(id: number | null): SessionTurn | undefined {
    return this.read?.turns.find((t) => t.id === id);
  }

  /** A line at or above the last ratified cut cannot hold the cut (R-0267). */
  private ratified(turn: SessionTurn): boolean {
    const agreed = this.read?.agreed;
    return agreed !== null && agreed !== undefined && turn.order <= agreed.order;
  }

  /** The sitting's divider brought to the top of the scroll. */
  private reach(sittingId: number): void {
    const line = this.list.querySelector<HTMLElement>(`.sitting[data-sitting="${sittingId}"]`);
    if (line) this.list.scrollTop += line.getBoundingClientRect().top - this.list.getBoundingClientRect().top;
    for (const to of this.jump.querySelectorAll<HTMLElement>(".ct-to"))
      to.classList.toggle("on", Number(to.dataset.sitting) === sittingId);
  }

  private move(turnId: number): void {
    const turn = this.turn(turnId);
    if (!turn) return;
    if (this.ratified(turn)) {
      toast("That part was already ratified");
      return;
    }
    tap(Feature.CutLine);
    const at = turn.order;
    if (this.next === End.First) {
      this.first = turnId;
      if ((this.turn(this.last)?.order ?? 0) < at) this.last = turnId;
      this.next = End.Last;
    } else {
      if (at < (this.turn(this.first)?.order ?? 0)) this.first = turnId;
      else this.last = turnId;
      this.next = End.First;
    }
    this.paint();
  }

  /** One tap puts it on the agenda: a new cut, or the lines moved on the one
   * already there. */
  private async place(): Promise<void> {
    const read = this.read;
    if (!read || this.first === null || this.last === null) return;
    tap(Feature.CutConfirm);
    if (read.cut_id === null) await api.putOnAgenda(this.first, this.last, this.day);
    else await api.moveCut(read.cut_id, this.first, this.last);
    this.handlers.onPlaced();
  }

  /** The thread, its sitting dividers and the row of sittings, drawn once a
   * read; a tap only repaints what is lit. */
  private draw(): void {
    const read = this.read!;
    const now = new Date();
    this.jump.innerHTML = read.sittings
      .map(
        (one) =>
          `<button class="ct-to" type="button" data-sitting="${one.id}">` +
          `<span class="ct-td">${esc(rowDate(new Date(one.started), now))}</span>` +
          (one.title ? `<span class="ct-tt">${esc(one.title)}</span>` : "") +
          `</button>`,
      )
      .join("");
    this.list.innerHTML = "";
    const starts = new Map(read.sittings.map((one) => [one.first_statement_id, one]));
    let agreedDrawn = read.agreed === null;
    for (const turn of read.turns) {
      const sitting = starts.get(turn.id);
      if (sitting) {
        this.list.append(divider(sitting.id, sitting.started, sitting.previous_started));
      }
      if (!agreedDrawn && !this.ratified(turn)) {
        agreedDrawn = true;
        this.list.append(this.agreedLine(read));
      }
      const bubble = el("div", `bub line ${turn.client ? "user" : "coach"}`, esc(turn.text));
      bubble.dataset.turn = String(turn.id);
      this.list.append(bubble);
    }
    this.paint();
  }

  private paint(): void {
    const first = this.turn(this.first);
    const last = this.turn(this.last);
    for (const old of this.list.querySelectorAll(".cutline.now")) old.remove();
    for (const bubble of this.list.querySelectorAll<HTMLElement>(".bub.line")) {
      const at = this.turn(Number(bubble.dataset.turn))!.order;
      const inside = !!first && !!last && first.order <= at && at <= last.order;
      bubble.classList.toggle("lit", inside);
      bubble.classList.toggle("after", !inside);
    }
    if (first && last) {
      this.bubble(first.id).before(this.endLine(`cut starts · turn ${first.order}`));
      this.bubble(last.id).after(this.endLine(`cut ends · turn ${last.order} · ${last.day}`));
    }
    const span = first && last ? `turns ${first.order} to ${last.order}` : "";
    this.bar.innerHTML =
      `<div class="ct-hint">tap the ${this.next} line of the cut</div>` +
      `<button class="btn ct-go" type="button">put ${span} on the agenda</button>`;
  }

  private bubble(id: number): HTMLElement {
    return this.list.querySelector<HTMLElement>(`.bub.line[data-turn="${id}"]`)!;
  }

  private endLine(label: string): HTMLElement {
    return el(
      "div",
      "cutline now",
      `<div class="ln"></div><span class="lb">${esc(label)}</span><div class="ln"></div>`,
    );
  }

  /** The last ratified cut, faint across the thread. */
  private agreedLine(read: SessionTurns): HTMLElement {
    return el(
      "div",
      "cutline",
      `<div class="ln"></div><span class="lb">${esc(
        `last cut · turn ${read.agreed?.order ?? 0} · ratified ${read.agreed?.ratified ?? ""}`,
      )}</span><div class="ln"></div>`,
    );
  }
}
