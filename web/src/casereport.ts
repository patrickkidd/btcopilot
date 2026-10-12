import * as api from "./api";
import "./casereport.css";
import { PicEvent, REST, SelKind, reduce } from "./caption";
import { Books } from "./books";
import { cards, dashboard, familyIcon, rail } from "./case";
import { Card, caseView } from "./caseview";
import { aimedEvents, chipOf } from "./chips";
import { BACK } from "./tokens";
import { CLUSTER, esc, flash, slideOver } from "./dom";
import { Drawer, frameOn } from "./drawer";
import { Lens } from "./lens";
import { ask, dismiss, dismissed, phase, Phase, REWRITING } from "./outdated";
import { Sheet } from "./sheet";
import { untold } from "./snapshots";
import type { Opened, Part, View } from "./store";
import { ChipKind, ChipTone, InteractionKind, ItemKind, RewriteState, type Chip, type Rewrite, type Timeline } from "./types";
import { Feature } from "./track";
import { toast } from "./toast";
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
  fetch<T>(ask: (key: string | null, signal: AbortSignal) => Promise<T>): Promise<T | null>;
  /** Read the open diagram's record again, which redraws the report. */
  reload(): Promise<boolean>;
}

/** As long as the longest glide to a jump's target may take (dom.ts). */
const GLIDE_MS = 2000;
/** How often the rewrite is asked whether the coach has finished, as the chat's vote asks of shadow replies. */
const POLL_MS = 2000;
/** The cards the coach writes; the rest are drawn from the diagram each time and never go out of date. */
const WRITTEN = new Set<Card>([Card.Main, Card.Guesses, Card.OwnPart, Card.Choice, Card.WorkOn]);

const q = (root: HTMLElement, id: string): HTMLElement => {
  const found = root.querySelector<HTMLElement>(`#${id}`);
  if (!found) throw new Error(`the case report screen has no #${id}`);
  return found;
};

export class CaseReport implements View {
  private readonly lens: Lens;
  private readonly drawer: Drawer;
  private readonly books: Books;
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
  /** The card a strip tap asked for, lit while the cards glide to it and while they rest at their foot. */
  private asked: Card | null = null;
  private gliding = false;
  /** The cluster whose play-by-play is up. */
  private playing: string | null = null;
  /** The question on opening a report that is out of date; the scrim does not put it away. */
  private readonly sheet: Sheet;
  /** The diagrams whose report the coach is rewriting now. */
  private readonly rewriting = new Set<number>();
  /** Per diagram, the change "Refresh the report" was tapped for this time the app is open, so a failed rewrite does not ask again at once. */
  private readonly refreshed = new Map<number, number>();

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
    this.books = new Books(root, () => this.hooks.fetch(api.casePassages));
    this.drawer = new Drawer(
      q(root, "case-pbp"),
      (step, events) => {
        this.drawer.close();
        if (step) this.lens.picture.open(events);
        else this.lens.picture.back(0);
        this.lens.rest();
      },
      (chip) => this.chip(chip),
      this.books,
    );
    // the about page slides back out at its full height before the line folds, as on the chat screen
    this.strip = fold(null, root, () => {}, () => {
      if (this.lens.picture.aboutOpen()) this.lens.climb(CLUSTER);
      return this.lens.picture.settled;
    });
    // a tap on the folded strip opens it, and the cards moving as it opens fold nothing
    root.querySelector(":scope > .pic")!.addEventListener("pointerdown", () => {
      if (root.classList.contains("folded")) this.openedAt = this.body.scrollTop;
    });
    this.sheet = new Sheet(root, "rc");
    this.sheet.panel.addEventListener("click", (e) => this.answer(e.target as HTMLElement));
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
    this.sheet.lower();
    this.books.forget();
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
    // asked for early so a book opens at once; a failure shows at the book's tap
    this.books.ask().catch(() => {});
    this.drawer.close();
    const wide = this.hooks.wide();
    q(this.root, "case-family").hidden = wide;
    this.column.hidden = !wide;
    let v;
    try {
      v = caseView(opened.record, opened.sittings, opened.diagram?.owner_name ?? null);
    } catch (error) {
      console.error(error);
      this.body.innerHTML = `<p class="fault">The case report cannot be drawn from this diagram: ${esc((error as Error).message)}</p>`;
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
    this.onYou(this.root);
    this.lens.picture.setData(opened.record);
    this.lens.rest();
    this.mark();
    this.follow();
  }

