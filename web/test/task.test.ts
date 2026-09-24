import { describe, expect, it, vi } from "vitest";
import { TaskKind, type FinishedTask, type Tasks } from "../src/types";

vi.stubGlobal("window", { BOOTSTRAP: { user: { coder: true } } });

const found: { tasks: Tasks } = { tasks: { task: null, done: [] } };
vi.mock("../src/api", () => ({ tasks: async () => found.tasks }));

const { finishedRow, OneTask, wayIn } = await import("../src/task");

describe("wayIn", () => {
  // R-0311
  it("offers the card to a coder whether or not a task is open", () => {
    expect(wayIn(true)).toBe("Your coding task");
  });

  // R-0311
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
  // R-0344
  it("makes a ratified row a way in to the result", () => {
    const row = finishedRow(done(true));
    expect(row).toContain('data-result="8"');
    expect(row).toContain("opens");
    expect(row).toContain("sn-chev");
  });

  // no ruling
  it("leaves a row the room has not ratified as a faint record", () => {
    const row = finishedRow(done(false));
    expect(row).not.toContain("data-result");
    expect(row).not.toContain("sn-chev");
    expect(row).toContain("done Sep 12");
  });
});

/** The coder's screen as the card draws it, for what the server says is open
 * and finished. */
const screenFor = async (tasks: Tasks): Promise<string> => {
  found.tasks = tasks;
  const body = { innerHTML: "", addEventListener: () => {} } as unknown as HTMLElement;
  await new OneTask(body, { onStart: () => {}, onResult: () => {} }).load();
  return body.innerHTML;
};

const open = {
  kind: TaskKind.Code,
  cut_id: 9,
  coding_id: null,
  meeting_date: "2026-09-25",
  title: "Code Marcus's conversation",
  detail: "up to Sep 20",
  ready: true,
};

const history = [done(true), { ...done(false), coding_id: 4, cut_id: 7 }, { ...done(true), coding_id: 5, cut_id: 6 }];

describe("the coder's screen", () => {
  // R-0265
  it("shows the one task now as a single card with a single button", async () => {
    const html = await screenFor({ task: open, done: history });
    expect(html.match(/class="row tkcard/g)).toHaveLength(1);
    expect(html.match(/class="addbtn"/g)).toHaveLength(1);
    expect(html).toContain("Code Marcus&#39;s conversation");
  });

  // R-0265
  it("puts what is finished after the task, never before it", async () => {
    const html = await screenFor({ task: open, done: history });
    expect(html.indexOf("tkcard")).toBeGreaterThanOrEqual(0);
    expect(html.indexOf("tkcard")).toBeLessThan(html.indexOf("done before"));
    expect(html.match(/plrow done/g)).toHaveLength(3);
  });

  // R-0265
  it("never draws the past as a to-do list to tick or pick from", async () => {
    const html = await screenFor({ task: null, done: history });
    expect(html).not.toContain("<input");
    expect(html).not.toContain("addbtn");
    expect(html).not.toMatch(/<(ul|ol|li)\b/);
    expect(html).toContain("Nothing is on the agenda to code yet.");
  });
});
