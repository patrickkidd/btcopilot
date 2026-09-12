import * as api from "./api";
import {
  LINE,
  drawTimeline,
  eventsOf,
  group,
  telling,
  when,
  words,
} from "./ballot";
import { esc, el } from "./dom";
import { openEditor } from "./editor";
import { toast } from "./toast";
import {
  ItemStatus,
  Settle,
  VoteChoice,
  type BallotItem,
  type CastVote,
  type Cut,
  type Person,
  type Tally,
  type Take,
  type TimelineEvent,
} from "./types";

/** The meeting: closing what the vote could not, and ratifying the record.
 *
 * Only the items the ballot left open are here, the most split first, with the
 * names and the counts shown for the first time (R-0250, R-0252, R-0274). The
 * ones the vote settled are collapsed below to confirm or reopen. Every open
 * item must be given one of three choices and the ratify button stays dead
 * until each one has, saying how many still need one (R-0257).
 */

export interface MeetingHandlers {
  onTitle(title: string): void;
  /** Ratified: on to what the meeting produced. */
  onRatified(cutId: number): void;
}

/** Which choice a row is showing as taken, worked out from what the item is
 * now rather than kept on the side. */
function choiceOf(item: BallotItem): Settle | null {
  if (item.status === ItemStatus.Unresolved) return Settle.Unresolved;
  if (item.status === ItemStatus.Settled) return Settle.Keep;
  return null;
}

/** One side of an item as the room hears it: the reading, who is behind it and
 * how many that is. */
interface Side {
  label: string;
  names: string[];
  take: Take;
}

/** The margin a row stands at, as the room hears it: the two biggest sides, or
 * the one side when nobody said anything else. */
function verdict(sides: Side[]): string {
  const sizes = sides.map((one) => one.names.length).sort((a, b) => b - a);
  if (sizes.length < 2) return "nobody voted against";
  return `${sizes[0]} to ${sizes[1]} — talk`;
}

const dots = (filled: number, empty: number): string =>
  `<i class="vt on"></i>`.repeat(Math.max(filled, 0)) +
  `<i class="vt"></i>`.repeat(Math.max(empty, 0));

export class Meeting {
  private cut: Cut | null = null;
  private items: BallotItem[] = [];
  private tallies = new Map<number, Tally>();
  private scrim = el("div", "fs-scrim");
  private sheet = el("div", "fs-sheet bl-sheet");

  constructor(
    private stats: HTMLElement,
    private view: HTMLElement,
    private body: HTMLElement,
    private bar: HTMLElement,
    private overlay: HTMLElement,
    private handlers: MeetingHandlers,
  ) {
    this.overlay.append(this.scrim, this.sheet);
    this.scrim.hidden = true;
    this.sheet.hidden = true;
    this.scrim.addEventListener("click", () => this.close());
    this.body.addEventListener("click", (clicked) => void this.onTap(clicked));
    this.bar.addEventListener("click", (clicked) => void this.onBar(clicked));
  }

  async open(cutId: number): Promise<void> {
    const [cut, items, tallies] = await Promise.all([
      api.cut(cutId),
      api.namedItems(cutId),
      api.tallies(cutId),
    ]);
    this.cut = cut;
    this.items = items;
    this.tallies = new Map(tallies.map((one) => [one.review_item_id, one]));
    this.render();
  }

  /** What the room has still to settle, the most split first: an item nobody
   * agreed on is read before one that only one coder read differently. */
  private open_(): BallotItem[] {
    return this.items
      .filter((one) => one.status === ItemStatus.Disputed && this.theirs(one))
      .sort((a, b) => this.split(b) - this.split(a));
  }

  /** An item somebody in the room wrote. What only the coach wrote down is
   * never the room's to settle; it is read afterwards as an audit
   * (R-0254). The reading only carries the room's own takes, so an item with
   * none is the coach's alone. */
  private theirs(item: BallotItem): boolean {
    return item.takes.length > 0;
  }

  /** How split an item is: the more sides it has, and the smaller the biggest
   * of them, the more split the room is on it. */
  private split(item: BallotItem): number {
    const sides = this.sides(item);
    const biggest = Math.max(...sides.map((one) => one.names.length), 0);
    return sides.length * 100 - biggest;
  }

  /** What the vote settled, which is not read aloud but can be reopened. */
  private settled(): BallotItem[] {
    return this.items.filter(
      (one) => one.status !== ItemStatus.Disputed && this.theirs(one),
    );
  }

