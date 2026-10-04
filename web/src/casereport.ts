import * as api from "./api";
import "./casereport.css";
import { PicEvent, REST, SelKind, reduce } from "./caption";
import { cards, dashboard, familyIcon, passages, rail } from "./case";
import { Card, caseView } from "./caseview";
import { chipOf } from "./chips";
import { BACK } from "./tokens";
import { CLUSTER, esc, flash, slideOver } from "./dom";
import { Drawer } from "./drawer";
import { Lens } from "./lens";
import { Sheet } from "./sheet";
import { untold } from "./snapshots";
import type { Opened, Part, View } from "./store";
import { ChipKind, ChipTone, InteractionKind, ItemKind, type Chip, type Passages, type Timeline } from "./types";
import { Feature } from "./track";
import { AWAY_PX, fold, type Fold } from "./viewport";

/** The case report screen: the cards drawn from the store's open diagram
 * (doc/UI_STANDARDS.md), the chat screen's own timeline pinned over them
 * (R-0696, R-0711), the strip of cards that glides to the card tapped
 * (R-0702), the family picture in the column on a wide window and behind the
 * family button on the phone (R-0697), and each card's book of passages
 * (R-0691). A record the report cannot be drawn from says why on the screen
 * and in the console, never a blank page. */

export interface CaseHooks {
  /** A tap recorded against the item it touched (R-0065). */
  record(kind: InteractionKind, item: ItemKind, id: string | null): void;
  track(feature: Feature): void;
  /** Whether the window is wide enough for the family to stand beside the cards. */
  wide(): boolean;
  /** Read something about the open diagram, dropped if another is opened meanwhile. */
  fetch<T>(ask: (id: number | null, signal: AbortSignal) => Promise<T>): Promise<T | null>;
}

/** As long as the longest glide to a jump's target may take (dom.ts). */
const GLIDE_MS = 2000;

const q = (root: HTMLElement, id: string): HTMLElement => {
  const found = root.querySelector<HTMLElement>(`#${id}`);
  if (!found) throw new Error(`the case report screen has no #${id}`);
  return found;
};

export class CaseReport implements View {
  private readonly lens: Lens;
  private readonly drawer: Drawer;
  private readonly sheet: Sheet;
  /** The chat's own fold of the timeline (R-0696): a strip while the cards are read, the full line at their top or on a chip's tap. */
  private readonly strip: Fold;
  /** Where the cards stood when a tap opened the line. */
  private openedAt: number | null = null;
  private readonly body: HTMLElement;
  private readonly rail: HTMLElement;
  private readonly column: HTMLElement;
  private readonly famout: HTMLElement;
  private opened: Opened | null = null;
  /** Drawn from the record the store last gave, or to be drawn when shown. */
  private stale = true;
  private passages: Passages | null = null;
  /** The card a strip tap asked for, lit while the cards glide to it and while they rest at their foot. */
  private asked: Card | null = null;
  private gliding = false;
  /** The cluster whose play-by-play is up. */
  private playing: string | null = null;

