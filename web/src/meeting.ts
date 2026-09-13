import * as api from "./api";
import {
  LINE,
  drawTimeline,
  eventsOf,
  group,
  names,
  telling,
  when,
  words,
} from "./ballot";
import { esc, el, type Title } from "./dom";
import { openEditor } from "./editor";
import { toast } from "./toast";
import {
  ItemStatus,
  Decision,
  VoteChoice,
  type BallotItem,
  type CastVote,
  type Cut,
  type Person,
  type Tally,
  type Opinion,
  type TimelineEvent,
} from "./types";

/** The meeting: closing what the vote could not, and ratifying the record.
 *
 * The items the ballot left open are here with the names and the counts shown
 * for the first time (R-0250, R-0252, R-0274), read either most split first or
 * in the order the events happened (R-0316). The ones the vote decided are in
 * the list too and open the same card on a tap (R-0317). Every open item must
 * be given a choice — keep one of the versions, change it, or mark it
 * unresolved — and the ratify button stays dead until each one has, saying how
 * many still need one (R-0257).
 */

export interface MeetingHandlers {
  onTitle(title: string | Title): void;
  /** Ratified: on to what the meeting produced. */
  onRatified(cutId: number): void;
}

/** Which choice a row is showing as taken, worked out from what the item is
 * now rather than kept on the side. */
function choiceOf(item: BallotItem): Decision | null {
  if (item.status === ItemStatus.Unresolved) return Decision.Unresolved;
  if (item.status === ItemStatus.Decided) return Decision.Keep;
  return null;
}

/** One side of an item as the room hears it: the reading, who is behind it and
 * how many that is. */
interface Side {
  label: string;
  names: string[];
  opinion: Opinion;
}

/** The order the list is read in: the most split first, or the day each event
 * happened (R-0316). */
enum Sort {
  Divergence = "divergence",
  Time = "time",
}

const dots = (filled: number, empty: number): string =>
  `<i class="vt on"></i>`.repeat(Math.max(filled, 0)) +
  `<i class="vt"></i>`.repeat(Math.max(empty, 0));

export class Meeting {
  private cut: Cut | null = null;
  private items: BallotItem[] = [];
  private tallies = new Map<number, Tally>();
  private sort = Sort.Divergence;
  /** The event the room is on: its dot is green and, when the vote agreed on
   * it, its card is the one open (R-0317, R-0320). */
  private at: number | null = null;
  private scrim = el("div", "fs-scrim");
  private sheet = el("div", "fs-sheet bl-sheet");

