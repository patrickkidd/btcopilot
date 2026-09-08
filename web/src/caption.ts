import { ChipKind, InteractionKind, ItemKind } from "./types";
import { token } from "./chips";

/** Two taps on the picture (R-0073). The first tap looks: a caption appears and
 * nothing enters the chat. The second tap is the caption's one amber chip, and
 * that speaks. Tapping the same mark again closes it; tapping another moves the
 * caption. Every tap is recorded against the item it touched, including the
 * looks that send nothing. */

export enum PicEvent {
  Tap = "tap",
  TapChip = "tap_chip",
  TapPlay = "tap_play",
  Dismiss = "dismiss",
}

/** What the caption is about. A stretch can be played; a moment, a question and
 * the undated shelf can only be asked about. */
export enum SelKind {
  Cluster = "cluster",
  Event = "event",
  Count = "count",
  Question = "question",
  Shelf = "shelf",
}

export interface Sel {
  kind: SelKind;
  /** The stretch's id, or the comma-joined event ids a mark stands for. */
  id: string;
}

export interface PicState {
  sel: Sel | null;
  playing: string | null;
}

export interface Record_ {
  kind: InteractionKind;
  item_kind: ItemKind;
  item_id: string;
}

export interface Outcome {
  state: PicState;
  insert: Sel | null;
  play: string | null;
  record: Record_ | null;
}

export const REST: PicState = { sel: null, playing: null };

const ITEM: Record<SelKind, ItemKind> = {
  [SelKind.Cluster]: ItemKind.Cluster,
  [SelKind.Event]: ItemKind.Event,
  [SelKind.Count]: ItemKind.Event,
  [SelKind.Question]: ItemKind.Event,
  [SelKind.Shelf]: ItemKind.Diagram,
};

export const CHIP_KIND: Record<SelKind, ChipKind> = {
  [SelKind.Cluster]: ChipKind.Cluster,
  [SelKind.Event]: ChipKind.Event,
  [SelKind.Count]: ChipKind.Event,
  [SelKind.Question]: ChipKind.Event,
  [SelKind.Shelf]: ChipKind.Event,
};

export const playable = (sel: Sel | null): boolean =>
  sel?.kind === SelKind.Cluster;

const same = (a: Sel | null, b: Sel) => a?.kind === b.kind && a.id === b.id;

export function reduce(state: PicState, event: PicEvent, sel?: Sel): Outcome {
  const still = { state, insert: null, play: null, record: null };
  switch (event) {
    case PicEvent.Tap: {
      if (!sel) return still;
      const open = same(state.sel, sel) ? null : sel;
      return {
        state: { sel: open, playing: null },
        insert: null,
        play: null,
        record: open
          ? {
              kind: InteractionKind.Look,
              item_kind: ITEM[sel.kind],
              item_id: sel.id,
            }
          : null,
      };
    }
    case PicEvent.TapChip: {
      const target = sel ?? state.sel;
      if (!target) return still;
      return {
        state: { sel: null, playing: null },
        insert: target,
        play: null,
        record: {
          kind: InteractionKind.Say,
          item_kind: ITEM[target.kind],
          item_id: target.id,
        },
      };
    }
    case PicEvent.TapPlay: {
      const target = sel ?? state.sel;
      if (!playable(target)) return still;
      const cluster = target as Sel;
      return {
        state: { sel: cluster, playing: cluster.id },
        insert: null,
        play: cluster.id,
        record: {
          kind: InteractionKind.Play,
          item_kind: ItemKind.Cluster,
          item_id: cluster.id,
        },
      };
    }
    case PicEvent.Dismiss:
      return { state: REST, insert: null, play: null, record: null };
  }
}

/** The reference a caption's chip drops into the composer. */
export const selToken = (sel: Sel, label: string): string =>
  token(CHIP_KIND[sel.kind], sel.id, label);
