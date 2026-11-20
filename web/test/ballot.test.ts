import { describe, expect, it, vi } from "vitest";
import {
  DOTS,
  ballotOrder,
  choosable,
  contextMarkup,
  nowWords,
  opinionCard,
  passage,
  ownCard,
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
  const said = { statement_id: 4, who: "Coach", text: "When did it start? [[ask:high school years]]", number: 1 };

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
  it("shows the date as far as it was said, an estimate or an unsure date as its year, and a stand-in as no date", () => {
    const [entry] = toPairing(pairing(1, [opinion(1, 1, moved)]), new Map()).versions[0];
    expect(writtenDate(entry)).toBe("1994");
    for (const date of ["1900-01-01", "0001-01-01", "1970-01-01"])
      expect(writtenDate({ ...entry, date })).toBe("no date yet");
    expect(writtenDate({ ...entry, date: "" })).toBe("no date yet");
    expect(writtenDate({ ...entry, date: "1990-01-01", prec: "day", cert: "approximate" })).toBe("1990");
    expect(writtenDate({ ...entry, date: "1930-01-01", prec: "", cert: "unknown" })).toBe("1930");
    expect(writtenDate({ ...entry, date: "1970-09-01", prec: "month", cert: "certain" })).toBe("Sep 1970");
    expect(writtenDate({ ...entry, date: "1980-05-11", prec: "day", cert: "certain" })).toBe("11 May 1980");
    expect(writtenDate({ ...entry, date: "1997-01-01", end: "1997-06-01" })).toBe("1997");
  });

  // R-0965, R-0967
  it("gives a noted event beside a shift none of the shift's places, so they differ by the kind alone", () => {
    const item = pairing(5, [
      opinion(1, 1, { kind: "noted", dateTime: "2015-09-01", datePrecision: "month", title: "Started grad program" }),
      opinion(2, 2, {
        kind: "shift",
        dateTime: "2015-09-01",
        datePrecision: "month",
        anxiety: "down",
        functioning: "up",
        relationship: "defined-self",
        relationshipTargets: [7],
        title: "Moved to SF",
      }, { toward_names: ["Lee"] }),
      opinion(3, 3, { kind: "shift", dateTime: "2015-09-01", datePrecision: "month", anxiety: "up" }),
    ]);
    const opinions = pairOpinions(toPairing(item, new Map()));
    const noted = opinionCards(opinions.filter((one) => one.entries[0].kind === "noted"), null, false);
    expect(noted).not.toMatch(/recorded/);
    const html = opinionCards(opinions, null, false);
    expect(html).toContain('<span class="pv-tag pv-diff">noted</span>');
    expect(html).toContain("no functioning recorded");
    expect(html.match(/no functioning recorded/g)).toHaveLength(1);
  });

  // R-0965
  it("walks the pairings in the order of the conversation, then people, couples, events, then the earliest date any coder gave", () => {
    const said = (id: number) => ({ line: { statement_id: id, who: "Ada", text: "", number: id } });
    const at = (
      id: number,
      kind: ItemKind,
      lines: number[],
      dates: string[] = ["2000-01-01"],
    ): BallotItem => ({
      ...pairing(
        id,
        dates.map((dateTime, n) => opinion(n + 1, id, { dateTime }, lines[n] ? said(lines[n]) : {})),
      ),
      item_kind: kind,
    });
    const items = [
      at(1, ItemKind.Event, [40, 9], ["2000-01-01", "2000-01-01"]),
      at(2, ItemKind.Event, [9], ["2015-09-01"]),
      at(3, ItemKind.Event, [9, 9], ["2016-01-01", "1990-01-01"]),
      at(4, ItemKind.Person, [9]),
      at(5, ItemKind.PairBond, [9]),
      at(6, ItemKind.Event, [3]),
      at(7, ItemKind.Event, []),
    ];
    expect(ballotOrder(items).map((one) => one.id)).toEqual([6, 4, 5, 3, 1, 2, 7]);
  });

  // R-0965
  it("walks by the statement whose passage each pairing shows, the one most entries were written from, so the passage never goes back", () => {
    const said = (id: number) => ({ line: { statement_id: id, who: "Ada", text: "", number: id } });
    const at = (id: number, lines: number[]): BallotItem =>
      pairing(
        id,
        lines.map((line, n) => opinion(n + 1, id, { dateTime: "2000-01-01" }, said(line))),
      );
    const items = [at(1, [39, 46, 46]), at(2, [40, 41]), at(3, [44])];
    const walked = ballotOrder(items);
    expect(walked.map((one) => one.id)).toEqual([2, 3, 1]);
    expect(walked.map((one) => toPairing(one, new Map()).line?.statement_id)).toEqual([40, 44, 46]);
  });

  // R-0965
  it("says no date on the strip when no opinion gives one, and the first shown opinion's date when one does", () => {
    const none = toPairing(pairing(8, [opinion(1, 1, { kind: "noted" }), opinion(2, 2, { kind: "noted", dateTime: "1900-01-01" })]), new Map());
    expect(nowWords(none)).toBe("");
    const dated = toPairing(pairing(9, [opinion(1, 1, { kind: "noted" }), opinion(2, 2, moved)]), new Map());
    expect(nowWords(dated)).toBe("1994");
  });

  // R-0965, R-0966
  it("draws an opinion written with change… as a card like the others, never as a sentence", () => {
    const item = { ...pairing(10, [opinion(1, 1, moved), opinion(2, 2, { ...moved, anxiety: "down" })]), people: [{ id: 3, name: "Ann" }] };
    const html = ownCard(
      toPairing(item, new Map()),
      { kind: "noted", person: 3, dateTime: "1950-01-01", datePrecision: "year", dateCertainty: "approximate", title: "Moved to Anchorage" },
      new Map(),
      whoOf([item]),
      false,
    );
    expect(html).toContain("your opinion");
    expect(html).toContain('<span class="pv-tag pv-diff">noted</span>');
    expect(html).toContain("1950");
    expect(html).toContain("Ann");
    expect(html).not.toMatch(/Jan|something noted|recorded/);
  });

  // R-0968
  it("offers each person once in change…, by the name most coders gave", () => {
    const person = (coding: number, id: number, name: string) =>
      opinion(coding, id, { id, name, gender: "male", parents: null });
    const john = { ...pairing(30, [person(1, 5, "John"), person(1, 6, "John"), person(2, 5, "Johnny"), person(3, 5, "Johnny")]), item_kind: ItemKind.Person };
    const event = {
      ...pairing(31, [opinion(1, 1, moved)]),
      people: [
        { id: 5, name: "John" },
        { id: 6, name: "John" },
        { id: 7, name: "Robert" },
      ],
    };
    expect(choosable(event, whoOf([john, event])).map((one) => one.name)).toEqual(["Johnny", "Robert"]);
  });

  // R-0965, R-0966
  it("puts the accent only on what the opinions part ways on, with no field names, coder names or counts", () => {
    const item = pairing(3, [
      opinion(1, 1, moved, { coder: "ballot1" }),
      opinion(2, 2, { ...moved, anxiety: "down", relationshipTargets: [7] }, { toward_names: ["Jim"] }),
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

  // R-0967, R-0968
  it("shows Emily's places in every card, the gender not recorded as an empty chip, and merges the cards that differ only by name", () => {
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
    expect(opinions).toHaveLength(2);
    const html = opinionCards(opinions, null, false);
    expect(html.match(/<span class="pv-same">Emily<\/span>/g)).toHaveLength(2);
    expect(html).not.toContain("Patrick's partner");
    expect(html.match(/chip pv-diff">no gender recorded</g)).toHaveLength(1);
    expect(html.match(/chip pv-diff">female</g)).toHaveLength(1);
    expect(html.match(/chip pv-same">no parents recorded</g)).toHaveLength(2);
    expect(html).not.toContain("no last name recorded");
  });

  // R-0968
  it("names Jim's first wife the same on every card, by the first name given on a tie, and never accents her name", () => {
    const wife = (name: string) => ({ id: 2, name, gender: "female", parents: null });
    const record = (name: string) =>
      ({
        people: [
          { id: 1, name: "Jim" },
          { id: 2, name },
        ],
        pair_bonds: [{ id: 5, person_a: 1, person_b: 2 }],
      }) as unknown as CodingRecord;
    const given = ["Jim's first wife", "Jim's ex-wife", "Julia's mother"];
    const records = new Map(given.map((name, at) => [at + 1, record(name)]));
    const her = {
      ...pairing(30, given.map((name, at) => opinion(at + 1, 2, wife(name)))),
      item_kind: ItemKind.Person,
    };
    const jim = {
      ...pairing(31, [1, 2, 3].map((coding) => opinion(coding, 1, { id: 1, name: "Jim" }))),
      item_kind: ItemKind.Person,
    };
    const couple = {
      ...pairing(32, [1, 2, 3].map((coding) => opinion(coding, 5, { id: 5, person_a: 1, person_b: 2 }))),
      item_kind: ItemKind.PairBond,
    };
    const moved = pairing(33, [
      opinion(1, 9, { kind: "shift", person: 2, anxiety: "up" }, { person_name: given[0] }),
      opinion(3, 9, { kind: "shift", person: 2, anxiety: "down" }, { person_name: given[2] }),
    ]);
    const who = whoOf([her, jim, couple, moved]);
    const cards = (item: BallotItem) =>
      opinionCards(pairOpinions(toPairing(item, records, who)), null, false);

    const herCards = pairOpinions(toPairing(her, records, who));
    expect(herCards).toHaveLength(1);
    expect(cards(her)).toContain('<span class="pv-same">Jim&#39;s first wife</span>');
    expect(cards(couple)).toContain("Jim &amp; Jim&#39;s first wife");
    expect(cards(couple)).not.toMatch(/ex-wife|Julia/);
    expect(cards(moved).match(/<span class="pv-same">Jim&#39;s first wife<\/span>/g)).toHaveLength(2);
    expect(cards(moved)).not.toContain("Julia");
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

  // R-0970
  it("draws every opinion as one box, a coder's several entries as rows under a line saying how many, no row tappable", () => {
    const mother = (id: number, name: string) => ({ id, name, gender: "female", parents: null });
    const item = {
      ...pairing(40, [
        opinion(1, 2, mother(2, "Julia's mother")),
        opinion(1, 3, mother(3, "Anthony's mother")),
        opinion(1, 4, mother(4, "Joseph's mother")),
        opinion(2, 2, mother(2, "Jim's first wife")),
        opinion(3, 2, mother(2, "Jim's ex-wife")),
      ]),
      item_kind: ItemKind.Person,
    };
    const opinions = pairOpinions(toPairing(item, new Map()));
    const html = opinionCards(opinions, null, false);
    expect(html.match(/class="opinion /g)).toHaveLength(opinions.length);
    const box = html.split('class="opinion ').find((one) => one.includes("wrote 3 separate people"))!;
    expect(box).toMatch(/^tap pv many"/);
    expect(box.match(/class="pv-entry"/g)).toHaveLength(3);
    expect(box.match(/pv-tag/g)).toHaveLength(1);
    expect(html).not.toMatch(/data-entry|data-row/);
  });

  // R-0963, R-0967, R-0970
  it("lights a box only when every coder's entry it stands for is picked", () => {
    const item = pairing(9, [opinion(1, 1, moved), opinion(2, 2, moved), opinion(3, 3, { ...moved, anxiety: "down" })]);
    const opinions = pairOpinions(toPairing(item, new Map()));
    expect(opinions).toHaveLength(2);
    const merged = opinions.findIndex((one) => one.codings.length === 2);
    const lit = (chosen: string[]) =>
      opinionCards(opinions, null, false, new Set(chosen)).includes(`pv on" data-opinion="${merged}"`);
    expect(lit(["1:1", "2:2"])).toBe(true);
    expect(lit(["1:1"])).toBe(false);
  });

  // R-0968, R-0970
  it("names each row of a coder's several entries as that coder named it, and everyone else by the most given name", () => {
    const mother = (id: number, name: string) => ({ id, name, gender: "female", parents: null });
    const given = ["Julia's mother", "Anthony's mother", "Joseph's mother"];
    const her = {
      ...pairing(41, [
        ...given.map((name, at) => opinion(1, at + 2, mother(at + 2, name))),
        opinion(2, 2, mother(2, "Jim's first wife")),
        opinion(3, 2, mother(2, "Jim's first wife")),
      ]),
      item_kind: ItemKind.Person,
    };
    const moved = pairing(42, [
      opinion(1, 9, { kind: "shift", person: 3, anxiety: "up" }, { person_name: given[1] }),
      opinion(1, 8, { kind: "shift", person: 4, anxiety: "up" }, { person_name: given[2] }),
      opinion(2, 9, { kind: "shift", person: 2, anxiety: "up" }, { person_name: "Jim's first wife" }),
    ]);
    const who = whoOf([her, moved]);
    const cards = (item: BallotItem) =>
      opinionCards(pairOpinions(toPairing(item, new Map(), who)), null, false);
    for (const name of given)
      expect(cards(her)).toContain(`<span class="pv-same">${name.replace("'", "&#39;")}</span>`);
    expect(cards(her).match(/Jim&#39;s first wife/g)).toHaveLength(1);
    expect(cards(moved)).toContain("Anthony&#39;s mother");
    expect(cards(moved)).toContain("Joseph&#39;s mother");
    expect(cards(moved)).not.toMatch(/pv-diff">(Anthony|Joseph|Jim)/);
  });

  // R-0965
  it("draws one dot per pairing, in rows of 33, the one on screen enlarged", () => {
    const ids = Array.from({ length: 66 }, (_, at) => at + 1);
    const { svg, height } = drawPairs(ids, 5, (id) => (id < 5 ? "d-ok" : "d-no"));
    expect(svg.match(/<circle/g)).toHaveLength(66);
    expect(height).toBe(DOTS.top * 2 + DOTS.row);
    expect(svg.match(/d-on/g)).toHaveLength(1);
    expect(svg.match(/d-ok/g)).toHaveLength(4);
    expect(svg).not.toMatch(/<text/);
  });
});

vi.stubGlobal("window", { BOOTSTRAP: { user: { pro: false } } });
const { line } = await import("../src/coding");

describe("where a code was said, behind an (i)", () => {
  const said = (id: number) => ({ line: { statement_id: id, who: "Ada", text: `line ${id}`, number: id } });
  const at = (coding: number, id: number, line: number, change = {}) =>
    opinion(coding, id, { ...moved, ...change }, said(line));
  const marks = (html: string) => [...html.matchAll(/data-line="(\d+)" data-box="(\d+)"/g)].map((m) => [Number(m[1]), Number(m[2])]);
  const words = (html: string) => html.replace(/<[^>]*>/g, " ").split(/\s+/).filter(Boolean);

  // R-0977, R-0975
  it("puts the app's (i) on the passage, opening its own line, and no words", () => {
    const html = passage(said(9).line);
    expect(html).toContain('class="info" aria-label="where this was said" data-line="9"');
    expect(html).not.toMatch(/open in transcript/);
    expect(words(html)).toEqual(words(html.replace(/<button[\s\S]*?<\/button>/, "")));
  });

  // R-0977
  it("puts an (i) beside a box only when it was written from another line than the passage", () => {
    const shown = toPairing(pairing(1, [at(1, 1, 9), at(2, 2, 9), at(3, 3, 12, { anxiety: "down" })]), new Map());
    const opinions = pairOpinions(shown);
    const other = opinions.findIndex((one) => one.codings.includes(3));
    expect(marks(opinionCards(opinions, null, false, new Set(), shown.line!.statement_id))).toEqual([[12, other]]);
  });

  // R-0977
  it("puts no (i) beside any box when every box was written from the passage's line", () => {
    const shown = toPairing(pairing(2, [at(1, 1, 9), at(2, 2, 9, { anxiety: "down" })]), new Map());
    expect(marks(opinionCards(pairOpinions(shown), null, false, new Set(), 9))).toEqual([]);
  });

  // R-0977
  it("puts one (i) per other line, in row order, beside a box whose rows came from two other lines", () => {
    const shown = toPairing(
      pairing(3, [at(1, 1, 9), at(1, 2, 15, { kind: "noted" }), at(1, 3, 12, { anxiety: "down" }), at(2, 4, 9), at(3, 5, 9)]),
      new Map(),
    );
    const opinions = pairOpinions(shown);
    const several = opinions.findIndex((one) => one.entries.length > 1);
    const rows = opinions[several].entries.map((entry) => entry.line!.statement_id).filter((id) => id !== 9);
    expect(marks(opinionCards(opinions, null, false, new Set(), 9))).toEqual(rows.map((id) => [id, several]));
    expect(rows).toHaveLength(2);
  });

  // R-0977, R-0975
  it("shows only what the person and the coach said, in the chat's own bubbles, never a coder's thread or note", () => {
    const talk = {
      count: 3,
      lines: [
        { id: 4, number: 1, who: "Ann", client: true, text: "My mother got sick" },
        { id: 7, number: 3, who: "Coach", client: false, text: "When was that?" },
      ].map((one) => ({ ...one, said: [{ text: "scribe: add Ann's mother", lines: [{ verb: "Added", text: "Ann's mother" }] }], note: "a coder's note" })),
    };
    const html = contextMarkup(talk, 7, "", line);
    expect(html.match(/class="bub line (user|coach)/g)).toEqual(['class="bub line user', 'class="bub line coach']);
    expect(html).toContain("My mother got sick");
    expect(html).toContain("When was that?");
    expect(html).not.toMatch(/scribe|Added|coder&#39;s note|coder's note/);
    expect(html).toContain('class="bub line coach sel" data-turn="7"');
    expect(html).toContain("line 3 of 3");
  });

  // R-0977
  it("heads the conversation with the box whose (i) opened it, the coder's words whole, and with nothing more from the passage's", () => {
    const shown = toPairing(pairing(4, [at(1, 1, 9), at(2, 2, 12, { anxiety: "down", title: "Moved far away from the whole family" })]), new Map());
    const opinions = pairOpinions(shown);
    const other = opinions.findIndex((one) => one.codings.includes(2));
    const talk = { count: 12, lines: [9, 12].map((id) => ({ id, number: id, who: "Ann", client: true, text: `line ${id}` })) };
    const boxed = contextMarkup(talk, 12, opinionCard(opinions, other, false, true), line);
    expect(boxed).toContain('<div class="ctx-box"><div class="opinion tap pv"');
    expect(boxed).toContain('<div class="pv-words">Moved far away from the whole family</div>');
    expect(contextMarkup(talk, 9, "", line)).not.toContain("ctx-box");
  });
});