  constructor(
    private stats: HTMLElement,
    private view: HTMLElement,
    private sorter: HTMLElement,
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
    this.view.addEventListener("click", (clicked) => this.onDot(clicked));
    this.sorter.addEventListener("click", (clicked) => this.onSort(clicked));
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

  /** What the room has still to decide, the most split first: an item nobody
   * agreed on is read before one that only one coder read differently. */
  private open_(): BallotItem[] {
    return this.listed()
      .filter((one) => one.status === ItemStatus.Disputed)
      .sort((a, b) => this.split(b) - this.split(a));
  }

  /** What the meeting reads: the events of the cut the room itself coded, which
   * is what the wire draws and what the header counts. */
  private listed(): BallotItem[] {
    return eventsOf(this.items).filter((one) => this.theirs(one));
  }

  /** An item somebody in the room wrote. What only the coach wrote down is
   * never the room's to decide; it is read afterwards as an audit
   * (R-0254). The reading only carries the room's own opinions, so an item with
   * none is the coach's alone. */
  private theirs(item: BallotItem): boolean {
    return item.opinions.length > 0;
  }

  /** How split an item is: the more sides it has, and the smaller the biggest
   * of them, the more split the room is on it. */
  private split(item: BallotItem): number {
    const sides = this.sides(item);
    const biggest = Math.max(...sides.map((one) => one.names.length), 0);
    return sides.length * 100 - biggest;
  }

  /** What the vote decided, which is not read aloud but can be reopened. */
  private decided(): BallotItem[] {
    return this.listed().filter((one) => one.status !== ItemStatus.Disputed);
  }

  private render(): void {
    const cut = this.cut;
    if (!cut) return;
    this.handlers.onTitle({ name: cut.session, tail: "ratify" });
    const open = this.open_();
    this.stats.innerHTML = this.head(open.length);
    this.view.style.height = `${LINE.height}px`;
    this.view.innerHTML = drawTimeline(
      eventsOf(this.items),
      this.at ?? open[0]?.id ?? null,
    );
    this.sorter.innerHTML = this.sorts();
    this.body.innerHTML =
      this.sort === Sort.Time ? this.byTime() : this.byDivergence(open);
    this.bar.innerHTML = this.ratifyBar(open.length);
  }

  /** The header: the title, one line of labelled figures, and the colours the
   * wire under it is drawn in. Nothing here is said again below (R-0321). */
  private head(open: number): string {
    const cut = this.cut;
    const day = cut?.meeting_date
      ? new Date(`${cut.meeting_date}T00:00:00`).toLocaleDateString(undefined, {
          weekday: "short",
          month: "short",
          day: "numeric",
        })
      : null;
    const first = (cut?.agreement ?? {}).first_pass ?? null;
    const events = eventsOf(this.items).length;
    return (
      `<div class="mtitle">Meeting${day ? ` · ${esc(day)}` : ""}` +
      `${cut?.session ? ` · ${esc(cut.session)}` : ""}</div>` +
      `<div class="mfigs"><span>${events} event${events === 1 ? "" : "s"}</span>` +
      `<span>${open} disputed</span>` +
      (first?.percent === null || first?.percent === undefined
        ? ""
        : `<span>${first.percent}% agreed before the vote</span>`) +
      `</div>` +
      `<div class="mkey"><span><i class="sw ok"></i>agreed</span>` +
      `<span><i class="sw no"></i>disputed</span>` +
      `<span><i class="sw now"></i>now</span></div>`
    );
  }

  private sorts(): string {
    const one = (which: Sort, label: string): string =>
      `<button class="seg${which === this.sort ? " on" : ""}" type="button" ` +
      `data-sort="${which}">${label}</button>`;
    return (
      one(Sort.Divergence, "by divergence") + one(Sort.Time, "by time")
    );
  }

  /** The most split first, with what the vote agreed on listed after it. */
  private byDivergence(open: BallotItem[]): string {
    const decided = this.decided();
    return (
      `<div class="div">Disputed<span class="dcount">most split first</span></div>` +
      (open.length
        ? open.map((one) => this.row(one)).join("")
        : `<div class="none">Every open item has a choice.</div>`) +
      (decided.length
        ? `<div class="div">Everyone agreed` +
          `<span class="dcount">tap one to change it</span></div>` +
          decided.map((one) => this.agreed(one)).join("")
        : "")
    );
  }

  /** Every event the room wrote, in the order they happened, the agreed ones in
   * the same list and marked agreed (R-0316). */
  private byTime(): string {
    const rows = this.listed();
    if (!rows.length) return `<div class="none">Nothing to decide.</div>`;
    return rows
      .map((one) =>
        one.status === ItemStatus.Disputed ? this.row(one) : this.agreed(one),
      )
      .join("");
  }

  /** One item's card: its tally, every version with who wrote it and its own
   * button to keep it, the line it came from, and what else can be done with it
   * (R-0318, R-0319). An agreed item opens the same card, with a way to close
   * it again (R-0317). */
  private row(item: BallotItem, closable = false): string {
    const chosen = choiceOf(item);
    const first = item.opinions[0];
    const sides = this.sides(item);
    const biggest = Math.max(...sides.map((one) => one.names.length), 0);
    const kept = item.status === ItemStatus.Decided;
    const versions = sides
      .map(
        (one) =>
          `<div class="side"><span class="sdots">${dots(one.names.length, 0)}</span>` +
          `<span class="slab">${esc(one.label)}</span>` +
          `<span class="swho">${esc(one.names.join(", "))} = ${one.names.length}</span>` +
          `<button class="btn mt-keep" type="button" ` +
          `data-coding="${one.opinion.coding_id}"${kept ? " disabled" : ""}>` +
          `keep this</button></div>`,
      )
      .join("");
    const missing = item.not_coded
      ? `<div class="side"><span class="sdots">${dots(0, item.not_coded)}</span>` +
        `<span class="slab">left this event out</span>` +
        `<span class="swho">= ${item.not_coded}</span></div>`
      : "";
    const line = item.line
      ? `<div class="quote"><b>${esc(item.line.who)}:</b> ` +
        `&ldquo;${esc(item.line.text)}&rdquo;</div>`
      : "";
    return (
      `<div class="drow${closable ? " hasx" : ""}" data-item="${item.id}">` +
      (closable
        ? `<button class="mt-close cardx" type="button" aria-label="close">×</button>`
        : "") +
      `<div class="top"><span class="tally">` +
      `${dots(biggest, item.coders - biggest)}</span>` +
      `<span class="pick">${esc(when(first?.item.dateTime))} · ` +
      `${esc(names(item))}</span></div>` +
      `<div class="tline">${versions}${missing}</div>` +
      line +
      `<div class="acts2">` +
      this.choice(Decision.Change, "change…", chosen) +
      this.choice(Decision.Unresolved, "mark unresolved", chosen) +
      `</div></div>`
    );
  }

  private choice(which: Decision, label: string, chosen: Decision | null): string {
    const on = which === chosen ? (which === Decision.Keep ? " primary on" : " on") : "";
    return (
      `<button class="btn${on} mt-choice" type="button" ` +
      `data-choice="${which}">${label}</button>`
    );
  }

  /** Each reading of an item with everybody behind it: whoever wrote it and
   * whoever voted for it. The meeting is where the names appear, and the count
   * beside a reading is how many people it is, not how many opinions (R-0252,
   * R-0274). */
  private sides(item: BallotItem): Side[] {
    const fields = telling(item.opinions);
    const votes = this.tallies.get(item.id)?.votes ?? [];
    // A vote is a coder's last word: whoever voted counts on the side they
    // voted for, not on the one they first wrote.
    const decided = new Map(
      votes.map((vote) => [vote.name, vote.value?.coding_id ?? null]),
    );
    return group(item)
      .map((one) => {
        const wrote = item.opinions
          .filter((opinion) => (words(opinion, fields) || "as written") === one.label)
          .map((opinion) => opinion.coder)
          .filter(
            (name) =>
              name !== undefined &&
              (!decided.has(name) || decided.get(name) === one.opinion.coding_id),
          ) as string[];
        const voted = votes
          .filter((vote) => this.votedFor(vote, one.opinion))
          .map((vote) => vote.name);
        return {
          label: one.label,
          names: [...new Set([...wrote, ...voted])],
          opinion: one.opinion,
        };
      })
      // A reading everybody who wrote it has since voted away from is not a
      // side of the argument any more.
      .filter((one) => one.names.length > 0);
  }

  private votedFor(vote: CastVote, opinion: Opinion): boolean {
    return (
      vote.choice === VoteChoice.Opinion &&
      vote.value?.coding_id === opinion.coding_id
    );
  }

  /** An item the vote settled: one row saying who and what and that it is
   * agreed, which opens the same card as a disputed one on a tap (R-0317). */
  private agreed(item: BallotItem): string {
    if (this.at === item.id) return this.row(item, true);
    const first = item.opinions[0];
    const mark =
      item.status === ItemStatus.Unresolved ? "left unresolved" : "agreed";
    return (
      `<div class="collapsed" data-item="${item.id}">` +
      `<span>${esc(when(first?.item.dateTime))} · ${esc(names(item))}</span>` +
      `<span class="mark">${mark}</span></div>`
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
    if (target.closest(".mt-close")) {
      this.at = null;
      this.render();
      return;
    }
    if (row.classList.contains("collapsed")) {
      this.at = item.id;
      this.render();
      return;
    }
    const keep = target.closest<HTMLElement>(".mt-keep");
    if (keep) {
      await this.decide(item, Decision.Keep, {
        coding_id: Number(keep.dataset.coding),
      });
      return;
    }
    const choice = target.closest<HTMLElement>(".mt-choice")?.dataset.choice;
    if (choice === Decision.Change) this.change(item);
    else if (choice === Decision.Unresolved)
      await this.decide(item, Decision.Unresolved);
  }

  /** Every dot answers: it puts the room on that event and brings its card up,
   * opening it when the vote had agreed on it (R-0320). */
  private onDot(clicked: Event): void {
    const dot = (clicked.target as Element).closest<HTMLElement>("[data-item]");
    if (!dot) return;
    const id = Number(dot.dataset.item);
    const item = this.items.find((one) => one.id === id);
    if (!item || !this.theirs(item)) {
      toast("Only the coach wrote that one down");
      return;
    }
    this.at = id;
    this.render();
    this.body
      .querySelector(`[data-item="${id}"]`)
      ?.scrollIntoView({ block: "center" });
  }

  private onSort(clicked: Event): void {
    const chosen = (clicked.target as Element).closest<HTMLElement>("[data-sort]")
      ?.dataset.sort;
    if (!chosen || chosen === this.sort) return;
    this.sort = chosen as Sort;
    this.render();
  }

  private async decide(
    item: BallotItem,
    choice: Decision,
    value: Record<string, unknown> | null = null,
  ): Promise<void> {
    try {
      await api.decide(item.id, choice, value);
    } catch (error) {
      // The record refuses some opinions — a shift with no variable, say — and
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
   * so the room can decide on something nobody wrote. */
  private change(item: BallotItem): void {
    const from = item.opinions[0]?.item ?? {};
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
    editor.querySelector(".save")!.textContent = "decide on this";
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
    await this.decide(item, Decision.Change, body);
  }

  private close(): void {
    this.scrim.classList.remove("in");
    this.sheet.classList.remove("in");
    window.setTimeout(() => {
      this.scrim.hidden = true;
      this.sheet.hidden = true;
    }, 280);
  }

  /** Ratifying writes the agreed record and asks the coach for the guideline
   * changes, which takes about ten seconds. The button goes dead and the app's
   * own three dots say it is working, so a second tap does nothing. */
  private async onBar(clicked: Event): Promise<void> {
    const button = (clicked.target as Element).closest<HTMLButtonElement>(
      ".mt-ratify",
    );
    if (!button || button.disabled) return;
    const cut = this.cut;
    if (!cut) return;
    button.disabled = true;
    button.textContent = "ratifying";
    button.classList.add("dots3");
    try {
      await api.ratify(cut.id);
    } catch (error) {
      this.bar.innerHTML = this.ratifyBar(0);
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
