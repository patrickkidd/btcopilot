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
  owner_username: "patrick@example.com",
  person_id: 1,
  addressed: true,
  ...over,
});

// R-0888
it("every diagram in the list names its owner: you on your own, else their first name, else their account name before its @", () => {
  expect(diagramOwner(diagram({}))).toBe("you");
  expect(diagramOwner(diagram({ owned: false, person_id: null }))).toBe("Patrick");
  expect(diagramOwner(diagram({ owned: false, owner_name: null }))).toBe("patrick");
  expect(diagramOwner(diagram({ owned: false, owner_name: null, owner_username: "ana" }))).toBe("ana");
});
