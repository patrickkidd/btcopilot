import { describe, expect, it, vi } from "vitest";
import { TaskKind, type FinishedTask, type Tasks } from "../src/types";

vi.stubGlobal("window", { BOOTSTRAP: { user: { coder: true } } });

const found: { tasks: Tasks; help: boolean; seen: number | null } = {
  tasks: { task: null, done: [] },
  help: false,
  seen: null,
};
const saved: object[] = [];
vi.mock("../src/api", () => ({
  tasks: async () => found.tasks,
  preferences: async () => ({ how_it_works: found.help, task_card_seen: found.seen }),
  setPreferences: async (body: object) => saved.push(body),
}));

const { cardDue, finishedRow, landing, OneTask } = await import("../src/task");
const { Place } = await import("../src/place");

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

describe("how the coding task is explained", () => {
  // R-0869
  it("says the app writes onto the family diagram, never into the record", async () => {
    found.help = true;
    const html = await screenFor({ task: open, done: [] });
    found.help = false;
    expect(html).toContain("The app writes what you type onto the family diagram for you.");
    expect(html).not.toMatch(/\brecord\b/);
    expect(html).toContain("A cut is the part of one conversation");
  });
});

describe("the task card on opening the app", () => {
  // R-0944
  it("opens once for a cut the coder has not seen, and notes it", async () => {
    found.tasks = { task: open, done: [] };
    found.seen = null;
    saved.length = 0;
    expect(await cardDue()).toBe(true);
    expect(saved).toEqual([{ task_card_seen: 9 }]);
  });

  // R-0944
  it("stays on the chat for a cut already seen, or no cut at all", async () => {
    saved.length = 0;
    found.tasks = { task: open, done: [] };
    found.seen = 9;
    expect(await cardDue()).toBe(false);
    found.tasks = { task: null, done: history };
    found.seen = null;
    expect(await cardDue()).toBe(false);
    expect(saved).toEqual([]);
  });

  // R-0944
  it("opens again when a new cut is on the agenda", async () => {
    found.tasks = { task: { ...open, cut_id: 10 }, done: [] };
    found.seen = 9;
    expect(await cardDue()).toBe(true);
  });

  // R-0944
  it("lands a reload on the card's own address on the chat once the cut was seen", async () => {
    saved.length = 0;
    found.tasks = { task: open, done: [] };
    found.seen = 9;
    expect(await landing(Place.Task)).toBe(Place.Chat);
    expect(await landing(Place.Account)).toBe(Place.Account);
    expect(saved).toEqual([]);
  });

  // R-0944
  it("opens the card where it landed for a cut not yet seen, noting it first", async () => {
    saved.length = 0;
    found.tasks = { task: open, done: [] };
    found.seen = null;
    expect(await landing(Place.Task)).toBe(Place.Task);
    expect(saved).toEqual([{ task_card_seen: 9 }]);
    found.seen = 9;
    expect(await landing(Place.Chat)).toBe(Place.Chat);
  });
});
