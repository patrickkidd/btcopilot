import { ChipKind, InteractionKind, ItemKind } from "./types";
import { token } from "./chips";

/** Two taps on the picture (R-0073). The first tap looks: the moment writes
 * itself out on the picture and nothing enters the chat. The second tap is the
 * amber chip beside it, and that speaks. Every tap is recorded against the item
 * it touched, including the looks that send nothing. */

export enum PicEvent {
  Tap = "tap",
  TapChip = "tap_chip",
  TapPlay = "tap_play",
  Dismiss = "dismiss",
}

export enum SelKind {
  Event = "event",
  Cluster = "cluster",
  Shelf = "shelf",
}

export interface Sel {
  kind: SelKind;
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
  [SelKind.Event]: ItemKind.Event,
  [SelKind.Cluster]: ItemKind.Cluster,
  [SelKind.Shelf]: ItemKind.Diagram,
};

export const CHIP_KIND: Record<SelKind, ChipKind> = {
  [SelKind.Event]: ChipKind.Event,
  [SelKind.Cluster]: ChipKind.Cluster,
  [SelKind.Shelf]: ChipKind.Event,
};


export function reduce(state: PicState, event: PicEvent, sel?: Sel): Outcome {
  const still = { state, insert: null, play: null, record: null };
  switch (event) {
    case PicEvent.Tap: {
      if (!sel) return { state: REST, insert: null, play: null, record: null };
      // A tap on a moment picks it, and picking the one already picked leaves
      // it picked. Putting the picture down is a tap on the ground beside it,
      // never a second tap on the thing itself.
      return {
        state: { sel, playing: null },
        insert: null,
        play: null,
        record: {
          kind: InteractionKind.Look,
          item_kind: ITEM[sel.kind],
          item_id: sel.id,
        },
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
      if (!target || target.kind !== SelKind.Cluster) return still;
      return {
        state: { sel: target, playing: target.id },
        insert: null,
        play: target.id,
        record: {
          kind: InteractionKind.Play,
          item_kind: ItemKind.Cluster,
          item_id: target.id,
        },
      };
    }
    case PicEvent.Dismiss:
      return { state: REST, insert: null, play: null, record: null };
  }
}

export const selToken = (sel: Sel, label: string): string =>
  token(CHIP_KIND[sel.kind], sel.id, label);
