import { describe, expect, it } from "vitest";
import { arrange, bar, crosses, draw, Mark, Sex, Tie, VIEW, type Box, type Cast, type Frame, type Layout } from "../src/diagram";
import { FIELD, Move } from "../src/moves";
import { family as wholeFamily, Told } from "../src/snapshots";
import { CORINNE, DELPHINE, MARCUS, timeline } from "./whitlock";

/** The whole family stepped through dates: lines before their date. */

const cast = (): Cast => ({
  people: {
    a: { name: "Marcus Whitlock", g: Sex.Male, born: 1951 },
    b: { name: "Delphine Reyes", g: Sex.Female, born: 1953 },
    c: { name: "Corinne Whitlock", g: Sex.Female, born: 1975, you: true },
    d: { name: "Theo Whitlock", g: Sex.Male, born: 1979 },
  },
  bonds: [{ a: "a", b: "b", st: Tie.Married, married: true, from: 1970 }],
  kids: [{ of: ["a", "b"], kids: ["c", "d"] }],
  index: "c",
  marked: [],
  cross: [],
  words: {},
  moves: [],
  kin: [],
  places: [],
  anxious: [],
  assoc: {},
  until: 2000,
});

const frame = (L: Layout, t: number): Frame => ({
  t,
  bonds: L.bonds.map((b) => ({ ...b, fresh: 0, hot: false })),
  marks: [],
  died: new Set(),
  moves: [],
  kin: [],
  label: "",
});