  /** The grey line at the top of the cards, the coach's cards dimmed while it
   * rewrites them, and the sheet that asks on opening a report out of date. */
  private mark(): void {
    const opened = this.opened!;
    const out = opened.record.report_out_of_date ?? null;
    const id = opened.diagram?.id ?? null;
    const shown = id === null ? [] : [dismissed(id), this.refreshed.get(id) ?? null].filter((n): n is number => n !== null);
    const now = phase(out, shown.length ? Math.max(...shown) : null, id !== null && this.rewriting.has(id));
    this.body.querySelectorAll<HTMLElement>(".level[data-card]").forEach((l) =>
      l.classList.toggle("dim", now === Phase.Rewriting && WRITTEN.has(l.dataset.card as Card)),
    );
    if (now === Phase.Current) return;
    const line = document.createElement("button");
    line.type = "button";
    line.className = "aged";
    line.disabled = now === Phase.Rewriting;
    line.textContent = now === Phase.Rewriting ? REWRITING : out!.sentence;
    this.body.querySelector(".case")?.prepend(line);
    if (now === Phase.Asking) this.sheet.show(ask(out!.sentence, esc));
  }

  /** The sheet's two answers: the coach rewrites its cards, or the report
   * is read as it was, and this device does not ask again for this change. */
  private answer(el: HTMLElement): void {
    const act = el.closest<HTMLElement>("[data-act]")?.dataset.act;
    const out = this.opened?.record.report_out_of_date;
    if (!act || !out) return;
    this.sheet.lower();
    const id = this.opened!.diagram!.id;
    if (act === "refresh") {
      this.refreshed.set(id, out.change_id);
      void this.rewrite(id);
      return;
    }
    dismiss(id, out.change_id);
    this.render();
  }

  /** The coach rewrites its five cards (R-0825); the report is read again
   * when it is done. One the server will not start now (already running, or
   * no session yet) says so; a failed one, or one the server no longer knows,
   * says so and puts the cards back as they were. Kept per diagram, so
   * another family opened meanwhile is neither dimmed nor reloaded. */
  private async rewrite(id: number): Promise<void> {
    let job: Rewrite | null;
    try {
      job = await this.hooks.fetch(api.rewriteReport);
    } catch (error) {
      if (!(error instanceof api.Failed) || error.status !== 409) throw error;
      toast("The report is already being rewritten, or this family has no session yet");
      return;
    }
    this.rewriting.add(id);
    this.render();
    try {
      while (job?.state === RewriteState.Running) {
        await new Promise((done) => window.setTimeout(done, POLL_MS));
        job = await api.reportRewrite(job.id).catch((error: unknown) => {
          if (error instanceof api.Failed && error.status === 404) return { id: job!.id, state: RewriteState.Failed };
          throw error;
        });
      }
      if (job?.state === RewriteState.Failed) throw new Error(`the coach could not rewrite the case report, rewrite ${job.id}`);
    } catch (error) {
      toast("The coach could not rewrite the report. Try again.");
      throw error;
    } finally {
      this.rewriting.delete(id);
      this.render();
    }
    // a family opened since the tap is not the one rewritten
    if (this.opened?.diagram?.id === id) await this.hooks.reload();
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
    // a chip naming a cluster, or events inside one, opens that cluster the
    // way a tap on it on the timeline does, so explain is offered (R-0700),
    // and lights what it names there
    const ids = aimedEvents(chip, tl.clusters);
    const cluster = ids.length ? tl.clusters.find((c) => ids.every((id) => c.event_ids.includes(id))) : undefined;
    if (cluster) {
      this.lens.openCluster(cluster);
      this.lens.picture.spotlight(ids);
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
    if (card === Card.Family) return this.family();
    if (!at) return;
    this.asked = card;
    // the glide passes other cards on its way; the one asked for stays lit
    this.gliding = true;
    window.setTimeout(() => (this.gliding = false), GLIDE_MS);
    flash(at, true);
    this.follow();
  }

  /** The family slid out on the phone, its pictures on the record's own person. */
  private family(): void {
    slideOver(this.famout, true);
    this.onYou(this.famout);
  }

  /** Each picture wider than its frame opens on the record's own person and
   * their words, as the Family drawer opens on its step's person (R-0759). */
  private onYou(within: HTMLElement): void {
    within.querySelectorAll<HTMLElement>(".fam[data-who]").forEach((f) => frameOn(f, [f.dataset.who!], f.dataset.who!, false));
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
    if (this.books.tap(el)) return;
    const out = this.opened?.record.report_out_of_date;
    if (hit("button.aged") && out) return this.sheet.show(ask(out.sentence, esc));
    const all = hit(".who.lall[data-target]");
    if (all) return this.chip({ kind: ChipKind.Event, target: all.dataset.target!, label: "Coach", tone: ChipTone.Data, bare: false });
    const jump = hit("[data-jump]");
    if (jump) return this.jump(jump.dataset.jump as Card);
    if (hit("#case-family, .famcard")) return this.family();
    if (hit("#case-famout-close")) return slideOver(this.famout, false);
    const chip = hit("button.chip[data-kind]");
    if (chip && !hit("#case-pbp")) {
      if (hit("#case-famout")) slideOver(this.famout, false);
      this.chip(chipOf(chip));
    }
  }
}
