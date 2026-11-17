import { describe, expect, it } from "vitest";
import {
  DOTS,
  drawPairs,
  drawTimeline,
  opinionCards,
  pairOpinions,
  toPairing,
  whoOf,
  writtenDate,
  eventsOf,
  litCoding,
  names,
  quote,
  versionLine,
  what,
  when,
  wordedLine,
  words,
} from "../src/ballot";
import {
  ItemKind,
  ItemStatus,
  VoteChoice,
  type BallotItem,
  type CodingRecord,
  type Opinion,
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

describe("the values a coder reads", () => {
  // R-0869
  it("words an opinion's kind, date and relationship, never the stored slug", () => {
    const opinion = {
      person_name: "Rosa",
      item: { dateTime: "1971-03-02", kind: "shift", relationship: "defined-self" },
    } as never;
    const said = words(opinion, ["dateTime", "person_name", "kind", "relationship"]);
    expect(said).toContain(when("1971-03-02"));
    expect(said).toContain("a shift");
    expect(said).toContain("defined self");
    expect(said).not.toMatch(/1971-03-02|defined-self|· shift/);
  });

  // R-0869
  it("words a line the server already joined, value by value", () => {
    const said = wordedLine("1971-03-02 · shift · distance · left for Juneau");
    expect(said).toBe(`${when("1971-03-02")} · a shift · relationship: distance · left for Juneau`);
  });

  // R-0869
  it("names the variable an up or a down belongs to", () => {
    expect(wordedLine("symptom: up · anxiety: down")).toBe("symptom up · anxiety down");
  });
});

describe("a quoted line on the vote", () => {
  const said = { statement_id: 4, who: "Coach", text: "When did it start? [[ask:high school years]]" };

  // R-0072, R-0270
  it("draws the coach's markup as the chat does, never as brackets", () => {
    for (const html of [quote(said), versionLine({ item: {}, line: said }, true)]) {
      expect(html).not.toContain("[[");
      expect(html).toContain("<b>Coach:</b> &ldquo;When did it start? ");
      expect(html).toContain('class="chip ask" data-kind="ask"');
      expect(html).toContain(">[high school years]</button>&rdquo;");
    }
  });
});

const opinion = (
  coding: number,
  itemId: number,
  event: Record<string, unknown>,
  extra: Partial<Opinion> = {},
): Opinion => ({ coding_id: coding, item_id: itemId, person_name: "Ada", item: event, ...extra });

const pairing = (id: number, opinions: Opinion[]): BallotItem =>
  ({
    id,
    item_kind: ItemKind.Event,
    status: ItemStatus.Disputed,
    coders: 3,
    not_coded: 0,
    people: [],
    line: null,
    opinions,
  }) as unknown as BallotItem;

const moved = {
  kind: "shift",
  dateTime: "1994-01-01",
  datePrecision: "year",
  dateCertainty: "approximate",
  anxiety: "up",
  title: "Moved",
};

describe("a pairing on the vote", () => {
  // R-0965
  it("merges versions that say the same thing, whatever their words, and keeps a coder's joined entries as one version", () => {
    const item = pairing(14, [
      opinion(1, 10, { ...moved, title: "Moved in" }),
      opinion(2, 20, { ...moved, title: "Into the stepfather's house" }),
      opinion(3, 30, moved),
      opinion(3, 31, { kind: "noted", dateTime: "1994-01-01", datePrecision: "year", title: "Moved" }),
    ]);
    const opinions = pairOpinions(toPairing(item, new Map()));
    expect(opinions).toHaveLength(2);
    expect(opinions.find((one) => one.codings.length === 2)!.codings.sort()).toEqual([1, 2]);
    expect(opinions.find((one) => one.codings[0] === 3)!.entries).toHaveLength(2);
  });

  // R-0252, R-0965
  it("shuffles the versions per pairing, the same way on every visit", () => {
    const item = pairing(
      7,
      [1, 2, 3, 4].map((coding) => opinion(coding, coding, { ...moved, title: String(coding) })),
    );
    const order = (seen: BallotItem) =>
      toPairing(seen, new Map()).versions.map((one) => one[0].coding_id).join();
    expect(order(item)).toBe(order(item));
    expect([7, 8, 9, 10, 11].some((id) => order({ ...item, id }) !== "1,2,3,4")).toBe(true);
  });

  // R-0956, R-0965
  it("shows the date as far as it was said, and a stand-in or unknown date as no sure date", () => {
    const [entry] = toPairing(pairing(1, [opinion(1, 1, moved)]), new Map()).versions[0];
    expect(writtenDate(entry)).toBe("1994");
    for (const date of ["1900-01-01", "0001-01-01", "1970-01-01"])
      expect(writtenDate({ ...entry, date })).toBe("no sure date");
    expect(writtenDate({ ...entry, cert: "unknown" })).toBe("no sure date");
  });

  // R-0965, R-0966
  it("puts the accent only on what the opinions part ways on, with no field names, coder names or counts", () => {
    const item = pairing(3, [
      opinion(1, 1, moved, { coder: "ballot1" }),
      opinion(2, 2, { ...moved, anxiety: "down" }, { toward_names: ["Jim"] }),
    ]);
    const seen = toPairing(item, new Map());
    const html = opinionCards(pairOpinions(seen), null, false);
    expect(html).toContain('<span class="chip pv-diff">anxiety ↑</span>');
    expect(html).toContain('<span class="pv-same">1994</span>');
    expect(html).toContain('<span class="pv-diff">Jim</span>');
    expect(html).toContain('<span class="pv-tag pv-same">shift</span>');
    expect(html).not.toMatch(/ballot1|coders?\b|date:|kind:/);
    expect(html.match(/opinion \d/g)).toEqual(["opinion 1", "opinion 2"]);
  });

  // R-0965, R-0966
  it("accents nothing inside one opinion, even where a coder's own entries differ", () => {
    const item = pairing(4, [opinion(1, 1, moved), opinion(1, 2, { ...moved, anxiety: "down" })]);
    const seen = toPairing(item, new Map());
    const html = opinionCards(pairOpinions(seen), null, false);
    expect(html).not.toContain("pv-diff");
  });

  // R-0965, R-0967
  it("accents a place in every card when the opinions hold different numbers of entries, and never a place they agree on", () => {
    const item = pairing(6, [
      opinion(1, 1, moved),
      opinion(2, 2, moved),
      opinion(2, 3, { ...moved, kind: "noted", anxiety: "down" }),
    ]);
    const html = opinionCards(pairOpinions(toPairing(item, new Map())), null, false);
    expect(html.match(/<span class="pv-tag pv-diff">shift<\/span>/g)).toHaveLength(2);
    expect(html).toContain('<span class="pv-tag pv-diff">noted</span>');
    expect(html.match(/<span class="chip pv-diff">anxiety ↑<\/span>/g)).toHaveLength(2);
    expect(html).toContain('<span class="chip pv-diff">anxiety ↓</span>');
    expect(html).not.toMatch(/pv-diff">(1994|Ada)</);
  });

  // R-0961, R-0965
  it("merges parents named in either order, and accents neither order", () => {
    const record = (bond: [number, number]) =>
      ({
        people: [
          { id: 1, name: "Wally" },
          { id: 2, name: "Louann" },
          { id: 3, name: "Kid" },
        ],
        pair_bonds: [{ id: 7, person_a: bond[0], person_b: bond[1] }],
      }) as unknown as CodingRecord;
    const kid = { id: 3, name: "Kid", gender: "male", parents: 7 };
    const item = {
      ...pairing(5, [opinion(1, 3, kid), opinion(2, 3, kid)]),
      item_kind: ItemKind.Person,
    };
    const seen = toPairing(
      item,
      new Map([
        [1, record([1, 2])],
        [2, record([2, 1])],
      ]),
    );
    const opinions = pairOpinions(seen);
    expect(opinions).toHaveLength(1);
    expect(opinionCards(opinions, null, false)).not.toContain("pv-diff");
  });

  // R-0967
  it("shows Emily's places in every card, the gender not recorded as an empty chip, and merges the cards that read the same", () => {
    const record = { people: [], pair_bonds: [] } as unknown as CodingRecord;
    const emily = (name: string, gender: string | null) => ({ id: 9, name, gender, parents: null });
    const item = {
      ...pairing(8, [
        opinion(1, 9, emily("Emily", null)),
        opinion(2, 9, emily("Patrick's partner", "female")),
        opinion(3, 9, emily("Emily", null)),
        opinion(4, 9, emily("Emily", "female")),
      ]),
      item_kind: ItemKind.Person,
    };
    const records = new Map([1, 2, 3, 4].map((id) => [id, record]));
    const opinions = pairOpinions(toPairing(item, records));
    expect(opinions).toHaveLength(3);
    const html = opinionCards(opinions, null, false);
    expect(html.match(/class="pv-diff">(Emily<|Patrick)/g)).toHaveLength(3);
    expect(html.match(/chip pv-diff">no gender recorded</g)).toHaveLength(1);
    expect(html.match(/chip pv-diff">female</g)).toHaveLength(2);
    expect(html.match(/chip pv-same">no parents recorded</g)).toHaveLength(3);
    expect(html).not.toContain("no last name recorded");
  });

  // R-0967
  it("compares Jane's parents by who they are, so two spellings are one value, and accents the place in every card", () => {
    const record = (louann: string) =>
      ({
        people: [
          { id: 1, name: "Wally" },
          { id: 2, name: louann },
          { id: 3, name: "Jane" },
        ],
        pair_bonds: [{ id: 7, person_a: 1, person_b: 2 }],
      }) as unknown as CodingRecord;
    const jane = { id: 3, name: "Jane", gender: "female", parents: 7 };
    const people = (id: number, person: number) =>
      ({
        ...pairing(id, [1, 2, 3].map((coding) => opinion(coding, person, {}))),
        item_kind: ItemKind.Person,
      }) as BallotItem;
    const item = {
      ...pairing(5, [
        opinion(1, 3, jane),
        opinion(2, 3, { ...jane, parents: null }),
        opinion(2, 4, jane),
        opinion(3, 3, jane),
      ]),
      item_kind: ItemKind.Person,
    };
    const who = whoOf([people(20, 1), people(21, 2), item]);
    const records = new Map([
      [1, record("Louann")],
      [2, record("LouAnn")],
      [3, record("LouAnn")],
    ]);
    const opinions = pairOpinions(toPairing(item, records, who));
    expect(opinions).toHaveLength(2);
    const html = opinionCards(opinions, null, false);
    expect(html).toMatch(/chip pv-diff">born to (Louann|LouAnn) &amp; Wally</);
    expect(html).toContain('chip pv-diff">no parents recorded<');
    expect(html).not.toMatch(/chip pv-same">born to/);
    expect(html).not.toMatch(/pv-diff">(Jane|female)</);
  });

  // R-0963, R-0967
  it("lets a tap on a merged card's entry select every coder's entry it stands for", () => {
    const item = pairing(9, [opinion(1, 1, moved), opinion(2, 2, moved), opinion(3, 3, { ...moved, anxiety: "down" })]);
    const opinions = pairOpinions(toPairing(item, new Map()));
    expect(opinions).toHaveLength(2);
    const both = new Set(["1:1", "2:2"]);
    const html = opinionCards(opinions, null, false, both);
    expect(html).toContain('<div class="pv-entry on" data-entry="1:1 2:2">');
    expect(opinionCards(opinions, null, false, new Set(["1:1"]))).not.toContain("pv-entry on");
  });

  // R-0965
  it("draws one dot per pairing, in rows of 33, the one on screen enlarged", () => {
    const ids = Array.from({ length: 66 }, (_, at) => at + 1);
    const { svg, height } = drawPairs(ids, 5, (id) => id < 5);
    expect(svg.match(/<circle/g)).toHaveLength(66);
    expect(height).toBe(DOTS.top * 2 + DOTS.row);
    expect(svg.match(/d-on/g)).toHaveLength(1);
    expect(svg.match(/d-ok/g)).toHaveLength(4);
    expect(svg).not.toMatch(/<text/);
  });
});
