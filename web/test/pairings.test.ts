import { describe, expect, it, vi } from "vitest";

vi.mock("../src/api", async (real) => ({
  ...(await real<typeof import("../src/api")>()),
  split: vi.fn(async () => ({ items: [], deleted: [] })),
  cut: vi.fn(async () => ({ session: "S", vote_opened_at: "2026-10-28T03:49:00" })),
  items: vi.fn(async () => []),
  records: vi.fn(async () => []),
}));
vi.mock("../src/track", async (real) => ({
  ...(await real<typeof import("../src/track")>()),
  tap: vi.fn(),
}));

const { Pairings, Section, findable, joinList, lookOrder, mark, matches, nearest, yearText } = await import(
  "../src/pairings"
);
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

  // R-0972
  it("marks how sure a pairing is with one class per state, unset read as unsure", () => {
    expect(mark(item(1, ItemKind.Event, Confidence.Unsure))).toBe("mark c-unsure");
    expect(mark(item(2, ItemKind.Event, Confidence.Likely))).toBe("mark c-likely");
    expect(mark(item(3, ItemKind.Event, Confidence.Sure))).toBe("mark c-sure");
    expect(mark(item(4, ItemKind.Event, null))).toBe("mark c-unsure");
  });

  // R-0055, R-0963
  it("comes back to the pairing an address names, or to the one nearest it when a join took it away", () => {
    const pairings = [12, 30, 21].map((id) => toPairing(item(id, ItemKind.Event, null), new Map()));
    expect(nearest(pairings, 21)).toBe(2);
    expect(nearest(pairings, 29)).toBe(1);
    expect(nearest(pairings, 15)).toBe(0);
  });

  // R-0963
  it("is shut once the vote is open: nothing is drawn and the caller goes back to the agenda", async () => {
    const body = { innerHTML: "" };
    const screen = Object.assign(Object.create(Pairings.prototype), { live: false, screen: { body } });
    expect(await screen.open(7)).toBe(false);
    expect(screen.live).toBe(false);
    expect(body.innerHTML).toBe("");
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
    context: { tapped: () => false },
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

const told = (
  coding: number,
  id: number,
  said: number,
  event: Record<string, unknown>,
  number = said,
): Opinion =>
  ({
    coding_id: coding,
    item_id: id,
    person_name: "Ann",
    item: { kind: "shift", person: 1, ...event },
    line: { statement_id: said, who: "Ann", text: "", number },
  }) as unknown as Opinion;

const pairing = (id: number, opinions: Opinion[], kind = ItemKind.Event) =>
  toPairing({ id, item_kind: kind, status: ItemStatus.Disputed, opinions } as unknown as BallotItem, new Map());

describe("the join list on Patrick's look over the pairings", () => {
  const here = pairing(1, [told(1, 1, 20, { dateTime: "1995-01-01", title: "Moved away" })]);
  const before = pairing(2, [told(1, 2, 17, { dateTime: "2010-01-01", title: "Quit school" })]);
  const after = pairing(3, [told(2, 3, 23, { title: "Fights at home" })]);
  const far = pairing(4, [
    told(1, 4, 40, { dateTime: "2005-06-01", title: "Started drinking" }),
    told(2, 5, 41, { dateTime: "1990-01-01", title: "Drank", description: "a lot at the lake" }),
  ]);
  const early = pairing(5, [told(1, 6, 2, { dateTime: "1980-01-01", title: "Born" })]);
  const undated = pairing(6, [told(1, 7, 60, { dateTime: "1900-01-01", title: "Sick" })]);
  const person = pairing(7, [{ coding_id: 1, item_id: 9, item: { id: 9, name: "Ann" } } as Opinion], ItemKind.Person);
  const all = [far, undated, here, after, early, person, before];

  // R-0974
  it("lists first the pairings within three lines of this one's passage in the conversation's order, then the rest by earliest year, the undated last, each once", () => {
    const list = joinList(here, all);
    const ids = (section: keyof typeof list) => list[section].map((one) => one.item.id);
    expect(ids(Section.Near)).toEqual([2, 3]);
    expect(ids(Section.All)).toEqual([5, 4]);
    expect(ids(Section.Undated)).toEqual([6]);
    const listed = Object.values(list).flat().map((one) => one.item.id);
    expect(new Set(listed).size).toBe(listed.length);
    expect(listed).not.toContain(1);
    expect(listed).not.toContain(7);
  });

  // R-0974
  it("measures the same part of the conversation in the cut's lines, not its statement numbers, which skip", () => {
    const sleep = pairing(11, [told(1, 11, 6, { title: "Sleep problems began" }, 1)]);
    const ski = pairing(12, [told(1, 12, 12, { title: "Up before ski races" }, 4)]);
    const later = pairing(13, [told(1, 13, 14, { title: "Fights at home" }, 9)]);
    const list = joinList(ski, [sleep, ski, later]);
    expect(list[Section.Near].map((one) => one.item.id)).toEqual([11]);
    expect(list[Section.Undated].map((one) => one.item.id)).toEqual([13]);
  });

  // R-0974
  it("gives the year a pairing's boxes give, or the range when they give different years, and nothing for a stand-in", () => {
    expect(yearText(here)).toBe("1995");
    expect(yearText(far)).toBe("1990–2005");
    expect(yearText(undated)).toBe("");
  });

  // R-0974
  it("finds a pairing by the words of any of its boxes, the people named and a year", () => {
    const found = findable(far);
    expect(matches(found, "lake")).toBe(true);
    expect(matches(found, "ann 1990")).toBe(true);
    expect(matches(found, "STARTED drink")).toBe(true);
    expect(matches(found, "school")).toBe(false);
    expect(matches(findable(person), "ann")).toBe(true);
  });
});
