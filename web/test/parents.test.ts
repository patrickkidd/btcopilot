import { describe, expect, it } from "vitest";
import {
  bornToNames,
  findBond,
  partnerLine,
  PersonKind,
  type Family,
} from "../src/editor";
import type { PairBond, Person, TimelineEvent } from "../src/types";

const person = (
  id: number,
  name: string,
  last: string,
  gender: PersonKind,
  parents: number | null = null,
): Person => ({
  id,
  name,
  last_name: last,
  gender,
  notes: null,
  primary: false,
  birth: null,
  birth_event: null,
  death_event: null,
  parents,
});

const rafael = person(1, "Rafael", "Ortega", PersonKind.Male);
const marisol = person(2, "Marisol", "Ortega", PersonKind.Female);
const ines = person(3, "Ines", "Ortega", PersonKind.Female, 10);

const bond: PairBond = { id: 10, person_a: 1, person_b: 2, married: true };

const event = (kind: string, dateTime: string): TimelineEvent =>
  ({ id: 20, kind, dateTime, person: 1, spouse: 2 }) as TimelineEvent;

const family = (events: TimelineEvent[] = []): Family => ({
  people: [rafael, marisol, ines],
  pair_bonds: [bond],
  events,
});

describe("bornToNames", () => {
  // R-0345
  it("says the two parents by name, and never the word bond", () => {
    const said = bornToNames(ines, family());
    expect(said).toBe("Rafael Ortega and Marisol Ortega");
    expect(said).not.toMatch(/bond/i);
  });

  // R-0345
  it("says nothing for somebody the record has no parents for", () => {
    expect(bornToNames(rafael, family())).toBeNull();
  });
});

describe("partnerLine", () => {
  // R-0326
  it("names the other person and the year they married", () => {
    expect(partnerLine(bond, rafael, family([event("married", "1970-06")]))).toBe(
      "with Marisol Ortega · married 1970",
    );
  });

  // R-0326
  it("names the other person alone when they did not marry", () => {
    const together = { ...bond, married: false };
    expect(partnerLine(together, rafael, family())).toBe("with Marisol Ortega");
  });

  // R-0326
  it("says the year it ended when the record has one", () => {
    expect(
      partnerLine(bond, marisol, family([event("divorced", "1994-03")])),
    ).toBe("with Rafael Ortega · married · ended 1994");
  });
});

describe("findBond", () => {
  // no ruling
  it("takes the couple those two already are, named either way round", () => {
    expect(findBond(family(), 1, 2)).toBe(bond);
    expect(findBond(family(), 2, 1)).toBe(bond);
  });

  // no ruling
  it("finds none for two people who are not a couple", () => {
    expect(findBond(family(), 1, 3)).toBeUndefined();
  });
});
