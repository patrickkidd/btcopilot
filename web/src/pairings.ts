import * as api from "./api";
import {
  PairSheet,
  drawStrip,
  entryKey,
  leftOut,
  many,
  opinionCards,
  opinionKeys,
  pairOpinions,
  passage,
  saidDate,
  toPairing,
  whoOf,
  walkOrder,
  type PairEntry,
  type PairScreen,
  type Pairing,
  type Who,
} from "./ballot";
import { el, esc, stepBtn, type Title } from "./dom";
import { isStructure } from "./structure";
import { Feature, tap } from "./track";
import { Confidence, type BallotItem, type CodingRecord, type Entry, type Repaired } from "./types";

/** Patrick's look over the ballot's pairings before he opens the vote: the
 * ones the call marked unsure first, on the vote's own card, identical
 * versions merged as on the vote, one box per opinion, a tap on it taking
 * every coder's entry it stands for; one entry of a box holding several is
 * taken out from the split list. He alone joins and splits; coders never
 * change a pairing (R-0963, R-0967, R-0970). */

export interface PairingsHandlers {
  onTitle(title: string | Title): void;
  onDone(): void;
  /** Another pairing is on screen. */
  onMoved(): void;
}

const RANK = [Confidence.Unsure, Confidence.Likely, Confidence.Sure];

const sure = (item: BallotItem): Confidence => item.pairing_confidence ?? Confidence.Unsure;

const rank = (item: BallotItem) => RANK.indexOf(sure(item));

/** How sure a pairing is, as the one mark it has wherever it shows: its dot
 * on the strip, its chip on the card and in the join list (R-0972). */
export const mark = (item: BallotItem): string => `mark c-${sure(item)}`;

const chip = (item: BallotItem): string =>
  `<span class="tok ${mark(item)}">${esc(sure(item))}</span>`;

/** Unsure first, and within each the order the ballot walks, the
 * conversation's. */
export const lookOrder = (items: BallotItem[]): BallotItem[] =>
  walkOrder(items.filter((one) => one.opinions.length > 0))
    .map((item, at) => ({ item, at }))
    .sort((a, b) => rank(a.item) - rank(b.item) || a.at - b.at)
    .map(({ item }) => item);

/** Where the pairing with this id stands in the list, or, when it is gone,
 * the one whose id is nearest it. */
export const nearest = (pairings: Pairing[], id: number): number =>
  pairings.reduce(
    (best, one, at) =>
      Math.abs(one.item.id - id) < Math.abs(pairings[best].item.id - id) ? at : best,
    0,
  );

/** How far either side of a pairing's passage the join list looks for the
 * pairings from the same part of the conversation, in lines of the cut
 * (R-0974). */
const NEAR = 3;

/** The sections of the join list, in the order they show (R-0974). */
export enum Section {
  Near = "near",
  All = "all",
  Undated = "undated",
}

const HEADS: Record<Section, string> = {
  [Section.Near]: "From the same part of the conversation",
  [Section.All]: "All, by year",
  [Section.Undated]: "no date yet",
};

/** The years a pairing's boxes give, earliest first. */
export const yearsOf = (pairing: Pairing): number[] =>
  [
    ...new Set(
      pairing.versions
        .flat()
        .filter(saidDate)
        .map((one) => Number(one.date.slice(0, 4))),
    ),
  ].sort((a, b) => a - b);

/** One year, or the range when the boxes give different ones. */
export function yearText(pairing: Pairing): string {
  const years = yearsOf(pairing);
  return years.length > 1 ? `${years[0]}–${years.at(-1)}` : String(years[0] ?? "");
}

/** The pairings `current` can join, each once: those whose passage is
 * within three lines of the cut of its own, in the conversation's order; then the
 * rest by the earliest year a box gives; the undated last, in the
 * conversation's order. People and couples have no year, so the rest of them
 * stand in that order too (R-0974). */
export function joinList(current: Pairing, pairings: Pairing[]): Record<Section, Pairing[]> {
  const byId = new Map(pairings.map((one) => [one.item.id, one]));
  const others = walkOrder(
    pairings
      .filter((one) => one !== current && one.item.item_kind === current.item.item_kind)
      .map((one) => one.item),
  ).map((item) => byId.get(item.id)!);
  const at = (one: Pairing) => one.line?.number ?? null;
  const here = at(current);
  const close = (one: Pairing) => {
    const there = at(one);
    return here !== null && there !== null && Math.abs(there - here) <= NEAR;
  };
  const rest = others.filter((one) => !close(one));
  const dated = (one: Pairing) => yearsOf(one).length > 0;
  return {
    [Section.Near]: others.filter(close),
    [Section.All]: rest.filter(dated).sort((a, b) => yearsOf(a)[0] - yearsOf(b)[0]),
    [Section.Undated]: rest.filter((one) => !dated(one)),
  };
}

