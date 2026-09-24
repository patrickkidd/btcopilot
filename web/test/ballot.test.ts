import { describe, expect, it } from "vitest";
import { drawTimeline, eventsOf, litCoding, names, what, when } from "../src/ballot";
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
  // R-0318
  it("says an event has no date yet rather than calling it undated", () => {
    expect(when(null)).toBe("no date yet");
    expect(when("")).toBe("no date yet");
  });

  // R-0438
  it("reads a year on its own as the year", () => {
    expect(when("1998")).toBe("1998");
  });
});

describe("what a row is named", () => {
  // R-0318
  it("uses the description when there is one", () => {
    expect(what(item(1, { kind: "noted", description: "left for Juneau" }))).toBe(
      "left for Juneau",
    );
  });

  // R-0318
  it("says the kind in words when the description is empty", () => {
    expect(what(item(1, { kind: "shift", description: "" }))).toBe("a shift");
    expect(what(item(2, { kind: "death" }))).toBe("a death");
  });

  // R-0318
  it("names who and what together, never a placeholder", () => {
    expect(names(item(1, { kind: "birth" }, "Marcus"))).toBe("Marcus · a birth");
    expect(names(item(2, { kind: "shift" }))).toBe("a shift");
  });
});

describe("the events of a cut", () => {
  // R-0316
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

  // R-0339
  it("is the one this coder chose while the vote is open", () => {
    expect(litCoding(item(1, { kind: "birth" }), vote(7), false)).toBe(7);
  });

  // R-0339
  it("is the one the meeting kept once the cut is ratified", () => {
    const decided = { ...item(1, { kind: "birth" }), kept_coding_id: 9 };
    expect(litCoding(decided, vote(7), true)).toBe(9);
  });

  // R-0339
  it("lights nothing when a ratified item was written out rather than kept", () => {
    expect(litCoding(item(1, { kind: "birth" }), vote(7), true)).toBeNull();
  });
});

/** An event three coders wrote, agreed or split between readings. */
const coded = (id: number, status: ItemStatus, readings: string[]): BallotItem =>
  ({
    id,
    item_kind: ItemKind.Event,
    status,
    coders: 3,
    not_coded: 0,
    people: [],
    opinions: readings.map((description, at) => ({
      coding_id: id * 10 + at,
      person_name: null,
      item: { kind: "noted", description, dateTime: `199${id}-01-01` },
    })),
  }) as unknown as BallotItem;

const cut = [
  coded(1, ItemStatus.Agreed, ["left", "left", "left"]),
  coded(2, ItemStatus.Disputed, ["moved to Arizona", "moved in 1969", "moved in 1969"]),
  coded(3, ItemStatus.Disputed, ["came back", "came back"]),
  coded(4, ItemStatus.Agreed, ["died", "died", "died"]),
];

const circles = (svg: string) =>
  [...svg.matchAll(/<circle class="(d-\w+)" cx="([\d.]+)"[^>]*data-item="(\d+)"/g)].map((m) => ({
    kind: m[1],
    x: Number(m[2]),
    id: Number(m[3]),
  }));

describe("the agreement timeline", () => {
  // R-0277
  it("is one wire with one dot per event, however many coders wrote it", () => {
    const svg = drawTimeline(cut, null);
    expect(svg.match(/<svg/g)).toHaveLength(1);
    expect(svg.match(/class="wire2"/g)).toHaveLength(1);
    expect(circles(svg).map((c) => c.id)).toEqual([1, 2, 3, 4]);
  });

  // R-0277
  it("lays the events along the wire in the order it is given them", () => {
    const xs = circles(drawTimeline(cut, null)).map((c) => c.x);
    expect(xs).toEqual([...xs].sort((a, b) => a - b));
    expect(new Set(xs).size).toBe(xs.length);
  });

  // R-0278
  it("marks agreed dots apart from disputed ones, with a count beside a split", () => {
    const svg = drawTimeline(cut, 4);
    expect(circles(svg).map((c) => [c.id, c.kind])).toEqual([
      [1, "d-ok"],
      [2, "d-no"],
      [3, "d-no"],
      [4, "d-on"],
    ]);
    // two different readings of event 2; event 3 was written one way only
    const counts = [...svg.matchAll(/<text class="d-n"[^>]*>(\d+)<\/text>/g)].map((m) => m[1]);
    expect(counts).toEqual(["2"]);
  });
});