const tie = (svg: string) => svg.match(/<path class="([^"]*)" data-bond="a\|b" d="([^"]*)"/)!.slice(1);
const kin = (svg: string) => [...svg.matchAll(/<path class="(kin[^"]*)" d="([^"]*)"/g)].map((m) => [m[1], m[2]]);

describe("a line before its date", () => {
  const L = arrange(cast());

  // R-0756
  it("fades a couple's line before their first dated event and each child's line before the birth, in the same place", () => {
    const [early, met, born] = [1960, 1970, 1976].map((t) => draw(L, frame(L, t)));
    expect(tie(early)[0]).toBe("tie yet");
    expect(tie(met)[0]).toBe("tie");
    expect(tie(early)[1]).toBe(tie(met)[1]);
    expect(kin(early).map(([c]) => c)).toEqual(["kin yet", "kin yet"]);
    expect(kin(born).map(([c]) => c)).toEqual(["kin", "kin yet"]);
    expect(kin(born).map(([, d]) => d)).toEqual(kin(early).map(([, d]) => d));
  });

  // R-0756
  it("draws a couple with no dated event plainly from the first step", () => {
    const c = cast();
    delete c.bonds[0].from;
    const M = arrange(c);
    expect(tie(draw(M, frame(M, 1900)))[0]).toBe("tie");
  });
});

// R-0742
it("shows a separation's slash only from its own date in the whole family", () => {
  const tl = timeline();
  const t = new Told(tl, wholeFamily(tl), true);
  const at = (id: number) => t.shot(t.told.snapshots.findIndex((s) => s.event_ids.includes(id))).svg;
  const slashes = (svg: string) => (svg.match(/class="slash[^"]*"/g) ?? []).length;
  expect(slashes(at(109))).toBe(0);
  expect(slashes(at(201))).toBe(1);
  expect(slashes(at(204))).toBe(2);
});

// R-0798
it("runs a move's rings in the whole family out to their full reach, and neither shrinks the picture nor moves anyone to keep them inside it", () => {
  const at = (kind: string) => {
    const tl = timeline();
    Object.assign(tl.events.find((e) => e.id === 131)!, { relationship: kind, relationshipTargets: [CORINNE] });
    const t = new Told(tl, wholeFamily(tl), true);
    return t.shot(t.told.snapshots.findIndex((s) => s.event_ids.includes(131))).svg;
  };
  const [rings, none] = [at(Move.Distance), at(Move.Conflict)];
  const reaches = [...rings.matchAll(/<circle class="fld[^"]*"[^>]*><animate attributeName="r" values="[\d.]+;([\d.]+)"/g)].map((m) => Number(m[1]));
  expect(reaches.length).toBeGreaterThan(0);
  expect(reaches.filter((r) => r !== FIELD)).toEqual([]);
  const box = (svg: string) => svg.match(/viewBox="([^"]*)"/)![1];
  expect(box(rings)).toBe(box(none));
  const places = (svg: string) => [...svg.matchAll(/<g class="p[^"]*" data-id="[^"]*">(<[^>]*>)/g)].map((m) => m[0]);
  expect(places(none).length).toBeGreaterThan(3);
  expect(places(rings)).toEqual(places(none));
});

// R-0756
it("fades a couple's line in the whole family until their first dated event", () => {
  const tl = timeline();
  const t = new Told(tl, wholeFamily(tl), true);
  const at = (id: number) => t.shot(t.told.snapshots.findIndex((s) => s.event_ids.includes(id))).svg;
  const line = (svg: string) => svg.match(new RegExp(`<path class="([^"]*)" data-bond="${MARCUS}\\|${DELPHINE}"`))![1];
  expect(line(at(103))).toBe("tie yet");
  expect(line(at(109))).toMatch(/^tie(?! yet)/);
});

/** Two stand-in families whose names once lay on a child's line and on
 * another name: a father with a second wife and a son by her, and three
 * generations with a granddaughter under the reader. */
const p = (name: string, g: Sex, born: number | null, you = false) => ({ name, g, born, you });
const wed = (a: string, b: string, from: number) => ({ a, b, st: Tie.Married, married: true, from });
const rest = { marked: [], cross: [], words: {}, moves: [], places: [], anxious: [] };
const remarried = (): Cast => ({
  ...rest,
  people: {
    f: p("Frank Abernathy", Sex.Male, 1920), h: p("Helen Abernathy", Sex.Female, 1922),
    g: p("George Lindqvist", Sex.Male, 1921), m: p("Mabel Lindqvist", Sex.Female, 1924),
    t: p("Tom Abernathy", Sex.Male, 1950), a: p("Ann Lindqvist", Sex.Female, 1952),
    l: p("Lucy Abernathy", Sex.Female, 1976, true), b: p("Ben Abernathy", Sex.Male, 1979),
    c: p("Carol Dunmore", Sex.Female, 1955), x: p("Max Abernathy", Sex.Male, 1990),
  },
  bonds: [wed("f", "h", 1945), wed("g", "m", 1947), wed("t", "a", 1974), wed("t", "c", 1988)],
  kids: [{ of: ["f", "h"], kids: ["t"] }, { of: ["g", "m"], kids: ["a"] }, { of: ["t", "a"], kids: ["l", "b"] }, { of: ["t", "c"], kids: ["x"] }],
  index: "l",
  kin: [{ k: Mark.Move, kind: Move.Cutoff, from: "l", to: "t" }],
  assoc: { f: "h", h: "f", g: "m", m: "g", t: "l", a: "g", l: "t", b: "t", c: "t", x: "t" },
  until: 1998,
});
const generations = (): Cast => ({
  ...rest,
  people: {
    n: p("Nora Halloran", Sex.Female, 1982, true), fr: p("Frank Halloran", Sex.Male, 1950), e: p("Elaine Halloran", Sex.Female, 1953),
    w: { ...p("Walter Halloran", Sex.Male, null), died: 1990 }, j: p("June Halloran", Sex.Female, null),
    hp: p("Harold Price", Sex.Male, null), r: p("Ruth Price", Sex.Female, null),
    s: p("Sean Halloran", Sex.Male, 1979), k: p("Kate Halloran", Sex.Female, 1986), d: p("Daniel Moreau", Sex.Male, null),
    li: p("Lily Moreau", Sex.Female, 2012), pe: p("Peter Halloran", Sex.Male, 1948), c: p("Carol Price", Sex.Female, 1956),
  },
  bonds: [wed("fr", "e", 1976), wed("w", "j", 1947), wed("hp", "r", 1945), wed("n", "d", 2009)],
  kids: [{ of: ["fr", "e"], kids: ["n", "s", "k"] }, { of: ["w", "j"], kids: ["fr", "pe"] }, { of: ["hp", "r"], kids: ["e", "c"] }, { of: ["n", "d"], kids: ["li"] }],
  index: "n",
  kin: [
    { k: Mark.Move, kind: Move.Distance, from: "n", to: "e" },
    { k: Mark.Move, kind: Move.Conflict, from: "n", to: "d" },
  ],
  assoc: { n: "e", fr: "w", e: "n", w: "j", j: "w", hp: "r", r: "hp", s: "fr", k: "fr", d: "n", li: "n", pe: "w", c: "hp" },
  until: 2019,
});

/** Every name that lies on another name, and every child's line that runs through a name. */
function clashes(L: Layout): string[] {
  const ids = Object.keys(L.P);
  const half = (id: string) => (L.P[id].you ? 0.6 : 0.5) * L.w;
  const on = (a: Box, b: Box) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
  const out: string[] = [];
  ids.forEach((a, i) => ids.slice(i + 1).forEach((b, j) => on(L.names[i], L.names[i + 1 + j]) && out.push(`${a} on ${b}`)));
  L.kids.forEach((k) => {
    const r = bar(L, { a: k.of[0], b: k.of[1] });
    k.kids.forEach((kid) => {
      const line: [[number, number], [number, number]] = [[L.x[kid], L.y[kid] - half(kid)], [Math.min(Math.max(L.x[kid], r.x0), r.x1), r.y]];
      ids.forEach((id, i) => crosses(line, L.names[i]) && out.push(`${kid}'s line through ${id}`));
    });
  });
  return out;
}

describe("names", () => {
  // R-0566, R-0744, R-0759
  it("never lie on a child's line, the picture scrolling rather than shrinking its people", () => {
    const L = arrange(remarried());
    expect(clashes(L)).toEqual([]);
    expect(L.w).toBe(44);
    expect(L.vw).toBeGreaterThan(VIEW);
  });

  // R-0566
  it("never lie on one another across rows", () => {
    expect(clashes(arrange(generations()))).toEqual([]);
  });
});