const wordsOf = (entry: PairEntry): string[] => [
  entry.kind,
  entry.who,
  entry.toward,
  entry.title,
  entry.desc,
  ...entry.values.map((one) => one.said),
];

/** Every word of every box of a pairing, the people it names and its years,
 * which the join list's search looks through. */
export const findable = (pairing: Pairing): string =>
  [...pairing.versions.flat().flatMap(wordsOf), ...yearsOf(pairing).map(String)]
    .join(" ")
    .toLowerCase();

export const matches = (found: string, query: string): boolean =>
  query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((term) => found.includes(term));

const entries = (pairing: Pairing): Entry[] =>
  pairing.versions.flat().map(({ coding_id, item_id }) => ({ coding_id, item_id }));

export class Pairings {
  private cutId = 0;
  private session = "";
  private pairings: Pairing[] = [];
  private records = new Map<number, CodingRecord>();
  private who: Who = whoOf([]);
  private at = 0;
  /** The entries tapped, which a split takes out or a join moves. */
  private chosen = new Set<string>();
  private whole = new Set<number>();
  private full = new Set<number>();
  private sheet: PairSheet;
  private live = false;

  constructor(
    private screen: PairScreen,
    private handlers: PairingsHandlers,
  ) {
    this.sheet = new PairSheet(screen.overlay);
    screen.body.addEventListener("click", (clicked) => this.onTap(clicked));
    screen.bar.addEventListener("click", (clicked) => this.onTap(clicked));
    screen.view.addEventListener("click", (clicked) => {
      const dot = (clicked.target as Element).closest<HTMLElement>("[data-item]");
      if (this.live && dot) this.go(Number(dot.dataset.item));
    });
    this.sheet.sheet.addEventListener("click", (clicked) => {
      const row = (clicked.target as Element).closest<HTMLElement>("[data-join]");
      if (row)
        void this.join(
          Number(row.dataset.join),
          row.closest<HTMLElement>("[data-section]")!.dataset.section as Section,
        );
      const one = (clicked.target as Element).closest<HTMLElement>("[data-split]");
      if (one) void this.pick(one.dataset.split!.split(" "));
    });
  }

  /** Open a cut's pairings on `itemId`, or, when a join took it away, on the
   * pairing nearest it; with none named, on the first. Once the vote is open
   * the pairings are shut, and nothing opens (R-0963). */
  async open(cutId: number, itemId: number | null = null): Promise<boolean> {
    const [cut, items, records] = await Promise.all([
      api.cut(cutId),
      api.items(cutId),
      api.records(cutId),
    ]);
    if (cut.vote_opened_at !== null) return false;
    this.live = true;
    this.cutId = cutId;
    this.session = cut.session;
    this.records = new Map(records.map((one) => [one.coding_id, one]));
    this.pairings = this.paired(lookOrder(items));
    this.at = itemId === null ? 0 : nearest(this.pairings, itemId);
    this.render();
    return true;
  }

  /** The pairing on screen, which the address names. */
  onItem(): number | null {
    return this.pairing()?.item.id ?? null;
  }

  /** The people pairings decide who a person is on every card, so all of
   * them are drawn again whenever one changes. */
  private paired(items: BallotItem[]): Pairing[] {
    this.who = whoOf(items);
    return items.map((one) => toPairing(one, this.records, this.who));
  }

  private pairing(): Pairing | null {
    return this.pairings[this.at] ?? null;
  }

  private render(): void {
    const pairing = this.pairing();
    if (!pairing) {
      this.screen.body.innerHTML = `<div class="none">No pairings yet.</div>`;
      this.screen.view.innerHTML = "";
      this.screen.caption.innerHTML = "";
      this.screen.bar.innerHTML = "";
      return;
    }
    this.handlers.onTitle({
      name: this.session,
      tail: `pairings · ${this.at + 1} of ${this.pairings.length}`,
    });
    const unsure = this.pairings.filter((one) => rank(one.item) === 0).length;
    drawStrip(
      this.screen,
      this.pairings.map((one) => one.item.id),
      pairing,
      (id) => mark(this.pairings.find((one) => one.item.id === id)!.item),
      `${unsure} unsure`,
    );
    this.screen.body.innerHTML = this.card(pairing);
    this.screen.bar.innerHTML = this.controls(pairing);
  }

