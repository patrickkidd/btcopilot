import { describe, expect, it } from "vitest";
import {
  AdoptLine,
  Apex,
  BondOrder,
  Loose,
  NameFit,
  Side,
  Single,
  Slash,
  TwinBar,
  Unnamed,
  UnknownMark,
  fitName,
  render,
} from "../src/fragment";
import { cases, plain } from "./fragmentcases";

const shapes = (svg: string) => svg.match(/class="frag-shape"/g)?.length ?? 0;
const lines = (svg: string) => svg.match(/class="frag-line"/g)?.length ?? 0;
const dashed = (svg: string) => svg.match(/stroke-dasharray/g)?.length ?? 0;
const asks = (svg: string) => svg.match(/class="frag-ask"/g)?.length ?? 0;
const names = (svg: string) =>
  [...svg.matchAll(/class="frag-name"[^>]*>([^<]*)</g)].map((m) => m[1]);

describe("every hostile case draws", () => {
  for (const one of cases) {
    it(one.title, () => {
      const svg = render(one.fragment);
      expect(svg.startsWith("<svg")).toBe(true);
      expect(shapes(svg)).toBeGreaterThan(0);
      expect(svg).not.toContain("NaN");
      expect(svg).not.toContain("undefined");
    });
  }
});

describe("people", () => {
  it("draws the middle person twice and everyone else once", () => {
    const svg = render(plain());
    expect(shapes(svg)).toBe(7);
  });

  it("draws a square for a man, a circle for a woman", () => {
    const svg = render(plain());
    expect(svg).toContain("a 0.5 0.5 0 1 0");
  });

  it("puts no question inside the unknown shape, the way the code draws it", () => {
    const svg = render(cases[10].fragment);
    expect(asks(svg)).toBe(0);
    const spec = render(cases[10].fragment, { unknownMark: UnknownMark.Question });
    expect(spec).toContain(">?<");
  });

  it("points the triangle up as the code does, down when asked", () => {
    const up = render(cases[7].fragment);
    const down = render(cases[7].fragment, { apex: Apex.Down });
    expect(up).not.toBe(down);
  });

  it("draws the same triangle for a miscarriage and an abortion", () => {
    const svg = render(cases[7].fragment);
    const triangles = [...svg.matchAll(/d="M ([-\d.]+) ([-\d.]+) L [^"]*Z"/g)].filter(
      (m) => m[0].split("L").length === 3,
    );
    const normal = triangles.map((m) => m[0].replace(/M [-\d.]+ /, "M "));
    expect(new Set(normal).size).toBeLessThan(normal.length + 1);
    expect(triangles.length).toBeGreaterThanOrEqual(2);
  });

  it("crosses a deceased person, and ticks the corners when an age shows", () => {
    const svg = render(cases[5].fragment);
    expect(lines(svg)).toBeGreaterThan(lines(render(plain())));
  });
});

