import { el, esc } from "./dom";

/** The tool the coach writes its own notes on a turn with. The server sends it
 * to admins and auditors only; it is never a line in the reply. */
export const NOTES_TOOL = "coach_notes";

export interface Notes {
  register: string;
  lane: string;
  why: string;
  holding: string;
  plateau: { reached: boolean; biggest_gap: string };
  hunch: string;
  person: string;
  variable: string;
}

const history = ({ reached, biggest_gap }: Notes["plateau"]) =>
  `${reached ? "Levelled off" : "Still filling in"}; biggest gap: ${biggest_gap}`;

export function notesHtml(notes: Notes): string {
  const rows: [string, string][] = [
    ["What it's doing", notes.register],
    ["Aiming at", notes.lane],
    ["Why this question", notes.why],
    ["Holding for later", notes.holding],
    ["History", history(notes.plateau)],
    ["Hunch", notes.hunch],
    ["How the person seems", notes.person],
    ["Variable in play", notes.variable],
  ];
  return (
    `<summary>coach's notes</summary><dl>` +
    rows.map(([label, value]) => `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`).join("") +
    `</dl>`
  );
}

/** A closed one-line toggle under the reply that opens the notes as a
 * labelled list. */
export const notesView = (notes: Notes) => el("details", "notes", notesHtml(notes));
