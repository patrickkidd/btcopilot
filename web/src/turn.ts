import { toolLine } from "./tools";
import { TurnEventKind, type Reply, type View } from "./types";

/** What the page does with one turn, in the order the coach did it. The reply
 * arrives whole, so this decides what the chat says it did, when the picture
 * and the list must re-read, and which views to draw — before the words are
 * typed out and their chips aim the picture. */

export enum StepKind {
  Note = "note",
  Reload = "reload",
  Show = "show",
}

export type Step =
  | { kind: StepKind.Note; line: string }
  | { kind: StepKind.Reload }
  | { kind: StepKind.Show; view: View };

export function steps(reply: Reply): Step[] {
  const out: Step[] = [];
  for (const event of reply.events) {
    switch (event.type) {
      case TurnEventKind.ToolCall: {
        const line = toolLine(event.name, event.args);
        if (line) out.push({ kind: StepKind.Note, line });
        break;
      }
      case TurnEventKind.RecordPatch:
        // Several edits in a row only need one re-read.
        if (out.at(-1)?.kind !== StepKind.Reload) out.push({ kind: StepKind.Reload });
        break;
      case TurnEventKind.View:
        out.push({ kind: StepKind.Show, view: event.view });
        break;
    }
  }
  return out;
}
