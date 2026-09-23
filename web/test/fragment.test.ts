import { describe, expect, it } from "vitest";
import { fitName, render } from "../src/fragment";
import { cases, plain } from "./fragmentcases";

const shapes = (svg: string) => svg.match(/class="frag-shape"/g)?.length ?? 0;
const lines = (svg: string) => svg.match(/class="frag-line"/g)?.length ?? 0;
const dashed = (svg: string) => svg.match(/stroke-dasharray/g)?.length ?? 0;
const asks = (svg: string) => svg.match(/class="frag-ask"/g)?.length ?? 0;
const names = (svg: string) =>
  [...svg.matchAll(/class="frag-name"[^>]*>([^<]*)</g)].map((m) => m[1]);
const paths = (svg: string) =>
  [...svg.matchAll(/class="frag-line" d="([^"]*)"/g)].map((m) => m[1]);
const triangles = (svg: string) =>
  [...svg.matchAll(/d="M ([-\d.]+) ([-\d.]+) L ([-\d.]+) ([-\d.]+) L ([-\d.]+) ([-\d.]+) Z"/g)].map(
    (m) => m.slice(1).map(Number),
  );

const named = (key: string) => cases.find((c) => c.key === key)!.fragment;

describe("every hostile case draws", () => {
  for (const one of cases) {
    // R-0324, R-0325
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
  // R-0324
  it("draws the middle person twice and everyone else once", () => {
    const svg = render(plain());
    expect(shapes(svg)).toBe(7);
  });

  // R-0324
  it("draws a square for a man, a circle for a woman", () => {
    const svg = render(plain());
    expect(svg).toContain("a 0.5 0.5 0 1 0");
  });

  // R-0325
  it("puts no question inside the shape of a person with no gender recorded", () => {
    const svg = render(named("11"));
    expect(asks(svg)).toBe(0);
    expect(svg).not.toContain(">?<");
  });

  // R-0325
  it("points the miscarriage triangle up", () => {
    const [, apexY, , baseY] = triangles(render(named("7")))[0];
    expect(apexY).toBeLessThan(baseY);
  });

  // R-0325
  it("draws the same triangle for a miscarriage and an abortion", () => {
    const svg = render(named("8"));
    const two = triangles(svg);
    expect(two.length).toBe(2);
    const shifted = two.map((t) =>
      t.map((v, i) => (i % 2 === 0 ? v - t[0] : v)).join(" "),
    );
    expect(shifted[0]).toBe(shifted[1]);
  });

  // R-0324
  it("crosses a deceased person, and ticks the corners when an age shows", () => {
    expect(lines(render(named("6")))).toBeGreaterThan(lines(render(plain())));
  });
});

describe("the bond", () => {
  // R-0324
  it("is a squared U with right angles", () => {
    expect(render(plain())).toMatch(/d="M [-\d.]+ [-\d.]+ V [-\d.]+ H [-\d.]+ V [-\d.]+"/);
  });

  // R-0325
  it("dashes a bond that is only bonded and solidifies one that ended", () => {
    expect(dashed(render(named("3")))).toBeGreaterThan(0);
    expect(dashed(render(plain()))).toBe(0);
  });

  // R-0325
  it("draws one straight mark for a separation and two for a divorce", () => {
    const svg = render(named("2"));
    const before = new Set(paths(render(plain())));
    const marks = paths(svg).filter((d) => !before.has(d));
    expect(marks).toHaveLength(2);
    for (const d of marks) {
      const [, x1, , x2] = d.match(/M ([-\d.]+) ([-\d.]+) L ([-\d.]+) ([-\d.]+)/)!;
      expect(x1).toBe(x2);
    }
  });

  // R-0325
  it("puts the man on the left even when the woman is older", () => {
    const olderWoman = plain();
    olderWoman.events = olderWoman.events.map((e) =>
      e.kind === "birth" && e.person === 2 ? { ...e, dateTime: "1920-01-01" } : e,
    );
    const svg = render(olderWoman);
    const squares = [...svg.matchAll(/d="M ([-\d.]+) -2.5 H/g)].map((m) => Number(m[1]));
    expect(Math.min(...squares)).toBeLessThan(0);
  });

  // R-0325
  it("puts the earlier bond left of the later one, overlapping side to side", () => {
    const svg = render(named("3"));
    const partners = names(svg);
    expect(partners.indexOf("Delphine")).toBeLessThan(partners.indexOf("Nadine"));
  });

  // R-0325
  it("draws a partner nobody named like anybody else, with the generic name", () => {
    const svg = render(named("4"));
    expect(names(svg)).toContain("Marcus's");
    expect(shapes(svg)).toBe(shapes(render(plain())));
  });

  // R-0325
  it("draws a parent nobody named like anybody else", () => {
    expect(shapes(render(named("5")))).toBe(shapes(render(plain())));
  });
});

describe("children", () => {
  // R-0325
  it("hangs each child from the crossbar, oldest on the left", () => {
    const order = names(render(plain()));
    expect(order.indexOf("Corinne")).toBeLessThan(order.indexOf("Theo"));
  });

  // R-0325
  it("dashes an adopted child's line", () => {
    expect(dashed(render(named("10")))).toBe(1);
  });

  // R-0325
  it("joins twins with one shared line and one riser", () => {
    expect(lines(render(named("9")))).toBe(lines(render(plain())) + 3);
  });

  // R-0325
  it("leaves a child whose parents' bond is absent standing alone", () => {
    const svg = render(named("12"));
    expect(asks(svg)).toBe(0);
    expect(lines(svg)).toBe(lines(render(plain())));
    expect(shapes(svg)).toBe(shapes(render(plain())) + 1);
  });
});

describe("the name under the shape", () => {
  // R-0325
  it("keeps the given name only", () => {
    expect(fitName("Corinne Whitlock", 0.25)).toBe("Corinne");
  });

  // R-0325
  it("cuts a long name with an ellipsis", () => {
    const out = fitName("Corinnebartholomewinaverylongname1234", 0.25);
    expect(out.endsWith("…")).toBe(true);
  });

  // R-0325
  it("keeps combining marks with their letter", () => {
    expect(names(render(named("15"))).join(" ")).toContain("Ко́ринна");
  });
});
