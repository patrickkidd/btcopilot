import { describe, expect, it } from "vitest";
import { Loose, codes, eventDivider, eventRow, groupOf, personRow, sections } from "../src/rows";
import { DateCertainty, type Cluster, type Person, type TimelineEvent } from "../src/types";

const person = (over: Partial<Person> = {}): Person => ({
  id: 1,
  name: "Marcus",
  last_name: "Halloran",
  gender: "male",
  notes: null,
  primary: true,
  birth: null,
  birth_event: null,
  death_event: null,
  parents: null,
  ...over,
});

describe("a row in the people list", () => {
  // R-0326
  it("is the name alone, with no second line under it", () => {
    const html = personRow(person());
    expect(html).toContain("Marcus Halloran");
    expect(html).not.toContain('class="r2"');
    expect(html).not.toContain("no birth on the record");
  });

  // R-0326
  it("says nothing about a birth the record does hold", () => {
    const html = personRow(person({ birth: "1946-04-02" }));
    expect(html).not.toContain("1946");
    expect(html).not.toContain('class="r2"');
  });
});

const coded: TimelineEvent = {
  id: 4,
  label: "Stopped calling home",
  sentence: "",
  person_name: "Marcus",
  person: 1,
  dateTime: "1992-04-01",
  endDateTime: null,
  dateCertainty: null,
  kind: "shift",
  description: null,
  notes: null,
  location: null,
  symptom: "up",
  anxiety: "up",
  functioning: "same",
  relationship: "conflict",
  relationshipTargets: [2],
  relationshipTriangles: [],
  spouse: null,
  child: null,
};

describe("an event row's summary line", () => {
  // R-0143
  it("writes the coding in letters and arrows so it fits a phone", () => {
    const names = new Map([[2, "Mom"]]);
    const said = codes(coded, names);
    expect(said).toBe("S\u2191  A\u2191  F=  R conflict\u2192Mom");
    const row = eventRow(coded, names);
    expect(row).not.toMatch(/symptom|anxiety|functioning|relationship/i);
  });
});

describe("an event row's first line", () => {
  // R-0457
  it("is the label the server gives every view, as it is", () => {
    const row = eventRow({ ...coded, label: "died, possibly around July 4" }, new Map());
    expect(row).toContain('<div class="r1">died, possibly around July 4</div>');
  });
});

describe("the header over events no cluster holds", () => {
  const cluster = { id: "c1", label: "Leaving and losing", count: 3 } as Cluster;

  // R-0289
  it("says a dated event is in no cluster, and never calls it unplaced", () => {
    expect(groupOf(coded, undefined)).toBe(Loose.Dated);
    expect(eventDivider(Loose.Dated)).toContain("not in a cluster");
    expect(eventDivider(Loose.Dated)).not.toContain("unplaced");
  });

  // R-0289
  it("puts an event with no date, or only a guessed one, under no sure date yet", () => {
    expect(groupOf({ ...coded, dateTime: null }, undefined)).toBe(Loose.Undated);
    expect(
      groupOf({ ...coded, dateCertainty: DateCertainty.Unknown }, undefined),
    ).toBe(Loose.Undated);
    expect(eventDivider(Loose.Undated)).toContain("no sure date yet");
  });

  // R-0289
  it("gives way to the cluster that holds the event", () => {
    expect(groupOf(coded, cluster)).toBe(cluster);
    expect(eventDivider(cluster)).toContain("3 events");
  });
});

describe("the events list's stretches", () => {
  // R-0289
  it("lists a cluster once even when a loose event falls inside its years", () => {
    const cluster = { id: "c1", label: "1994\u20132021", count: 3 } as Cluster;
    const at = (id: number, dateTime: string) => ({ ...coded, id, dateTime });
    const events = [at(1, "1994-01-01"), at(2, "2015-01-01"), at(3, "2018-01-01"), at(4, "2021-01-01")];
    const held = new Set([1, 3, 4]);
    const found = sections(events, (id) => (held.has(id) ? cluster : undefined));
    expect(found.map((s) => [s.group === cluster ? "c1" : s.group, s.events.map((e) => e.id)])).toEqual([
      ["c1", [1, 3, 4]],
      [Loose.Dated, [2]],
    ]);
  });
});
