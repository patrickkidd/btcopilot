import { describe, expect, it } from "vitest";
import { DateCertainty } from "../src/certainty";
import {
  PIC_H,
  ROWS,
  ROW_H,
  WIRE,
  YEAR_TOP,
  ZONE,
  baseOpacity,
  clip,
  cycle,
  dateText,
  dotRadius,
  rows,
  words,
  wrap2,
  zones,
} from "../src/spotlight";

const PHONE = 390;
/** The picked dot's radius, and the height of the year written under it. */
const PICKED_R = 7;
const YEAR_H = 13;

describe("the words a moment says about itself", () => {
  // R-0009
  it("a date the record is sure of says its month", () => {
    expect(dateText("1996-06-15", DateCertainty.Certain)).toBe("Jun 1996");
  });

  // R-0009
  it("a date it only guessed says its year and nothing more", () => {
    expect(dateText("1996-06-15", DateCertainty.Approximate)).toBe("1996");
  });

  // R-0457
  it("a label names everyone it is about, the speaker included", () => {
    const say = (who: string) =>
      words("2001-03-01", DateCertainty.Certain, who, "bonded \u00b7 together for a year");
    expect(say("Patrick & Emily")).toBe("Patrick & Emily \u00b7 bonded \u00b7 together for a year");
    expect(say("Emily & Patrick")).toBe("Emily & Patrick \u00b7 bonded \u00b7 together for a year");
    expect(say("Patrick")).toBe("Patrick \u00b7 bonded \u00b7 together for a year");
    expect(say("")).toBe("bonded \u00b7 together for a year");
  });

  // R-0235
  it("a long line wraps onto a second row at a space", () => {
    expect(wrap2("the winter everybody stopped speaking", 20)).toEqual([
      "the winter everybody",
      "stopped speaking",
    ]);
  });

  // R-0181
  it("a word too long to break is cut rather than left hanging", () => {
    const [first] = wrap2("x".repeat(40), 20);
    expect(first).toHaveLength(20);
  });

  // R-0181
  it("clip leaves short text alone and marks what it cuts", () => {
    expect(clip("short", 10)).toBe("short");
    expect(clip("a much longer line", 10).endsWith("…")).toBe(true);
  });
});

describe("the spotlight: dense and sparse", () => {
  // R-0402
  it("dots shrink as the record gets busier", () => {
    expect(dotRadius(6)).toBe(4.5);
    expect(dotRadius(20)).toBe(3.5);
    expect(dotRadius(45)).toBe(2.6);
    expect(dotRadius(200)).toBe(1.8);
  });

  // R-0001
  it("what the coach did not name recedes only when it named something", () => {
    expect(baseOpacity(6, 0)).toBe(1);
    expect(baseOpacity(6, 2)).toBe(0.35);
    expect(baseOpacity(60, 0)).toBe(0.6);
  });

  // R-0134
  it("with more named moments than rows, the first and last take one row each", () => {
    const laid = rows(
      [
        { id: 3, x: 300, text: "third" },
        { id: 1, x: 40, text: "first" },
        { id: 2, x: 150, text: "second" },
      ],
      16,
      374,
    );
    expect(laid.map((r) => r.id)).toEqual([1, 3]);
    expect(laid.map((r) => r.row)).toEqual([0, 1]);
    expect(laid.length).toBeLessThanOrEqual(ROWS.length);
  });

  // R-0181
  it("a moment near the right edge writes its words to the left instead", () => {
    const [row] = rows([{ id: 1, x: 366, text: "at the very end" }], 16, 374);
    expect(row.align).toBe("right");
    expect(row.left).toBeLessThan(366);
  });

  // R-0461
  it("a moment with no room for words keeps its row so its leader is drawn", () => {
    // two dots almost on top of each other at the right edge: the second has
    // nothing to write into, but the picture must still point at it
    const laid = rows(
      [
        { id: 1, x: 368, text: "the first one" },
        { id: 2, x: 370, text: "the second one" },
      ],
      16,
      374,
    );
    expect(laid.map((r) => r.id)).toEqual([1, 2]);
    expect(laid[1].text).toBe("");
    expect(laid[1].x).toBe(370);
  });


  // R-0103
  it("a dot alone has a whole thumb centred on it", () => {
    const [only] = zones([{ x: 200 }], PHONE);
    expect(only).toMatchObject({ left: 200 - ZONE / 2, width: ZONE });
  });

  // R-0103
  it("a dot at the edge of the picture keeps a whole thumb, reaching inward", () => {
    const [edge] = zones([{ x: 16 }], PHONE);
    expect(edge).toMatchObject({ left: 0, width: ZONE });
  });

  // R-0402
  it("two dots nearer than a thumb split the space between them at the midpoint", () => {
    const [a, b] = zones([{ x: 200 }, { x: 220 }], PHONE);
    expect(a.left + a.width).toBe(210);
    expect(b.left).toBe(210);
    expect([a.left, b.left + b.width]).toEqual([200 - ZONE / 2, 220 + ZONE / 2]);
  });

  // R-0402
  it("dots drawn over one another share one target", () => {
    const zoned = zones([{ x: 200 }, { x: 203 }], PHONE);
    expect(zoned.map((z) => z.marks.length)).toEqual([2]);
  });

  // R-0402
  it("on a crowded line every tap lands on the target of the nearest dot", () => {
    const marks = Array.from({ length: 60 }, (_, i) => ({ x: 16 + (i * 358) / 59 }));
    const zoned = zones(marks, PHONE);
    expect(zoned.reduce((n, z) => n + z.marks.length, 0)).toBe(60);
    zoned.forEach((zone, i) => {
      const next = zoned[i + 1];
      if (next) expect(zone.left + zone.width).toBeCloseTo(next.left, 6);
      for (const mark of zone.marks)
        expect(mark.x >= zone.left && mark.x <= zone.left + zone.width).toBe(true);
    });
  });

  // R-0103
  it("the picked dot stands clear of the words above it and the year clears the controls", () => {
    const words = ROWS[1] + ROW_H;
    expect(WIRE - PICKED_R - words).toBeGreaterThanOrEqual(10);
    expect(PIC_H - (YEAR_TOP + YEAR_H)).toBeGreaterThanOrEqual(6);
  });

  // R-0402
  it("a tap steps through the moments under it, then comes back to the first", () => {
    const inZone = [7, 8, 9];
    expect(cycle(inZone, null)).toBe(7);
    expect(cycle(inZone, 7)).toBe(8);
    expect(cycle(inZone, 9)).toBe(7);
    expect(cycle(inZone, 99)).toBe(7);
  });
});
