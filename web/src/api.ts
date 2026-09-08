import type {
  Account,
  Diagram,
  InteractionKind,
  ItemKind,
  PlayReply,
  Preferences,
  Reply,
  Session,
  Statement,
  Timeline,
  TimelineEvent,
} from "./types";

const ROOT = "/personal";

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
  let response: Response;
  try {
    response = await fetch(ROOT + path, {
      method,
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf(),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(PATIENCE_MS),
    });
  } catch (whatever) {
    throw new Failed(0, `${method} ${path}: ${(whatever as Error).message}`);
  }
  if (!response.ok)
    throw new Failed(response.status, `${method} ${path}: ${await response.text()}`);
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const timeline = () => call<Timeline>("GET", "/timeline");

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

export const saveEvent = (id: number | null, body: Partial<TimelineEvent>) =>
  id === null
    ? call<TimelineEvent>("POST", "/events", body)
    : call<TimelineEvent>("PATCH", `/events/${id}`, body);

export const deleteEvent = (id: number) => call<void>("DELETE", `/events/${id}`);

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
