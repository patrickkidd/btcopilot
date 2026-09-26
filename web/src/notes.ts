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
    `<div class="notes-card" role="dialog" aria-label="Coach's notes">` +
    `<div class="notes-head">Coach's notes` +
    `<button type="button" class="notes-close" aria-label="Close">&#x2715;</button></div><dl>` +
    rows.map(([label, value]) => `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`).join("") +
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
    if (closing || (t !== veil && !t.closest(".notes-close"))) return;
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
