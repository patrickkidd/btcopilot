import { CHIP_KIND, PicEvent, REST, SelKind, reduce, type Outcome, type PicState, type Sel } from "./caption";
import { aimedEvents, Lead } from "./chips";
import { CLUSTER, pathRow } from "./dom";
import { Picture, Target, Via, type Tap } from "./picture";
import { ASK_MARK, FAMILY_MARK, IN_CHAT_MARK, listButton, PLAY_MARK, tok } from "./tokens";
import { Feature } from "./track";
import { ChipKind, ChipTone, InteractionKind, ItemKind, Spotlight, type Chip, type Cluster, type Timeline } from "./types";

/** The picture and the row under it, as one controller: a tap on the line, a
 * chip in the words, the path over the line and the (i) all come through here
 * and leave one selection (caption.ts). The chat screen (main.ts) and the case
 * page (casepage.ts) each stand one up. What a tap leads to beyond the picture
 * (the editor, the thread, the list, the coach) is given by the screen through
 * the hooks, so a read-only page can leave it undone. */

export interface LensHosts {
  view: HTMLElement;
  caption: HTMLElement;
  path: HTMLElement;
  info: HTMLElement;
}

export interface LensHooks {
  /** The record as it stands. */
  timeline(): Timeline;
  /** A tap recorded against the item it touched (R-0065). */
  record(kind: InteractionKind, item: ItemKind, id: string | null): void;
  /** A feature's tap counted. */
  track(feature: Feature): void;
  /** The words of the picked event inside an open cluster: the event's own editor. */
  edit(eventId: number): void;
  /** Where an event was coded and the way to those words; null when nowhere. */
  trace(eventId: number): (() => void) | null;
  /** A chip put into the message box. */
  insert(chip: Chip, lead: Lead): void;
  /** The cluster on screen told. */
  explain(clusterId: string): void;
  /** The list glyph at the end of the row: whether to draw it, and what it
   * opens. Null where there is no list to open. */
  list: { shown(): boolean; open(): void } | null;
  /** The Family button beside the list, whatever is open: whether the record has a
   * dated step to show, and what it opens (R-0742). Absent where there is none. */
  family?: { live(): boolean; open(): void };
  /** After every redraw of the row, for whatever follows the picture (the address bar). */
  changed?(): void;
  /** Before a chip aims the picture, for whatever must show it first (the folded picture). */
  aiming?(): void;
  /** A tap on the book button of the page behind a cluster's i: the screen's
   * books raise the passages behind what a cluster is (R-0691). Absent on a
   * screen with no books. */
  book?(button: HTMLElement): void;
}

// Hidden for now (Patrick, 2026-09-29: "the design is too busy and I'm not sure what value that brings yet").
const ASK_SHOWN = false;

export class Lens {
  readonly picture: Picture;
  /** What is picked on the picture, and what is playing. */
  state: PicState = REST;

  constructor(
    private readonly hosts: LensHosts,
    private readonly hooks: LensHooks,
    spot: Spotlight = Spotlight.Unified,
  ) {
    this.picture = new Picture(
      hosts.view,
      { onTap: (tap: Tap) => this.onTap(tap), onBook: (button) => hooks.book?.(button) },
      spot,
    );
    hosts.path.addEventListener("click", (e) => {
      const step = (e.target as Element).closest<HTMLElement>("[data-step]");
      if (step) this.climb(Number(step.dataset.step));
    });
    hosts.info.addEventListener("click", () => {
      hooks.track(Feature.PictureInfo);
      this.picture.about();
      this.rest();
    });
  }

  /** Nothing picked: the row says what the picture shows. */
  rest(): void {
    this.state = REST;
    this.actions();
  }

