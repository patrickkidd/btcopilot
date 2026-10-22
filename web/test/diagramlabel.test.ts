import { expect, it } from "vitest";
import { Access, diagramOwner, type Diagram } from "../src/types";

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
it("every diagram in the list names its owner's first name, the user's own included, and never an email", () => {
  expect(diagramOwner(diagram({ owned: false, person_id: null }))).toBe("Patrick");
  expect(diagramOwner(diagram({}))).toBe("Patrick");
  expect(diagramOwner(diagram({ owner_name: null, owner: "pat@example.com" }))).toBe("");
});
