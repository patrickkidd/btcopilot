import { describe, expect, it } from "vitest";
import { PicEvent, REST, reduce } from "../src/caption";
import { InteractionKind, ItemKind } from "../src/types";

describe("two taps on the picture", () => {
  it("the first tap opens a caption, records a look, and says nothing", () => {
    const out = reduce(REST, PicEvent.TapCluster, "ch0");
    expect(out.state).toEqual({ open: "ch0", playing: null });
    expect(out.insert).toBeNull();
    expect(out.record).toEqual({
      kind: InteractionKind.Look,
      item_kind: ItemKind.Cluster,
      item_id: "ch0",
    });
  });

  it("the second tap is the chip, and it speaks", () => {
    const open = reduce(REST, PicEvent.TapCluster, "ch0").state;
    const out = reduce(open, PicEvent.TapChip);
    expect(out.insert).toBe("[[cluster:ch0]]");
    expect(out.record).toEqual({
      kind: InteractionKind.Say,
      item_kind: ItemKind.Cluster,
      item_id: "ch0",
    });
    expect(out.state).toEqual(REST);
  });

  it("tapping the open cluster again closes it and records nothing", () => {
    const open = reduce(REST, PicEvent.TapCluster, "ch0").state;
    const out = reduce(open, PicEvent.TapCluster, "ch0");
    expect(out.state).toEqual(REST);
    expect(out.record).toBeNull();
  });

  it("tapping a different cluster moves the caption", () => {
    const open = reduce(REST, PicEvent.TapCluster, "ch0").state;
    const out = reduce(open, PicEvent.TapCluster, "ch1");
    expect(out.state.open).toBe("ch1");
    expect(out.record?.item_id).toBe("ch1");
  });

  it("play asks for the play-by-play, records it, and keeps the caption open", () => {
    const open = reduce(REST, PicEvent.TapCluster, "ch0").state;
    const out = reduce(open, PicEvent.TapPlay);
    expect(out.play).toBe("ch0");
    expect(out.state).toEqual({ open: "ch0", playing: "ch0" });
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
      reduce(REST, PicEvent.TapCluster, "ch0").state,
      PicEvent.TapPlay,
    ).state;
    expect(reduce(playing, PicEvent.Dismiss).state).toEqual(REST);
  });
});