  constructor(
    private readonly root: HTMLElement,
    private readonly hooks: CaseHooks,
  ) {
    this.body = q(root, "case-body");
    this.rail = q(root, "case-rail");
    this.column = q(root, "case-column");
    this.famout = q(root, "case-famout");
    q(root, "case-family").innerHTML = familyIcon(22);
    root.querySelectorAll<HTMLElement>(".backbtn").forEach((b) => (b.innerHTML = BACK));
    const timeline = (): Timeline => this.opened!.record;
    this.lens = new Lens(
      { view: q(root, "case-view"), caption: q(root, "case-caption"), path: q(root, "case-path"), info: q(root, "case-info") },
      {
        timeline,
        record: hooks.record,
        track: hooks.track,
        // the case report has no editor, no thread and no message box
        edit: () => {},
        trace: () => null,
        insert: () => {},
        explain: (id) => this.explain(id),
        list: null,
      },
    );
    this.drawer = new Drawer(
      q(root, "case-pbp"),
      (step, events) => {
        this.drawer.close();
        if (step) this.lens.picture.open(events);
        else this.lens.picture.back(0);
        this.lens.rest();
      },
      (chip) => this.chip(chip),
    );
    this.sheet = new Sheet(root, "bk");
    // the about page slides back out at its full height before the line folds, as on the chat screen
    this.strip = fold(null, root, () => {}, () => {
      if (this.lens.picture.aboutOpen()) this.lens.climb(CLUSTER);
      return this.lens.picture.settled;
    });
    // a tap on the folded strip opens it, and the cards moving as it opens fold nothing
    root.querySelector(":scope > .pic")!.addEventListener("pointerdown", () => {
      if (root.classList.contains("folded")) this.openedAt = this.body.scrollTop;
    });
    root.addEventListener("click", (e) => this.tap(e));
    this.body.addEventListener(
      "scroll",
      () => {
        this.follow();
        const at = this.body.scrollTop;
        // the line opened by a tap stays open until the reader scrolls on by
        // hand; the cards moving as it opens is not that
        if (this.openedAt !== null && Math.abs(at - this.openedAt) <= AWAY_PX) return;
        this.openedAt = null;
        this.strip.scrolled(at <= 0, at > AWAY_PX);
      },
      { passive: true },
    );
  }

  reset(): void {
    this.opened = null;
    this.passages = null;
    this.stale = true;
    this.drawer.close();
    this.lens.picture.clear();
    this.lens.state = REST;
    this.body.replaceChildren();
    this.rail.replaceChildren();
  }

  draw(opened: Opened, _parts: Part[]): void {
    this.opened = opened;
    this.stale = true;
    if (!this.root.hidden) this.render();
  }

  /** The window crossed the width where the family stands beside the cards. */
  refit(): void {
    this.stale = true;
    if (!this.root.hidden) this.render();
  }

  /** On screen: drawn from the record as it stands now. */
  show(): void {
    if (this.stale) this.render();
  }

  private render(): void {
    const opened = this.opened;
    if (!opened) return;
    this.stale = false;
    this.drawer.close();
    const wide = this.hooks.wide();
    q(this.root, "case-family").hidden = wide;
    this.column.hidden = !wide;
    let v;
    try {
      v = caseView(opened.record, opened.sittings, opened.diagram?.owner_name ?? null);
    } catch (error) {
      console.error(error);
      this.body.innerHTML = `<p class="fault">The case report cannot be drawn from this record: ${esc((error as Error).message)}</p>`;
      this.rail.replaceChildren();
      return;
    }
    q(this.root, "case-title").textContent = `${v.name} · Case report`;
    q(this.root, "case-by").textContent = v.owner ? `presented by ${v.owner}` : "";
    this.body.innerHTML = cards(v, wide);
    this.rail.innerHTML = rail(v);
    const dash = dashboard(v);
    q(this.root, "case-dash").innerHTML = wide ? dash : "";
    q(this.root, "case-famout-body").innerHTML = wide ? "" : dash;
    this.lens.picture.setData(opened.record);
    this.lens.rest();
    this.follow();
  }

  /** A chip on the report: an event lights on the timeline as in the chat; a
   * person lights that person's events (R-0700); a cluster opens on the
   * timeline the way its pill does, so explain is offered (R-0700). */
  private chip(chip: Chip): void {
    const tl = this.opened!.record;
    // what a chip names is shown on the full line, so a folded line opens first
    this.openedAt = this.body.scrollTop;
    this.strip.open();
    if (chip.kind === ChipKind.Person) {
      const ids = tl.events.filter((e) => e.dateTime && [e.person, e.child, e.spouse].includes(Number(chip.target))).map((e) => e.id);
      if (ids.length) this.lens.apply(reduce(REST, PicEvent.Tap, { kind: SelKind.Event, id: String(ids[0]) }), ids);
      return;
    }
    if (chip.kind === ChipKind.Cluster) {
      const cluster = tl.clusters.find((c) => c.id === chip.target);
      if (!cluster) return;
      this.lens.picture.open(cluster.event_ids);
      this.lens.picture.spotlight(cluster.event_ids);
      // opening a cluster is a look at it, recorded like any other (R-0065)
      this.hooks.record(InteractionKind.Look, ItemKind.Cluster, cluster.id);
      this.lens.rest();
      return;
    }
    this.lens.aim(chip);
  }

