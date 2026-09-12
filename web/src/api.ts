import type {
  Account,
  Agenda,
  CoderLine,
  Coding,
  Cut,
  SessionTurns,
  CodingThread,
  Rule,
  Scribed,
  Tasks,
  Diagram,
  InteractionKind,
  ItemKind,
  PlayReply,
  Person,
  Passkey,
  PasskeyCreationOptions,
  Preferences,
  Reply,
  Session,
  Statement,
  Timeline,
  TimelineEvent,
} from "./types";

const ROOT = "/personal";
/** The review is its own door, beside the app's own (R-0296). */
const REVIEW = "/review";

/** How long the page waits for an answer before it tells the reader nothing
 * came back. A server that never answers must not leave a caret blinking. */
const PATIENCE_MS = 60_000;

function csrf(): string {
  return (
    document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? ""
  );
}

/** A request that did not come back with an answer. It keeps the status so the
 * page can say which of the three things happened: nothing came back, the
 * server refused it, or the server broke. */
export class Failed extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(`${status || "no answer"}: ${detail}`);
    this.name = "Failed";
  }

  /** Nothing came back at all: the network, or a server that never answered. */
  get silent(): boolean {
    return this.status === 0;
  }
}

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  return send(method, ROOT + path, body);
}

/** The same request against the review's own endpoints. */
async function ask<T>(method: string, path: string, body?: unknown): Promise<T> {
  return send(method, REVIEW + path, body);
}

async function send<T>(method: string, url: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf(),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(PATIENCE_MS),
    });
  } catch (error) {
    // Only a request that never got an answer: the network, or the wait above
    // running out. Anything else thrown here is a mistake in this code and has
    // to surface as itself rather than as the server being unreachable.
    if (!(error instanceof TypeError || error instanceof DOMException)) throw error;
    throw new Failed(0, `${method} ${url}: ${error.message}`);
  }
  if (!response.ok)
    throw new Failed(response.status, `${method} ${url}: ${await response.text()}`);
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

/** The record the app is on, or another one the reader can open — which is how
 * the coding screen shows the record it is being coded onto. */
export const timeline = (diagramId?: number) =>
  call<Timeline>(
    "GET",
    diagramId === undefined ? "/timeline" : `/timeline?diagram_id=${diagramId}`,
  );

/** One agent-loop turn. The coach answers with its words and, behind them, the
 * tool calls, the deltas already applied and the views it asked for. */
export const say = (statement: string, sessionId: number | null) =>
  sessionId === null
    ? call<Reply>("POST", "/chat", { statement })
    : call<Reply>("POST", `/sessions/${sessionId}/statements`, { statement });

export const play = (clusterId: string) =>
  call<PlayReply>("POST", "/play", { cluster_id: clusterId });

/** Every tap is learning data (R-0077), including the looks that send nothing.
 * A tap with no item in view is still about the record, so it is stored against
 * the diagram itself rather than dropped. */
export const record = (
  diagramId: number,
  kind: InteractionKind,
  itemKind: ItemKind,
  itemId: string | null = null,
) =>
  call<void>("POST", "/interactions", {
    diagram_id: diagramId,
    kind,
    item_kind: itemKind,
    item_id: itemId,
  });

export const session = (id: number) =>
  call<{ statements: Statement[] }>("GET", `/sessions/${id}`);

/** Which record a write lands on: the one the app is on, or the one a coding
 * is of. Every writing route takes the same query. */
const onDiagram = (path: string, diagramId?: number) =>
  diagramId === undefined ? path : `${path}?diagram_id=${diagramId}`;

export const saveEvent = (
  id: number | null,
  body: Partial<TimelineEvent>,
  diagramId?: number,
) =>
  id === null
    ? call<TimelineEvent>("POST", onDiagram("/events", diagramId), body)
    : call<TimelineEvent>("PATCH", onDiagram(`/events/${id}`, diagramId), body);

export const deleteEvent = (id: number, diagramId?: number) =>
  call<void>("DELETE", onDiagram(`/events/${id}`, diagramId));

/** The record's Person: a name, a last name and a gender. When someone was
 * born, and whether they have died, are events about them. */
export const savePerson = (
  id: number | null,
  body: Partial<Person>,
  diagramId?: number,
) =>
  id === null
    ? call<Person>("POST", onDiagram("/people", diagramId), body)
    : call<Person>("PATCH", onDiagram(`/people/${id}`, diagramId), body);

export const deletePerson = (id: number, diagramId?: number) =>
  call<void>("DELETE", onDiagram(`/people/${id}`, diagramId));

/** Sessions, newest activity first. The server has no current-session pointer:
 * posting into a session is what makes it the one you come back to. */
