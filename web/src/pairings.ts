import * as api from "./api";
import {
  PairSheet,
  drawStrip,
  entryKey,
  leftOut,
  nowWords,
  opinionCards,
  pairOpinions,
  passage,
  toPairing,
  whoOf,
  walkOrder,
  writtenDate,
  type PairScreen,
  type Pairing,
  type Who,
} from "./ballot";
import { esc, stepBtn, type Title } from "./dom";
import { Feature, tap } from "./track";
import { Confidence, type BallotItem, type CodingRecord, type Entry, type Repaired } from "./types";

/** Patrick's look over the ballot's pairings before he opens the vote: the
 * ones the call marked unsure first, on the vote's own card, identical
 * versions merged as on the vote, a tap on an entry taking every coder's entry
 * it stands for. He alone joins and splits; coders never change a pairing
 * (R-0963, R-0967). */

export interface PairingsHandlers {
  onTitle(title: string | Title): void;
  onDone(): void;
}

const RANK = [Confidence.Unsure, Confidence.Likely, Confidence.Sure];

const rank = (item: BallotItem) => RANK.indexOf(item.pairing_confidence ?? Confidence.Unsure);

/** Unsure first, and within each the order the ballot walks. */
export const lookOrder = (items: BallotItem[]): BallotItem[] =>
  walkOrder(items.filter((one) => one.opinions.length > 0))
    .map((item, at) => ({ item, at }))
    .sort((a, b) => rank(a.item) - rank(b.item) || a.at - b.at)
    .map(({ item }) => item);

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
      if (row) void this.join(Number(row.dataset.join));
    });
  }

  async open(cutId: number): Promise<void> {
    const [cut, items, records] = await Promise.all([
      api.cut(cutId),
      api.items(cutId),
      api.records(cutId),
    ]);
    this.live = true;
    this.cutId = cutId;
    this.session = cut.session;
    this.records = new Map(records.map((one) => [one.coding_id, one]));
    this.pairings = this.paired(lookOrder(items));
    this.at = 0;
    this.render();
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
      (id) => rank(this.pairings.find((one) => one.item.id === id)!.item) > 0,
      `${unsure} unsure`,
    );
    this.screen.body.innerHTML = this.card(pairing);
    this.screen.bar.innerHTML = this.controls(pairing);
  }

  private card(pairing: Pairing): string {
    const { item } = pairing;
    return (
      `<div class="bl-card pv-card">` +
      (pairing.line ? passage(pairing.line, this.whole.has(item.id)) : "") +
      `<div class="progress">${esc(item.pairing_confidence ?? Confidence.Unsure)}</div>` +
      (item.pairing_reason ? `<div class="note">${esc(item.pairing_reason)}</div>` : "") +
      opinionCards(pairOpinions(pairing), null, this.full.has(item.id), this.chosen) +
      leftOut(item) +
      `</div>`
    );
  }

  /** A split needs some of the pairing's entries tapped, never all of them. */
  private controls(pairing: Pairing): string {
    const all = entries(pairing).length;
    const some = this.chosen.size;
    return (
      stepBtn("‹ Back", `id="pr-prev"`, this.at === 0) +
      `<button class="btn" id="pr-join" type="button">join&hellip;</button>` +
      `<button class="btn" id="pr-split" type="button"${some && some < all ? "" : " disabled"}>` +
      `split off</button>` +
      stepBtn(this.at === this.pairings.length - 1 ? "Done" : "Next ›", `id="pr-next"`, false)
    );
  }

  private onTap(clicked: Event): void {
    const target = clicked.target as Element;
    const pairing = this.pairing();
    if (!pairing || !this.live) return;
    const { item } = pairing;
    const entry = target.closest<HTMLElement>("[data-entry]");
    if (target.closest(".pv-words.clip")) {
      this.full.add(item.id);
      this.render();
    } else if (entry) {
      const keys = entry.dataset.entry!.split(" ");
      const on = keys.every((key) => this.chosen.has(key));
      keys.forEach((key) => (on ? this.chosen.delete(key) : this.chosen.add(key)));
      this.render();
    } else if (target.closest("#bl-quote.clip")) {
      this.whole.add(item.id);
      this.render();
    } else if (target.closest("#pr-split")) void this.split(pairing);
    else if (target.closest("#pr-join")) this.offer(pairing);
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

  /** The other pairings of the same kind of item to join with: with entries
   * tapped, those move into the one picked; with none, the one picked comes
   * into this one whole. */
  private offer(pairing: Pairing): void {
    const rows = this.pairings
      .filter((one) => one !== pairing && one.item.item_kind === pairing.item.item_kind)
      .map((one) => {
        const first = one.versions[0][0];
        const title = [first.kind, first.who, first.title].filter(Boolean).join(" · ");
        return (
          `<button class="pv-row" type="button" data-join="${one.item.id}">` +
          `<span class="rtitle">${esc(title)}</span>` +
          `<span class="rsub">${esc(nowWords(one) || writtenDate(first))} · ` +
          `${esc(one.item.pairing_confidence ?? Confidence.Unsure)}</span></button>`
        );
      })
      .join("");
    this.sheet.show(rows);
  }

  private async join(otherId: number): Promise<void> {
    const pairing = this.pairing()!;
    const other = this.pairings.find((one) => one.item.id === otherId)!;
    const moving = this.picked(pairing);
    tap(Feature.PairingJoin);
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
