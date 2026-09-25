import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { token } from "../src/chips";
import { PARTLY, questionsHtml } from "../src/questions";
import { toolLine, ToolName } from "../src/tools";
import {
  ChipKind,
  ChipTone,
  EvidenceKind,
  InteractionKind,
  ItemKind,
  QuestionKind,
  type AskedQuestion,
} from "../src/types";
import { drawer, fetched, sentAt } from "./drawer";

const NOW = new Date("2026-09-24T12:00:00");

const note = (
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
  evidence:
    kind === QuestionKind.Impression
      ? [
          { kind: EvidenceKind.Event, id: 14, label: "Moved to Tacoma" },
          { kind: EvidenceKind.Cluster, id: "c2", label: "The winter the mill shut" },
          { kind: EvidenceKind.Statement, id: 812, label: "You said, 2 Sep", discussion_id: 5, at: "2026-09-02" },
          { kind: EvidenceKind.Statement, id: 90, label: "a message no longer in the record", discussion_id: null, at: null },
        ]
      : [],
  pushback: null,
});

const IMPRESSION = "When things get tense, your uncle gets busy and your aunt goes quiet.";
const FAMILY = [
  note("q1", QuestionKind.Fact, "Where was your uncle born?", "2026-09-02"),
  note("i2", QuestionKind.Impression, IMPRESSION, "2026-09-20"),
  note("q3", QuestionKind.Thought, "What does your aunt do when she is worried?", "2026-09-02"),
  note("i4", QuestionKind.Impression, "You go quiet when the family fights.", "2026-09-21", false),
];

/** What the tab says, tags stripped, in the order it says it. */
const words = (html: string) => html.replace(/<[^>]+>/g, "\n").split("\n").filter(Boolean);

describe("impressions on the coach's tab", () => {
  // R-0006, R-0485
  it("the tab is From the coach, and impressions come after both kinds of question", () => {
    expect(readFileSync("index.html", "utf8")).toMatch(/id="tab-questions"[^>]*>From the coach</);
    const said = words(questionsHtml(FAMILY, NOW));
    expect(said.filter((w) => w.endsWith("thought") || w.endsWith("find") || w === "Impressions")).toEqual([
      "Food for thought",
      "Facts to find",
      "Impressions",
    ]);
  });

  // R-0006
  it("shows an impression's words, what it rests on and the day it was raised, and never one that did not fit", () => {
    const said = words(questionsHtml(FAMILY, NOW));
    expect(said.slice(said.indexOf("Impressions") + 1)).toEqual([
      IMPRESSION,
      "Based on:",
      "Moved to Tacoma",
      "The winter the mill shut",
      "You said, 2 Sep",
      "a message no longer in the record",
      "Raised Sunday ›",
      "⋯",
      "Doesn't fit",
      "Partly",
    ]);
    expect(said).not.toContain("You go quiet when the family fights.");
    // a message whose session is gone goes nowhere
    expect(questionsHtml(FAMILY, NOW)).toContain(
      '<span class="blabel">a message no longer in the record</span>',
    );
  });

  // R-0007
  it("shows no count and no state", () => {
    const said = words(questionsHtml(FAMILY.filter((q) => q.kind === QuestionKind.Impression), NOW)).filter((w) => !/^(Raised|You said)/.test(w));
    expect(said.join(" ")).not.toMatch(/\d/);
    expect(said.join(" ").toLowerCase()).not.toMatch(/\b(held|raised|resolved|revised|let go|open|closed)\b/);
  });
});

describe("tapping an impression", () => {
  // R-0072
  it("puts its words in the message box as a teal reference and sends nothing", async () => {
    const { handlers, click } = drawer(FAMILY);
    await click("i2", ".itext");
    const chip = handlers.onChip.mock.calls[0][0];
    expect(chip).toEqual({
      kind: ChipKind.Impression,
      target: "i2",
      label: IMPRESSION,
      tone: ChipTone.Data,
      bare: false,
    });
    expect(token(chip.kind, chip.target)).toBe("[[impression:i2]]");
    expect(handlers.record).toHaveBeenCalledWith(InteractionKind.ChipTap, ItemKind.Question, "i2");
    expect(fetched).not.toHaveBeenCalled();
    expect(handlers.say).not.toHaveBeenCalled();
  });

  // R-0072
  it("on what it rests on puts that in the message box, or opens the message it came from", async () => {
    const { handlers, click } = drawer(FAMILY);
    await click("i2", "[data-ev]", { ev: "0" });
    expect(handlers.onChip).toHaveBeenCalledWith({
      kind: ChipKind.Event,
      target: "14",
      label: "Moved to Tacoma",
      tone: ChipTone.Data,
      bare: false,
    });
    expect(handlers.record).toHaveBeenCalledWith(InteractionKind.ChipTap, ItemKind.Event, "14");
    await click("i2", "[data-ev]", { ev: "2" });
    expect(handlers.onAsked).toHaveBeenCalledWith({ discussion_id: 5, statement_id: 812 }, false);
    expect(fetched).not.toHaveBeenCalled();
  });
});