  private card(pairing: Pairing): string {
    const { item } = pairing;
    return (
      `<div class="bl-card pv-card">` +
      `<div class="pv-ask"><h3>Are these the same thing?</h3>${chip(item)}</div>` +
      (pairing.line ? passage(pairing.line, this.whole.has(item.id)) : "") +
      (item.pairing_reason
        ? `<div class="pv-why"><div class="pv-label">why paired</div>` +
          `<div class="note">${esc(item.pairing_reason)}</div></div>`
        : "") +
      opinionCards(pairOpinions(pairing), null, this.full.has(item.id), this.chosen) +
      leftOut(item) +
      `</div>`
    );
  }

  /** A split takes out the boxes picked, never all of them; with none picked
   * it lists the entries of the boxes holding several. */
  private controls(pairing: Pairing): string {
    const all = entries(pairing).length;
    const some = this.chosen.size;
    const can = some ? some < all : pairOpinions(pairing).some(many);
    return (
      stepBtn("‹ Back", `id="pr-prev"`, this.at === 0) +
      `<button class="btn" id="pr-join" type="button" title="the same thing as another pairing: join them">` +
      `join&hellip;</button>` +
      `<button class="btn" title="not all the same thing: take one out" id="pr-split" type="button"` +
      `${can ? "" : " disabled"}>` +
      `split&hellip;</button>` +
      stepBtn(this.at === this.pairings.length - 1 ? "Done" : "Next ›", `id="pr-next"`, false)
    );
  }

  private onTap(clicked: Event): void {
    const target = clicked.target as Element;
    const pairing = this.pairing();
    if (!pairing || !this.live) return;
    const { item } = pairing;
    const box = target.closest<HTMLElement>("[data-opinion]");
    if (target.closest(".pv-words.clip")) {
      this.full.add(item.id);
      this.render();
    } else if (target.closest("#bl-quote.clip")) {
      this.whole.add(item.id);
      this.render();
    } else if (box) {
      const keys = opinionKeys(pairOpinions(pairing)[Number(box.dataset.opinion)]);
      const on = keys.every((key) => this.chosen.has(key));
      keys.forEach((key) => (on ? this.chosen.delete(key) : this.chosen.add(key)));
      this.render();
    } else if (target.closest("#pr-split")) {
      if (this.chosen.size) void this.split(pairing);
      else this.choices(pairing);
    } else if (target.closest("#pr-join")) this.offer(pairing);
    else if (target.closest("#pr-prev") && this.at > 0) this.step(this.at - 1);
    else if (target.closest("#pr-next")) {
      if (this.at === this.pairings.length - 1) this.handlers.onDone();
      else this.step(this.at + 1);
    }
  }

  private step(at: number): void {
    this.at = at;
    this.chosen.clear();
    this.render();
    this.handlers.onMoved();
  }

  private go(id: number): void {
    this.sheet.close();
    this.step(this.pairings.findIndex((one) => one.item.id === id));
  }

  private picked(pairing: Pairing): Entry[] {
    return entries(pairing).filter((one) => this.chosen.has(entryKey(one)));
  }

  private async split(pairing: Pairing): Promise<void> {
    tap(Feature.PairingSplit);
    this.apply(await api.split(this.cutId, this.picked(pairing)), pairing.item.id);
  }

  /** One entry from the split list, with every coder's entry it stands for. */
  private async pick(keys: string[]): Promise<void> {
    tap(Feature.PairingSplitPick);
    this.sheet.close();
    this.chosen = new Set(keys);
    await this.split(this.pairing()!);
  }

