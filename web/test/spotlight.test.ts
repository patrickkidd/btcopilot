import { describe, expect, it } from "vitest";
import {
  Certainty,
  ROWS,
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

describe("the words a moment says about itself", () => {
  it("a date the record is sure of says its month", () => {
    expect(dateText("1996-06-15", Certainty.Certain)).toBe("Jun 1996");
  });

  it("a date it only guessed says its year and nothing more", () => {
    expect(dateText("1996-06-15", Certainty.Approximate)).toBe("1996");
  });

  it("the person is named only when the record is not about them", () => {
    expect(words("2001-03-01", Certainty.Certain, "Ada", "Ada", "Moved out")).toBe(
      "Mar 2001 · Moved out",
    );
    expect(words("2001-03-01", Certainty.Certain, "Ben", "Ada", "Moved out")).toBe(
      "Mar 2001 · Ben · Moved out",
    );
  });

  it("a long line wraps onto a second row at a space", () => {
    expect(wrap2("the winter everybody stopped speaking", 20)).toEqual([
      "the winter everybody",
      "stopped speaking",
    ]);
  });

  it("a word too long to break is cut rather than left hanging", () => {
    const [first] = wrap2("x".repeat(40), 20);
    expect(first).toHaveLength(20);
  });

  it("clip leaves short text alone and marks what it cuts", () => {
    expect(clip("short", 10)).toBe("short");
    expect(clip("a much longer line", 10).endsWith("…")).toBe(true);
  });
});

describe("the spotlight: dense and sparse", () => {
  it("dots shrink as the record gets busier", () => {
    expect(dotRadius(6)).toBe(4.5);
    expect(dotRadius(20)).toBe(3.5);
    expect(dotRadius(45)).toBe(2.6);
    expect(dotRadius(200)).toBe(1.8);
  });

  it("what the coach did not name recedes only when it named something", () => {
    expect(baseOpacity(6, 0)).toBe(1);
    expect(baseOpacity(6, 2)).toBe(0.35);
    expect(baseOpacity(60, 0)).toBe(0.6);
  });

  it("three named moments take one row each, in time order", () => {
    const laid = rows(
      [
        { id: 3, x: 300, text: "third" },
        { id: 1, x: 40, text: "first" },
        { id: 2, x: 150, text: "second" },
      ],
      16,
      374,
    );
    expect(laid.map((r) => r.id)).toEqual([1, 2, 3]);
    expect(laid.map((r) => r.row)).toEqual([0, 1, 2]);
    expect(laid.length).toBeLessThanOrEqual(ROWS.length);
  });

  it("a moment near the right edge writes its words to the left instead", () => {
    const [row] = rows([{ id: 1, x: 366, text: "at the very end" }], 16, 374);
    expect(row.align).toBe("right");
    expect(row.left).toBeLessThan(366);
  });

  it("more named moments than rows keeps the first three", () => {
    const laid = rows(
      Array.from({ length: 6 }, (_, i) => ({ id: i, x: 20 + i * 50, text: "x" })),
      16,
      374,
    );
    expect(laid).toHaveLength(3);
  });

  it("every tap zone is at least the 44px floor and holds its own moments", () => {
    const marks = Array.from({ length: 60 }, (_, i) => ({
      id: i,
      x: 16 + (i * 358) / 59,
    }));
    const zoned = zones(marks, 16, 374);
    expect(zoned.every((z) => z.width >= ZONE)).toBe(true);
    expect(zoned.reduce((n, z) => n + z.marks.length, 0)).toBe(60);
  });

  it("a single moment still gets a zone", () => {
    expect(zones([{ x: 200 }], 16, 374)).toHaveLength(1);
  });

  it("a tap steps through the moments under it, then lets go", () => {
    const inZone = [7, 8, 9];
    expect(cycle(inZone, null)).toBe(7);
    expect(cycle(inZone, 7)).toBe(8);
    expect(cycle(inZone, 9)).toBeNull();
    expect(cycle(inZone, 99)).toBe(7);
  });
});
