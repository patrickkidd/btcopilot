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

/** What these edits made, one entry per item, the strongest touch kept. */
export function made(deltas: Delta[]): Made[] {
  const out: Made[] = [];
  merge(out, deltas.map((delta) => ({ kind: delta.item_kind, id: String(delta.item_id), touch: touchOf(delta) })));
  return out;
}

function merge(out: Made[], items: Made[]): void {
  for (const one of items) {
    const had = out.find((m) => m.kind === one.kind && m.id === one.id);
    if (had) had.touch = stronger(had.touch, one.touch);
    else out.push({ ...one });
  }
}

/** Hand one turn to the page, event by event. The same events in the same
 * order always leave the page in the same state, which is what lets a page
 * rebuild the bubble by reading the turn back from its first event. Each edit
 * is handed on as it lands, so the page can draw it with its line. */
export function feed(sink: TurnSink): (event: TurnEvent) => void {
  return (event) => {
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
        sink.made(made(event.deltas));
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

/** What one frame draws of a turn: the lines that landed since the frame
 * before, the events the reads among them looked at, and what the edits behind
 * them made. */
export interface Batch {
  lines: Line[];
  reads: number[][];
  made: Made[];
}

/** How the page waits for a frame, reads the record again, and draws. */
export interface Redraw<T> {
  frame(): Promise<unknown>;
  /** The record as it now stands; null when the read was dropped. */
  read(): Promise<T | null>;
  /** One frame of the turn: the record read again, or null when no read goes
   * with this batch, and the batch's lines drawn with it. */
  draw(record: T | null, batch: Batch): void;
}

/** A turn's lines and the record they changed, drawn in the same frame
 * (R-0898). What lands within one frame is one batch and one redraw; what
 * lands while a batch is being read is the next batch, so edits never queue a
 * read each. A page that is behind (reading a turn back, or a hidden tab
 * coming back) draws the lines of every batch it is behind on as they come
 * and reads the record once, at the last batch of edits: a batch skips its read
 * whenever a later batch of edits has already landed. */
export class Lockstep<T> {
  private open: Batch | null = null;
  /** Batches with edits that have landed and are not yet drawn. */
  private waiting = 0;

  constructor(
    private enqueue: (work: () => Promise<void>) => void,
    private page: Redraw<T>,
  ) {}

  /** Something else is drawn next, so what lands after it is a new batch. */
  close(): void {
    this.open = null;
  }

  line(line: Line): void {
    this.batch().lines.push(line);
  }

  read(ids: number[]): void {
    this.batch().reads.push(ids);
  }

  made(items: Made[]): void {
    const batch = this.batch();
    if (!batch.made.length && items.length) this.waiting += 1;
    merge(batch.made, items);
  }

  private batch(): Batch {
    if (this.open) return this.open;
    const batch: Batch = { lines: [], reads: [], made: [] };
    this.open = batch;
    this.enqueue(async () => {
      await this.page.frame();
      if (this.open === batch) this.open = null;
      if (batch.made.length) this.waiting -= 1;
      let record: T | null = null;
      if (batch.made.length && !this.waiting) {
        record = await this.page.read();
        // a frame of its own, so no two reads are drawn in one frame
        if (record !== null) await this.page.frame();
      }
      this.page.draw(record, batch);
    });
    return batch;
  }
}
