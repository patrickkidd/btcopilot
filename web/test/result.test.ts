import { expect, it } from "vitest";
import { arow } from "../src/result";

// R-0869
it("names a differing event by its title and says which variable went up", () => {
  const said = arow({
    review_item_id: 1,
    item_kind: "event",
    label: "Death",
    room: "symptom: up",
    coach: "symptom: down · anxiety: same",
    reason: null,
  });
  expect(said).toContain("<span>Death</span>");
  expect(said).toContain("the room: symptom up");
  expect(said).toContain("the AI: symptom down · anxiety same");
  expect(said).not.toMatch(/: up|: down|: same/);
});
