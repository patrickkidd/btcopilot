import * as api from "./api";
import { el, esc } from "./dom";
import { dragScroll } from "./drag";
import { Picture, Target, type Tap } from "./picture";
import { eventDivider, eventRow, fullName, personRow } from "./rows";
import { toast } from "./toast";
import {
  emptyTimeline,
  type Cluster,
  type CodingThread,
  type CodingTurn,
  type Person,
  type Timeline,
  type TimelineEvent,
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

enum Which {
  Events = "events",
  People = "people",
}

const PLACEHOLDER = {
  none: "tap a line, then say what happened",
  picked: "say what this line tells you happened",
};

export class Coding {
  private thread: CodingThread | null = null;
  private timeline: Timeline = emptyTimeline();
  private picked: number | null = null;
  private tab = Which.Events;
  private query = "";
  private sending = false;
  private picture: Picture;
  private scrim = el("div", "fs-scrim");
  private sheet = el("div", "fs-sheet cf-sheet");

  constructor(
    private list: HTMLElement,
    private composer: HTMLElement,
    private send: HTMLElement,
    private rows: HTMLElement,
    private search: HTMLInputElement,
    private tabs: HTMLElement,
    view: HTMLElement,
    private overlay: HTMLElement,
    private handlers: CodingHandlers,
  ) {
    this.picture = new Picture(view, { onTap: (tap: Tap) => this.onPicture(tap) });
    this.overlay.append(this.scrim, this.sheet);
    this.scrim.hidden = true;
    this.sheet.hidden = true;
    this.wire();
    dragScroll(this.list);
    dragScroll(this.rows);
  }

  /** Open one coding: its conversation, and the record it is being coded
   * onto. */
  async open(codingId: number): Promise<void> {
    this.thread = await api.codingThread(codingId);
    this.picked = null;
    this.handlers.onTitle(`${this.thread.session} · up to ${this.thread.cut_day}`);
    this.render();
    await this.reread();
  }

  showing(): CodingThread | null {
    return this.thread;
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
    this.search.addEventListener("input", () => {
      this.query = this.search.value;
      this.drawer();
    });
    this.tabs.addEventListener("click", (e) => {
      const tab = (e.target as Element).closest<HTMLElement>(".tab");
      if (!tab) return;
      this.tab = tab.id.endsWith("people") ? Which.People : Which.Events;
      this.query = "";
      this.search.value = "";
      this.search.placeholder =
        this.tab === Which.People ? "Search people" : "Search events";
      for (const one of this.tabs.querySelectorAll<HTMLElement>(".tab")) {
        const on = one === tab;
        one.classList.toggle("on", on);
        one.setAttribute("aria-selected", String(on));
      }
      this.drawer();
    });
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
    this.after(turn, el("div", "bub user", esc(said)), turn);
    this.sending = true;
    let written;
    try {
      written = await api.scribe(thread.coding_id, turn, said);
    } catch (error) {
      this.after(
        turn,
        el("div", "bub coach", `<div class="did q">${esc(whatFailed(error))}</div>`),
        turn,
      );
      return;
    } finally {
      this.sending = false;
    }
    const lines = written.asked
      ? `<div class="did q">${esc(written.asked)}</div>`
      : written.lines.map((line) => `<div class="did">${esc(line)}</div>`).join("");
    this.after(turn, el("div", "bub coach", lines), turn);
    if (!written.asked) {
      await this.reread();
      this.picture.light(written.made);
    }
  }

  /** The record this coding is being written onto, which the picture and the
   * drawer both read. */
  private async reread(): Promise<void> {
    if (!this.thread) return;
    this.timeline = await api.timeline(this.thread.diagram_id);
    this.picture.setData(this.timeline);
    this.drawer();
  }

  private onPicture(tap: Tap): void {
    if (tap.target === Target.Ground) this.picture.dismiss();
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
        this.list.append(this.tagged(el("div", "bub coach", `<div class="did">${esc(line)}</div>`), turn.id));
    }
    this.list.append(this.cutline(thread, true));
    this.paint();
    this.list.scrollTop = this.list.scrollHeight;
  }

  private bubble(turn: CodingTurn): HTMLElement {
    const node = el(
      "div",
      "bub coach line",
      `<div class="who">${esc(turn.who)}</div>${esc(turn.text)}`,
    );
    return this.tagged(node, turn.id);
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
    this.list.scrollTop = this.list.scrollHeight;
  }

  private drawer(): void {
    const words = this.query.trim().toLowerCase();
    this.rows.innerHTML =
      this.tab === Which.People ? this.people(words) : this.events(words);
  }

  private events(words: string): string {
    const names = new Map(this.timeline.people.map((p: Person) => [p.id, p.name]));
    const shown = this.timeline.events.filter((event: TimelineEvent) =>
      `${event.label} ${event.person_name}`.toLowerCase().includes(words),
    );
    if (!shown.length) return `<div class="none">Nothing coded yet.</div>`;
    let html = "";
    let last: string | null | undefined;
    for (const event of shown) {
      const cluster = this.timeline.clusters.find((c: Cluster) =>
        c.event_ids.includes(event.id),
      );
      const key = cluster ? cluster.id : null;
      if (key !== last) {
        last = key;
        html += eventDivider(cluster);
      }
      html += eventRow(event, names);
    }
    return html;
  }

  private people(words: string): string {
    const shown = this.timeline.people.filter((person: Person) =>
      fullName(person).toLowerCase().includes(words),
    );
    if (!shown.length) return `<div class="none">Nobody coded yet.</div>`;
    return shown.map((person: Person) => personRow(person)).join("");
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
