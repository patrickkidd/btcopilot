import * as api from "./api";
import { esc, el, type Title } from "./dom";
import {
  openBondEditor,
  openEditor,
  openPersonEditor,
  type Family,
} from "./editor";
import { toast } from "./toast";
import {
  drawVersion,
  fieldsOf,
  isStructure,
  structureName,
  versionWords,
} from "./structure";
import {
  ItemKind,
  ItemStatus,
  VoteChoice,
  type BallotItem,
  type CodingRecord,
  type PairBond,
  type Person,
  type Opinion,
  type TimelineEvent,
  type Vote,
} from "./types";

/** The vote before the meeting: one disputed event per screen, the opinions shown
 * without names so nobody defers to the most senior person in the room
 * (R-0252, R-0257). Nothing the coach thinks is in here at all (R-0254). No
 * rule decides anything before the meeting; the tallies only inform it
 * (R-0274). */

export interface BallotHandlers {
  onTitle(title: string | Title): void;
  /** The last item is voted on: back to the one task card. */
  onDone(): void;
  /** Open the conversation at the line this item came from (R-0278). */
  onTranscript(statementId: number): void;
}

/** The fields an opinion can differ from the others by, in the order they read. */
export const TELLING = [
  "dateTime",
  "person_name",
  "kind",
  "description",
  "symptom",
  "anxiety",
  "functioning",
  "relationship",
] as const;

const WORDS: Record<string, (value: string) => string> = {
  symptom: (value) => `symptom ${value}`,
  anxiety: (value) => `anxiety ${value}`,
  functioning: (value) => `functioning ${value}`,
  relationship: (value) => `relationship: ${value}`,
};

/** One dot per event, as the picture draws a line of them. */
export const LINE = { width: 400, height: 66, y: 34, edge: 16 };

/** The agreement timeline, which the ballot and the meeting both stand under:
 * one dot per event of the cut in order, teal where the vote agreed, amber
 * where it did not with a small count beside it, and the event in front of the
 * room enlarged in green (R-0277, R-0278). */
export function drawTimeline(
  events: BallotItem[],
  current: number | null,
): string {
  const step = (LINE.width - LINE.edge * 2) / Math.max(events.length, 1);
  const dots = events
    .map((one, index) => {
      const x = LINE.edge + step * (index + 0.5);
      if (one.id === current)
        return `<circle class="d-on" cx="${x}" cy="${LINE.y}" r="7.5" data-item="${one.id}"/>`;
      if (one.status === ItemStatus.Agreed)
        return `<circle class="d-ok" cx="${x}" cy="${LINE.y}" r="4.5" data-item="${one.id}"/>`;
      // The small number says how many different opinions there are, so it is
      // only there when there is more than one to tell apart.
      const opinions = group(one).length;
      return (
        `<circle class="d-no" cx="${x}" cy="${LINE.y}" r="5.5" data-item="${one.id}"/>` +
        (opinions > 1
          ? `<text class="d-n" x="${x + 8}" y="${LINE.y - 12}">${opinions}</text>`
          : "")
      );
    })
    .join("");
  return (
    `<div class="ss tl"><svg viewBox="0 0 ${LINE.width} ${LINE.height}" ` +
    `height="${LINE.height}">` +
    `<line class="wire2" x1="${LINE.edge}" y1="${LINE.y}" ` +
    `x2="${LINE.width - LINE.edge}" y2="${LINE.y}"/>${dots}</svg></div>`
  );
}

/** What a coder votes on: a disputed event that at least one person wrote. An
 * item only the coach wrote carries no opinion here, and is the meeting's to take
 * up rather than the room's to vote on (R-0254); the server refuses a vote on
 * one, so it never reaches the ballot. */
export const onBallot = (one: BallotItem) =>
  (one.item_kind === ItemKind.Event || isStructure(one.item_kind)) &&
  one.status === ItemStatus.Disputed &&
  one.opinions.length > 0;

/** The order the ballot walks: the people and the bonds first, then the events,
 * because an event about somebody nobody has agreed on yet cannot be settled
 * (R-0326). */
export function ballotOrder(items: BallotItem[]): BallotItem[] {
  const structure = items.filter((one) => isStructure(one.item_kind));
  return [...structure, ...eventsOf(items).filter(onBallot)].filter(onBallot);
}

/** Every event of a cut in the order they happened, which is the order both
 * screens walk them in. */
