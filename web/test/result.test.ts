import { expect, it } from "vitest";
import { arow } from "../src/result";

// R-0869
it("names a differing event by who, what and when and says which variable went up", () => {
  const said = arow({
    review_item_id: 1,
    item_kind: "event",
    label: "Rose · Death · Feb 2011",
    room: "symptom: up",
    coach: "symptom: down · anxiety: same",
    reason: null,
  });
  expect(said).toContain("<span>Rose · Death · Feb 2011</span>");
  expect(said).toContain("the room: symptom up");
  expect(said).toContain("the AI: symptom down · anxiety same");
  expect(said).not.toMatch(/: up|: down|: same/);
});
