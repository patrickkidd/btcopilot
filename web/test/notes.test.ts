import { expect, it } from "vitest";
import { INFO, NOTES_TOOL, notesHtml, type Notes } from "../src/notes";
import { toolLine } from "../src/tools";
import { feed, type TurnSink } from "../src/turn";
import { TurnEventKind, type TurnEvent } from "../src/types";

const notes: Notes = {
  register: "coaching",
  lane: "Mother's side",
  why: "The move <in> 1994 is unexplained",
  holding: "The father's drinking",
  plateau: { reached: false, biggest_gap: "grandparents' dates" },
  hunch: "Distance after the move",
  person: "Calm, brief",
  variable: "anxiety",
};

const call = { name: NOTES_TOOL, args: { ...notes }, names: {}, refusal: null };

function watch() {
  const seen = { lines: 0, notes: [] as Notes[] };
  const sink = {
    note: () => void (seen.lines += 1),
    notes: (n: Notes) => void seen.notes.push(n),
    made: () => {},
    show: () => {},
    text: () => {},
    reset: () => {},
    done: () => {},
    failed: () => {},
    refused: () => {},
  } satisfies TurnSink;
  return { seen, take: feed(sink) };
}

// R-0520, R-0521, R-0522
it("shows the eight notes under plain labels", () => {
  const out = notesHtml(notes);
  for (const label of [
    "What it&#39;s doing",
    "Aiming at",
    "Why this question",
    "Holding for later",
    "History",
    "Hunch",
    "How the person seems",
    "Variable in play",
  ])
    expect(out).toContain(`<dt>${label}</dt>`);
  expect(out).toContain("<dd>Still filling in; biggest gap: grandparents&#39; dates</dd>");
  expect(out).toContain("&lt;in&gt;");
  expect(out).toContain('class="notes-close"');
  expect(out).not.toContain("<summary>");
});

// R-0478, R-0520
it("hands a live notes call to the notes, never as a tool line", () => {
  const { seen, take } = watch();
  take({ type: TurnEventKind.ToolCall, ...call } as TurnEvent);
  expect(seen.notes).toEqual([notes]);
  expect(seen.lines).toBe(0);
  expect(toolLine(call)).toBeNull();
});

// R-0520
it("shows no notes when the turn carries none", () => {
  const { seen, take } = watch();
  take({ type: TurnEventKind.Text, text: "Hello" });
  expect(seen.notes).toEqual([]);
});

// R-0522
it("opens the notes from a circled i button drawn in outline, never a press and hold", () => {
  expect(INFO).toMatch(/^<button type="button" class="info" aria-label="Coach's notes">/);
  expect(INFO).toContain("<circle");
});
