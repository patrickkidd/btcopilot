import { describe, expect, it } from "vitest";
import { arrange, draw, Sex, Tie, type Cast, type Frame, type Layout } from "../src/diagram";
import { family as wholeFamily, Told } from "../src/snapshots";
import { timeline } from "./whitlock";

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
  anxious: [],
  assoc: {},
  until: 2000,
});

const frame = (L: Layout, t: number): Frame => ({
  t,
  bonds: L.bonds.map((b) => ({ ...b, fresh: false, hot: false })),
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
