/** What a session is called, and what the sessions sheet's search box finds.
 * Pure, so it can be checked without a browser. */

import type { Diagram, Session } from "./types";

/** One family and the sessions on it. A personal account has one of these; a
 * professional has one per record. */
export interface Family {
  diagram: Diagram;
  sessions: Session[];
}

/** A session the coach has not titled yet. */
export const untitled = (session: Session) => !session.title?.trim();

const TITLE_WORDS = 6;

/** A session the coach has not titled yet is named by what was first said in
 * it, the way a notes list names a note by its first line. */
export const sessionTitle = (session: Session) => {
  if (!untitled(session)) return session.title as string;
  const words = session.preview?.split(" ").filter(Boolean) ?? [];
  if (!words.length) return "New session";
  const head = words.slice(0, TITLE_WORDS).join(" ");
  return words.length > TITLE_WORDS ? `${head}…` : head;
};

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