  /** A tap on the wire steps through the events under the thumb; a tap on the
   * words picks the one whose row was tapped; a tap on the shelf asks about what
   * has no date. */
  private onTap(tap: Tap): void {
    const picture = this.picture;
    // Empty ground on the picture puts it down: nothing selected, nothing named,
    // the whole line at a glance again.
    if (tap.target === Target.Ground) {
      this.putDown();
      return;
    }
    if (tap.target === Target.Close) {
      this.climb(CLUSTER);
      return;
    }
    if (tap.target === Target.Shelf) {
      this.apply(reduce(this.state, PicEvent.Tap, { kind: SelKind.Shelf, id: "shelf" }));
      return;
    }
    // At rest the picture shows the whole line; a tap opens one cluster, which
    // is the one level change the reader makes for themselves.
    if (tap.target === Target.Cluster) {
      const cluster = picture.clusterAt(tap.index);
      if (cluster) this.openCluster(cluster);
      else this.rest();
      return;
    }
    // A label names one event: tapping it picks that event, and where a zone
    // holds several the tap steps to the next of them.
    const selected = picture.selection();
    const chosen = tap.target === Target.Zone ? picture.next(tap.index, selected) : picture.rowAt(tap.x, tap.y);
    // blank ground inside the label band: the same as blank wire
    if (tap.target === Target.Band && chosen === null) {
      this.putDown();
      return;
    }
    // The words of the event already picked are the way to where it came from,
    // and which way depends on what the picture is showing. Only the words do
    // this: a dot picks and never travels, and a label naming some other event
    // picks that one.
    const words = tap.target === Target.Band && chosen === selected && selected !== null;
    // inside one cluster: the event's own editor
    if (words && picture.opened()) {
      this.hooks.edit(selected as number);
      return;
    }
    // on a line of events that belong to no cluster: where it was said
    if (words) {
      this.hooks.trace(selected as number)?.();
      return;
    }
    this.apply(reduce(this.state, PicEvent.Tap, chosen === null ? undefined : { kind: SelKind.Event, id: String(chosen) }));
  }

  /** The coach pointing: the events its words name become the spotlight, and
   * everything else on the wire recedes. A chip never changes the picture's
   * height, so nothing below it moves (the owner: chat bubbles must never move
   * from a tap on a chip). */
  aim(chip: Chip): void {
    const { clusters } = this.hooks.timeline();
    const ids = aimedEvents(chip, clusters);
    if (!ids.length) return;
    this.hooks.aiming?.();
    // A chip in the coach's words does exactly what a tap on the picture does:
    // there is one selection, wherever the reader touched it. A chip naming an
    // event selects that event, opening the cluster it belongs to (Patrick,
    // 2026-10-01); a chip naming a cluster selects the cluster (R-0543).
    if (chip.kind === ChipKind.Event) {
      this.apply(reduce(REST, PicEvent.Tap, { kind: SelKind.Event, id: String(ids[0]) }), ids);
      return;
    }
    const cluster = clusters.find((c) => ids.every((id) => c.event_ids.includes(id)));
    if (!cluster) return;
    this.apply(reduce(REST, PicEvent.Tap, { kind: SelKind.Cluster, id: cluster.id }));
    // a chip may name a cluster off screen, so the line goes to it
    this.picture.spotlight(cluster.event_ids);
  }

  /** A cluster opened, from its pill or from a chip that names it: the one
   * selection both paths share, so the row offers the same explain. */
  openCluster(cluster: Cluster): void {
    this.picture.open(cluster.event_ids);
    // opening a cluster is a look at it, recorded like any other (R-0065)
    this.hooks.record(InteractionKind.Look, ItemKind.Cluster, cluster.id);
    this.rest();
  }

  /** One place turns a picture tap into its consequences: what the picture shows,
   * what goes in the composer, what gets recorded, what plays. `named` is what a
   * chip named, when the tap was on a chip rather than the picture. */
  apply(outcome: Outcome, named: number[] | null = null): void {
    this.state = outcome.state;
    const sel = this.state.sel;
    if (sel?.kind === SelKind.Event) this.picture.pick(Number(sel.id), named ?? [Number(sel.id)], named ? Via.Chip : Via.Dot);
    else this.picture.select(null);
    if (sel?.kind === SelKind.Cluster) {
      const cluster = this.hooks.timeline().clusters.find((c) => c.id === sel.id);
      if (cluster) this.picture.open(cluster.event_ids);
    }
    this.actions();
    if (outcome.record) this.hooks.record(outcome.record.kind, outcome.record.item_kind, outcome.record.item_id);
    if (outcome.insert)
      this.hooks.insert(
        {
          kind: CHIP_KIND[outcome.insert.kind],
          target: outcome.insert.id,
          label: this.selLabel(outcome.insert),
          tone: ChipTone.Data,
          bare: false,
        },
        Lead.Ask,
      );
    if (outcome.play) this.hooks.explain(outcome.play);
  }

