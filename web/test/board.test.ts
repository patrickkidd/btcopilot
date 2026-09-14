import { describe, expect, it } from "vitest";
import { castOfSteps, movesIn } from "../src/board";
import type { TimelineEvent } from "../src/types";

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
  it("keeps every moment, not only the ones with a mark to draw", () => {
    expect(movesIn(stretch).map((s) => s.event.id)).toEqual([27, 24, 23]);
  });

  it("puts the people a bond ties on stage with the one who shifted", () => {
    expect(castOfSteps(movesIn(stretch))).toEqual([20, 25]);
  });

  it("keeps a moment that names nobody, so the walk still steps past it", () => {
    expect(movesIn([event({ id: 9, person: null })]).map((s) => s.cast)).toEqual([
      [],
    ]);
  });
});
