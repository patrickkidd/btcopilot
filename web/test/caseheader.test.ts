import { expect, it } from "vitest";
import { subjectName } from "../src/caseview";
import { emptyTimeline, type Person, type Timeline } from "../src/types";

const family = (people: Partial<Person>[]): Timeline => ({ ...emptyTimeline(), people: people as Person[] });

it("the case report header names the person the case belongs to, not the diagram's owner", () => {
  // R-PENDING-387-2
  const tl = family([
    { id: 1, name: "Ivy", primary: true },
    { id: 2, name: "Ash" },
  ]);
  expect(subjectName(tl)).toBe("Ivy");
});

it("the header names no one while the person has only the placeholder name or none", () => {
  // R-PENDING-387-2
  expect(subjectName(family([{ id: 1, name: "User", primary: true }]))).toBeNull();
  expect(subjectName(family([{ id: 1, name: "Ash" }]))).toBeNull();
});
