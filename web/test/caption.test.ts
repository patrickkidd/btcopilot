import { describe, expect, it } from "vitest";
import {
  PicEvent,
  REST,
  SelKind,
  playable,
  reduce,
  selToken,
  type Sel,
} from "../src/caption";
import { InteractionKind, ItemKind } from "../src/types";

const cluster: Sel = { kind: SelKind.Cluster, id: "ch0" };
const other: Sel = { kind: SelKind.Cluster, id: "ch1" };
const moment: Sel = { kind: SelKind.Event, id: "42" };
const shelf: Sel = { kind: SelKind.Shelf, id: "shelf" };

describe("two taps on the picture", () => {
  it("the first tap opens a caption, records a look, and says nothing", () => {
    const out = reduce(REST, PicEvent.Tap, cluster);
    expect(out.state).toEqual({ sel: cluster, playing: null });
    expect(out.insert).toBeNull();
    expect(out.record).toEqual({
      kind: InteractionKind.Look,
      item_kind: ItemKind.Cluster,
      item_id: "ch0",
    });
  });

  it("the second tap is the chip, and it speaks", () => {
    const open = reduce(REST, PicEvent.Tap, cluster).state;
    const out = reduce(open, PicEvent.TapChip);
    expect(out.insert).toEqual(cluster);
    expect(out.record).toEqual({
      kind: InteractionKind.Say,
      item_kind: ItemKind.Cluster,
      item_id: "ch0",
    });
    expect(out.state).toEqual(REST);
  });

  it("tapping the open mark again closes it and records nothing", () => {
    const open = reduce(REST, PicEvent.Tap, cluster).state;
    const out = reduce(open, PicEvent.Tap, cluster);
    expect(out.state).toEqual(REST);
    expect(out.record).toBeNull();
  });

  it("tapping a different mark moves the caption", () => {
    const open = reduce(REST, PicEvent.Tap, cluster).state;
    const out = reduce(open, PicEvent.Tap, other);
    expect(out.state.sel).toEqual(other);
    expect(out.record?.item_id).toBe("ch1");
  });

  it("a moment and a stretch with the same id are different marks", () => {
    const open = reduce(REST, PicEvent.Tap, { kind: SelKind.Event, id: "ch0" }).state;
    const out = reduce(open, PicEvent.Tap, cluster);
    expect(out.state.sel).toEqual(cluster);
  });

  it("a tapped moment records against the event, not the stretch", () => {
    const out = reduce(REST, PicEvent.Tap, moment);
    expect(out.record?.item_kind).toBe(ItemKind.Event);
    expect(selToken(moment, "Sleep got worse")).toBe(
      "[[event:42|Sleep got worse]]",
    );
  });

  it("the undated shelf is recorded against the diagram itself", () => {
    expect(reduce(REST, PicEvent.Tap, shelf).record?.item_kind).toBe(
      ItemKind.Diagram,
    );
  });

  it("only a stretch can be played", () => {
    expect(playable(cluster)).toBe(true);
    for (const sel of [moment, shelf, { kind: SelKind.Count, id: "1,2" }]) {
      expect(playable(sel as Sel)).toBe(false);
      const open = reduce(REST, PicEvent.Tap, sel as Sel).state;
      expect(reduce(open, PicEvent.TapPlay).play).toBeNull();
    }
  });

  it("play asks for the play-by-play, records it, and keeps the caption open", () => {
    const open = reduce(REST, PicEvent.Tap, cluster).state;
    const out = reduce(open, PicEvent.TapPlay);
    expect(out.play).toBe("ch0");
    expect(out.state).toEqual({ sel: cluster, playing: "ch0" });
    expect(out.record?.kind).toBe(InteractionKind.Play);
  });

  it("a chip or play tap with nothing open does nothing at all", () => {
    for (const event of [PicEvent.TapChip, PicEvent.TapPlay]) {
      const out = reduce(REST, event);
      expect(out.state).toEqual(REST);
      expect(out.record).toBeNull();
      expect(out.insert).toBeNull();
      expect(out.play).toBeNull();
    }
  });

  it("dismiss returns to rest", () => {
    const playing = reduce(
      reduce(REST, PicEvent.Tap, cluster).state,
      PicEvent.TapPlay,
    ).state;
    expect(reduce(playing, PicEvent.Dismiss).state).toEqual(REST);
  });
});
