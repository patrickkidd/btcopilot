import { beforeEach, describe, expect, it, vi } from "vitest";
import { token } from "../src/chips";
import { face } from "../src/chat";
import { EMPTY, Questions, questionsHtml } from "../src/questions";
import { toolLine, ToolName } from "../src/tools";
import {
  ChipKind,
  ChipTone,
  InteractionKind,
  ItemKind,
  QuestionKind,
  type AskedQuestion,
} from "../src/types";

const NOW = new Date("2026-09-24T12:00:00");

const asked = (
  id: string,
  kind: QuestionKind,
  text: string,
  day: string,
  open = true,
): AskedQuestion => ({
  id,
  text,
  kind,
  open,
  asked_at: day,
  asked_in: { discussion_id: 7, statement_id: 70 },
});

const FAMILY = [
  asked("q1", QuestionKind.Fact, "When did your uncle Abel leave the farm?", "2026-09-02"),
  asked("q2", QuestionKind.Thought, "What does your sister do when she is worried?", "2026-09-02"),
  asked("q3", QuestionKind.Fact, "Who raised your mother after 1950?", "2026-09-20"),
  asked("q4", QuestionKind.Thought, "Why might the letters matter now?", "2026-09-20"),
  asked("q5", QuestionKind.Fact, "Where was Abel born?", "2026-09-21", false),
];

/** What the tab says, tags stripped, in the order it says it. */
const words = (html: string) => html.replace(/<[^>]+>/g, "\n").split("\n").filter(Boolean);

describe("the questions tab", () => {
  // R-0006, R-0485
  it("lists only the open questions, food for thought before facts to find", () => {
    const said = words(questionsHtml(FAMILY, NOW));
    expect(said).not.toContain("Where was Abel born?");
    expect(said).toEqual([
      "Food for thought",
      "Why might the letters matter now?",
      "Asked Sunday ›",
      "What does your sister do when she is worried?",
      "Asked Sep 2 ›",
      "Facts to find",
      "Who raised your mother after 1950?",
      "Asked Sunday ›",
      "When did your uncle Abel leave the farm?",
      "Asked Sep 2 ›",
    ]);
  });

  // R-0006, R-0485
  it("leaves out a section with nothing in it", () => {
    const said = words(questionsHtml(FAMILY.filter((q) => q.kind === QuestionKind.Fact), NOW));
    expect(said).not.toContain("Food for thought");
    expect(said[0]).toBe("Facts to find");
  });

  // R-0006
  it("says one sentence when nothing is open", () => {
    expect(words(questionsHtml([FAMILY[4]], NOW))).toEqual([EMPTY]);
    expect(words(questionsHtml([], NOW))).toEqual([EMPTY]);
  });

  // R-0007, R-0485
  it("shows no count and no state anywhere", () => {
    const html = questionsHtml(FAMILY, NOW);
    const said = words(html).filter((w) => !w.startsWith("Asked ") && !w.includes("?"));
    expect(said.join(" ")).not.toMatch(/\d/);
    expect(html.toLowerCase()).not.toMatch(/\b(held|resolved|declined|closed|open|answered)\b/);
  });

  // R-0006
  it("keeps the day of a question whose session is gone, as words that go nowhere", () => {
    const gone = { ...FAMILY[0], asked_in: null };
    const html = questionsHtml([gone], NOW);
    expect(html).toContain('<span class="qwhen">Asked Sep 2</span>');
    expect(html).not.toContain('<button type="button" class="qwhen"');
  });
});

/** Just enough of a list for the tab's own taps: the clicks it listens for, and
 * rows that know which question they hold. */
function drawer() {
  const heard: Record<string, (e: unknown) => void> = {};
  const body = {
    innerHTML: "",
    scrollTop: 0,
    addEventListener: (kind: string, fn: (e: unknown) => void) => {
      heard[kind] = fn;
    },
  } as unknown as HTMLElement;
  const handlers = {
    onChip: vi.fn(),
    onAsked: vi.fn(),
    onDismissed: vi.fn(),
    record: vi.fn(),
  };
  const list = new Questions(body, handlers);
  list.show(FAMILY);
  const click = async (id: string, on: string) => {
    const row = { dataset: { q: id } };
    const target = { closest: (sel: string) => (sel === ".qrow" || sel === on ? row : null) };
    heard.click({ target });
    // the tap's own requests settle before anything is looked at
    await new Promise((settle) => setTimeout(settle, 0));
  };
  return { handlers, click };
}

const fetched = vi.fn(async () => ({ ok: true, status: 204, text: async () => "" }));

beforeEach(() => {
  fetched.mockClear();
  vi.stubGlobal("fetch", fetched);
  vi.stubGlobal("document", { querySelector: () => null });
});

