import * as api from "./api";
import { el, esc, type Title } from "./dom";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import type { SessionTurn, SessionTurns } from "./types";

/** Placing the cut: the conversation read-only, the point everyone codes up
 * to, and the one button that puts it on the table (R-0267).
 *
 * The cut starts at the last turn. Tapping any line moves it there, turns
 * after it are dimmed and wait for a later cut, and it can never be placed
 * before the last point already ratified.
 */

export interface CutHandlers {
  /** The cut is on the table: the table screen takes over. */
  onPlaced(): void;
  /** What the screen is called, which the title row shows. */
  onTitle(title: string | Title): void;
}

export class Cut {
  private read: SessionTurns | null = null;
  private at: number | null = null;

  constructor(
    private list: HTMLElement,
    private bar: HTMLElement,
    private handlers: CutHandlers,
  ) {
    this.list.addEventListener("click", (e) => {
      const bubble = (e.target as Element).closest<HTMLElement>(".bub.line");
      if (bubble) void this.move(Number(bubble.dataset.turn));
    });
    this.bar.addEventListener("click", (e) => {
      if ((e.target as Element).closest(".ct-go")) void this.place();
    });
    dragScroll(this.list);
  }

  /** Open one conversation to place its cut. A conversation already on the
   * table opens on the line it was cut at. */
  async open(discussionId: number): Promise<void> {
    this.read = await api.sessionTurns(discussionId);
    const last = this.read.turns[this.read.turns.length - 1];
    this.at = this.read.on_table?.statement_id ?? last?.id ?? null;
    this.handlers.onTitle(this.read.session);
    this.render();
  }

  /** A line at or above the last ratified cut cannot hold the cut (R-0267). */
  private ratified(turn: SessionTurn): boolean {
    const agreed = this.read?.agreed;
    return agreed !== null && agreed !== undefined && turn.order <= agreed.order;
  }

  private async move(turnId: number): Promise<void> {
    const turn = this.read?.turns.find((t) => t.id === turnId);
    if (!turn) return;
    if (this.ratified(turn)) {
      toast("That part was already ratified");
      return;
    }
    this.at = turnId;
    this.render();
  }

  /** One tap puts it on the table: a new cut, or the line moved on the one
   * already there. */
  private async place(): Promise<void> {
    const read = this.read;
    if (!read || this.at === null) return;
    if (read.cut_id === null) await api.putOnTable(read.discussion_id, this.at);
    else await api.moveCut(read.cut_id, this.at);
    this.handlers.onPlaced();
  }

  private render(): void {
    const read = this.read;
    if (!read) return;
    this.list.innerHTML = "";
    let agreedDrawn = read.agreed === null;
    let past = false;
    for (const turn of read.turns) {
      if (!agreedDrawn && !this.ratified(turn)) {
        agreedDrawn = true;
        this.list.append(this.line(read, false));
      }
      const bubble = el(
        "div",
        `bub line ${turn.client ? "user" : "coach"}${past ? " after" : ""}`,
        esc(turn.text),
      );
      bubble.dataset.turn = String(turn.id);
      this.list.append(bubble);
      if (turn.id === this.at) {
        this.list.append(this.line(read, true));
        past = true;
      }
    }
    this.bar.innerHTML =
      `<div class="ct-hint">tap any line to move the cut</div>` +
      `<button class="btn ct-go" type="button">put on the table at turn ` +
      `${this.order()}</button>`;
    // The cut is what the screen is about, so it is what the screen opens on.
    this.list
      .querySelector(".cutline.now")
      ?.scrollIntoView({ block: "center" });
  }

  private order(): number {
    return this.read?.turns.find((t) => t.id === this.at)?.order ?? 0;
  }

  /** The two lines across the thread: the last ratified cut faint, and the cut
   * being placed, dashed amber. */
  private line(read: SessionTurns, now: boolean): HTMLElement {
    const turn = read.turns.find((t) => t.id === this.at);
    const label = now
      ? `cut here · turn ${turn?.order ?? 0} · ${turn?.day ?? ""}`
      : `last cut · turn ${read.agreed?.order ?? 0} · ratified ${read.agreed?.ratified ?? ""}`;
    return el(
      "div",
      `cutline${now ? " now" : ""}`,
      `<div class="ln"></div><span class="lb">${esc(label)}</span><div class="ln"></div>`,
    );
  }
}
