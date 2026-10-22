import { describe, expect, it } from "vitest";
import { feed, Lockstep, type Made, type TurnSink } from "../src/turn";
import { type Line, text, ToolName } from "../src/tools";
import { ItemKind, Touch, TurnEventKind, type Reply, type TurnEvent } from "../src/types";

/** What the page would be showing, written down instead of drawn. */
interface Shown {
  notes: Line[];
  lit: Made[];
  read: number[];
  reloads: number;
  words: string;
  statement: number | null;
  warning: string | null;
}

function watch(): { shown: Shown; take: (event: TurnEvent) => void } {
  const shown: Shown = {
    notes: [],
    lit: [],
    read: [],
    reloads: 0,
    words: "",
    statement: null,
    warning: null,
  };
  const sink: TurnSink = {
    note: (line) => void shown.notes.push(line),
    notes: () => {},
    made: (items) => {
      shown.reloads += 1;
      shown.lit = items;
    },
    read: (ids) => {
      shown.read = ids;
    },
    show: () => {},
    go: () => {},
    report: () => {},
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
    speak: () => {},
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
    expect(shown.lit).toEqual([{ kind: ItemKind.Person, id: "11", touch: Touch.Change }]);
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

  // R-0539
  it("says whether each event was added, changed or removed, the strongest kept", () => {
    const { shown, take } = watch();
    const one = (id: string, field: string | null, before: unknown, after: unknown) => ({
      item_kind: ItemKind.Event,
      item_id: id,
      field,
      before,
      after,
    });
    take({
      type: TurnEventKind.RecordPatch,
      deltas: [
        one("12", null, null, { id: 12 }),
        one("12", "description", null, "left home"),
        one("13", "description", "left", "left home"),
        one("14", "description", "left", "left home"),
        one("14", null, { id: 14 }, null),
      ],
      turn_id: "t1",
    });
    take(done());
    expect(shown.lit).toEqual([
      { kind: ItemKind.Event, id: "12", touch: Touch.Add },
      { kind: ItemKind.Event, id: "13", touch: Touch.Change },
      { kind: ItemKind.Event, id: "14", touch: Touch.Remove },
    ]);
  });

  // R-0539
  it("hands on the events a read looked at as it lands, and reads nothing again", () => {
    const { shown, take } = watch();
    take({
      type: TurnEventKind.ToolCall,
      name: ToolName.ReadEvents,
      args: { cluster: "c1" },
      names: {},
      refusal: null,
      read: [10, 11],
    });
    expect(shown.read).toEqual([10, 11]);
    expect(shown.reloads).toBe(0);
    expect(shown.notes.length).toBe(1);
  });
});

/** A page following a turn the way the chat page does: lines and edits go to
 * the lock step, everything else to the same queue after them. The record on
 * the server is the people the patches so far have added. */
function page() {
  const server: string[] = [];
  const frames: (() => void)[] = [];
  let frame = 0;
  const shown = {
    lines: [] as string[],
    record: [] as string[],
    lit: [] as Made[],
    reads: 0,
    words: "",
    spoken: "",
    /** The record on screen as each line was drawn. */
    with: [] as { line: string; record: string[] }[],
    /** The frame each read was drawn in. */
    drawnIn: [] as number[],
  };
  let queue: Promise<void> = Promise.resolve();
  let busy = 0;
  const enqueue = (work: () => Promise<void> | void) => {
    busy += 1;
    queue = queue.then(work).finally(() => void (busy -= 1));
  };
  const lock = new Lockstep<string[]>(enqueue, {
    frame: () => new Promise<void>((done) => frames.push(done)),
    read: async () => {
      shown.reads += 1;
      return [...server];
    },
    draw: (read, batch) => {
      shown.lit.push(...batch.made);
      if (read) {
        shown.record = read;
        shown.drawnIn.push(frame);
      }
      for (const line of batch.lines) {
        shown.lines.push(text(line));
        shown.with.push({ line: text(line), record: [...shown.record] });
      }
    },
  });
  const step = (work: () => void) => {
    lock.close();
    enqueue(work);
  };
  const take = feed({
    note: (line) => lock.line(line),
    notes: () => {},
    made: (items) => lock.made(items),
    read: (ids) => lock.read(ids),
    show: () => {},
    go: () => {},
    report: () => {},
    text: (words) => step(() => void (shown.words += words)),
    reset: () => step(() => void (shown.words = "")),
    done: (reply) => step(() => void (shown.words = reply.statement)),
    failed: () => {},
    refused: () => {},
    speak: (statement) => void (shown.spoken = statement),
  });
  /** Frames go by until nothing is left to draw. */
  const settle = async () => {
    while (busy || frames.length) {
      const due = frames.splice(0);
      if (due.length) frame += 1;
      for (const done of due) done();
      await new Promise((r) => setTimeout(r, 0));
    }
  };
  const land = (event: TurnEvent) => {
    if (event.type === TurnEventKind.RecordPatch) server.push(String(event.deltas[0].item_id));
    take(event);
  };
  return { shown, land, settle, frames };
}

