import { describe, expect, it } from "vitest";
import { MAX_RUN, MIN_GAP, MarkKind, merge, span } from "../src/layout";

const at = (...xs: number[]) => xs.map((x, i) => ({ id: i + 1, x }));

describe("the resting strip, sparse and dense", () => {
  it("one event still gets a span wide enough to draw a line on", () => {
    const { min, max } = span([2014]);
    expect(max - min).toBeGreaterThan(1);
    expect(min).toBeLessThan(2014);
    expect(max).toBeGreaterThan(2014);
  });

  it("three events over forty years keep the ends off the edge", () => {
    const { min, max } = span([1981, 2003, 2021]);
    expect(min).toBeLessThan(1981);
    expect(max).toBeGreaterThan(2021);
    // the padding is a fraction of the span, not a fixed decade
    expect(min).toBeGreaterThan(1975);
    expect(max).toBeLessThan(2027);
  });

  it("an empty record still has a span", () => {
    expect(span([]).max).toBeGreaterThan(span([]).min);
  });

  it("far-apart events stay one dot each", () => {
    const slots = merge(at(10, 120, 300));
    expect(slots).toHaveLength(3);
    expect(slots.every((s) => s.kind === MarkKind.Dot)).toBe(true);
  });

  it("a lone event next to a dense run is never swallowed by a count", () => {
    const slots = merge(at(10, 200, 203, 206));
    expect(slots).toHaveLength(2);
    expect(slots[0].kind).toBe(MarkKind.Dot);
    expect(slots[1].kind).toBe(MarkKind.Count);
    expect(slots[1].ids).toEqual([2, 3, 4]);
  });

  it("sixty events across a phone width become a handful of count marks", () => {
    const marks = Array.from({ length: 60 }, (_, i) => ({
      id: i,
      x: 26 + (i * 300) / 59,
    }));
    const slots = merge(marks);
    expect(slots.length).toBeGreaterThan(2);
    expect(slots.length).toBeLessThan(10);
    expect(slots.reduce((n, s) => n + s.ids.length, 0)).toBe(60);
    expect(slots.every((s) => s.kind === MarkKind.Count)).toBe(true);
  });

  it("no count mark stretches so far that it stops saying when", () => {
    const marks = Array.from({ length: 60 }, (_, i) => ({ id: i, x: 26 + i * 5 }));
    for (const slot of merge(marks))
      if (slot.kind === MarkKind.Count)
        expect(slot.to - slot.from).toBeLessThanOrEqual(MAX_RUN);
  });

  it("every event ends up in exactly one mark, in time order", () => {
    const slots = merge(at(300, 10, 12, 150));
    const ids = slots.flatMap((s) => s.ids);
    expect(new Set(ids).size).toBe(4);
    expect(slots.map((s) => s.x)).toEqual([...slots.map((s) => s.x)].sort((a, b) => a - b));
  });

  it("marks exactly one gap apart stay separate dots", () => {
    expect(merge(at(100, 100 + MIN_GAP))).toHaveLength(2);
    expect(merge(at(100, 100 + MIN_GAP - 1))).toHaveLength(1);
  });
});