  /** The cluster told in the play-by-play drawer: the record's own dated
   * events, one picture per date, nothing said for it (R-0570). */
  private explain(clusterId: string): void {
    const tl = this.opened!.record;
    const cluster = tl.clusters.find((c) => c.id === clusterId);
    if (!cluster) return;
    const told = untold(tl, cluster.event_ids);
    if (told.snapshots.length) {
      this.drawer.open(tl, { ...told, cluster_id: cluster.id }, null);
      this.playing = cluster.id;
    }
    this.lens.rest();
  }

  /** The strip lights the card at the top of the cards; at the foot of the
   * cards, where the last cards cannot reach the top, the card asked for. */
  private follow(): void {
    const b = this.body;
    const end = b.scrollTop + b.clientHeight >= b.scrollHeight - 2;
    if (!end && !this.gliding) this.asked = null;
    const top = b.getBoundingClientRect().top + 12;
    let lit: string | null = null;
    b.querySelectorAll<HTMLElement>(".level[data-card]").forEach((l) => {
      if (lit === null || l.getBoundingClientRect().top <= top) lit = l.dataset.card!;
    });
    if (this.asked) lit = this.asked;
    this.rail.querySelectorAll<HTMLElement>("[data-jump]").forEach((b) => b.classList.toggle("on", b.dataset.jump === lit));
  }

  /** To a card: the cards glide to it and it is ringed, the app's own light
   * for what a jump points at (Patrick, 2026-10-03: a strip tap animates the
   * scroll). The family on a wide window is in the column; on the phone the
   * family button's picture slides out. */
  private jump(card: Card): void {
    this.drawer.close();
    const at = this.body.querySelector<HTMLElement>(`.level[data-card="${card}"]`);
    if (card === Card.Family && this.hooks.wide()) {
      const pinned = this.column.querySelector<HTMLElement>(".level");
      if (pinned) flash(pinned, true);
      return;
    }
    if (card === Card.Family) {
      slideOver(this.famout, true);
      return;
    }
    if (!at) return;
    this.asked = card;
    // the glide passes other cards on its way; the one asked for stays lit
    this.gliding = true;
    window.setTimeout(() => (this.gliding = false), GLIDE_MS);
    flash(at, true);
    this.follow();
  }

  private async book(button: HTMLElement): Promise<void> {
    this.passages ??= await this.hooks.fetch(api.casePassages);
    if (!this.passages) return;
    this.sheet.show(passages(this.passages, button.dataset.book!, button.dataset.title!));
  }

  private tap(e: Event): void {
    this.act(e.target as HTMLElement);
    // another cluster opened while a play-by-play is up closes it (Patrick, 2026-10-03)
    if (this.playing !== null && this.lens.picture.openCluster()?.id !== this.playing) {
      this.drawer.close();
      this.playing = null;
    }
  }

  private act(el: HTMLElement): void {
    const hit = (sel: string) => el.closest<HTMLElement>(sel);
    if (hit(".fs-sheet.bk .cardx, .fs-scrim.bk")) return this.sheet.lower();
    const book = hit(".book[data-book]");
    if (book) return void this.book(book);
    const all = hit(".who.lall[data-target]");
    if (all) return this.chip({ kind: ChipKind.Event, target: all.dataset.target!, label: "Coach", tone: ChipTone.Data, bare: false });
    const jump = hit("[data-jump]");
    if (jump) return this.jump(jump.dataset.jump as Card);
    if (hit("#case-family, .famcard")) return slideOver(this.famout, true);
    if (hit("#case-famout-close")) return slideOver(this.famout, false);
    const chip = hit("button.chip[data-kind]");
    if (chip && !hit("#case-pbp")) {
      if (hit("#case-famout")) slideOver(this.famout, false);
      this.chip(chipOf(chip));
    }
  }
}
