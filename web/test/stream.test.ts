import { describe, expect, it } from "vitest";
import { feed, type Made, type TurnSink } from "../src/turn";
import { ToolName } from "../src/tools";
import { ItemKind, TurnEventKind, type Reply, type TurnEvent } from "../src/types";

/** What the page would be showing, written down instead of drawn. */
interface Shown {
  notes: string[];
  lit: Made[];
  reloads: number;
  words: string;
  statement: number | null;
  warning: string | null;
}

function watch(): { shown: Shown; take: (event: TurnEvent) => void } {
  const shown: Shown = {
    notes: [],
    lit: [],
    reloads: 0,
    words: "",
    statement: null,
    warning: null,
  };
  const sink: TurnSink = {
    note: (line) => void shown.notes.push(line),
    made: (items) => {
      shown.reloads += 1;
      shown.lit = items;
    },
    show: () => {},
    text: (text) => {
      shown.words += text;
    },
    reset: () => {
      shown.words = "";
    },
    done: (reply: Reply) => {
      shown.words = reply.statement;
      shown.statement = reply.statement_id;
    },
    failed: (message) => {
      shown.warning = message;
    },
    refused: (message) => {
      shown.words = message;
    },
  };
  return { shown, take: feed(sink) };
}

const call = (
  name: string,
  args: Record<string, unknown> = {},
  names: Record<string, string> = {},
): TurnEvent => ({
  type: TurnEventKind.ToolCall,
  name,
  args,
  names,
  refusal: null,
});

const patch = (): TurnEvent => ({
  type: TurnEventKind.RecordPatch,
  deltas: [
    {
      item_kind: ItemKind.Person,
      item_id: "11",
      field: "name",
      before: null,
      after: "Nell",
    },
  ],
  turn_id: "t1",
});

const done = (): TurnEvent => ({
  type: TurnEventKind.Done,
  statement: "Added Nell.",
  statement_id: 7,
  views: null,
  events: [],
  turn_id: "t1",
  discussion_id: 2,
});

const TURN: TurnEvent[] = [
  call(ToolName.EditPerson, { name: "Nell" }, { it: "Nell" }),
  patch(),
  { type: TurnEventKind.Text, text: "Added " },
  { type: TurnEventKind.Text, text: "Nell." },
  done(),
];

describe("following a turn", () => {
  // R-0185, R-0369
  it("draws what the coach did, then what it said", () => {
    const { shown, take } = watch();
    for (const event of TURN) take(event);
    expect(shown.notes.length).toBe(1);
    expect(shown.reloads).toBe(1);
    expect(shown.lit).toEqual([{ kind: ItemKind.Person, id: "11" }]);
    expect(shown.words).toBe("Added Nell.");
    expect(shown.statement).toBe(7);
  });

  // R-0369
  it("reads back the same way it was followed live", () => {
    const live = watch();
    for (const event of TURN) live.take(event);
    const replayed = watch();
    for (const event of TURN) replayed.take(event);
    expect(replayed.shown).toEqual(live.shown);
  });

  // R-0369
  it("shows nothing twice when the page attaches part way through", () => {
    const away = watch();
    // the page followed the first half, went away, then read the turn back
    // from its first event into a bubble built again
    for (const event of TURN.slice(0, 2)) away.take(event);
    const back = watch();
    for (const event of TURN) back.take(event);
    expect(back.shown.notes.length).toBe(1);
    expect(back.shown.statement).toBe(7);
    expect(back.shown.words).toBe("Added Nell.");
  });


  // R-0369
  it("drops words the coach said again", () => {
    const { shown, take } = watch();
    take({ type: TurnEventKind.Text, text: "A first go." });
    take({ type: TurnEventKind.TextReset });
    take({ type: TurnEventKind.Text, text: "The one to keep." });
    expect(shown.words).toBe("The one to keep.");
  });

  // R-0182
  it("says in a sentence when the turn did not finish", () => {
    const { shown, take } = watch();
    take({ type: TurnEventKind.Text, text: "half a" });
    take({
      type: TurnEventKind.Failed,
      message: "The coach did not finish that turn.",
    });
    expect(shown.warning).toBe("The coach did not finish that turn.");
    expect(shown.statement).toBe(null);
  });

  // R-0410
  it("speaks a refusal in the coach's voice and offers no retry", () => {
    const { shown, take } = watch();
    take({ type: TurnEventKind.Text, text: "half a" });
    take({
      type: TurnEventKind.Refused,
      message: "I can't take that one up here.",
    });
    expect(shown.words).toBe("I can't take that one up here.");
    expect(shown.warning).toBe(null);
    expect(shown.statement).toBe(null);
  });
});