  private selLabel(sel: Sel): string {
    const timeline = this.hooks.timeline();
    if (sel.kind === SelKind.Event) return timeline.events.find((e) => String(e.id) === sel.id)?.label ?? "this event";
    if (sel.kind === SelKind.Cluster) return timeline.clusters.find((c) => c.id === sel.id)?.title ?? "this cluster";
    const n = timeline.shelf.length;
    return n ? `${n} thing${n === 1 ? "" : "s"} with no date yet` : "what has no date";
  }

  /** The cluster on screen told: the row's explain, which opens the
   * play-by-play drawer straight away (R-0542, R-0570). */
  play(clusterId: string): void {
    this.apply(reduce(this.state, PicEvent.TapPlay, { kind: SelKind.Cluster, id: clusterId }));
  }

  /** The row under the picture: what it is showing, and the things a tap can do
   * about it. The words themselves live on the picture (converged mockup). */
  actions(): void {
    this.crumb();
    this.hooks.changed?.();
    const host = this.hosts.caption;
    const picture = this.picture;
    const sel = this.state.sel;
    const open = picture.openCluster();
    // the Family button is on the row whatever is open or picked; a record with
    // no dated step has none at all
    const family = this.hooks.family?.live() ? this.hooks.family : null;
    const tail = (family ? tok("cap-family", "g", FAMILY_MARK, "Family", true) : "") + (this.hooks.list?.shown() ? listButton("menu-open") : "");
    // Nothing open and nothing picked: there is nothing to act on, so the row
    // says what a tap will do instead.
    if (!sel && !open) {
      // the about page is words already, and an empty picture has nothing to
      // tap; no hint under either
      const hint = picture.aboutOpen() || picture.empty() ? "" : "tap a cluster";
      host.innerHTML = `<span class="cta">${hint}</span>` + tail;
      this.wireList();
      return;
    }

    // One cluster open: ask about it, or have it explained. Picked an event
    // inside it: ask about that, or go to where it was said.
    const event = sel?.kind === SelKind.Event ? Number(sel.id) : null;
    const trace = event === null ? null : this.hooks.trace(event);
    const moves = !sel && open ? picture.countDated(open.event_ids) : 0;

    host.innerHTML =
      (ASK_SHOWN ? tok("cap-chip", "", ASK_MARK, "ask", true) : "") +
      tok("cap-play", "g", PLAY_MARK, "explain", moves > 0) +
      tok("cap-trace", "data", IN_CHAT_MARK, "in chat", !!trace) +
      tail;

    const at = (id: string) => host.querySelector<HTMLElement>(`#${id}`);
    if (ASK_SHOWN)
      at("cap-chip")?.addEventListener("click", () =>
        this.apply(
          sel
            ? reduce(this.state, PicEvent.TapChip)
            : reduce(this.state, PicEvent.TapChip, {
                kind: SelKind.Cluster,
                id: (open as Cluster).id,
              }),
        ),
      );
    if (trace)
      at("cap-trace")?.addEventListener("click", () => {
        this.hooks.track(Feature.TraceToChat);
        trace();
      });
    if (moves && open) at("cap-play")?.addEventListener("click", () => this.play(open.id));
    this.wireList();
  }

  private wireList(): void {
    const family = this.hooks.family;
    if (family) this.hosts.caption.querySelector<HTMLElement>("#cap-family")?.addEventListener("click", () => family.open());
    // on the wide layout the drawer is pinned open and no button is drawn (R-0352)
    const list = this.hooks.list;
    if (!list?.shown()) return;
    this.hosts.caption.querySelector<HTMLElement>("#menu-open")?.addEventListener("click", () => list.open());
  }

  /** The path over the line: where the reader is, from the whole timeline
   * down, each earlier step the way back to it (R-0540). */
  crumb(): void {
    this.hosts.path.innerHTML = pathRow(this.picture.path(), this.picture.picked());
    this.hosts.info.hidden = !this.picture.opened();
  }

  /** Empty ground on the picture puts it down: the whole line at a glance. */
  putDown(): void {
    this.picture.dismiss();
    this.rest();
  }

  /** Back up to one step of the path: the path's own steps, and the about
   * page's close button, which goes where the cluster's step goes. */
  climb(step: number): void {
    this.hooks.track(Feature.PictureUp);
    this.picture.back(step);
    this.rest();
  }
}
