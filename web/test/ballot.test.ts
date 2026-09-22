import { describe, expect, it } from "vitest";
import { eventsOf, litCoding, names, what, when } from "../src/ballot";
import {
  ItemKind,
  ItemStatus,
  VoteChoice,
  type BallotItem,
  type Vote,
} from "../src/types";

const item = (
  id: number,
  event: Record<string, unknown>,
  person: string | null = null,
): BallotItem =>
  ({
    id,
    item_kind: ItemKind.Event,
    status: ItemStatus.Disputed,
    coders: 2,
    not_coded: 0,
    people: [],
    opinions: [{ coding_id: id, person_name: person, item: event }],
  }) as unknown as BallotItem;

describe("the date word", () => {
  it("says an event has no date yet rather than calling it undated", () => {
    expect(when(null)).toBe("no date yet");
    expect(when("")).toBe("no date yet");
  });

  it("reads a year on its own as the year", () => {
    expect(when("1998")).toBe("1998");
  });
});

describe("what a row is named", () => {
  it("uses the description when there is one", () => {
    expect(what(item(1, { kind: "noted", description: "left for Juneau" }))).toBe(
      "left for Juneau",
    );
  });

  it("says the kind in words when the description is empty", () => {
    expect(what(item(1, { kind: "shift", description: "" }))).toBe("a shift");
    expect(what(item(2, { kind: "death" }))).toBe("a death");
  });

  it("names who and what together, never a placeholder", () => {
    expect(names(item(1, { kind: "birth" }, "Marcus"))).toBe("Marcus · a birth");
    expect(names(item(2, { kind: "shift" }))).toBe("a shift");
  });
});

describe("the events of a cut", () => {
  it("reads in the order they happened", () => {
    const events = eventsOf([
      item(1, { kind: "shift", dateTime: "2021-06-02" }),
      item(2, { kind: "noted", description: "left for Juneau", dateTime: "1998-01-09" }),
      item(3, { kind: "death", dateTime: "2010-03-11" }),
    ]);
    expect(events.map((one) => one.id)).toEqual([2, 3, 1]);
  });
});

describe("which version is lit", () => {
  const vote = (coding: number) =>
    ({
      choice: VoteChoice.Opinion,
      value: { coding_id: coding },
    }) as unknown as Vote;

  it("is the one this coder chose while the vote is open", () => {
    expect(litCoding(item(1, { kind: "birth" }), vote(7), false)).toBe(7);
  });

  it("is the one the meeting kept once the cut is ratified", () => {
    const decided = { ...item(1, { kind: "birth" }), kept_coding_id: 9 };
    expect(litCoding(decided, vote(7), true)).toBe(9);
  });

  it("lights nothing when a ratified item was written out rather than kept", () => {
    expect(litCoding(item(1, { kind: "birth" }), vote(7), true)).toBeNull();
  });
});