describe("tapping a question", () => {
  // R-0072
  it("puts it in the message box as a reference in its own words and sends nothing", async () => {
    const { handlers, click } = drawer();
    await click("q4", ".chip");
    const chip = handlers.onChip.mock.calls[0][0];
    expect(chip).toEqual({
      kind: ChipKind.Question,
      target: "q4",
      label: "Why might the letters matter now?",
      tone: ChipTone.Ask,
      bare: false,
    });
    expect(face(chip.kind, chip.label)).toBe("Why might the letters matter now?");
    expect(token(chip.kind, chip.target)).toBe("[[question:q4]]");
    expect(fetched).not.toHaveBeenCalled();
  });

  // R-0077
  it("is recorded as a chip tap on that question", async () => {
    const { handlers, click } = drawer();
    await click("q4", ".chip");
    expect(handlers.record).toHaveBeenCalledWith(InteractionKind.ChipTap, ItemKind.Question, "q4");
  });

  // R-0006
  it("on the day it was asked goes to where it was asked", async () => {
    const { handlers, click } = drawer();
    await click("q3", "button.qwhen");
    expect(handlers.onAsked).toHaveBeenCalledWith({ discussion_id: 7, statement_id: 70 });
    expect(handlers.onChip).not.toHaveBeenCalled();
  });
});

describe("dismissing a question", () => {
  // R-0077
  it("stores it as put away by the reader, records the tap, and reads the record again", async () => {
    const { handlers, click } = drawer();
    await click("q1", ".fs-act");
    expect(fetched).toHaveBeenCalledTimes(1);
    const [url, init] = fetched.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/app/questions/q1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({
      state: "resolved",
      outcome: "declined_by_user",
    });
    expect(handlers.record).toHaveBeenCalledWith(InteractionKind.Dismiss, ItemKind.Question, "q1");
    expect(handlers.onDismissed).toHaveBeenCalled();
  });
});

const WORDS = "Who were your grandfather's brothers?";
const line = (
  name: ToolName,
  args: Record<string, unknown>,
  refusal: string | null = null,
) => toolLine({ name, args, names: { it: WORDS }, refusal });

describe("what a question tool call says in plain words", () => {
  // R-0478
  it("keeps a question for later without saying its words", () => {
    const held = { text: WORDS, kind: "fact", state: "held" };
    expect(toolLine({ name: ToolName.AddQuestion, args: held, names: {}, refusal: null })).toBe(
      "Kept a question for later",
    );
    expect(
      toolLine({
        name: ToolName.AddQuestion,
        args: { ...held, asked_in: 12 },
        names: {},
        refusal: "It said where a question was asked without asking it.",
      }),
    ).toBe("Tried to keep a question for later. It said where a question was asked without asking it.");
  });

  // R-0478
  it("says a question asked was added to your questions", () => {
    expect(line(ToolName.AddQuestion, { text: WORDS, kind: "fact", state: "asked" })).toBe(
      `Added “${WORDS}” to your questions`,
    );
    expect(line(ToolName.SetQuestion, { id: "q2", version: 3, state: "asked" })).toBe(
      `Added “${WORDS}” to your questions`,
    );
  });

  // R-0478
  it("says how a closed question ended", () => {
    const closed = (outcome: string) =>
      line(ToolName.SetQuestion, { id: "q2", version: 3, state: "resolved", outcome });
    expect(closed("fact")).toBe(`Closed “${WORDS}”: the answer is in the record`);
    expect(closed("answered")).toBe(`Closed “${WORDS}”: you answered it`);
    expect(closed("unknown")).toBe(`Closed “${WORDS}”: you don't know`);
    expect(closed("declined_in_chat")).toBe(`Closed “${WORDS}”: you'd rather not say`);
    expect(closed("let_go")).toBe(`Let go of “${WORDS}”`);
  });

  // R-0478
  it("closes a question kept for later without saying its words", () => {
    const kept = (outcome: string, refusal: string | null = null) =>
      toolLine({
        name: ToolName.SetQuestion,
        args: { id: "q6", version: 4, state: "resolved", outcome },
        names: {},
        refusal,
      });
    expect(kept("let_go")).toBe("Let go of a question kept for later");
    expect(kept("fact")).toBe("Closed a question kept for later: the answer is in the record");
    expect(kept("answered")).toBe("Closed a question kept for later: you answered it");
    expect(kept("unknown")).toBe("Closed a question kept for later: you don't know");
    expect(kept("declined_in_chat")).toBe("Closed a question kept for later: you'd rather not say");
    expect(kept("declined_by_user", "Only you can dismiss a question.")).toBe(
      "Tried to close a question kept for later. Only you can dismiss a question.",
    );
    expect(toolLine({ name: ToolName.ReadQuestions, args: {}, names: {}, refusal: null })).toBe(
      "Looked at questions",
    );
  });

  // R-0478
  it("says it looked at the questions", () => {
    expect(line(ToolName.ReadQuestions, {})).toBe("Looked at questions");
  });

  // R-0478
  it("says a refused call was tried, and why", () => {
    expect(
      line(
        ToolName.AddQuestion,
        { text: WORDS, kind: "fact", state: "asked" },
        "That question is already there.",
      ),
    ).toBe(`Tried to add “${WORDS}” to your questions. That question is already there.`);
    expect(
      line(
        ToolName.SetQuestion,
        { id: "q2", version: 3, state: "resolved", outcome: "declined_by_user" },
        "Only you can dismiss a question.",
      ),
    ).toBe(`Tried to close “${WORDS}”. Only you can dismiss a question.`);
    expect(
      line(
        ToolName.SetQuestion,
        { id: "q2", version: 3, state: "resolved", outcome: "answered" },
        "That question is already closed.",
      ),
    ).toBe(`Tried to close “${WORDS}”. That question is already closed.`);
  });
});
