import { beforeEach, expect, it, vi } from "vitest";
import { Concept, conceptLinks, conceptsOf } from "../src/concepts";

const signIn = (coder: boolean) =>
  vi.stubGlobal("window", { BOOTSTRAP: { user: { username: "c", coder } } });

beforeEach(() => signIn(true));

// R-0541
it("names the pages of every code the versions carry, once each", () => {
  const found = conceptsOf([
    { anxiety: "up", relationship: "conflict" },
    { anxiety: "down", relationship: "overfunctioning" },
    { relationship: "underfunctioning", symptom: null },
  ]);
  expect(found).toEqual([Concept.Anxiety, Concept.Conflict, Concept.Reciprocity]);
});

// R-0541
it("names nothing for a person or a bond, and a move with no page", () => {
  expect(conceptsOf([{ name: "Mom" }, { relationship: "fusion" }])).toEqual([]);
  expect(conceptLinks([])).toBe("");
});

// R-0541
it("links each page in a tab of its own, and the index when asked", () => {
  const html = conceptLinks([Concept.TowardAway], true);
  expect(html).toContain(
    '<a href="/app/theory/toward-away" target="_blank" rel="noopener">toward and away</a>',
  );
  expect(html).toContain('<a href="/app/theory" target="_blank" rel="noopener">');
});

// R-0541, R-0567
it("renders no link for anyone who is not a coder", () => {
  signIn(false);
  expect(conceptLinks([Concept.Anxiety], true)).toBe("");
});
