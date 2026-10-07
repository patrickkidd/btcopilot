import type { OutOfDate } from "./types";

/** Whether the coach's five cards on the case report still stand: the sheet
 * that asks on opening, the grey line at the top of the cards, and the
 * cards dimmed while the coach rewrites them (Patrick's approved mockup,
 * 2026-10-07). */

export enum Phase {
  /** Nothing has changed since the coach wrote its cards. */
  Current = "current",
  /** Out of date and not yet answered on this device: the sheet asks. */
  Asking = "asking",
  /** Out of date, and "Show the last report" was chosen for this change or a later one. */
  Behind = "behind",
  /** The coach is rewriting its cards. */
  Rewriting = "rewriting",
}

export function phase(out: OutOfDate | null, dismissed: number | null, rewriting: boolean): Phase {
  if (rewriting) return Phase.Rewriting;
  if (!out) return Phase.Current;
  return dismissed !== null && dismissed >= out.change_id ? Phase.Behind : Phase.Asking;
}

/** The line at the top of the cards while the coach rewrites them. */
export const REWRITING = "The coach is rewriting its five cards from the diagram as it stands now.";

/** The sheet that asks on opening an out-of-date report. */
export const ask = (sentence: string, esc: (s: string) => string): string =>
  `<div class="cf-t">This report is out of date</div>` +
  `<p class="cf-p">${esc(sentence)}</p>` +
  `<p class="cf-p">The coach can rewrite its five cards now. Or you can read the report as it was last written.</p>` +
  `<div class="cf-btns">` +
  `<button class="cf-go" type="button" data-act="refresh">Refresh the report</button>` +
  `<button class="cf-no" type="button" data-act="last">Show the last report</button>` +
  `</div>`;

const key = (diagramId: number) => `fd-report-last-shown-${diagramId}`;

/** The change "Show the last report" was chosen for on this device, if any. */
export function dismissed(diagramId: number): number | null {
  try {
    const kept = window.localStorage.getItem(key(diagramId));
    return kept === null ? null : Number(kept);
  } catch {
    return null;
  }
}

export function dismiss(diagramId: number, changeId: number): void {
  try {
    window.localStorage.setItem(key(diagramId), String(changeId));
  } catch {
    // a device that refuses to remember asks again next time the report opens
  }
}
