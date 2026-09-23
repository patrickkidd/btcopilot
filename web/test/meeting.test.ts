import { describe, expect, it } from "vitest";
import { choiceOf, markOf, seated, type Side } from "../src/meeting";
import {
  Decision,
  ItemKind,
  ItemStatus,
  type BallotItem,
  type Opinion,
} from "../src/types";

const item = (id: number, status: ItemStatus, kept?: number): BallotItem => ({
  id,
  cut_id: 1,
  item_kind: ItemKind.Event,
  item_id: null,
  status,
  opinions: [],
  coders: 3,
  not_coded: 0,
  people: [],
  line: null,
  kept_coding_id: kept ?? null,
});

const side = (label: string, coding: number): Side => ({
  label,
  names: ["ballot1"],
  opinion: { coding_id: coding, item: {} } as Opinion,
});

describe("seated", () => {
  // R-0341
  it("keeps an item where it sat when the room decides on it", () => {
    const first = [
      item(7, ItemStatus.Disputed),
      item(9, ItemStatus.Disputed),
      item(4, ItemStatus.Agreed),
    ];
    const order = seated([], first);
    expect(order).toEqual([7, 9, 4]);
    // 9 is decided, so the sort would now put it after 7 and beside 4.
    const after = [item(7, ItemStatus.Disputed), item(4, ItemStatus.Agreed), item(9, ItemStatus.Decided)];
    expect(seated(order, after)).toEqual([7, 9, 4]);
    expect(seated(order, after).indexOf(9)).toBe(order.indexOf(9));
  });

  // no ruling
  it("seats what the list has newly gained at the end and drops what it lost", () => {
    const order = seated([7, 9], [item(9, ItemStatus.Disputed), item(11, ItemStatus.Disputed)]);
    expect(order).toEqual([9, 11]);
  });
});

describe("markOf", () => {
  // R-0257
  it("says the words of the version the room kept", () => {
    const sides = [side("moved to Arizona", 2), side("moved in 1969", 3)];
    expect(markOf(item(7, ItemStatus.Decided, 3), sides)).toBe("moved in 1969");
  });

  // R-0257
  it("says unresolved when the room left it so, and agreed when the vote settled it", () => {
    expect(markOf(item(7, ItemStatus.Unresolved), [])).toBe("unresolved");
    expect(markOf(item(7, ItemStatus.Agreed), [side("as written", 2)])).toBe("agreed");
  });
});

describe("choiceOf", () => {
  // R-0339, R-0317
  it("lights the choice the reopened card was decided with", () => {
    expect(choiceOf(item(7, ItemStatus.Decided))).toBe(Decision.Keep);
    expect(choiceOf(item(7, ItemStatus.Unresolved))).toBe(Decision.Unresolved);
    expect(choiceOf(item(7, ItemStatus.Disputed))).toBe(null);
  });
});
