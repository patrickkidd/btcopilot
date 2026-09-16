import { describe, expect, it, vi } from "vitest";
import type { FinishedTask } from "../src/types";

vi.stubGlobal("window", { BOOTSTRAP: { user: { coder: true } } });

const { finishedRow, wayIn } = await import("../src/task");

describe("wayIn", () => {
  it("offers the card to a coder whether or not a task is open", () => {
    expect(wayIn(true)).toBe("Your coding task");
  });

  it("offers nothing to a reader who does no coding", () => {
    expect(wayIn(false)).toBeNull();
  });
});

const done = (ratified: boolean): FinishedTask => ({
  coding_id: 3,
  cut_id: 8,
  title: "Marcus's conversation up to Sep 4",
  detail: ratified ? "ratified Sep 18" : "done Sep 12",
  ratified,
});

describe("finishedRow", () => {
  it("makes a ratified row a way in to the result", () => {
    const row = finishedRow(done(true));
    expect(row).toContain('data-result="8"');
    expect(row).toContain("opens");
    expect(row).toContain("sn-chev");
  });

  it("leaves a row the room has not ratified as a faint record", () => {
    const row = finishedRow(done(false));
    expect(row).not.toContain("data-result");
    expect(row).not.toContain("sn-chev");
    expect(row).toContain("done Sep 12");
  });
});
