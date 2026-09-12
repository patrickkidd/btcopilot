import * as api from "./api";
import { el, esc } from "./dom";
import { dragScroll } from "./drag";
import { Picture, Target, type Tap } from "./picture";
import { Menu, Tab } from "./menu";
import { toast } from "./toast";
import { PLAY_MARK, tok } from "./tokens";
import {
  emptyTimeline,
  type CodingThread,
  type CodingTurn,
  type Timeline,
} from "./types";

/** The coding screen: one conversation, read-only, up to the cut Patrick put
 * on the table. You tap a line, say in your own words what it tells you
 * happened, and the scribe writes it into your own record of that family.
 *
 * Nobody else's coding is ever on this screen, and nothing here submits the
 * task: Done lives in the title row, where it cannot read as "add" (R-0271).
 */

export interface CodingHandlers {
  /** Done: the coding is submitted and the next single task card takes its
   * place. */
  onDone(): void;
  /** The (i) in the title row: the guidelines. */
  onGuidelines(): void;
  /** What the screen is called, which the title row shows. */
  onTitle(title: string): void;
}

const PLACEHOLDER = {
  none: "tap a line, then say what happened",
  picked: "say what this line tells you happened",
};

export class Coding {
  private thread: CodingThread | null = null;
  private timeline: Timeline = emptyTimeline();
  private picked: number | null = null;
  private drawer: Menu | null = null;
  private sending = false;
  private picture: Picture;
  private scrim = el("div", "fs-scrim");
  private sheet = el("div", "fs-sheet cf-sheet");

  constructor(
    private list: HTMLElement,
    private composer: HTMLElement,
    private caption: HTMLElement,
    private send: HTMLElement,
    private rows: HTMLElement,
    private search: HTMLInputElement,
    private tabs: HTMLElement,
    private addRow: HTMLElement,
    view: HTMLElement,
    private overlay: HTMLElement,
    private handlers: CodingHandlers,
  ) {
    // No coach turn in a coding, so the board it opens carries the two step
    // arrows and nothing to ask with.
    this.picture = new Picture(view, {
      onTap: (tap: Tap) => this.onPicture(tap),
      canExplain: false,
    });
    this.overlay.append(this.scrim, this.sheet);
    this.scrim.hidden = true;
    this.sheet.hidden = true;
    this.wire();
    dragScroll(this.list);
    dragScroll(this.rows);
  }

  /** Open one coding: its conversation, and the record it is being coded
   * onto. */
  async open(codingId: number, atStatement?: number): Promise<void> {
    this.thread = await api.codingThread(codingId);
    this.picked = null;
    // The drawer edits the record this coding is of, never the coder's own
    // family, so it is built on that record's id (R-0267).
    this.drawer = new Menu(this.rows, () => this.reread(), this.thread.diagram_id);
    this.drawer.onTab = (tab) => this.markTab(tab);
    this.handlers.onTitle(`${this.thread.session} · up to ${this.thread.cut_day}`);
    this.render();
    await this.refresh();
    // The ballot opens the transcript at the line an item came from, which is
    // a turn far above the cut (R-0278).
    if (atStatement !== undefined)
      this.list
        .querySelector(`[data-turn="${atStatement}"]`)
        ?.scrollIntoView({ block: "center" });
  }

  /** The record after something was written into it: the picture, the drawer
   * beside it and the row under it all read the one re-read, the way the chat
   * screen does after a coach turn. */
  private async refresh(): Promise<void> {
    this.drawer?.show(await this.reread());
    this.marks();
  }

  showing(): CodingThread | null {
    return this.thread;
  }

  /** A coding that has been submitted cannot be added to (R-0271), which is
   * how the ballot reads it: the conversation and what was written from it. */
  finished(): boolean {
    return this.thread?.done_at != null;
  }

  /** Done asks once, in a sheet, and says where the coding goes (R-0271). */
  confirm(): void {
    const thread = this.thread;
    if (!thread) return;
    const meeting = thread.meeting_date
      ? new Date(`${thread.meeting_date}T00:00:00`).toLocaleDateString(undefined, {
          weekday: "short",
          month: "short",
          day: "numeric",
        })
      : "the next meeting";
    this.sheet.innerHTML =
      `<div class="fs-handle"><div class="fs-grab"></div></div>` +
      `<div class="cf-t">Finish coding?</div>` +
      `<p class="cf-p">Your coding of ${esc(thread.session)} up to ` +
      `${esc(thread.cut_day)} will be saved and submitted for the meeting on ` +
      `${esc(meeting)}.</p>` +
      `<p class="cf-p">You will not be able to change it after this, and you ` +
      `will see the other coders' takes only after the vote.</p>` +
      `<div class="cf-btns">` +
      `<button class="cf-go" type="button">Submit for the meeting</button>` +
      `<button class="cf-no" type="button">Keep coding</button></div>`;
    this.scrim.hidden = false;
    this.sheet.hidden = false;
    void this.sheet.offsetWidth;
    this.scrim.classList.add("in");
    this.sheet.classList.add("in");
  }