  private render(): void {
    const cut = this.cut;
    if (!cut) return;
    this.handlers.onTitle(`${cut.session} · ratify`);
    const open = this.open_();
    const settled = this.settled();
    this.stats.innerHTML = this.figures(open.length, settled.length);
    this.view.style.height = `${LINE.height}px`;
    this.view.innerHTML = drawTimeline(eventsOf(this.items), open[0]?.id ?? null);
    this.body.innerHTML =
      `<div class="div">Disputed · ${open.length}` +
      `<span class="dcount">most split first</span></div>` +
      (open.length
        ? open.map((one) => this.row(one)).join("")
        : `<div class="none">Every open item has a choice.</div>`) +
      (settled.length
        ? `<div class="div">Everyone agreed · ${settled.length}` +
          `<span class="dcount">confirm or reopen</span></div>` +
          settled.map((one) => this.collapsed(one)).join("")
        : "");
    this.bar.innerHTML = this.ratifyBar(open.length);
  }

  /** The agreement figures from the first pass, what is in this cut, and the
   * day the meeting falls on. */
  private figures(open: number, settled: number): string {
    const cut = this.cut;
    const first = (cut?.agreement ?? {}).first_pass ?? null;
    const day = cut?.meeting_date
      ? new Date(`${cut.meeting_date}T00:00:00`).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        })
      : null;
    return (
      (day ? `<span>meeting ${esc(day)}</span>` : "") +
      `<span>${this.items.length} items in this cut</span>` +
      `<span>${open} open</span><span>${settled} agreed</span>` +
      (first?.percent === null || first?.percent === undefined
        ? ""
        : `<span>first pass <b>${first.percent}%</b></span>`)
    );
  }

  /** One disputed item: its tally, what each side wrote with who wrote it, the
   * line it came from, and the three choices. */
  private row(item: BallotItem): string {
    const chosen = choiceOf(item);
    const first = item.takes[0];
    const sides = this.sides(item);
    const biggest = Math.max(...sides.map((one) => one.names.length), 0);
    const lines = sides
      .map(
        (one) =>
          `<span>${dots(one.names.length, 0)} ${esc(one.label)} · ` +
          `${esc(one.names.join(", "))} = ${one.names.length}</span>`,
      )
      .join("");
    const missing = item.not_coded
      ? `<span>${dots(0, item.not_coded)} not coded = ${item.not_coded}</span>`
      : "";
    const line = item.line
      ? `<div class="quote"><b>${esc(item.line.who)}:</b> ` +
        `&ldquo;${esc(item.line.text)}&rdquo;</div>`
      : "";
    return (
      `<div class="drow" data-item="${item.id}">` +
      `<div class="top"><span class="tally">` +
      `${dots(biggest, item.coders - biggest)}</span>` +
      `<span class="pick">${esc(when(first?.item.dateTime))} · ` +
      `${first?.person_name ? `${esc(first.person_name)} · ` : ""}` +
      `${esc(String(first?.item.description ?? first?.item.kind ?? "an item"))}` +
      `</span></div>` +
      `<div class="tline">${lines}${missing}` +
      `<span class="verdict">${esc(verdict(sides))}</span></div>` +
      line +
      `<div class="acts2">` +
      this.choice(Settle.Keep, "keep", chosen) +
      this.choice(Settle.Change, "change…", chosen) +
      this.choice(Settle.Unresolved, "mark unresolved", chosen) +
      `</div></div>`
    );
  }

  private choice(which: Settle, label: string, chosen: Settle | null): string {
    const on = which === chosen ? (which === Settle.Keep ? " primary on" : " on") : "";
    return (
      `<button class="btn${on} mt-choice" type="button" ` +
      `data-choice="${which}">${label}</button>`
    );
  }

  /** Each reading of an item with everybody behind it: whoever wrote it and
   * whoever voted for it. The meeting is where the names appear, and the count
   * beside a reading is how many people it is, not how many takes (R-0252,
   * R-0274). */
  private sides(item: BallotItem): Side[] {
    const fields = telling(item.takes);
    const votes = this.tallies.get(item.id)?.votes ?? [];
    // A vote is a coder's last word: whoever voted counts on the side they
    // voted for, not on the one they first wrote.
    const decided = new Map(
      votes.map((vote) => [vote.name, vote.value?.coding_id ?? null]),
    );
    return group(item)
      .map((one) => {
        const wrote = item.takes
          .filter((take) => (words(take, fields) || "as written") === one.label)
          .map((take) => take.coder)
          .filter(
            (name) =>
              name !== undefined &&
              (!decided.has(name) || decided.get(name) === one.take.coding_id),
          ) as string[];
        const voted = votes
          .filter((vote) => this.votedFor(vote, one.take))
          .map((vote) => vote.name);
        return {
          label: one.label,
          names: [...new Set([...wrote, ...voted])],
          take: one.take,
        };
      })
      // A reading everybody who wrote it has since voted away from is not a
      // side of the argument any more.
      .filter((one) => one.names.length > 0);
  }

  private votedFor(vote: CastVote, take: Take): boolean {
    return (
      vote.choice === VoteChoice.Take &&
      vote.value?.coding_id === take.coding_id
    );
  }

  private collapsed(item: BallotItem): string {
    const first = item.takes[0];
    const settled =
      item.status === ItemStatus.Unresolved ? " · left unresolved" : "";
    return (
      `<div class="collapsed" data-item="${item.id}">` +
      `<span>${esc(when(first?.item.dateTime))} · ` +
      `${esc(String(first?.item.description ?? first?.item.kind ?? "an item"))}` +
      `${settled}</span>` +
      `<span class="reopen mt-reopen">reopen</span></div>`
    );
  }

  /** The ratify button, dead until every open item has a choice and saying how
   * many still need one (R-0257). */
  private ratifyBar(open: number): string {
    return (
      `<button class="btn mt-ratify" type="button"${open ? " disabled" : ""}>` +
      (open
        ? `ratify · ${open} item${open === 1 ? "" : "s"} still need ` +
          `${open === 1 ? "a choice" : "choices"}`
        : "ratify") +
      `</button>` +
      `<span class="note">${open ? "nothing is ratified yet" : "this writes the agreed record"}</span>`
    );
  }

  private async onTap(clicked: Event): Promise<void> {
    const target = clicked.target as Element;
    const row = target.closest<HTMLElement>("[data-item]");
    if (!row) return;
    const item = this.items.find((one) => one.id === Number(row.dataset.item));
    if (!item) return;
    if (target.closest(".mt-reopen")) {
      await this.settle(item, Settle.Reopen);
      return;
    }
    const choice = target.closest<HTMLElement>(".mt-choice")?.dataset.choice;
    if (choice === Settle.Change) this.change(item);
    else if (choice === Settle.Keep)
      await this.settle(item, Settle.Keep, {
        coding_id: item.takes[0]?.coding_id,
      });
    else if (choice === Settle.Unresolved)
      await this.settle(item, Settle.Unresolved);
  }

  private async settle(
    item: BallotItem,
    choice: Settle,
    value: Record<string, unknown> | null = null,
  ): Promise<void> {
    try {
      await api.settle(item.id, choice, value);
    } catch (error) {
      // The record refuses some takes — a shift with no variable, say — and
      // says why in its own words, which is what the room needs to hear.
      toast(
        error instanceof api.Failed && error.status === 400
          ? error.detail.replace(/^\w+ [^:]+: /, "")
          : "Nothing came back",
      );
      return;
    }
    if (this.cut) await this.open(this.cut.id);
  }

  /** "change…" opens the app's own event editor over the meeting, prefilled,
   * so the room can settle on something nobody wrote. */
  private change(item: BallotItem): void {
    const from = item.takes[0]?.item ?? {};
    const people = item.people.map(
      (one) => ({ id: one.id, name: one.name }) as Person,
    );
    const editor = openEditor(
      from as unknown as TimelineEvent,
      people,
      () => this.close(),
      undefined,
      undefined,
      (body) => void this.written(item, body),
    );
    editor.querySelector(".save")!.textContent = "settle on this";
    editor
      .querySelector(".acts")
      ?.before(
        el(
          "div",
          "hint",
          "The transcript line and the session it came from are kept with the " +
            "event; they are not edited here.",
        ),
      );
    editor.querySelector(".del")?.remove();
    editor.querySelector(".acts")?.append(el("button", "del", "cancel"));
    editor
      .querySelector(".acts .del")!
      .addEventListener("click", () => this.close());
    this.sheet.innerHTML = `<div class="fs-handle"><div class="fs-grab"></div></div>`;
    const scroller = el("div", "fs-body");
    scroller.append(editor);
    this.sheet.append(scroller);
    this.scrim.hidden = false;
    this.sheet.hidden = false;
    void this.sheet.offsetWidth;
    this.scrim.classList.add("in");
    this.sheet.classList.add("in");
  }

  private async written(
    item: BallotItem,
    body: Record<string, unknown>,
  ): Promise<void> {
    this.close();
    await this.settle(item, Settle.Change, body);
  }

  private close(): void {
    this.scrim.classList.remove("in");
    this.sheet.classList.remove("in");
    window.setTimeout(() => {
      this.scrim.hidden = true;
      this.sheet.hidden = true;
    }, 280);
  }

  private async onBar(clicked: Event): Promise<void> {
    if (!(clicked.target as Element).closest(".mt-ratify")) return;
    const cut = this.cut;
    if (!cut) return;
    try {
      await api.ratify(cut.id);
    } catch (error) {
      toast(
        error instanceof api.Failed && error.status === 400
          ? "Every open item needs a choice first"
          : "The ratification did not go through",
      );
      return;
    }
    this.handlers.onRatified(cut.id);
  }
}