export function eventsOf(items: BallotItem[]): BallotItem[] {
  const day = (item: BallotItem) => String(item.opinions[0]?.item.dateTime ?? "");
  return items
    .filter((one) => one.item_kind === ItemKind.Event)
    .sort((a, b) => day(a).localeCompare(day(b)));
}

export const when = (value: unknown): string => {
  if (typeof value !== "string" || !value) return "no date yet";
  if (/^\d{4}$/.test(value)) return value;
  const day = new Date(`${value}T00:00:00`);
  if (Number.isNaN(day.getTime())) return value;
  return day.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

/** An event kind said the way a first-time reader would say it, for an item
 * whose writer left the description empty (R-0318). */
const KIND_WORDS: Record<string, string> = {
  shift: "a shift",
  birth: "a birth",
  adopted: "an adoption",
  bonded: "a new bond",
  married: "a marriage",
  separated: "a separation",
  divorced: "a divorce",
  moved: "a move",
  death: "a death",
};

/** What happened, never a placeholder: with no description the kind is said in
 * words (R-0318). */
export function what(item: BallotItem): string {
  const first = item.opinions[0];
  const kind = String(first?.item.kind ?? "");
  return String(first?.item.description ?? "") || KIND_WORDS[kind] || kind;
}

/** Who a row is about and what happened, which is what every row of the meeting
 * is named by (R-0318). */
export function names(item: BallotItem): string {
  const said = what(item);
  const who = item.opinions[0]?.person_name ?? "";
  return who && said ? `${who} · ${said}` : who || said;
}

/** What one opinion says, in the record's own words, for the fields given. */
export function words(opinion: Opinion, fields: readonly string[]): string {
  const said = fields
    .map((field) => {
      const value =
        field === "person_name" ? opinion.person_name : opinion.item[field];
      if (value === null || value === undefined || value === "") return "";
      const text = String(value);
      if (field === "dateTime") return when(text);
      if (field === "person_name") return `→ ${text}`;
      return WORDS[field] ? WORDS[field](text) : text;
    })
    .filter(Boolean);
  return said.join(" · ");
}

/** What an opinion says when the coders differ by nothing the words can show —
 * one of them simply left the item out. The date, the person and the words are
 * already above the opinions, so only the variables are left to say. */
const REST = [
  "symptom",
  "anxiety",
  "functioning",
  "relationship",
] as const;

/** The fields the coders read differently, which is what an opinion is chosen by.
 * When they wrote the same thing and only differ by who left it out, the whole
 * opinion is shown instead. */
export function telling(
  opinions: Opinion[],
  kind: ItemKind = ItemKind.Event,
): readonly string[] {
  const all = isStructure(kind) ? fieldsOf(kind) : TELLING;
  const differs = all.filter((field) => {
    const seen = new Set(
      opinions.map((opinion) =>
        String(
          (field === "person_name" ? opinion.person_name : opinion.item[field]) ?? "",
        ),
      ),
    );
    return seen.size > 1;
  });
  if (differs.length) return differs;
  return isStructure(kind) ? all : REST;
}

/** Opinions worded the same way are one opinion with a count beside it: the ballot
 * is about the readings, not about how many people are in the room. */
export interface Grouped {
  label: string;
  coders: number;
  opinion: Opinion;
}

export function group(
  item: BallotItem,
  records?: Map<number, CodingRecord>,
): Grouped[] {
  const fields = telling(item.opinions, item.item_kind);
  const found = new Map<string, Grouped>();
  for (const opinion of item.opinions) {
    const label =
      (isStructure(item.item_kind)
        ? versionWords(records?.get(opinion.coding_id ?? -1), opinion.item, fields)
        : words(opinion, fields)) || "as written";
    const already = found.get(label);
    if (already) already.coders += 1;
    else found.set(label, { label, coders: 1, opinion });
  }
  return [...found.values()];
}

/** The transcript line one version was written from, under that version. A
 * version with no line was not written from anything said: the coach replayed
 * it, or somebody typed it into the editor (R-0278). */
export function versionLine(opinion: Opinion, openable: boolean): string {
  if (!opinion.line)
    return `<div class="quote"><i>written in the editor</i></div>`;
  const open = openable
    ? `<div><button class="chip" type="button" ` +
      `data-said="${opinion.line.statement_id}">open in transcript</button></div>`
    : "";
  return (
    `<div class="quote"><b>${esc(opinion.line.who)}:</b> ` +
    `&ldquo;${esc(opinion.line.text)}&rdquo;</div>${open}`
  );
}

export class Ballot {
  private session = "";
  private items: BallotItem[] = [];
  private ballot: BallotItem[] = [];
  private mine = new Map<number, Vote>();
  /** The family each coding was written on, which a person or a bond is drawn
   * against (R-0326). */
  private records = new Map<number, CodingRecord>();
  private at = 0;
  private scrim = el("div", "fs-scrim");
  private sheet = el("div", "fs-sheet bl-sheet");

  constructor(
    private view: HTMLElement,
    private caption: HTMLElement,
    private body: HTMLElement,
    private overlay: HTMLElement,
    private handlers: BallotHandlers,
  ) {
    this.overlay.append(this.scrim, this.sheet);
    this.scrim.hidden = true;
    this.sheet.hidden = true;
    this.scrim.addEventListener("click", () => this.close());
    this.body.addEventListener("click", (clicked) => this.onTap(clicked));
    this.view.addEventListener("click", (clicked) => this.onDot(clicked));
    this.body.addEventListener("change", (changed) => {
      if ((changed.target as Element).classList.contains("say"))
        void this.say((changed.target as HTMLInputElement).value);
    });
  }

  /** The item the room is on, so stepping out to the transcript and back comes
   * back to it. */
  onItem(): number | null {
    return this.item()?.id ?? null;
  }

  /** Open the ballot of one cut on the first item this coder has not voted
   * on, or on `itemId` when coming back to one. An item they skipped is still
   * on the list (R-0257). */
  async open(cutId: number, itemId: number | null = null): Promise<void> {
    const [cut, items, votes, records] = await Promise.all([
      api.cut(cutId),
      api.items(cutId),
      api.votes(cutId),
      api.records(cutId),
    ]);
    this.session = cut.session;
    this.items = items;
    this.records = new Map(records.map((one) => [one.coding_id, one]));
    this.ballot = ballotOrder(items);
    this.mine = new Map(votes.map((vote) => [vote.review_item_id, vote]));
    const back = itemId === null ? -1 : this.ballot.findIndex((one) => one.id === itemId);
    this.at = back >= 0 ? back : Math.max(this.unvoted(0), 0);
    this.render();
  }

  /** Where the next item to vote on is, from here on and then from the top. */
  private unvoted(from: number): number {
    const count = this.ballot.length;
    for (let step = 0; step < count; step += 1) {
      const index = (from + step + count) % count;
      if (!this.mine.has(this.ballot[index].id)) return index;
    }
    return -1;
  }

  private item(): BallotItem | null {
    return this.ballot[this.at] ?? null;
  }

  private render(): void {
    const item = this.item();
    if (!item) {
      this.body.innerHTML = `<div class="none">Nothing left to vote on.</div>`;
      this.view.innerHTML = "";
      this.caption.innerHTML = "";
      return;
    }
    this.handlers.onTitle({
      name: this.session,
      tail: `ballot · ${this.at + 1} of ${this.ballot.length}`,
    });
    this.drawLine(item);
    this.body.innerHTML = this.card(item);
  }

  /** The agreement timeline, and under it what is left to vote on. */
  private drawLine(current: BallotItem): void {
    this.view.style.height = `${LINE.height}px`;
    this.view.innerHTML = drawTimeline(this.events(), current.id);
    const left = this.ballot.filter((one) => !this.mine.has(one.id)).length;
    this.caption.innerHTML =
      `<span class="cta">tap a dot to jump</span>` +
      `<button class="tok g" type="button">now · ` +
      `${esc(this.nowWords(current))}</button>` +
      `<button class="tok" type="button">${left} open</button>`;
  }

  /** What the strip says the room is on: an event by its date, a person or a
   * bond by their name, because structure is not on the wire (R-0326, 4d). */
  private nowWords(item: BallotItem): string {
    if (!isStructure(item.item_kind)) return when(item.opinions[0]?.item.dateTime);
    return structureName(item.item_kind, item.opinions[0]?.item ?? {}, item.people);
  }

  private events(): BallotItem[] {
    return eventsOf(this.items);
  }

  private card(item: BallotItem): string {
    const first = item.opinions[0];
    const structure = isStructure(item.item_kind);
    const vote = this.mine.get(item.id);
    const chosen = vote?.choice === VoteChoice.Opinion ? vote.value : null;
    const mine = vote?.choice === VoteChoice.Change ? vote.value : null;
    const opinions = group(item, this.records)
      .map((one, index) => {
        const on =
          chosen && chosen.coding_id === one.opinion.coding_id ? " on" : "";
        // How many coders backed an opinion is not shown here: names and counts
        // appear for the first time at the meeting, so nobody votes with the
        // room in view (R-0252, R-0272). A person or a bond is drawn as well as
        // written, so the argument reads as a shape (R-0326, 3b).
        const drawn = structure
          ? `<div class="frag">` +
            drawVersion(this.records, item.item_kind, one.opinion) +
            `</div>`
          : "";
        // A person or a bond is coded from a turn per version: several coders
        // may have written the same person from different things said, so the
        // line rides with the version and not with the item (R-0278).
        const said = structure ? versionLine(one.opinion, true) : "";
        return (
          `<div class="opinion tap${on}" data-coding="${one.opinion.coding_id}">` +
          `<span>opinion ${index + 1} · ${esc(one.label)}</span>${drawn}${said}</div>`
        );
      })
      .join("");
    const ownOpinion = mine
      ? `<div class="opinion tap on"><span>your opinion · ` +
        `${esc(
          structure
            ? versionWords(undefined, mine, fieldsOf(item.item_kind))
            : words({ item: mine } as Opinion, TELLING),
        )}</span></div>`
      : "";
    // The one count the ballot does show, because leaving an item out is not a
    // vote for any opinion and the room needs to know it happened. It is a
    // plain label, never a row you can tap.
    const left = item.not_coded
      ? `<div class="note">${item.not_coded} ` +
        `coder${item.not_coded === 1 ? "" : "s"} left this ` +
        `${isStructure(item.item_kind) ? "out" : "event out"}</div>`
      : "";
    const line =
      structure || !item.line
        ? ""
        : `<div class="quote"><b>${esc(item.line.who)}:</b> ` +
          `&ldquo;${esc(item.line.text)}&rdquo;</div>` +
          `<div><button class="chip" id="bl-line" type="button">open in transcript</button></div>`;
    const dropped = vote?.choice === VoteChoice.Drop ? " on" : "";
    return (
      `<div class="bl-card">` +
      (structure
        ? `<div class="progress">${
            item.item_kind === ItemKind.Person ? "a person" : "a couple"
          }${item.ambiguous ? " · the room decides who is who" : ""}</div>` +
          `<h3>${esc(this.nowWords(item))}</h3>`
        : `<div class="progress">${esc(when(first?.item.dateTime))}` +
          `${first?.person_name ? ` · → ${esc(first.person_name)}` : ""}</div>` +
          `<h3>${esc(what(item))}</h3>`) +
      opinions +
      ownOpinion +
      left +
      line +
      `</div>` +
      `<div class="phbtns">` +
      `<button class="btn" id="bl-change" type="button">change&hellip;</button>` +
      `<button class="btn${dropped}" id="bl-drop" type="button">drop</button></div>` +
      `<label class="saylab" for="bl-say">Say why you voted as you did ` +
      `(optional — you may skip it)</label>` +
      `<input class="say" id="bl-say" type="text" placeholder="say why (optional)" ` +
      `value="${esc(vote?.reason ?? "")}">` +
      `<div class="nextrow"><button class="btn" id="bl-next" type="button">` +
      `${this.last() ? "done" : "next ›"}</button></div>`
    );
  }

  /** The last screen of the ballot: nothing is left unvoted after this one. */
  private last(): boolean {
    const item = this.item();
    if (!item) return true;
    return this.ballot.every(
      (one) => one.id === item.id || this.mine.has(one.id),
    );
  }

  private onTap(clicked: Event): void {
    const target = clicked.target as Element;
    const item = this.item();
    if (!item) return;
    const said = target.closest<HTMLElement>("[data-said]");
    const opinion = said ? null : target.closest<HTMLElement>(".opinion.tap");
    if (opinion?.dataset.coding) {
      void this.vote(VoteChoice.Opinion, {
        coding_id: Number(opinion.dataset.coding),
      });
      return;
    }
    if (target.closest("#bl-drop")) void this.vote(VoteChoice.Drop, null);
    else if (target.closest("#bl-change")) this.change(item);
    else if (target.closest("#bl-line") && item.line)
      this.handlers.onTranscript(item.line.statement_id);
    else if (said) this.handlers.onTranscript(Number(said.dataset.said));
    else if (target.closest("#bl-next")) void this.next();
  }

  private onDot(clicked: Event): void {
    const dot = (clicked.target as Element).closest<HTMLElement>("[data-item]");
    if (!dot) return;
    const found = this.ballot.findIndex(
      (one) => one.id === Number(dot.dataset.item),
    );
    if (found < 0) {
      toast("The coders read that one the same way");
      return;
    }
    this.at = found;
    this.render();
  }

  private reason(): string | null {
    const said = this.body.querySelector<HTMLInputElement>("#bl-say");
    return said && said.value.trim() ? said.value.trim() : null;
  }

  private async vote(
    choice: VoteChoice,
    value: Record<string, unknown> | null,
  ): Promise<void> {
    const item = this.item();
    if (!item) return;
    const vote = await api.castVote(item.id, choice, value, this.reason());
    this.mine.set(item.id, vote);
    this.render();
  }

  /** Why you voted as you did, said after the vote itself. */
  private async say(reason: string): Promise<void> {
    const item = this.item();
    const vote = item ? this.mine.get(item.id) : null;
    if (!item || !vote) return;
    this.mine.set(
      item.id,
      await api.castVote(item.id, vote.choice, vote.value, reason || null),
    );
  }

  /** The next item, or the first one still unvoted when this was the last;
  /* when every item has a vote the ballot is finished. */
  private async next(): Promise<void> {
    const found = this.unvoted(this.at + 1);
    if (found < 0) {
      this.handlers.onDone();
      return;
    }
    this.at = found;
    this.render();
  }

  /** The family one version was written on, which the editor of a person or a
   * bond needs to offer the couples and the partners it can name. */
  private family(item: BallotItem): Family {
    const record = this.records.get(item.opinions[0]?.coding_id ?? -1);
    return {
      people: (record?.people ?? []) as Person[],
      pair_bonds: record?.pair_bonds ?? [],
      events: record?.events ?? [],
    };
  }

  /** A version of a bond, opened in the bond's own editor: whose bond it is
   * stands as person_a, and the editor asks for the other and whether they
   * married. */
  private bondEditor(item: BallotItem, bond: PairBond): HTMLElement {
    const family = this.family(item);
    const self =
      family.people.find((one) => one.id === bond.person_a) ?? family.people[0];
    return openBondEditor(bond, self, family, {
      done: () => this.close(),
      onSave: (body) => void this.own({ ...bond, ...body }),
    });
  }

  /** "change…" opens the app's own editor over the ballot, prefilled, so you can
   * write an opinion nobody wrote; it joins the count as one more opinion
   * (R-0257). A person or a bond opens their own editor, the same one the record
   * is corrected in (R-0326). The turn it came from is kept with the item. */
  private change(item: BallotItem): void {
    const vote = this.mine.get(item.id);
    const from =
      vote?.choice === VoteChoice.Change
        ? vote.value
        : (item.opinions[0]?.item ?? {});
    const people = item.people.map(
      (one) => ({ id: one.id, name: one.name }) as Person,
    );
    const editor =
      item.item_kind === ItemKind.Person
        ? openPersonEditor(from as unknown as Person, {
            done: () => this.close(),
            family: this.family(item),
            onSave: (body) => void this.own({ ...from, ...body }),
          })
        : item.item_kind === ItemKind.PairBond
          ? this.bondEditor(item, from as unknown as PairBond)
          : openEditor(
              from as unknown as TimelineEvent,
              people,
              () => this.close(),
              undefined,
              undefined,
              (body) => void this.own(body),
            );
    editor.querySelector(".save")!.textContent = "save as my opinion";
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
    editor
      .querySelector(".acts")
      ?.append(el("button", "del", "cancel"));
    editor.querySelector(".acts .del")!.addEventListener("click", () =>
      this.close(),
    );
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

  private async own(body: Record<string, unknown>): Promise<void> {
    await this.vote(VoteChoice.Change, body);
    this.close();
  }

  private close(): void {
    this.scrim.classList.remove("in");
    this.sheet.classList.remove("in");
    window.setTimeout(() => {
      this.scrim.hidden = true;
      this.sheet.hidden = true;
    }, 280);
  }
}