  private close(): void {
    this.scrim.classList.remove("in");
    this.sheet.classList.remove("in");
    window.setTimeout(() => {
      this.scrim.hidden = true;
      this.sheet.hidden = true;
    }, 280);
  }

  private async finish(): Promise<void> {
    const thread = this.thread;
    if (!thread) return;
    await api.finishCoding(thread.coding_id);
    this.close();
    this.handlers.onDone();
  }

  private wire(): void {
    this.list.addEventListener("click", (e) => {
      const bubble = (e.target as Element).closest<HTMLElement>(".bub.line");
      if (bubble) this.pick(Number(bubble.dataset.turn));
    });
    this.send.addEventListener("click", () => void this.say());
    this.composer.addEventListener("keydown", (e) => {
      const key = e as KeyboardEvent;
      if (key.key === "Enter" && !key.shiftKey) {
        key.preventDefault();
        void this.say();
      }
    });
    this.scrim.addEventListener("click", () => this.close());
    this.sheet.addEventListener("click", (e) => {
      const target = e.target as Element;
      if (target.closest(".cf-go")) void this.finish();
      else if (target.closest(".cf-no")) this.close();
    });
    this.search.addEventListener("input", () =>
      this.drawer?.search(this.search.value),
    );
    this.addRow.addEventListener("click", () => this.drawer?.add());
    this.tabs.addEventListener("click", (e) => {
      const tab = (e.target as Element).closest<HTMLElement>(".tab");
      if (!tab) return;
      const which = tab.id.endsWith("people") ? Tab.People : Tab.Events;
      this.search.value = "";
      this.drawer?.search("");
      this.drawer?.open(which);
      this.markTab(which);
    });
  }

  /** The two tab buttons say which list the drawer is on, including when the
   * drawer changes it itself. */
  private markTab(which: Tab): void {
    const people = which === Tab.People;
    this.search.placeholder = people ? "Search people" : "Search events";
    this.addRow.textContent = people ? "+ Add person" : "+ Add event";
    for (const one of this.tabs.querySelectorAll<HTMLElement>(".tab")) {
      const on = one.id.endsWith("people") === (which === Tab.People);
      one.classList.toggle("on", on);
      one.setAttribute("aria-selected", String(on));
    }
  }

  /** A turn above the last agreed line is there to read, and tapping it says
   * so and selects nothing: coding happens inside the cut (R-0271). */
  private pick(turnId: number): void {
    const turn = this.thread?.turns.find((t) => t.id === turnId);
    if (!turn) return;
    for (const line of this.list.querySelectorAll(".abv")) line.remove();
    if (turn.above) {
      this.picked = null;
      this.paint();
      const agreed = this.thread?.agreed;
      const said = `this part was agreed on ${agreed?.ratified ?? "an earlier day"} — code below the line`;
      this.after(turnId, el("div", "abv", esc(said)), turnId);
      return;
    }
    this.picked = turnId;
    this.paint();
  }

  private paint(): void {
    for (const bubble of this.list.querySelectorAll<HTMLElement>(".bub.line"))
      bubble.classList.toggle("sel", Number(bubble.dataset.turn) === this.picked);
    this.composer.dataset.ph =
      this.picked === null ? PLACEHOLDER.none : PLACEHOLDER.picked;
    this.marks();
  }

  /** The row under the picture. Nothing in a coding speaks to the coach, so
   * the chat's "ask", "in chat" and the board's "explain" are not here: the
   * one thing the row offers is the walk through an open cluster's moves, on
   * the record this coding is being written onto.
   *
   * The board has its own controls, so the row goes outright while it is up
   * rather than sitting there as an empty strip (owner ruling 2026-09-08). */
  private marks(): void {
    const onBoard = this.picture.onBoard();
    this.caption.classList.toggle("gone", onBoard);
    if (onBoard) {
      this.caption.innerHTML = "";
      return;
    }
    const open = this.picture.openCluster();
    if (!open) {
      const say = this.picked === null ? "tap a line" : "tap a cluster";
      this.caption.innerHTML = `<span class="cta">${say}</span>`;
      return;
    }
    const moves = this.picture.countMoves(open.event_ids);
    this.caption.innerHTML = tok(
      "coding-play",
      "g",
      PLAY_MARK,
      "play-by-play",
      moves > 0,
    );
    if (moves)
      this.caption.querySelector("#coding-play")?.addEventListener("click", () => {
        this.picture.openBoard(open.event_ids, open.id);
        this.marks();
      });
  }