  /** The other pairings of the same kind of item to join with, under a
   * search that hides and shows the rows in place as he types; the field is
   * not focused, so a phone keeps its keyboard down until he taps it. With
   * entries tapped, those move into the one picked; with none, the one picked
   * comes into this one whole (R-0974). */
  private offer(pairing: Pairing): void {
    const list = joinList(pairing, this.pairings);
    const heads = isStructure(pairing.item.item_kind) ? { ...HEADS, [Section.All]: "All" } : HEADS;
    const top = el(
      "div",
      "pv-jtop",
      `<div class="cf-t">Join with which pairing?</div>` +
        `<div class="fs-search"><input type="search" placeholder="Search words, people or a year" ` +
        `aria-label="Search the pairings"></div>`,
    );
    const body = el(
      "div",
      "pv-join",
      Object.values(Section)
        .filter((section) => list[section].length)
        .map(
          (section) =>
            `<div data-section="${section}"><div class="pv-label">${esc(heads[section])}</div>` +
            `${list[section].map(joinRow).join("")}</div>`,
        )
        .join("") + `<div class="none" hidden>nothing matches</div>`,
    );
    const input = top.querySelector("input")!;
    const shown = (within: Element) => within.querySelector("[data-find]:not([hidden])") !== null;
    input.addEventListener("input", () => {
      if (!input.dataset.searched) tap(Feature.PairingJoinSearch);
      input.dataset.searched = "1";
      for (const row of body.querySelectorAll<HTMLElement>("[data-find]"))
        row.hidden = !matches(row.dataset.find!, input.value);
      for (const section of body.querySelectorAll<HTMLElement>("[data-section]"))
        section.hidden = !shown(section);
      body.querySelector<HTMLElement>(".none")!.hidden = shown(body);
    });
    this.sheet.sheet.classList.remove("pv-split");
    this.sheet.show(body, top);
  }

  /** The entries of every box holding several, by name, under their opinion
   * when more than one box holds several (R-0970). */
  private choices(pairing: Pairing): void {
    const boxes = pairOpinions(pairing)
      .map((one, index) => ({ one, index }))
      .filter(({ one }) => many(one));
    const grouped = boxes.length > 1;
    const rows = boxes
      .map(
        ({ one, index }) =>
          (grouped ? `<div class="pv-label">opinion ${index + 1}</div>` : "") +
          one.entries
            .map(
              (entry, at) =>
                `<button class="pv-row" type="button" data-split="${esc(one.twins[at].map(entryKey).join(" "))}">` +
                `<span class="rtitle">${esc(entry.who)}</span>` +
                `<span class="rsub">${grouped ? "" : `opinion ${index + 1} · `}${esc(entry.kind)}</span></button>`,
            )
            .join(""),
      )
      .join("");
    const of = grouped ? "" : ` of opinion ${boxes[0].index + 1}`;
    tap(Feature.PairingSplitList);
    this.sheet.sheet.classList.add("pv-split");
    this.sheet.show(`<div class="cf-t">Take which entry out${of}?</div>${rows}`);
  }

  private async join(otherId: number, from: Section): Promise<void> {
    const pairing = this.pairing()!;
    const other = this.pairings.find((one) => one.item.id === otherId)!;
    const moving = this.picked(pairing);
    tap(from === Section.Near ? Feature.PairingJoinNear : Feature.PairingJoinAll);
    this.sheet.close();
    const answer = moving.length
      ? await api.join(other.item.id, [...entries(other), ...moving])
      : await api.join(pairing.item.id, [...entries(pairing), ...entries(other)]);
    this.apply(answer, moving.length && moving.length === entries(pairing).length ? otherId : pairing.item.id);
  }

  /** The pairings a join or a split changed take their places in the list,
   * new ones right after this one, emptied ones gone; the screen stays on
   * `stay` (R-0963). */
  private apply(answer: Repaired, stay: number): void {
    const gone = new Set(answer.deleted);
    const known = new Set(this.pairings.map((one) => one.item.id));
    const here = this.pairing()!.item.id;
    const kept = this.pairings
      .filter((one) => !gone.has(one.item.id))
      .map((one) => answer.items.find((that) => that.id === one.item.id) ?? one.item);
    const at = kept.findIndex((one) => one.id === here);
    kept.splice(at + 1, 0, ...answer.items.filter((one) => !known.has(one.id)));
    this.pairings = this.paired(kept);
    this.step(Math.max(kept.findIndex((one) => one.id === stay), 0));
  }

  close(): void {
    this.live = false;
    this.sheet.close();
  }
}

/** One row of the join list, its values in fixed places: the year or the
 * range, the kind, who and toward, the first box's title, its mark (R-0966,
 * R-0974). */
function joinRow(pairing: Pairing): string {
  const first = pairOpinions(pairing)[0].entries[0];
  return (
    `<button class="pv-row pv-jrow" type="button" data-join="${pairing.item.id}" ` +
    `data-find="${esc(findable(pairing))}">` +
    `<span class="pv-jy">${esc(yearText(pairing))}</span>` +
    `<span class="pv-jl"><span class="pv-tag">${esc(first.kind)}</span>` +
    `<span class="pv-jw">${esc(first.who)}${first.toward ? ` → ${esc(first.toward)}` : ""}</span></span>` +
    chip(pairing.item) +
    (first.title ? `<span class="pv-jt">${esc(first.title)}</span>` : "") +
    `</button>`
  );
}
