import { ChipKind, InteractionKind, ItemKind } from "./types";
import { token } from "./chips";

/** Two taps on the picture (R-0073). The first tap looks: a caption appears and
 * nothing enters the chat. The second tap is the caption's one amber chip, and
 * that speaks. Tapping the open cluster again closes it; tapping another moves
 * the caption. Every tap is recorded against the item it touched, including the
 * looks that send nothing. */

export enum PicEvent {
  TapCluster = "tap_cluster",
  TapChip = "tap_chip",
  TapPlay = "tap_play",
  Dismiss = "dismiss",
}

export interface PicState {
  open: string | null;
  playing: string | null;
}

export interface Record_ {
  kind: InteractionKind;
  item_kind: ItemKind;
  item_id: string;
}

export interface Outcome {
  state: PicState;
  insert: string | null;
  play: string | null;
  record: Record_ | null;
}

export const REST: PicState = { open: null, playing: null };

export function reduce(state: PicState, event: PicEvent, id?: string): Outcome {
  const still = { state, insert: null, play: null, record: null };
  switch (event) {
    case PicEvent.TapCluster: {
      if (!id) return still;
      const open = state.open === id ? null : id;
      return {
        state: { open, playing: null },
        insert: null,
        play: null,
        record: open
          ? { kind: InteractionKind.Look, item_kind: ItemKind.Cluster, item_id: id }
          : null,
      };
    }
    case PicEvent.TapChip: {
      const target = id ?? state.open;
      if (!target) return still;
      return {
        state: { open: null, playing: null },
        insert: token(ChipKind.Cluster, target),
        play: null,
        record: {
          kind: InteractionKind.Say,
          item_kind: ItemKind.Cluster,
          item_id: target,
        },
      };
    }
    case PicEvent.TapPlay: {
      const target = id ?? state.open;
      if (!target) return still;
      return {
        state: { open: target, playing: target },
        insert: null,
        play: target,
        record: {
          kind: InteractionKind.Play,
          item_kind: ItemKind.Cluster,
          item_id: target,
        },
      };
    }
    case PicEvent.Dismiss:
      return { state: REST, insert: null, play: null, record: null };
  }
}