  /** What the coder typed, sent to the scribe: their own words go into the
   * thread under the line, and what the scribe wrote goes under those. */
  private async say(): Promise<void> {
    const thread = this.thread;
    const said = (this.composer.textContent ?? "").trim();
    if (!thread || this.sending || !said) return;
    if (this.picked === null) {
      toast("Tap a line first");
      return;
    }
    const turn = this.picked;
    this.composer.innerHTML = "";
    const side = this.side(turn);
    this.after(turn, el("div", `bub said${side}`, esc(said)), turn);
    this.sending = true;
    let written;
    try {
      written = await api.scribe(thread.coding_id, turn, said);
    } catch (error) {
      this.after(
        turn,
        el("div", `bub coach sub${side}`, `<div class="did q">${esc(whatFailed(error))}</div>`),
        turn,
      );
      // A scribe that stopped part way has still written that part.
      await this.refresh();
      return;
    } finally {
      this.sending = false;
    }
    const lines = written.asked
      ? `<div class="did q">${esc(written.asked)}</div>`
      : written.lines.map((line) => `<div class="did">${esc(line)}</div>`).join("");
    this.after(turn, el("div", `bub coach sub${side}`, lines), turn);
    if (written.made.length) {
      await this.refresh();
      this.picture.light(written.made);
    }
  }

  /** The record this coding is being written onto, which the picture and the
   * drawer both read. */
  private async reread(): Promise<Timeline> {
    if (!this.thread) return this.timeline;
    this.timeline = await api.timeline(this.thread.diagram_id);
    this.picture.setData(this.timeline);
    return this.timeline;
  }

  /** The picture on this screen is the record being coded: a tap opens one
   * cluster, and a tap on the ground beside it puts it down. */
  private onPicture(tap: Tap): void {
    if (tap.target === Target.Ground) this.picture.dismiss();
    else if (tap.target === Target.Cluster) {
      const ids = this.picture.inCluster(tap.index);
      if (ids.length) this.picture.spotlight(ids);
    }
    this.marks();
  }

  private render(): void {
    const thread = this.thread;
    if (!thread) return;
    this.list.innerHTML = "";
    let hairline = thread.agreed === null;
    for (const turn of thread.turns) {
      if (!hairline && !turn.above) {
        hairline = true;
        this.list.append(this.cutline(thread, false));
      }
      this.list.append(this.bubble(turn));
      for (const line of turn.lines)
        this.list.append(
          this.tagged(
            el("div", `bub coach sub${this.side(turn.id)}`, `<div class="did">${esc(line)}</div>`),
            turn.id,
          ),
        );
    }
    this.list.append(this.cutline(thread, true));
    this.paint();
    this.toEnd();
  }

  /** The thread opens on the cut, which is what the task is about. The web
   * font lands after the bubbles are measured and every one of them grows, so
   * the end is held in view until the page has settled. */
  private toEnd(): void {
    const end = () => {
      this.list.scrollTop = this.list.scrollHeight;
    };
    end();
    requestAnimationFrame(end);
    void document.fonts?.ready.then(end);
  }

  private bubble(turn: CodingTurn): HTMLElement {
    const node = el("div", `bub line ${turn.client ? "user" : "coach"}`, esc(turn.text));
    return this.tagged(node, turn.id);
  }

  /** What hangs under a turn hangs on that turn's side of the thread. */
  private side(turnId: number): string {
    return this.thread?.turns.find((t) => t.id === turnId)?.client ? "" : " left";
  }

  private tagged(node: HTMLElement, turnId: number): HTMLElement {
    node.dataset.turn = String(turnId);
    return node;
  }

  /** The two lines across the thread: the last ratified cut as a faint
   * hairline, and this cut, dashed amber, with nothing shown after it. */
  private cutline(thread: CodingThread, now: boolean): HTMLElement {
    const last = thread.turns[thread.turns.length - 1];
    const label = now
      ? `cut here · turn ${last?.order ?? 0} · ${thread.cut_day}`
      : `last cut · turn ${thread.agreed?.order ?? 0} · ratified ${thread.agreed?.ratified}`;
    return el(
      "div",
      `cutline${now ? " now" : ""}`,
      `<div class="ln"></div><span class="lb">${esc(label)}</span><div class="ln"></div>`,
    );
  }

  /** Put something in the thread under the turn it belongs to, after anything
   * already written from that turn. */
  private after(turnId: number, node: HTMLElement, tag: number): void {
    this.tagged(node, tag);
    const mine = [
      ...this.list.querySelectorAll<HTMLElement>(`[data-turn="${turnId}"]`),
    ];
    const last = mine[mine.length - 1];
    if (last) last.after(node);
    else this.list.append(node);
    // The new line belongs under the turn the coder tapped, which may be far
    // above the cut: bring it into view there, never jump to the end.
    node.scrollIntoView({ block: "nearest" });
  }

}

/** What went wrong, in the words the coder needs. */
function whatFailed(error: unknown): string {
  const failed = error instanceof api.Failed ? error : null;
  if (!failed) throw error;
  console.warn(failed.message);
  if (failed.silent) return "No answer from the server";
  if (failed.status >= 500) return "The server broke on that one";
  return failed.detail.split(": ").slice(2).join(": ") || "That did not go in";
}
