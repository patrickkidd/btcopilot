import { describe, expect, it } from "vitest";
import { codes, eventRow, personRow } from "../src/rows";
import type { Person, TimelineEvent } from "../src/types";

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
