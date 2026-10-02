import { NOTES_TOOL, type Notes } from "./notes";
import { type Line, toolLine } from "./tools";
import {
  ItemKind,
  Touch,
  TurnEventKind,
  type ReportKind,
  type Delta,
  type Reply,
  type TurnEvent,
  type View,
} from "./types";

/** What the page does with one turn, in the order the coach does it. The events
 * arrive as they happen, so this decides what the chat says it did, when the
 * picture and the list must re-read, which views to draw, and what the words
 * say — the same either way, whether the page followed the turn from the start
 * or attached to it afterwards and read it back. */

/** What one line of what the coach did put in the record. */
export interface Made {
  kind: ItemKind;
  id: string;
  touch: Touch;
}

const RANK = Object.values(Touch);

/** Of two things done to one event, the one its colour says. */
export const stronger = (a: Touch, b: Touch): Touch =>
  RANK.indexOf(a) >= RANK.indexOf(b) ? a : b;

/** Everything one turn can tell the page. */
export interface TurnSink {
  note(line: Line): void;
  /** The coach's own notes on the turn, for admins and auditors. */
  notes(notes: Notes): void;
  /** The record has changed; these are what changed it, to light. */
  made(items: Made[]): void;
  /** A read looked at these events; the record is as it was. */
  read(ids: number[]): void;
  show(view: View): void;
  /** The coach moved the app to this address (R-0055). */
  go(address: string): void;
  /** The coach offered to send the person's words about the app (R-0056). */
  report(kind: ReportKind, words: string): void;
  /** The next words of the reply. */
  text(text: string): void;
  /** Those words again: what has been drawn is dropped. */
  reset(): void;
  done(reply: Reply): void;
  failed(message: string): void;
  refused(message: string): void;
}

/** A whole item with nothing before it was added, with nothing after it was
 * removed; one field set is a change. */
const touchOf = (delta: Delta): Touch =>
  delta.field !== null ? Touch.Change : delta.before === null ? Touch.Add : Touch.Remove;

function add(out: Made[], deltas: Delta[]): void {
  for (const delta of deltas) {
    const one = { kind: delta.item_kind, id: String(delta.item_id), touch: touchOf(delta) };
    const had = out.find((m) => m.kind === one.kind && m.id === one.id);
    if (had) had.touch = stronger(had.touch, one.touch);
    else out.push(one);
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
        if (event.name === NOTES_TOOL) {
          sink.notes(event.args as unknown as Notes);
          break;
        }
        const line = toolLine(event);
        if (line) sink.note(line);
        if (event.read) sink.read(event.read);
        break;
      }
      case TurnEventKind.RecordPatch:
        edits ??= [];
        add(edits, event.deltas);
        break;
      case TurnEventKind.View:
        sink.show(event.view);
        break;
      case TurnEventKind.Navigate:
        sink.go(event.address);
        break;
      case TurnEventKind.Report:
        sink.report(event.report.kind, event.report.words);
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
      case TurnEventKind.Refused:
        sink.refused(event.message);
        break;
    }
  };
}
