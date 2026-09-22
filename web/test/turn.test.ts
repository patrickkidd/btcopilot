import { describe, expect, it } from "vitest";
import { toolLine, ToolName } from "../src/tools";

describe("what a tool call says in plain words", () => {
  it("says added when the call makes something", () => {
    expect(toolLine(ToolName.EditPerson, { name: "Dad" })).toBe("Added Dad");
  });

  it("says changed when the call names what it is editing", () => {
    expect(toolLine(ToolName.EditPerson, { id: 3, name: "Dad" })).toBe("Changed Dad");
  });

  it("names an event by its words and its date", () => {
    expect(
      toolLine(ToolName.EditEvent, { description: "moved out", dateTime: "1994-06-01" }),
    ).toBe("Added moved out, 1994-06-01");
  });

  it("falls back to what kind of thing it is", () => {
    expect(toolLine(ToolName.EditPairBond, { person_a: 1, person_b: 2 })).toBe(
      "Added a couple",
    );
  });

  it("says nothing for reads and for showing the picture", () => {
    expect(toolLine(ToolName.ReadPeople, {})).toBeNull();
    expect(toolLine(ToolName.Show, { kind: "triangle" })).toBeNull();
  });

  it("says nothing for a tool it does not know", () => {
    expect(toolLine("invented", {})).toBeNull();
  });
});