const added = (k: number): TurnEvent[] => [
  call(ToolName.EditPerson, { name: `Kin ${k}` }, { it: `Kin ${k}` }),
  {
    type: TurnEventKind.RecordPatch,
    deltas: [{ item_kind: ItemKind.Person, item_id: String(k), field: null, before: null, after: { id: k } }],
    turn_id: "t1",
  },
];

/** Thirty edits in three steps, the coach thinking aloud between them. */
const LONG: TurnEvent[] = [
  ...Array.from({ length: 30 }, (_, i) => [
    ...(i % 10 === 0 && i ? [{ type: TurnEventKind.Text, text: "Next." } as TurnEvent, { type: TurnEventKind.TextReset } as TurnEvent] : []),
    ...added(i + 1),
  ]).flat(),
  { type: TurnEventKind.Text, text: "Added them." },
  {
    type: TurnEventKind.Done,
    statement: "Added them.",
    statement_id: 7,
    views: null,
    events: [],
    turn_id: "t1",
    discussion_id: 2,
  },
];

describe("drawing each edit with its line", () => {
  // R-0898
  it("draws each line with the record already holding what it added", async () => {
    const live = page();
    // a call and its patch come from the server back to back, within a frame
    for (let at = 0; at < LONG.length; at++) {
      live.land(LONG[at]);
      if (LONG[at].type !== TurnEventKind.ToolCall) await live.settle();
    }
    for (const k of [1, 2, 15, 29, 30])
      expect(live.shown.with.find((one) => one.line === `Added Kin ${k}`)!.record).toContain(String(k));
    expect(live.shown.reads).toBe(30);
    expect(new Set(live.shown.drawnIn).size).toBe(live.shown.drawnIn.length);
  });

  // R-0898, R-0369
  it("reads a turn back into the same state it was followed in live, reading the record once", async () => {
    const live = page();
    for (const event of LONG) {
      live.land(event);
      if (event.type !== TurnEventKind.ToolCall) await live.settle();
    }
    const back = page();
    for (const event of LONG) back.land(event);
    await back.settle();
    expect(back.shown.lines).toEqual(live.shown.lines);
    expect(back.shown.record).toEqual(live.shown.record);
    expect(back.shown.lit).toEqual(live.shown.lit);
    expect(back.shown.words).toBe("Added them.");
    expect(back.shown.reads).toBe(1);
  });

  // R-0898
  it("gathers what lands while the record is being read into the next redraw", async () => {
    const { shown, land, settle } = page();
    for (const event of added(1)) land(event);
    // the first batch is waiting for its frame; three more edits land in it
    for (const k of [2, 3, 4]) for (const event of added(k)) land(event);
    await settle();
    expect(shown.lines.length).toBe(4);
    expect(shown.reads).toBe(1);
    expect(shown.record).toEqual(["1", "2", "3", "4"]);
  });

  // R-0898
  it("reads the reply aloud as it ends, even in a hidden tab whose frames never come", async () => {
    const { shown, land, frames } = page();
    for (const event of LONG) land(event);
    await new Promise((r) => setTimeout(r, 0));
    // nothing has been drawn: the first frame is still awaited
    expect(frames.length).toBe(1);
    expect(shown.lines).toEqual([]);
    expect(shown.spoken).toBe("Added them.");
  });
});
