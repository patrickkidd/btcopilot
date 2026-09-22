import { toolLine } from "./tools";
import { ItemKind, TurnEventKind, type Reply, type TurnEvent, type View } from "./types";

/** What the page does with one turn, in the order the coach does it. The events
 * arrive as they happen, so this decides what the chat says it did, when the
 * picture and the list must re-read, which views to draw, and what the words
 * say — the same either way, whether the page followed the turn from the start
 * or attached to it afterwards and read it back. */

/** What one line of what the coach did put in the record. */
export interface Made {
  kind: ItemKind;
  id: string;
}

/** Everything one turn can tell the page. */
export interface TurnSink {
  note(line: string): void;
  /** The record has changed; these are what changed it, to light. */
  made(items: Made[]): void;
  show(view: View): void;
  /** The next words of the reply. */
  text(text: string): void;
  /** Those words again: what has been drawn is dropped. */
  reset(): void;
  done(reply: Reply): void;
  failed(message: string): void;
}

type Delta = { item_kind: ItemKind; item_id: string | number };

function add(out: Made[], deltas: Delta[]): void {
  for (const delta of deltas) {
    const one = { kind: delta.item_kind, id: String(delta.item_id) };
    if (!out.some((m) => m.kind === one.kind && m.id === one.id)) out.push(one);
  }
}

/** Hand one turn to the page, event by event. The same events in the same
 * order always leave the page in the same state, which is what lets a page
 * rebuild the bubble by reading the turn back from its first event. */
export function feed(sink: TurnSink): (event: TurnEvent) => void {
  // A run of edits is one re-read of the record, not one each: the page reads
  // it back when the run ends rather than between two edits of the same step.
  let edits: Made[] | null = null;
  const settle = () => {
    if (!edits) return;
    const items = edits;
    edits = null;
    sink.made(items);
  };
  return (event) => {
    if (event.type !== TurnEventKind.RecordPatch) settle();
    switch (event.type) {
      case TurnEventKind.ToolCall: {
        const line = toolLine(event.name, event.args);
        if (line) sink.note(line);
        break;
      }
      case TurnEventKind.RecordPatch:
        edits ??= [];
        add(edits, event.deltas);
        break;
      case TurnEventKind.View:
        sink.show(event.view);
        break;
      case TurnEventKind.Text:
        sink.text(event.text);
        break;
      case TurnEventKind.TextReset:
        sink.reset();
        break;
      case TurnEventKind.Done:
        sink.done(event);
        break;
      case TurnEventKind.Failed:
        sink.failed(event.message);
        break;
    }
  };
}
