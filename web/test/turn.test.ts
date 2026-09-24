import { describe, expect, it } from "vitest";
import { toolLine, ToolName } from "../src/tools";
import { ViewKind } from "../src/types";

describe("what a tool call says in plain words", () => {
  // R-0186
  it("says added when the call makes something", () => {
    expect(toolLine(ToolName.EditPerson, { name: "Dad" })).toBe("Added Dad");
  });

  // R-0186
  it("says changed when the call names what it is editing", () => {
    expect(toolLine(ToolName.EditPerson, { id: 3, name: "Dad" })).toBe("Changed Dad");
  });

  // R-0186
  it("names an event by its words and its date, as the record list says it", () => {
    expect(
      toolLine(ToolName.EditEvent, { description: "moved out", date: "1994-06-01" }),
    ).toBe("Added moved out, Jun 1994");
    expect(toolLine(ToolName.EditEvent, { description: "born", date: "1994" })).toBe(
      "Added born, 1994",
    );
  });

  // R-0186
  it("falls back to what kind of thing it is", () => {
    expect(toolLine(ToolName.EditPairBond, { person_a: 1, person_b: 2 })).toBe(
      "Added a couple",
    );
  });

  // R-0478
  it("says what the coach looked at", () => {
    expect(toolLine(ToolName.ReadPeople, {})).toBe("Looked at people");
    expect(toolLine(ToolName.ReadChanges, {})).toBe("Looked at recent changes");
  });

  // R-0478
  it("says what the coach showed", () => {
    expect(toolLine(ToolName.Show, { kind: ViewKind.Triangle })).toBe("Showed a triangle");
    expect(toolLine(ToolName.Show, { kind: ViewKind.Span })).toBe(
      "Showed a stretch of time",
    );
  });

});
