import type { Page } from "@playwright/test";

/** One coach turn, mocked the way the server runs it now (R-0369): the send is
 * answered at once with the turn it started, and everything the coach does
 * arrives afterwards on that turn's own stream. A spec says what the turn did
 * and what it said; this serves both halves.
 */

/** Where a turn is posted: a new thread, or the session already on screen. */
export const SEND = /\/app\/(chat|sessions\/\d+\/statements)$/;

/** Where the page follows the turn it just started. */
export const STREAM = /\/app\/turns\/[^/]+\/events/;

export interface MockedTurn {
  /** The words the coach ends on. */
  statement: string;
  statement_id: number;
  discussion_id?: number;
  /** What the coach did before it spoke, in the server's own event shapes:
   * `tool_call`, `record_patch`, `view`. */
  did?: Record<string, unknown>[];
  /** Held before the stream says anything, so a spec can look at the page
   * while the coach is still working. */
  hold?: Promise<void>;
  /** Milliseconds between what the coach did and the words it ends on, so a
   * spec can look at the page while the work is showing and nothing has been
   * said yet. The page picks the rest up the way it picks up any stream that
   * broke off: it comes back saying where it got to. */
  pause?: number;
  /** The status to refuse the send with, asked on every send. Null takes the
   * turn as usual, which is how a retry lands after a refusal. */
  refuse?: () => number | null;
}

function frames(events: Record<string, unknown>[], from: number): string {
  return events
    .map((event, at) => `id: ${from + at + 1}\ndata: ${JSON.stringify(event)}\n\n`)
    .join("");
}

export async function mockTurn(page: Page, turn: MockedTurn): Promise<void> {
  const discussion = turn.discussion_id ?? 1;
  let started = 0;
  await page.route(SEND, async (route) => {
    const refused = turn.refuse?.() ?? null;
    if (refused !== null) return route.fulfill({ status: refused, body: "no" });
    started += 1;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        turn_id: `t${started}`,
        discussion_id: discussion,
        // the user's own words, stored before the turn was handed over
        statement_id: turn.statement_id - 1,
      }),
    });
  });
  await page.route(STREAM, async (route) => {
    if (turn.hold) await turn.hold;
    const whole = [
      ...(turn.did ?? []),
      { type: "text", text: turn.statement },
      {
        type: "done",
        statement: turn.statement,
        statement_id: turn.statement_id,
        discussion_id: discussion,
        kind: "turn",
        views: null,
        events: turn.did ?? [],
        turn_id: `t${started}`,
      },
    ];
    // Where the page got to, which the browser says on its own when a stream
    // breaks off part way.
    const last = Number(route.request().headers()["last-event-id"] ?? 0);
    const first = turn.pause && !last ? (turn.did ?? []).length : whole.length;
    await route.fulfill({
      status: 200,
      headers: {
        "content-type": "text/event-stream",
        "cache-control": "no-cache",
      },
      body:
        (turn.pause ? `retry: ${turn.pause}\n\n` : "") +
        frames(whole.slice(last, first), last),
    });
  });
}
