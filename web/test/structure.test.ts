import { describe, expect, it } from "vitest";
import { ballotOrder, group, onBallot, telling } from "../src/ballot";
import {
  drawVersion,
  fragmentOf,
  structureName,
  versionWords,
} from "../src/structure";
import {
  ItemKind,
  ItemStatus,
  type BallotItem,
  type CodingRecord,
} from "../src/types";

const record: CodingRecord = {
  coding_id: 1,
  people: [
    { id: 1, name: "Marcus", gender: "male", parents: null },
    { id: 2, name: "Delphine", gender: "female", parents: null },
    { id: 3, name: "Corinne", gender: "female", parents: 10 },
  ],
  pair_bonds: [{ id: 10, person_a: 1, person_b: 2, married: true }],
  events: [
    { id: 20, kind: "married", person: 1, spouse: 2, dateTime: "1970-06-01" },
  ],
} as unknown as CodingRecord;

const records = new Map([[1, record], [2, { ...record, coding_id: 2 }]]);

const item = (
  id: number,
  kind: ItemKind,
  opinions: Record<string, unknown>[],
): BallotItem =>
  ({
    id,
    item_kind: kind,
    status: ItemStatus.Disputed,
    coders: 2,
    not_coded: 0,
    people: record.people.map((one) => ({ id: one.id, name: one.name })),
    opinions: opinions.map((one, index) => ({
      coding_id: index + 1,
      item: one,
    })),
  }) as unknown as BallotItem;

describe("what is on the ballot", () => {
  it("takes people and bonds as well as events", () => {
    expect(onBallot(item(1, ItemKind.Person, [{ id: 3, name: "Corinne" }]))).toBe(
      true,
    );
    expect(
      onBallot(item(2, ItemKind.PairBond, [{ id: 10, person_a: 1, person_b: 2 }])),
    ).toBe(true);
  });

  it("reads the people and the bonds before the events", () => {
    const events = item(5, ItemKind.Event, [{ kind: "shift", dateTime: "1980-01-01" }]);
    const people = item(6, ItemKind.Person, [{ id: 3, name: "Corinne" }]);
    expect(ballotOrder([events, people]).map((one) => one.id)).toEqual([6, 5]);
  });
});

describe("two versions of a person", () => {
  const disputed = item(1, ItemKind.Person, [
    { id: 3, name: "Corinne", gender: "female", parents: 10 },
    { id: 3, name: "Corinne", gender: "female", parents: null },
  ]);

  it("differ by who they were born to, said as the couple", () => {
    expect(telling(disputed.opinions, ItemKind.Person)).toEqual(["parents"]);
    const sides = group(disputed, records).map((one) => one.label);
    expect(sides).toEqual([
      "born to Marcus & Delphine",
      "no parents recorded",
    ]);
  });

  it("are each drawn as a family with that person in the middle", () => {
    const drawn = drawVersion(records, ItemKind.Person, disputed.opinions[0]);
    expect(drawn).toContain("<svg");
    expect(drawn).toContain("Marcus");
  });

  it("draws a person with no parents standing on their own", () => {
    const fragment = fragmentOf(record, ItemKind.Person, {
      id: 3,
      name: "Corinne",
      gender: "female",
      parents: null,
    });
    expect(fragment?.center).toBe(3);
    expect(fragment?.people.find((one) => one.id === 3)?.parents).toBe(null);
  });
});

describe("a bond", () => {
  it("is named by both people", () => {
    expect(
      structureName(
        ItemKind.PairBond,
        { person_a: 1, person_b: 2 },
        record.people.map((one) => ({ id: one.id, name: one.name })),
      ),
    ).toBe("Marcus & Delphine");
  });

  it("says whether they married rather than showing a true or a false", () => {
    expect(
      versionWords(record, { person_a: 1, person_b: 2, married: false }, [
        "married",
      ]),
    ).toBe("together, not married");
  });
});
