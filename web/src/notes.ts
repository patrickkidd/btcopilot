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

/** How long a press must last before it is a hold rather than a tap. */
export const HOLD_MS = 500;
/** How far a finger may drift before the press is a scroll instead. */
const DRIFT_PX = 10;

/** A press that fires once it has been held still for HOLD_MS. up() says
 * whether it fired, so the click that ends it can be swallowed. */
export function hold(onHold: () => void, ms = HOLD_MS) {
  let at: [number, number] | null = null;
  let fired = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const cancel = () => {
    clearTimeout(timer);
    at = null;
  };
  return {
    down(x: number, y: number) {
      at = [x, y];
      fired = false;
      timer = setTimeout(() => {
        fired = true;
        onHold();
      }, ms);
    },
    move(x: number, y: number) {
      if (at && Math.hypot(x - at[0], y - at[1]) > DRIFT_PX) cancel();
    },
    up() {
      cancel();
      return fired;
    },
  };
}

/** The notes pop out of the bubble they belong to, over the thread, until a
 * tap outside them or on close. */
export function notesView(notes: Notes, bubble: HTMLElement): void {
  const box = bubble.getBoundingClientRect();
  const veil = el("div", "notes-veil", notesHtml(notes));
  const card = veil.firstElementChild as HTMLElement;
  veil.addEventListener("click", (e) => {
    const t = e.target as Element;
    if (t === veil || t.closest(".notes-close")) veil.remove();
  });
  document.body.append(veil);
  const at = card.getBoundingClientRect();
  card.style.transformOrigin =
    `${box.left + box.width / 2 - at.left}px ${box.top + box.height / 2 - at.top}px`;
}
