import { describe, expect, it } from "vitest";
import { StepKind, steps } from "../src/turn";
import { toolLine, ToolName } from "../src/tools";
import { TurnEventKind, ViewKind, type Reply, type TurnEvent } from "../src/types";

const reply = (events: TurnEvent[]): Reply => ({
  statement: "Got it.",
  statement_id: 7,
  views: null,
  events,
  turn_id: "t1",
  discussion_id: 2,
});

const call = (name: string, args: Record<string, unknown> = {}): TurnEvent => ({
  type: TurnEventKind.ToolCall,
  name,
  args,
});

const patch = (): TurnEvent => ({
  type: TurnEventKind.RecordPatch,
  deltas: [],
  turn_id: "t1",
});

describe("what the page does with one turn", () => {
  it("says what the coach did and attaches what it made, without a separate re-read", () => {
    expect(steps(reply([call(ToolName.EditPerson, { name: "Dad" }), patch()]))).toEqual([
      { kind: StepKind.Note, line: "Added Dad", made: [] },
    ]);
  });

  it("re-reads once for a run of edits, not once each", () => {
    const out = steps(reply([patch(), patch(), patch()]));
    expect(out).toEqual([{ kind: StepKind.Reload }]);
  });

  it("keeps the order the coach worked in", () => {
    const out = steps(
      reply([
        call(ToolName.EditPerson, { name: "Dad" }),
        patch(),
        call(ToolName.Show),
        { type: TurnEventKind.View, view: { kind: ViewKind.Span, start: "1990-01-01", end: "1999-12-31" } },
      ]),
    );
    expect(out.map((s) => s.kind)).toEqual([StepKind.Note, StepKind.Show]);
  });

  it("does nothing for a turn where the coach only read and talked", () => {
    expect(steps(reply([call(ToolName.ReadPeople), call(ToolName.ReadEvents)]))).toEqual(
      [],
    );
  });
});

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
