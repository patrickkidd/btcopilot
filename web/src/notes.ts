import { closeX, el, esc } from "./dom";

/** The tool the coach writes its own notes on a turn with. The server sends it
 * to admins and auditors only; it is never a line in the reply. */
export const NOTES_TOOL = "coach_notes";

/** The kinds of talk a turn can be, as the server's `Register` names them. */
export enum Register {
  Coaching = "coaching",
  Correction = "record correction",
  AppHelp = "app help",
  Journaling = "journaling",
}

export interface Notes {
  register: Register;
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

/** The kind of talk this turn is, with every kind it could have been under it. */
const kinds = (chosen: Register) =>
  esc(chosen) +
  `<div class="notes-possible">Possible: ${esc(Object.values(Register).join(", "))}</div>`;

export function notesHtml(notes: Notes): string {
  const rows: [string, string][] = [
    ["What it's doing", kinds(notes.register)],
    ["Aiming at", esc(notes.lane)],
    ["Why this question", esc(notes.why)],
    ["Holding for later", esc(notes.holding)],
    ["History", esc(history(notes.plateau))],
    ["Hunch", esc(notes.hunch)],
    ["How the person seems", esc(notes.person)],
    ["Variable in play", esc(notes.variable)],
  ];
  return (
    `<div class="notes-card" role="dialog" aria-label="Coach's notes">` +
    `<div class="notes-head">Coach's notes` +
    `${closeX()}</div><dl>` +
    rows.map(([label, value]) => `<dt>${esc(label)}</dt><dd>${value}</dd>`).join("") +
    `</dl></div>`
  );
}

/** Opens the coach's notes on its turn, for admins and auditors. It sits in
 * the bubble's top-right corner out of the flow, so the bubble keeps its shape. */
export const INFO =
  `<button type="button" class="info" aria-label="Coach's notes">` +
  `<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/>` +
  `<path d="M8 7.25v4M8 4.75v.01"/></svg></button>`;

/** The notes pop out of the bubble they belong to, over the thread, until a
 * tap outside them or on close plays the pop-out backwards into the bubble. */
export function notesView(notes: Notes, bubble: HTMLElement): void {
  const box = bubble.getBoundingClientRect();
  const veil = el("div", "notes-veil", notesHtml(notes));
  const card = veil.firstElementChild as HTMLElement;
  let closing = false;
  veil.addEventListener("click", (e) => {
    const t = e.target as Element;
    if (closing || (t !== veil && !t.closest(".cardx"))) return;
    closing = true;
    const runs = veil.getAnimations({ subtree: true });
    runs.forEach((a) => a.reverse());
    Promise.all(runs.map((a) => a.finished)).then(() => veil.remove());
  });
  document.body.append(veil);
  const at = card.getBoundingClientRect();
  card.style.transformOrigin =
    `${box.left + box.width / 2 - at.left}px ${box.top + box.height / 2 - at.top}px`;
}
