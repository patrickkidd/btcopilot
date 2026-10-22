import { expect, it } from "vitest";
import { Access, diagramLabel, type Diagram } from "../src/types";

const diagram = (over: Partial<Diagram>): Diagram => ({
  id: 1,
  name: "Free Diagram",
  session_count: 0,
  last_activity: null,
  free: false,
  owned: true,
  access: Access.Own,
  owner: "Patrick Stinson",
  owner_name: "Patrick",
  person_id: 1,
  ...over,
});

// R-0888
it("a diagram someone else owns carries their first name after its name, one of the user's own does not", () => {
  expect(diagramLabel(diagram({ owned: false, person_id: null }))).toBe("Free Diagram · Patrick");
  expect(diagramLabel(diagram({}))).toBe("Free Diagram");
  expect(diagramLabel(diagram({ owned: false, owner_name: null }))).toBe("Free Diagram");
});
