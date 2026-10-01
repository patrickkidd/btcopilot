import * as api from "./api";
import { Feature, tap } from "./track";
import { el, esc, type Title } from "./dom";
import { dragScroll } from "./drag";
import { divider } from "./thread";
import { toast } from "./toast";
import { rowDate } from "./when";
import type { SessionTurn, SessionTurns } from "./types";

/** Placing the cut: the family's whole thread read-only in one scroll, with
 * the same line between sittings the chat shows, a row of the sittings in the
 * agenda's own boxes, each of which scrolls the thread to its first line, and
 * the one button that puts the cut on the agenda (R-0267).
 *
 * A cut is a first and a last line, in one sitting or across several. A new
 * cut starts with neither: the first tap lights its first line, the second
 * its last and everything between, and a tap after that starts over. No end
 * can be placed at or before the last point already ratified.
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
    private hint: HTMLElement,
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
      if ((e.target as Element).closest(".ct-go:not([disabled])")) void this.place();
    });
    dragScroll(this.list);
  }

  /** Open the thread of one sitting's family at that sitting. A cut already
   * on the agenda opens lit where it stands; a new one opens with nothing
   * chosen, and joins the meeting on `day`. */
  async open(discussionId: number, day: string | null): Promise<void> {
    this.day = day;
    const read = (this.read = await api.sessionTurns(discussionId));
    this.first = read.on_agenda?.start_statement_id ?? null;
    this.last = read.on_agenda?.statement_id ?? null;
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

  /** The sitting's divider brought to the top of the scroll, and its box into
   * the middle of the row of boxes. */
  private reach(sittingId: number): void {
    const line = this.list.querySelector<HTMLElement>(`.sitting[data-sitting="${sittingId}"]`);
    if (line) this.list.scrollTop += line.getBoundingClientRect().top - this.list.getBoundingClientRect().top;
    for (const to of this.jump.querySelectorAll<HTMLElement>(".ct-to"))
      to.classList.toggle("on", Number(to.dataset.sitting) === sittingId);
    const on = this.jump.querySelector<HTMLElement>(".ct-to.on");
    if (on) {
      const at = on.getBoundingClientRect();
      const row = this.jump.getBoundingClientRect();
      this.jump.scrollLeft += at.left - row.left - (row.width - at.width) / 2;
    }
  }

  private move(turnId: number): void {
    const turn = this.turn(turnId);
    if (!turn) return;
    if (this.ratified(turn)) {
      toast("That part was already ratified");
      return;
    }
    tap(Feature.CutLine);
    if (this.next === End.First) {
      this.first = turnId;
      this.last = null;
      this.next = End.Last;
    } else {
      const first = this.turn(this.first)!;
      if (turn.order < first.order) [this.first, this.last] = [turnId, first.id];
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

  /** The thread, its sitting dividers and the row of sitting boxes, drawn
   * once a read; a tap only repaints what is lit. A sitting with no title yet
   * is named by its first line. */
  private draw(): void {
    const read = this.read!;
    const now = new Date();
    this.jump.innerHTML = read.sittings
      .map((one) => {
        const lines = read.turns.filter((t) => t.sitting_id === one.id).length;
        const name = one.title || this.turn(one.first_statement_id)?.text || "";
        return (
          `<div class="sn-row push ct-to" data-sitting="${one.id}">` +
          `<div class="sn-m"><div class="sn-t">${esc(name)}</div>` +
          `<div class="sn-s">${rowDate(new Date(one.started), now)} · ${lines} ` +
          `statement${lines === 1 ? "" : "s"}</div></div></div>`
        );
      })
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

  /** Nothing chosen: every line as it is. The first line chosen: it alone
   * lit. Both: the range lit and the rest dimmed, and the button live. */
  private paint(): void {
    const first = this.turn(this.first);
    const last = this.turn(this.last);
    for (const old of this.list.querySelectorAll(".cutline.now")) old.remove();
    for (const bubble of this.list.querySelectorAll<HTMLElement>(".bub.line")) {
      const at = this.turn(Number(bubble.dataset.turn))!.order;
      const inside = !!first && first.order <= at && at <= (last ?? first).order;
      bubble.classList.toggle("lit", inside);
      bubble.classList.toggle("after", !!last && !inside);
    }
    if (first) this.bubble(first.id).before(this.endLine(`cut starts · turn ${first.order}`));
    if (last) this.bubble(last.id).after(this.endLine(`cut ends · turn ${last.order} · ${last.day}`));
    this.hint.textContent =
      first && last
        ? `Turns ${first.order} to ${last.order}. Tap a line to start again.`
        : "Tap the first line, then the last";
    this.bar.innerHTML =
      `<button class="btn ct-go" type="button"${first && last ? "" : " disabled"}>` +
      `Place this cut</button>`;
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
