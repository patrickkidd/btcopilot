import { describe, expect, it, vi } from "vitest";

vi.stubGlobal("window", {
  BOOTSTRAP: { user: { username: "c", admin: false, pro: false, coder: true } },
});

const { Coding } = await import("../src/coding");

/** The sheet that asks a coder to finish, drawn by the screen's own code on
 * stand-ins for the elements it writes into. */
function finishSheet(): string {
  const node = () => ({ innerHTML: "", hidden: true, offsetWidth: 0, classList: { add() {} } });
  const screen = {
    thread: { session: "Marcus", cut_day: "Sep 4", meeting_date: "2026-09-25" },
    sheet: node(),
    scrim: node(),
  };
  Coding.prototype.confirm.call(screen as unknown as InstanceType<typeof Coding>);
  return screen.sheet.innerHTML;
}

describe("the finish sheet", () => {
  // R-0315
  it.fails("names the other coders' versions as opinions", () => {
    // Known defect: the sheet still says the other coders' takes.
    const words = finishSheet();
    expect(words).toContain("Finish coding?");
    expect(words).not.toMatch(/\btakes?\b/);
    expect(words).toMatch(/\bopinions\b/);
  });
});