describe("pushing back on an impression", () => {
  // R-0077
  it("doesn't fit is stored, recorded, then said to the coach with the impression named", async () => {
    const { handlers, click } = drawer(FAMILY);
    await click("i2", ".nofit");
    expect(sentAt()).toEqual({
      url: "/app/questions/i2",
      method: "PATCH",
      body: { state: "resolved", outcome: "doesnt_fit" },
    });
    expect(handlers.record).toHaveBeenCalledWith(InteractionKind.DoesntFit, ItemKind.Question, "i2");
    expect(handlers.say).toHaveBeenCalledTimes(1);
    expect(handlers.say).toHaveBeenCalledWith("That doesn't fit: [[impression:i2]]");
    expect(fetched.mock.invocationCallOrder[0]).toBeLessThan(handlers.say.mock.invocationCallOrder[0]);
    expect(handlers.onDismissed).toHaveBeenCalled();
  });

  // R-0077, R-0073
  it("partly starts a reply in the message box and is only a push-back once that reply is sent", async () => {
    const { list, handlers, click } = drawer(FAMILY);
    await click("i2", ".partly");
    expect(handlers.onChip).toHaveBeenCalledWith(
      expect.objectContaining({ kind: ChipKind.Impression, target: "i2" }),
      " — partly, because ",
    );
    expect(handlers.record).toHaveBeenCalledWith(InteractionKind.Look, ItemKind.Question, "i2");
    expect(fetched).not.toHaveBeenCalled();
    expect(handlers.say).not.toHaveBeenCalled();

    await list.sending(`${token(ChipKind.Impression, "i2")}${PARTLY}it was only my uncle`);
    expect(sentAt()).toEqual({ url: "/app/questions/i2", method: "PATCH", body: { pushback: "partly" } });
    expect(handlers.record).toHaveBeenCalledTimes(1);
  });

  // R-0077, R-0073
  it("partly with the impression taken out of the reply stores nothing", async () => {
    const { list, click } = drawer(FAMILY);
    await click("i2", ".partly");
    await list.sending("never mind");
    expect(fetched).not.toHaveBeenCalled();
  });
});

const WORDS = "You hold on hard, then go off alone.";
const line = (
  name: ToolName,
  args: Record<string, unknown>,
  refusal: string | null = null,
  names: Record<string, string> = { it: WORDS },
) => toolLine({ name, args, names, refusal });

describe("what an impression tool call says in plain words", () => {
  // R-0478
  it("keeps one for later without its words", () => {
    expect(line(ToolName.AddImpression, { evidence: [], state: "held" }, null, {})).toBe(
      "Kept an impression for later",
    );
    expect(
      line(ToolName.SetImpression, { id: "i3", version: 2, state: "resolved", outcome: "let_go" }, null, {}),
    ).toBe("Let go of an impression kept for later");
  });

  // R-0478
  it("says what it noted, took back and let go of", () => {
    expect(line(ToolName.AddImpression, { text: WORDS, evidence: [], state: "raised" })).toBe(
      `Noted “${WORDS}”`,
    );
    expect(line(ToolName.SetImpression, { id: "i3", version: 2, state: "raised" })).toBe(
      `Noted “${WORDS}”`,
    );
    const closed = (outcome: string) =>
      line(ToolName.SetImpression, { id: "i3", version: 2, state: "resolved", outcome });
    expect(closed("revised")).toBe(`Took back “${WORDS}” to reword it`);
    expect(closed("let_go")).toBe(`Let go of “${WORDS}”`);
    expect(line(ToolName.ReadImpressions, {}, null, {})).toBe("Looked at impressions");
  });

  // R-0478
  it("says a refused call was tried, and why", () => {
    expect(
      line(
        ToolName.AddImpression,
        { text: WORDS, evidence: [], state: "raised" },
        "It gave the impression nothing to rest on.",
      ),
    ).toBe(`Tried to note “${WORDS}”. It gave the impression nothing to rest on.`);
  });
});
