import { describe, expect, it, vi } from "vitest";
import { Failed } from "../src/api";
import type { TimelineEvent } from "../src/types";

const said: string[] = [];
vi.mock("../src/toast", () => ({ toast: (text: string) => said.push(text) }));
const refusal: { error: Error | null } = { error: null };
vi.mock("../src/api", async (original) => ({
  ...(await original<typeof import("../src/api")>()),
  saveEvent: async () => {
    if (refusal.error) throw refusal.error;
  },
}));

const { Direction, EventKind, MAX_FIELD_LINES, Relationship, grownHeight, moved, save } =
  await import("../src/editor");

describe("grownHeight", () => {
  // R-0458
  it("takes the text's own height until ten lines, then stays", () => {
    const line = 22;
    const pad = 22;
    expect(grownHeight(line * 3 + pad, line, pad)).toBe(line * 3 + pad);
    expect(grownHeight(line * 40 + pad, line, pad)).toBe(
      line * MAX_FIELD_LINES + pad,
    );
  });
});

const shift = (fields: Partial<TimelineEvent> = {}): Partial<TimelineEvent> => ({
  kind: EventKind.Shift,
  description: "Shift that moved nothing",
  symptom: null,
  anxiety: null,
  functioning: null,
  relationship: null,
  ...fields,
});

describe("moved", () => {
  // R-0037
  it("refuses a shift with no variable and no relationship move", () => {
    expect(moved(shift())).toBe(false);
  });

  // R-0037
  it("takes a variable that stayed the same, or a relationship", () => {
    expect(moved(shift({ anxiety: Direction.Same }))).toBe(true);
    expect(moved(shift({ relationship: Relationship.Cutoff }))).toBe(true);
  });
});

describe("save", () => {
  it("keeps the editor open and says what the record wants when it refuses", async () => {
    said.length = 0;
    refusal.error = new Failed(
      400,
      "POST /app/events: event 7 is a shift with no variable and no relationship move: say which way",
    );
    const done = vi.fn();
    await save(null, shift(), done);
    expect(done).not.toHaveBeenCalled();
    expect(said).toEqual(["say which way"]);
  });
});