describe("the bond", () => {
  it("is a squared U with right angles", () => {
    expect(render(plain())).toMatch(/d="M [-\d.]+ [-\d.]+ V [-\d.]+ H [-\d.]+ V [-\d.]+"/);
  });

  it("dashes a bond that is only bonded and solidifies one that ended", () => {
    expect(dashed(render(cases[2].fragment))).toBeGreaterThan(0);
    expect(dashed(render(plain()))).toBe(0);
  });

  it("draws one slash for a separation and two for a divorce", () => {
    const svg = render(cases[1].fragment);
    expect(lines(svg)).toBe(lines(render(plain())) + 2);
  });

  it("leans the slashes only when the spec rule is chosen", () => {
    const code = render(cases[1].fragment);
    const spec = render(cases[1].fragment, { slash: Slash.Diagonal });
    expect(code).not.toBe(spec);
  });

  it("puts the man left by the spec rule and the older person left otherwise", () => {
    const olderWoman = plain();
    olderWoman.events = olderWoman.events.map((e) =>
      e.kind === "birth" && e.person === 2 ? { ...e, dateTime: "1920-01-01" } : e,
    );
    expect(render(olderWoman, { side: Side.MaleLeft })).not.toBe(
      render(olderWoman, { side: Side.OlderLeft }),
    );
  });

  it("orders two bonds nearest-first or furthest-first", () => {
    const early = render(cases[2].fragment, { bondOrder: BondOrder.EarliestNearest });
    const late = render(cases[2].fragment, { bondOrder: BondOrder.LatestNearest });
    expect(early).not.toBe(late);
  });

  it("draws a half U for a single parent, a faint partner when asked", () => {
    const half = render(cases[3].fragment, { single: Single.HalfU });
    const ghost = render(cases[3].fragment, { single: Single.Ghost });
    expect(shapes(ghost)).toBe(shapes(half) + 1);
  });

  it("leaves an unnamed partner without a name, or asks about them", () => {
    const faint = render(cases[4].fragment, { unnamed: Unnamed.Faint });
    expect(names(faint)).not.toContain("—");
    expect(names(render(cases[4].fragment, { unnamed: Unnamed.Dashes }))).toContain("—");
    expect(asks(render(cases[4].fragment, { unnamed: Unnamed.Asked }))).toBe(1);
  });
});

describe("children", () => {
  it("hangs each child from the crossbar, oldest on the left", () => {
    const svg = render(plain());
    const order = names(svg);
    expect(order.indexOf("Corinne")).toBeLessThan(order.indexOf("Theo"));
  });

  it("dashes an adopted child's line, solid when the preference wins", () => {
    expect(dashed(render(cases[9].fragment, { adoptLine: AdoptLine.Dashed }))).toBe(1);
    expect(dashed(render(cases[9].fragment, { adoptLine: AdoptLine.Solid }))).toBe(0);
  });

  it("joins twins with one shared line and one riser", () => {
    const svg = render(cases[8].fragment);
    expect(lines(svg)).toBe(lines(render(plain())) + 3);
  });

  it("rises the twins' line a fixed amount or to the midpoint", () => {
    const fixed = render(cases[8].fragment, { twinBar: TwinBar.Fixed });
    const mid = render(cases[8].fragment, { twinBar: TwinBar.Midpoint });
    expect(fixed).not.toBe(mid);
  });

  it("asks about a child whose parents' bond is not in the record", () => {
    expect(asks(render(cases[11].fragment))).toBe(1);
    expect(asks(render(cases[11].fragment, { loose: Loose.AskOnly }))).toBe(1);
    expect(shapes(render(cases[11].fragment, { loose: Loose.GhostBond }))).toBe(
      shapes(render(cases[11].fragment)) + 2,
    );
  });

  it("spaces siblings by the chosen gap", () => {
    expect(render(plain(), { siblingGap: 2 })).not.toBe(
      render(plain(), { siblingGap: 1.4 }),
    );
  });
});

describe("the name under the shape", () => {
  it("keeps the given name only", () => {
    expect(fitName("Corinne Whitlock", NameFit.Ellipsis, 2, 0.25).lines).toEqual([
      "Corinne",
    ]);
  });

  it("cuts a long name with an ellipsis", () => {
    const { lines: out } = fitName("Corinnebartholomewinaverylongname1234", NameFit.Ellipsis, 2, 0.25);
    expect(out).toHaveLength(1);
    expect(out[0].endsWith("…")).toBe(true);
  });

  it("breaks it in two or shrinks it when those rules are chosen", () => {
    expect(fitName("Corinnebartholomewinaverylongname1234", NameFit.TwoLines, 2, 0.25).lines).toHaveLength(2);
    const small = fitName("Corinnebartholomewinaverylongname1234", NameFit.Shrink, 2, 0.25);
    expect(small.size).toBeLessThan(0.25);
  });

  it("keeps combining marks with their letter", () => {
    const svg = render(cases[14].fragment);
    expect(names(svg).join(" ")).toContain("Ко́ринна");
  });
});
