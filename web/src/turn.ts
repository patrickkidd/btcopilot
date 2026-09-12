import { toolLine } from "./tools";
import { ItemKind, TurnEventKind, type Reply, type View } from "./types";

/** What the page does with one turn, in the order the coach did it. The reply
 * arrives whole, so this decides what the chat says it did, when the picture
 * and the list must re-read, and which views to draw — before the words are
 * typed out and their chips aim the picture. */

export enum StepKind {
  Note = "note",
  Reload = "reload",
  Show = "show",
}

/** What one line of what the coach did put in the record. */
export interface Made {
  kind: ItemKind;
  id: string;
}

export type Step =
  | { kind: StepKind.Note; line: string; made: Made[] }
  | { kind: StepKind.Reload }
  | { kind: StepKind.Show; view: View };

export function steps(reply: Reply): Step[] {
  const out: Step[] = [];
  for (const event of reply.events) {
    switch (event.type) {
      case TurnEventKind.ToolCall: {
        const line = toolLine(event.name, event.args);
        if (line) out.push({ kind: StepKind.Note, line, made: [] });
        break;
      }
      case TurnEventKind.RecordPatch: {
        // What a line put in the record belongs to that line, so the picture
        // can light it as the line lands. The line owns the re-read that comes
        // with it; a patch behind no line of its own still needs one.
        const last = out.at(-1);
        const made: Made[] = [];
        for (const delta of event.deltas) {
          const one = { kind: delta.item_kind, id: String(delta.item_id) };
          if (!made.some((m) => m.kind === one.kind && m.id === one.id)) made.push(one);
        }
        if (last?.kind === StepKind.Note && !last.made.length) last.made = made;
        else if (last?.kind !== StepKind.Reload) out.push({ kind: StepKind.Reload });
        break;
      }
      case TurnEventKind.View:
        out.push({ kind: StepKind.Show, view: event.view });
        break;
    }
  }
  return out;
}
