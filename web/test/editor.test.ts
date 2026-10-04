import { describe, expect, it, vi } from "vitest";
import { Failed } from "../src/api";
import { EventKind, type TimelineEvent } from "../src/types";

const refusal: { error: Error | null } = { error: null };
vi.mock("../src/api", async (original) => ({
  ...(await original<typeof import("../src/api")>()),
  saveEvent: async () => {
    if (refusal.error) throw refusal.error;
  },
}));

const { Direction, MAX_FIELD_LINES, Relationship, grownHeight, moved, save, unsaid } =
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
  title: "Moved nothing",
  description: "Shift that moved nothing",
  symptom: null,
  anxiety: null,
  functioning: null,
  relationship: null,
  ...fields,
});

describe("unsaid", () => {
  // R-0681
  it("refuses a noted event or a shift with no title of 2 to 4 words, as the record does", () => {
    const noted = { kind: EventKind.Noted, description: "Took a room over the store" };
    expect(unsaid(noted)).toBe('A noted event needs a title of 2 to 4 words, such as "Lost his job".');
    expect(unsaid(shift({ title: "", symptom: Direction.Up }))).toBe('A shift event needs a title of 2 to 4 words, such as "Lost his job".');
    expect(unsaid({ ...noted, title: "Took a room over the store" })).toBe('A noted event needs a title of 2 to 4 words, such as "Lost his job".');
    expect(unsaid({ ...noted, title: "Moved out" })).toBeNull();
    expect(unsaid({ kind: EventKind.Noted, title: "Moved out" })).toBe("A noted event needs a few words saying what happened.");
    expect(unsaid({ kind: EventKind.Birth })).toBeNull();
  });
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
  // R-0453
  it("keeps the editor open and hands it the record's plain words whole", async () => {
    refusal.error = new Failed(400, "POST /app/events", "The end date is before the start date.");
    const done = vi.fn();
    const refused = vi.fn();
    await save(null, shift(), done, refused);
    expect(done).not.toHaveBeenCalled();
    expect(refused).toHaveBeenCalledWith("The end date is before the start date.");
  });
});
