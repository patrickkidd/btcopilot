import { Failed } from "./api";
import { RewriteState, type OutOfDate, type Rewrite } from "./types";

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

/** The grey line's classes: while the coach rewrites, the three dots a
 * working button shows, as the coach's turn does while it waits. */
export const lineClass = (now: Phase): string => (now === Phase.Rewriting ? "aged dots3" : "aged");

/** The sheet that asks on opening an out-of-date report. */
export const ask = (sentence: string, esc: (s: string) => string): string =>
  `<div class="cf-t">This report is out of date</div>` +
  `<p class="cf-p">${esc(sentence)}</p>` +
  `<p class="cf-p">The coach can rewrite its eight cards now. Or you can read the report as it was last written.</p>` +
  `<div class="cf-btns">` +
  `<button class="cf-go" type="button" data-act="refresh">Refresh the report</button>` +
  `<button class="cf-no" type="button" data-act="last">Show the last report</button>` +
  `</div>`;

/** What a rewrite of the coach's cards asks of the screen. */
export interface Rewriter {
  /** Ask the coach to rewrite them; null when another family was opened meanwhile. */
  start(): Promise<Rewrite | null>;
  /** Ask whether the rewrite has finished. */
  poll(id: string): Promise<Rewrite>;
  /** Wait between two asks. */
  pause(): Promise<void>;
  say(text: string): void;
}

export const BUSY = "The report is already being rewritten, or this family has no session yet";
export const UNWRITTEN = "The coach could not rewrite the report. Try again.";

/** The coach rewrites its eight cards (R-0825): true once it has. One the
 * server will not start now (already running, or no session yet) is said and
 * is false; a failed one, or one the server no longer knows, is said and
 * thrown. Reading the report back is the caller's, after this, so a read that
 * fails is never told as a rewrite that failed. */
export async function rewritten(r: Rewriter): Promise<boolean> {
  let job: Rewrite | null;
  try {
    try {
      job = await r.start();
    } catch (error) {
      if (!(error instanceof Failed) || error.status !== 409) throw error;
      r.say(BUSY);
      return false;
    }
    while (job?.state === RewriteState.Running) {
      await r.pause();
      const id = job.id;
      job = await r.poll(id).catch((error: unknown) => {
        if (error instanceof Failed && error.status === 404) return { id, state: RewriteState.Failed };
        throw error;
      });
    }
    if (job?.state === RewriteState.Failed) throw new Error(`the coach could not rewrite the case report, rewrite ${job.id}`);
  } catch (error) {
    r.say(UNWRITTEN);
    throw error;
  }
  return true;
}

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
