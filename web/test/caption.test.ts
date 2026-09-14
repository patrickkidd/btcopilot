import { describe, expect, it } from "vitest";
import {
  PicEvent,
  REST,
  SelKind,
  reduce,
  selToken,
  type Sel,
} from "../src/caption";
import { InteractionKind, ItemKind } from "../src/types";

const moment: Sel = { kind: SelKind.Event, id: "42" };
const other: Sel = { kind: SelKind.Event, id: "43" };
const stretch: Sel = { kind: SelKind.Cluster, id: "ch0" };
const shelf: Sel = { kind: SelKind.Shelf, id: "shelf" };

describe("two taps on the picture", () => {
  it("the first tap picks a moment, records a look, and says nothing", () => {
    const out = reduce(REST, PicEvent.Tap, moment);
    expect(out.state).toEqual({ sel: moment, playing: null });
    expect(out.insert).toBeNull();
    expect(out.record).toEqual({
      kind: InteractionKind.Look,
      item_kind: ItemKind.Event,
      item_id: "42",
    });
  });

  it("the second tap is the chip, and it speaks", () => {
    const open = reduce(REST, PicEvent.Tap, moment).state;
    const out = reduce(open, PicEvent.TapChip);
    expect(out.insert).toEqual(moment);
    expect(out.record?.kind).toBe(InteractionKind.Say);
    expect(out.state).toEqual(REST);
    expect(selToken(moment, "Sleep got worse")).toBe(
      "[[event:42|Sleep got worse]]",
    );
  });

  it("tapping the same moment again leaves it picked and records another look", () => {
    const open = reduce(REST, PicEvent.Tap, moment).state;
    const out = reduce(open, PicEvent.Tap, moment);
    expect(out.state).toEqual({ sel: moment, playing: null });
    expect(out.record).toEqual({
      kind: InteractionKind.Look,
      item_kind: ItemKind.Event,
      item_id: "42",
    });
  });

  it("tapping the next moment moves the words to it", () => {
    const open = reduce(REST, PicEvent.Tap, moment).state;
    const out = reduce(open, PicEvent.Tap, other);
    expect(out.state.sel).toEqual(other);
    expect(out.record?.item_id).toBe("43");
  });

  it("a tap that lands on no moment lets go of the one that was picked", () => {
    const open = reduce(REST, PicEvent.Tap, moment).state;
    expect(reduce(open, PicEvent.Tap).state).toEqual(REST);
  });

  it("the undated shelf is recorded against the diagram itself", () => {
    expect(reduce(REST, PicEvent.Tap, shelf).record?.item_kind).toBe(
      ItemKind.Diagram,
    );
  });

  it("only a stretch can be played, and a moment plays the stretch it is in", () => {
    const open = reduce(REST, PicEvent.Tap, moment).state;
    expect(reduce(open, PicEvent.TapPlay).play).toBeNull();
    const out = reduce(open, PicEvent.TapPlay, stretch);
    expect(out.play).toBe("ch0");
    expect(out.record?.kind).toBe(InteractionKind.Play);
    expect(out.state).toEqual({ sel: stretch, playing: "ch0" });
  });

  it("a chip tap with nothing picked does nothing at all", () => {
    const out = reduce(REST, PicEvent.TapChip);
    expect(out.state).toEqual(REST);
    expect(out.record).toBeNull();
    expect(out.insert).toBeNull();
  });

  it("dismiss returns to rest", () => {
    const playing = reduce(
      reduce(REST, PicEvent.Tap, moment).state,
      PicEvent.TapPlay,
      stretch,
    ).state;
    expect(reduce(playing, PicEvent.Dismiss).state).toEqual(REST);
  });
});
