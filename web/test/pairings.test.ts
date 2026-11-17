import { describe, expect, it, vi } from "vitest";

vi.mock("../src/api", async (real) => ({
  ...(await real<typeof import("../src/api")>()),
  split: vi.fn(async () => ({ items: [], deleted: [] })),
}));
vi.mock("../src/track", async (real) => ({
  ...(await real<typeof import("../src/track")>()),
  tap: vi.fn(),
}));

const { Pairings, lookOrder, nearest } = await import("../src/pairings");
const { toPairing } = await import("../src/ballot");
const api = await import("../src/api");
const { Feature, tap } = await import("../src/track");
import { Confidence, ItemKind, ItemStatus, type BallotItem, type Opinion } from "../src/types";

const item = (
  id: number,
  kind: ItemKind,
  confidence: Confidence | null,
  dateTime = "2000-01-01",
): BallotItem =>
  ({
    id,
    item_kind: kind,
    status: ItemStatus.Disputed,
    pairing_confidence: confidence,
    opinions: [{ coding_id: 1, item_id: id, item: { dateTime } }],
  }) as unknown as BallotItem;

describe("Patrick's look over the pairings", () => {
  // R-0963
  it("puts the unsure ones first, then likely, then sure, each in the order the ballot walks", () => {
    const items = [
      item(1, ItemKind.Event, Confidence.Sure, "1990-01-01"),
      item(2, ItemKind.Event, Confidence.Unsure, "2001-01-01"),
      item(3, ItemKind.Event, Confidence.Likely),
      item(4, ItemKind.Person, Confidence.Sure),
      item(5, ItemKind.Event, Confidence.Unsure, "1999-01-01"),
    ];
    expect(lookOrder(items).map((one) => one.id)).toEqual([5, 2, 3, 4, 1]);
  });

  // R-0055, R-0963
  it("comes back to the pairing an address names, or to the one nearest it when a join took it away", () => {
    const pairings = [12, 30, 21].map((id) => toPairing(item(id, ItemKind.Event, null), new Map()));
    expect(nearest(pairings, 21)).toBe(2);
    expect(nearest(pairings, 29)).toBe(1);
    expect(nearest(pairings, 15)).toBe(0);
  });

  // R-0963
  it("leaves out a row no coder wrote anything in", () => {
    const empty = { ...item(6, ItemKind.Event, Confidence.Unsure), opinions: [] };
    expect(lookOrder([empty, item(7, ItemKind.Event, Confidence.Sure)]).map((one) => one.id)).toEqual([7]);
  });
});

/** Patrick's look on one pairing, drawn by the screen's own code on stand-ins
 * for the elements it writes into. */
function look(item: BallotItem) {
  const shown: string[] = [];
  const classes = new Set<string>();
  const screen = Object.assign(Object.create(Pairings.prototype), {
    cutId: 7,
    live: true,
    at: 0,
    chosen: new Set<string>(),
    pairings: [toPairing(item, new Map())],
    sheet: {
      sheet: { classList: { add: (name: string) => classes.add(name), remove: (name: string) => classes.delete(name) } },
      show: (html: string) => shown.push(html),
      close() {},
    },
    apply() {},
  });
  return { screen, shown, classes };
}

const mother = (coding: number, id: number, name: string, gender = "female"): Opinion =>
  ({ coding_id: coding, item_id: id, item: { id, name, gender, parents: null } }) as Opinion;

const people = (opinions: Opinion[]): BallotItem =>
  ({ id: 50, item_kind: ItemKind.Person, status: ItemStatus.Disputed, opinions }) as unknown as BallotItem;

describe("the split list on Patrick's look over the pairings", () => {
  const item = people([
    mother(1, 2, "Julia's mother"),
    mother(1, 3, "Anthony's mother"),
    mother(1, 4, "Joseph's mother"),
    mother(2, 2, "Jim's first wife"),
  ]);

  // R-0970
  it("opens with nothing picked, asking which entry of the opinion to take out, listing them by name", () => {
    const { screen, shown, classes } = look(item);
    expect(screen.controls(screen.pairings[0])).not.toContain("disabled>split");
    screen.onTap({ target: { closest: (sel: string) => (sel === "#pr-split" ? {} : null) } });
    expect(shown).toHaveLength(1);
    const opinion = shown[0].match(/out of opinion (\d)\?/)![1];
    for (const name of ["Julia&#39;s mother", "Anthony&#39;s mother", "Joseph&#39;s mother"])
      expect(shown[0]).toContain(`<span class="rtitle">${name}</span>`);
    expect(shown[0].match(/data-split=/g)).toHaveLength(3);
    expect(shown[0]).toContain(`opinion ${opinion} · person`);
    expect(shown[0]).not.toContain("Jim");
    expect(classes.has("pv-split")).toBe(true);
    expect(tap).toHaveBeenCalledWith(Feature.PairingSplitList);
  });

  // R-0970
  it("splits out only the entry tapped in the list", async () => {
    const { screen } = look(item);
    await screen.pick(["1:3"]);
    expect(api.split).toHaveBeenCalledWith(7, [{ coding_id: 1, item_id: 3 }]);
    expect(tap).toHaveBeenCalledWith(Feature.PairingSplitPick);
  });

  // R-0970
  it("groups the entries under their opinion when several opinions hold several", () => {
    const { screen, shown } = look(
      people([
        mother(1, 2, "Julia's mother"),
        mother(1, 3, "Anthony's mother"),
        mother(2, 2, "Jim's first wife", "male"),
        mother(2, 5, "Jim's ex-wife", "male"),
      ]),
    );
    screen.choices(screen.pairings[0]);
    expect(shown[0]).toContain("Take which entry out?");
    expect(shown[0].match(/class="pv-label">opinion \d</g)).toHaveLength(2);
    expect(shown[0].match(/data-split=/g)).toHaveLength(4);
  });

  // R-0970
  it("offers no split when no opinion holds several entries and nothing is picked", () => {
    const { screen } = look(people([mother(1, 2, "Jim's first wife"), mother(2, 2, "Jim's ex-wife")]));
    expect(screen.controls(screen.pairings[0])).toContain('id="pr-split" type="button" disabled>');
  });
});
