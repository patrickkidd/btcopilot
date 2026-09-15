import { describe, expect, it, vi } from "vitest";

vi.stubGlobal("window", { BOOTSTRAP: { user: { coder: true } } });

const { wayIn } = await import("../src/task");

describe("wayIn", () => {
  it("offers the card to a coder whether or not a task is open", () => {
    expect(wayIn(true)).toBe("Your coding task");
  });

  it("offers nothing to a reader who does no coding", () => {
    expect(wayIn(false)).toBeNull();
  });
});
