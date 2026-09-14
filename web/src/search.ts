/** What a session is called, and what the sessions sheet's search box finds.
 * Pure, so it can be checked without a browser. */

import { clockTime } from "./when";
import type { Diagram, Session } from "./types";

/** One family and the sessions on it. A personal account has one of these; a
 * professional has one per record. */
export interface Family {
  diagram: Diagram;
  sessions: Session[];
}

/** A session the coach has not titled yet. */
export const untitled = (session: Session) => !session.title?.trim();

/** A session the coach has not titled yet is named by when it happened, so two
 * of them can still be told apart. */
export const sessionTitle = (session: Session) =>
  untitled(session)
    ? `Untitled · ${clockTime(new Date(session.last_activity))}`
    : (session.title as string);

export const summaryOf = (session: Session) =>
  session.summary?.trim() ||
  (session.message_count === 0 ? "just started" : "in progress");

/** What one family shows for a search: the sessions whose name or summary
 * carry the words, and every session it has when the family's own name carries
 * them. A family whose name matches stays on screen even with no sessions on
 * it yet, which is the whole point of searching for the family. */
export function matching(
  family: Family,
  query: string,
): { rows: Session[]; byName: boolean } {
  const words = query.trim().toLowerCase();
  if (!words) return { rows: family.sessions, byName: false };
  if (family.diagram.name.toLowerCase().includes(words))
    return { rows: family.sessions, byName: true };
  return {
    rows: family.sessions.filter((s) =>
      `${sessionTitle(s)} ${summaryOf(s)}`.toLowerCase().includes(words),
    ),
    byName: false,
  };
}
