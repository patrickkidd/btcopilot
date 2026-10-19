import type { OutOfDate } from "./types";

/** Whether the coach's eight cards on the case report still stand: the sheet
 * that asks on opening, the grey line at the top of the cards, and the
 * cards dimmed while the coach rewrites them (Patrick's approved mockup,
 * 2026-10-07). */

export enum Phase {
  /** Nothing has changed since the coach wrote its cards. */
  Current = "current",
  /** Out of date and not yet answered on this device: the sheet asks. */
  Asking = "asking",
  /** Out of date, and "Show the last report" was chosen for this same out-of-date state. */
  Behind = "behind",
  /** The coach is rewriting its cards. */
  Rewriting = "rewriting",
}

/** One out-of-date state: its change and when it was made, so any other
 * state, a later change or the catch-up's mark, asks again. */
export const stamp = (out: OutOfDate): string => `${out.change_id}@${out.at}`;

export function phase(out: OutOfDate | null, answered: (string | null)[], rewriting: boolean): Phase {
  if (rewriting) return Phase.Rewriting;
  if (!out) return Phase.Current;
  return answered.includes(stamp(out)) ? Phase.Behind : Phase.Asking;
}

/** The line at the top of the cards while the coach rewrites them. */
export const REWRITING = "The coach is rewriting its eight cards from the diagram as it stands now.";

/** The sheet that asks on opening an out-of-date report. */
export const ask = (sentence: string, esc: (s: string) => string): string =>
  `<div class="cf-t">This report is out of date</div>` +
  `<p class="cf-p">${esc(sentence)}</p>` +
  `<p class="cf-p">The coach can rewrite its eight cards now. Or you can read the report as it was last written.</p>` +
  `<div class="cf-btns">` +
  `<button class="cf-go" type="button" data-act="refresh">Refresh the report</button>` +
  `<button class="cf-no" type="button" data-act="last">Show the last report</button>` +
  `</div>`;

const key = (diagramId: number) => `fd-report-last-shown-${diagramId}`;

/** The out-of-date state "Show the last report" was chosen for on this device, if any. */
export function dismissed(diagramId: number): string | null {
  try {
    return window.localStorage.getItem(key(diagramId));
  } catch {
    return null;
  }
}

export function dismiss(diagramId: number, out: OutOfDate): void {
  try {
    window.localStorage.setItem(key(diagramId), stamp(out));
  } catch {
    // a device that refuses to remember asks again next time the report opens
  }
}