export const sessionIndex = (diagramId?: number) =>
  call<Session[]>(
    "GET",
    diagramId === undefined ? "/sessions" : `/sessions?diagram_id=${diagramId}`,
  );

export const newSession = () => call<Session>("POST", "/sessions");

export const deleteSession = (id: number) =>
  call<void>("DELETE", `/sessions/${id}`);

export const renameSession = (id: number, title: string) =>
  call<Session>("PATCH", `/sessions/${id}`, { title });

export const preferences = () => call<Preferences>("GET", "/preferences");

export const setPreferences = (body: Partial<Preferences>) =>
  call<Preferences>("PATCH", "/preferences", body);

export const account = () => call<Account>("GET", "/account");

/** Every diagram the user can open — owned and granted — most recently active
 * first, each with how many sessions sit on it. */
export const diagrams = () => call<Diagram[]>("GET", "/diagrams");

/** Put the app on one of the user's diagrams. Which one is free of charge is a
 * billing fact and is never written by switching. */
export const selectDiagram = (id: number) =>
  call<Diagram>("POST", `/diagrams/${id}/select`);

/** The devices this account can sign in from without an emailed code. */
export const passkeys = () =>
  call<{ passkeys: Passkey[] }>("GET", "/passkeys").then((r) => r.passkeys);

export const passkeyRegisterOptions = () =>
  call<PasskeyCreationOptions>("POST", "/passkeys/register/options");

export const addPasskey = (credential: unknown) =>
  call<{ passkey: Passkey }>("POST", "/passkeys/register", credential).then(
    (r) => r.passkey,
  );

export const revokePasskey = (id: number) =>
  call<{ revoked: boolean }>("POST", `/passkeys/${id}/revoke`);

/** The one thing to code now, and what is already finished (R-0265). */
export const tasks = () => ask<Tasks>("GET", "/tasks");

/** Starting a task is making your own coding of that cut; asking twice gives
 * back the one you already have. */
export const startCoding = (cutId: number) =>
  ask<Coding>("POST", "/codings", { cut_id: cutId });

export const codingThread = (codingId: number) =>
  ask<CodingThread>("GET", `/codings/${codingId}/thread`);

/** What the coder says one turn tells them happened. The scribe writes it into
 * their record, or asks which person they mean. */
export const scribe = (codingId: number, statementId: number, text: string) =>
  ask<Scribed>("POST", `/codings/${codingId}/scribe`, {
    statement_id: statementId,
    text,
  });

/** Done: the coding is submitted for the meeting and cannot change (R-0271). */
export const finishCoding = (codingId: number) =>
  ask<Coding>("PATCH", `/codings/${codingId}`, { done_at: true });

/** ── The table ──────────────────────────────────────────────────────────
 * What Patrick put on the table, who is coding it and the one tap that opens
 * the vote (R-0258, R-0267). */

export const onTable = () => ask<Cut[]>("GET", "/cuts?on_table=true");

/** The whole conversation, so the cut can be placed on any line of it. */
export const sessionTurns = (discussionId: number) =>
  ask<SessionTurns>("GET", `/turns?discussion_id=${discussionId}`);

/** Putting a conversation on the table: the cut ends on the turn tapped, and
 * starts where the last cut left off. */
export const putOnTable = (discussionId: number, endStatementId: number) =>
  ask<Cut>("POST", "/cuts", {
    discussion_id: discussionId,
    end_statement_id: endStatementId,
  });

export const moveCut = (cutId: number, endStatementId: number) =>
  ask<Cut>("PATCH", `/cuts/${cutId}`, { end_statement_id: endStatementId });

export const setMeetingDate = (cutId: number, meetingDate: string) =>
  ask<Cut>("PATCH", `/cuts/${cutId}`, { meeting_date: meetingDate });

/** Nothing opens the vote but Patrick pressing it (R-0273). */
export const openVote = (cutId: number) =>
  ask<Cut>("PATCH", `/cuts/${cutId}`, { vote_opened_at: true });

/** Off the table again, which only works before anyone has started. */
export const offTable = (cutId: number) =>
  ask<void>("DELETE", `/cuts/${cutId}`);

/** One line per coder: not started, coding, done or voted (R-0258). */
export const coders = () => ask<CoderLine[]>("GET", "/coders");

export const nudge = () =>
  ask<{ nudged: number[]; nudged_at: string }>("POST", "/nudges", {});

export const agenda = () => ask<Agenda>("GET", "/agenda");

export const rules = () => ask<Rule[]>("GET", "/rules");

/** Closing your own line on the agenda: the flag you put on a rule (R-0276). */
export const flagClosed = (id: number) =>
  ask<Rule>("PATCH", `/rules/${id}`, { close_flag: true });

export const flagRule = (id: number) =>
  ask<Rule>("PATCH", `/rules/${id}`, { flag: true });
