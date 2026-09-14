import { describe, expect, it } from "vitest";
import { personRow } from "../src/rows";
import type { Person } from "../src/types";

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
  it("is the name alone, with no second line under it", () => {
    const html = personRow(person());
    expect(html).toContain("Marcus Halloran");
    expect(html).not.toContain('class="r2"');
    expect(html).not.toContain("no birth on the record");
  });

  it("says nothing about a birth the record does hold", () => {
    const html = personRow(person({ birth: "1946-04-02" }));
    expect(html).not.toContain("1946");
    expect(html).not.toContain('class="r2"');
  });
});
