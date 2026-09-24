import { describe, expect, it } from "vitest";
import { BOARD_H, board, castOfSteps, ellipse, movesIn } from "../src/board";
import { Move } from "../src/moves";
import type { Person, TimelineEvent } from "../src/types";

/** The owner's 2006 stretch: a pair bond formed, the same bond ended, and a
 * shift. Only the shift carries a mark the move language draws, and the board
 * used to show only that one, so two of his three moments were invisible
 * (REVIEW_LOG 70). */
const event = (over: Partial<TimelineEvent>): TimelineEvent => ({
  id: 0,
  label: "",
  sentence: "",
  person_name: "Patrick",
  person: 20,
  dateTime: null,
  endDateTime: null,
  dateCertainty: null,
  kind: null,
  description: null,
  notes: null,
  location: null,
  symptom: null,
  anxiety: null,
  functioning: null,
  relationship: null,
  relationshipTargets: [],
  relationshipTriangles: [],
  spouse: null,
  child: null,
  ...over,
});

const stretch = [
  event({ id: 27, kind: "bonded", dateTime: "2004-06-01", spouse: 25 }),
  event({ id: 24, kind: "separated", dateTime: "2005-12-01", spouse: 25 }),
  event({ id: 23, kind: "shift", dateTime: "2006-01-01", symptom: "up", anxiety: "up" }),
];

describe("the moments a cluster puts on the board", () => {
  // R-0292
  it("keeps every moment, not only the ones with a mark to draw", () => {
    expect(movesIn(stretch).map((s) => s.event.id)).toEqual([27, 24, 23]);
  });

  // R-0136
  it("puts the people a bond ties on stage with the one who shifted", () => {
    expect(castOfSteps(movesIn(stretch))).toEqual([20, 25]);
  });

  // R-0292
  it("keeps a moment that names nobody, so the walk still steps past it", () => {
    expect(movesIn([event({ id: 9, person: null })]).map((s) => s.cast)).toEqual([
      [],
    ]);
  });
});

const people = (n: number): Person[] =>
  Array.from({ length: n }, (_, i) => ({ id: i + 1, name: `P${i + 1}`, gender: null }) as Person);

describe("where the board stands its people", () => {
  // R-0135
  it("puts everyone on one simple ring, evenly spaced from the top", () => {
    const { figures } = ellipse(people(8), 390);
    const cx = figures[0].x;
    const cy = (figures[0].y + figures[4].y) / 2;
    const rx = figures[2].x - cx;
    const ry = cy - figures[0].y;
    for (const [i, f] of figures.entries()) {
      expect(((f.x - cx) / rx) ** 2 + ((f.y - cy) / ry) ** 2).toBeCloseTo(1, 5);
      const angle = Math.atan2((f.y - cy) / ry, (f.x - cx) / rx);
      expect(Math.cos(angle - (-Math.PI / 2 + (i / 8) * Math.PI * 2))).toBeCloseTo(1, 5);
    }
  });

  // R-0173
  it("takes only the height its people need", () => {
    const three = ellipse(people(3), 390).height;
    const four = ellipse(people(4), 390).height;
    expect(three).toBeLessThan(four);
    expect(four).toBeLessThanOrEqual(BOARD_H);
    expect(ellipse(people(1), 390).height).toBeLessThan(three);
  });
});

describe("what the board writes", () => {
  const cast = [
    { id: 20, name: "Ada", gender: "female" },
    { id: 21, name: "Ben", gender: "male" },
  ] as Person[];
  const walled = event({
    id: 5,
    person_name: "Ada",
    label: "she stopped calling",
    dateTime: "1993-04-01",
    relationship: Move.Cutoff,
    relationshipTargets: [21],
  });
  const drawn = (events: TimelineEvent[], at = 0) =>
    board(movesIn(events), at, cast, events, 390);
  const texts = (svg: string) => [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map((m) => m[1]);

  // R-0161
  it("says what the person reported under the board, not the move's name", () => {
    const { caption } = drawn([walled]);
    expect(caption).toContain("she stopped calling");
    expect(caption).not.toContain(Move.Cutoff);
  });

  // R-0161
  it("writes no move's name anywhere on the drawing", () => {
    const words = texts(drawn([walled]).svg).join(" ");
    for (const name of Object.values(Move)) expect(words).not.toContain(name);
  });

  // R-0162
  it("writes the move's date once, under its dot, and not in the words", () => {
    const { svg, caption } = drawn([walled]);
    expect(texts(svg).filter((t) => t.includes("1993"))).toHaveLength(1);
    expect(caption).not.toContain("1993");
  });

  // R-0177
  it("draws the move being played last on the years line, with nothing behind it", () => {
    const close = [0, 1, 2].map((i) =>
      event({ ...walled, id: 30 + i, dateTime: `1993-0${4 + i}-01` }),
    );
    for (const at of [0, 1, 2]) {
      const axis = /<g class="axis">(.*)<\/g>/.exec(drawn(close, at).svg)![1];
      const now = /<circle class="ax-now" cx="([^"]*)"/.exec(axis)!;
      // after it only its own date is written
      expect(axis.slice(axis.indexOf(now[0]))).toMatch(/^<circle class="ax-now"[^>]*\/><text[^>]*>[^<]*<\/text>$/);
      // and the only other things standing where it stands are the dots
      const there = [...axis.matchAll(new RegExp(`<(\\w+) class="([^"]*)" c?x1?="${now[1]}"`, "g"))];
      const shapes = there.filter((m) => m[1] !== "text").map((m) => m[2]);
      expect(shapes.filter((c) => !c.startsWith("ax-dot") && c !== "ax-now")).toEqual([]);
    }
  });
});
