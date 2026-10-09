import type {
  Account,
  Attached,
  NextMeeting,
  BallotItem,
  Vote,
  VoteChoice,
  CoderLine,
  Coding,
  Cut,
  CodingRecord,
  SessionTurns,
  CodingThread,
  Rule,
  Scribed,
  Tasks,
  Diagram,
  InteractionKind,
  ItemKind,
  PlayReply,
  Pushback,
  QuestionOutcome,
  QuestionState,
  PairBond,
  Person,
  Passkey,
  Picked,
  Cast,
  Shadows,
  PasskeyCreationOptions,
  Preferences,
  Started,
  Report,
  Result,
  Session,
  SessionKind,
  Decision,
  Delivery,
  Tally,
  Statement,
  Passages,
  Rewrite,
  Timeline,
  TimelineEvent,
  User,
  Utterance,
  Voice,
} from "./types";

const ROOT = "/app";
/** The review is its own door, beside the app's own (R-0296). */
const REVIEW = "/review";

/** How long the page waits for an answer before it tells the reader nothing
 * came back. A server that never answers must not leave a caret blinking. */
const PATIENCE_MS = 60_000;
/** How long the page waits for a play-by-play: the server's own longest answer
 * (btcopilot/playturn.py WAIT), so a slow model fails with the server's error. */
export const PLAY_WAIT_S = 390;

/** The session's newest CSRF token: the server sends it on every answer, so
 * a token replaced on the server reaches the page with the next answer, not
 * only on a reload; until one comes, the one the page was served with. */
let token: string | null = null;

export function csrf(): string {
  return token ?? document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? "";
}

/** Keep the token an answer carries, for every write after it. */
function keepToken(response: Response): void {
  const fresh = response.headers.get("X-CSRFToken");
  if (fresh) token = fresh;
}

/** A request that did not come back with an answer. It keeps the status so the
 * page can say which of the three things happened: nothing came back, the
 * server refused it, or the server broke. */
export class Failed extends Error {
  constructor(
    readonly status: number,
    readonly request: string,
    /** The server's own words, or the network's when nothing came back. */
    readonly said: string,
  ) {
    super(`${status || "no answer"}: ${request}: ${said}`);
    this.name = "Failed";
  }

  /** Nothing came back at all: the network, or a server that never answered. */
  get silent(): boolean {
    return this.status === 0;
  }
}

/** The part of a coach-facing reason that says what to do. */
const instruction = (said: string) => said.split(": ").slice(1).join(": ");

/** What went wrong, in the words the reader needs: when the server refused a
 * write, the `words` it gave for that. A hand edit's refusal is already whole
 * plain words; the default keeps what to do from a reason written for the coach. */
export function whatFailed(error: unknown, words = instruction): string {
  const failed = error instanceof Failed ? error : null;
  if (!failed) throw error;
  console.warn(failed.message);
  if (failed.silent) return "No answer from the server";
  if (failed.status >= 500) return "The server broke on that one";
  return words(failed.said) || "That did not go in";
}

/** A request for a diagram that is no longer the one open: the page opened
 * another before the answer came, so nothing is drawn from it. */
export class Dropped extends Error {
  constructor(readonly request: string) {
    super(`dropped: ${request}`);
    this.name = "Dropped";
  }
}

export async function call<T>(
  method: string,
  path: string,
  body?: unknown,
  patience?: number,
  signal?: AbortSignal,
): Promise<T> {
  return send(method, ROOT + path, body, false, patience, signal);
}

/** The same request against the review's own endpoints. */
async function ask<T>(method: string, path: string, body?: unknown): Promise<T> {
  return send(method, REVIEW + path, body);
}

async function send<T>(
  method: string,
  url: string,
  body?: unknown,
  keepalive = false,
  patience = PATIENCE_MS,
  signal?: AbortSignal,
): Promise<T> {
  const waited = AbortSignal.timeout(patience);
  try {
    const response = await fetch(url, {
      method,
      keepalive,
      // a form sets its own type, with the boundary between its parts
      headers: body instanceof FormData ? { "X-CSRFToken": csrf() } : {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf(),
      },
      body: body === undefined || body instanceof FormData ? body : JSON.stringify(body),
      signal: signal ? AbortSignal.any([signal, waited]) : waited,
    });
    keepToken(response);
    if (!response.ok)
      throw new Failed(response.status, `${method} ${url}`, await response.text());
    // an empty answer left unread is logged by the browser as aborted
    if (response.status === 204) {
      await response.text();
      return undefined as T;
    }
    return (await response.json()) as T;
  } catch (error) {
    if (signal?.aborted) throw new Dropped(`${method} ${url}`);
    // Only a request that never got an answer: the network, or the wait above
    // running out. Anything else thrown here is a mistake in this code and has
    // to surface as itself rather than as the server being unreachable.
    if (error instanceof Failed) throw error;
    if (!(error instanceof TypeError || error instanceof DOMException)) throw error;
    throw new Failed(0, `${method} ${url}`, error.message);
  }
}

/** Which diagram a request is about: the one the page has open, or the one a
 * coding is of. Every route that reads or writes a diagram takes the same
 * query; a page that has no diagram yet names none, and the server uses the
 * one the account is on. */
const onDiagram = (path: string, diagramId?: number | null) =>
  diagramId === undefined || diagramId === null
    ? path
    : `${path}${path.includes("?") ? "&" : "?"}diagram_id=${diagramId}`;

/** The record of the diagram open, or of the one a coding is of. */
export const timeline = (diagramId: number | null, signal?: AbortSignal) =>
  call<Timeline>("GET", onDiagram("/timeline", diagramId), undefined, undefined, signal);

/** The passages behind the case report's book buttons (R-0692). */
/** The coach rewrites every card it writes on the case report, and how far
 * it has got (R-0825). */
export const rewriteReport = (diagramId: number | null, signal?: AbortSignal) =>
  call<Rewrite>("POST", onDiagram("/case-report-rewrites", diagramId), undefined, undefined, signal);
export const reportRewrite = (id: string) => call<Rewrite>("GET", `/case-report-rewrites/${id}`);

export const casePassages = (diagramId: number | null, signal?: AbortSignal) =>
  call<Passages>("GET", onDiagram("/case-report-passages", diagramId), undefined, undefined, signal);

/** The browser's IANA time zone, sent with each message so the coach's
 * "today" is the person's day, not the server's (R-0760). */
export const timeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

/** One agent-loop turn. The send is short: it stores the words and hands the
 * turn to the coach, which answers on the turn's own stream. The server puts
 * them in the sitting they belong to. */
export const say = (diagramId: number | null, statement: string, file: File | null = null) =>
  call<Started & Attached>(
    "POST",
    onDiagram("/chat", diagramId),
    file ? said(statement, timeZone(), file) : { statement, time_zone: timeZone() },
    file ? READ_MS : undefined,
  );

/** A message with a file goes as a form. The server checks the file and
 * answers; a text file's words come back with the answer, a PDF or a photo is
 * read on the worker before the coach's turn, and the thread carries the text
 * once it is in. */
export function said(statement: string, zone: string, file: File): FormData {
  const form = new FormData();
  form.append("statement", statement);
  form.append("time_zone", zone);
  form.append("file", file, file.name);
  return form;
}

/** How long a send may take with a file of the largest size the server takes:
 * the upload on a slow link, and the server's checks of it. */
const READ_MS = 120_000;

/** Where one sitting starts, carried by its first words, and when the
 * sitting before it started; the family's first sitting has none before it. */
export interface Sitting {
  id: number;
  started: string;
  previous_started: string | null;
}

/** A statement as the thread reads it: which sitting it is in, and on a
 * sitting's first words, the sitting itself. */
export type Said = Statement & { session_id: number; sitting: Sitting | null };

/** The family's one thread, newest page first; `before` reads the page of
 * words just older than that statement. */
export const thread = (diagramId: number | null, before?: number, signal?: AbortSignal) =>
  call<Said[]>(
    "GET",
    onDiagram(before === undefined ? "/statements" : `/statements?before=${before}`, diagramId),
    undefined,
    undefined,
    signal,
  );

/** Pick a failed turn up where it stopped, on the same turn: nothing new is
 * said (R-0477). */
export const resume = (turnId: string) =>
  call<Started>("POST", `/turns/${turnId}/resume`);

/** Ask the running turn to end at its next step; its edits are taken back
 * and its stream says so (R-0636). */
export const stop = (turnId: string) =>
  call<{ turn_id: string }>("POST", `/turns/${turnId}/stop`);

/** Follow a running turn. A page attaching to one reads it from the start and
 * draws the bubble again; the browser's own reconnect says where it got to
 * with Last-Event-ID, so nothing already read is read twice. */
export const turnEvents = (turnId: string) =>
  new EventSource(`${ROOT}/turns/${turnId}/events`);

/** The release the server is running now. */
export const version = () =>
  call<{ version: string }>("GET", "/version").then((answer) => answer.version);

export const play = (diagramId: number | null, clusterId: string, signal?: AbortSignal) =>
  call<PlayReply>(
    "POST",
    onDiagram("/play", diagramId),
    { cluster_id: clusterId },
    PLAY_WAIT_S * 1000,
    signal,
  );

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

export interface ProductEvent {
  screen: string;
  name: string;
  item_kind: ItemKind | null;
  item_id: string | null;
  diagram_id: number | null;
  at: string;
}

/** Sent with keepalive so the batch flushed as the page hides still lands. */
export const productEvents = (sessionId: string, events: ProductEvent[]) =>
  send<{ stored: number }>(
    "POST",
    ROOT + "/product-events",
    { session_id: sessionId, events },
    true,
  );

export const session = (id: number) =>
  call<Session & { statements: Statement[] }>("GET", `/sessions/${id}`);

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

/** The bond between two people: one ever between any two of them, saying
 * whether they married. When it started and ended are events (R-0326). */
export const savePairBond = (
  id: number | null,
  body: Partial<PairBond>,
  diagramId?: number,
) =>
  id === null
    ? call<PairBond>("POST", onDiagram("/pair_bonds", diagramId), body)
    : call<PairBond>("PATCH", onDiagram(`/pair_bonds/${id}`, diagramId), body);

export const deletePairBond = (id: number, diagramId?: number) =>
  call<void>("DELETE", onDiagram(`/pair_bonds/${id}`, diagramId));

/** The reader's own change to a question or an impression: putting it away,
 * or pushing back on it. It stays in the record for the coach. */
export const saveQuestion = (
  diagramId: number | null,
  id: string,
  body: { state?: QuestionState; outcome?: QuestionOutcome; pushback?: Pushback },
) => call<unknown>("PATCH", onDiagram(`/questions/${id}`, diagramId), body);

/** Sessions, newest activity first. The server has no current-session pointer:
 * posting into a session is what makes it the one you come back to. */
export const sessionIndex = (diagramId: number | null, signal?: AbortSignal) =>
  call<Session[]>("GET", onDiagram("/sessions", diagramId), undefined, undefined, signal);

/** One family's sessions where something said carries every word, searched
 * the way the coach searches the chat. */
export const sessionSearch = (diagramId: number, words: string) =>
  call<Session[]>(
    "GET",
    `${onDiagram("/sessions", diagramId)}&words=${encodeURIComponent(words)}`,
  );

export const newSession = (diagramId: number | null, kind?: SessionKind) =>
  call<Session>("POST", onDiagram("/sessions", diagramId), kind ? { kind } : {});

export const deleteSession = (id: number) => call<void>("DELETE", `/sessions/${id}`);

export const renameSession = (id: number, title: string) =>
  call<Session>("PATCH", `/sessions/${id}`, { title });

/** A bug or feedback the coach offered and the person answered (R-0056). */
export const report = (body: Report) => call<{ id: number }>("POST", "/reports", body);

export const preferences = () => call<Preferences>("GET", "/preferences");

export const setPreferences = (body: Partial<Preferences>) =>
  call<Preferences>("PATCH", "/preferences", body);

export const account = () => call<Account>("GET", "/account");

/** The signed-in person's notifications, newest first: the unread ones, or
 * with `all` the opened ones too. */
export const notifications = (all = false) =>
  call<Delivery[]>("GET", `/notifications${all ? "?all=true" : ""}`);

/** Opening and putting away are one stamp, and the first counts. */
export const openNotification = (id: number) =>
  call<Delivery>("PATCH", `/notifications/${id}`, { opened: true });

/** Every diagram the user can open — owned and granted — most recently active
 * first, each with how many sessions sit on it. */
export const diagrams = (userId?: number) =>
  call<Diagram[]>("GET", `/diagrams${userId === undefined ? "" : `?user_id=${userId}`}`);

/** People found by email or name, for admins only. */
export const users = (q: string) =>
  call<User[]>("GET", `/users?q=${encodeURIComponent(q)}`);

/** Put the app on one of the user's diagrams. Which one is free of charge is a
 * billing fact and is never written by switching. */
export const selectDiagram = (id: number, signal?: AbortSignal) =>
  call<Diagram>("POST", `/diagrams/${id}/select`, undefined, undefined, signal);

/** A new case: an empty record the app is put on straight away (R-0243). */
export const newDiagram = (name: string) =>
  call<Diagram>("POST", "/diagrams", { name });

/** The audio goes to this server, which sends it on to be transcribed and
 * answers with the id to ask after (R-0348). */
export async function startTranscription(file: File): Promise<string> {
  const form = new FormData();
  form.append("audio", file, file.name);
  const response = await fetch(`${ROOT}/transcriptions`, {
    method: "POST",
    headers: { "X-CSRFToken": csrf() },
    body: form,
  });
  keepToken(response);
  if (!response.ok) throw new Error(await response.text());
  return ((await response.json()) as { id: string }).id;
}

export const transcription = (id: string) =>
  call<{
    status: string;
    utterances: Utterance[] | null;
    error: string | null;
  }>("GET", `/transcriptions/${id}`);

/** The voices a transcript holds, each with the first thing it said. */
export const recordingVoices = (utterances: Utterance[]) =>
  call<Voice[]>("POST", "/recordings/voices", { utterances });

/** The point of no return: the thread exists after this and the coach can read
 * it, so the voices are named before it is called. */
export const newRecording = (diagramId: number | null, body: {
  utterances: Utterance[];
  voices: Record<string, { type: string; name?: string; person_id?: number }>;
  title: string;
  date: string | null;
}) => call<Session>("POST", onDiagram("/recordings", diagramId), body);

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

/** ── The agenda ──────────────────────────────────────────────────────────
 * What Patrick put on the agenda, who is coding it and the one tap that opens
 * the vote (R-0258, R-0267). */

export const onAgenda = () => ask<Cut[]>("GET", "/cuts?on_agenda=true");

/** Every cut, whatever state it is in, so the agenda can offer the result of
 * the ones the room has already ratified. */
export const allCuts = () => ask<Cut[]>("GET", "/cuts");

/** One family's cuts, oldest first, so selecting a cut knows where the room
 * last ratified. */
export const diagramCuts = (diagramId: number) =>
  ask<Cut[]>("GET", `/cuts?diagram_id=${diagramId}`);

/** The whole thread of the sitting's family, which the agenda row reads the
 * days and sittings a cut spans from. */
export const sessionTurns = (discussionId: number) =>
  ask<SessionTurns>("GET", `/turns?discussion_id=${discussionId}`);

/** Putting lines of a thread on the agenda: the first and the last line
 * tapped, in one sitting or across several. */
export const putOnAgenda = (
  startStatementId: number,
  endStatementId: number,
  meetingDate: string | null,
) =>
  ask<Cut>("POST", "/cuts", {
    start_statement_id: startStatementId,
    end_statement_id: endStatementId,
    meeting_date: meetingDate,
  });

export const moveCut = (cutId: number, startStatementId: number, endStatementId: number) =>
  ask<Cut>("PATCH", `/cuts/${cutId}`, {
    start_statement_id: startStatementId,
    end_statement_id: endStatementId,
  });

export const setMeetingDate = (cutId: number, meetingDate: string) =>
  ask<Cut>("PATCH", `/cuts/${cutId}`, { meeting_date: meetingDate });

/** Nothing opens the vote but Patrick pressing it (R-0273). */
export const openVote = (cutId: number) =>
  ask<Cut>("PATCH", `/cuts/${cutId}`, { vote_opened_at: true });

/** Off the agenda again, which only works before anyone has started. */
export const offAgenda = (cutId: number) =>
  ask<{ id: number }>("DELETE", `/cuts/${cutId}`);

/** One line per coder: not started, coding, done or voted (R-0258). */
export const coders = (cutId?: number) =>
  ask<CoderLine[]>("GET", cutId === undefined ? "/coders" : `/coders?cut_id=${cutId}`);

export const nudge = () =>
  ask<{ nudged: number[]; nudged_at: string }>("POST", "/nudges", {});

/** ── The ballot ────────────────────────────────────────────────────────
 * Every item of a cut as every coder saw it, and this coder's own votes on
 * them. Names are not in either answer while people are voting (R-0272). */

export const cut = (cutId: number) => ask<Cut>("GET", `/cuts/${cutId}`);

export const items = (cutId: number) =>
  ask<BallotItem[]>("GET", `/items?cut_id=${cutId}`);

export const votes = (cutId: number) => ask<Vote[]>("GET", `/votes?cut_id=${cutId}`);

/** The family each coding was written on, which is what a person or a bond is
 * drawn against: a version of a person says nothing on its own (R-0326). */
export const records = (cutId: number) =>
  ask<CodingRecord[]>("GET", `/records?cut_id=${cutId}`);

/** One vote on one item: a take as it was written, a take of your own, or that
 * this should not be an event in the record at all (R-0257). */
export const castVote = (
  itemId: number,
  choice: VoteChoice,
  value: Record<string, unknown> | null,
  reason: string | null,
) => ask<Vote>("PUT", `/items/${itemId}/vote`, { choice, value, reason });

/** ── The meeting ───────────────────────────────────────────────────────
 * The same items read with the names on, which is where they first appear,
 * the tally beside each, the choice the room makes and the one button that
 * ratifies (R-0252, R-0257, R-0273). */

export const namedItems = (cutId: number) =>
  ask<BallotItem[]>("GET", `/items?cut_id=${cutId}&named=true`);

export const tallies = (cutId: number) =>
  ask<Tally[]>("GET", `/tallies?cut_id=${cutId}`);

/** What the room does with one open item: keep a take, change it to something
 * written out, leave it unresolved, or put a decided one back. */
export const decide = (
  itemId: number,
  choice: Decision,
  value: Record<string, unknown> | null = null,
) => ask<BallotItem>("PATCH", `/items/${itemId}`, { choice, value });

/** Ratifying, which is refused while any open item has no choice. */
export const ratify = (cutId: number) =>
  ask<Cut>("PATCH", `/cuts/${cutId}`, { ratified_at: true });

/** What the meeting produced, readable by everyone who took part. */
export const result = (cutId: number) => ask<Result>("GET", `/result?cut_id=${cutId}`);

export const agenda = () => ask<NextMeeting>("GET", "/agenda");

export const rules = () => ask<Rule[]>("GET", "/rules");

/** Flagging a guideline for the next meeting, and taking the flag off again.
 * Patrick alone may do either (R-0276, R-0346). */
export const flagRule = (id: number, on: boolean) =>
  ask<Rule>("PATCH", `/rules/${id}`, { flag: on });

/** One turn's replies to vote on in the chat (R-0636). */
export const shadows = (turnId: string) =>
  ask<Shadows>("GET", `/picks?turn=${encodeURIComponent(turnId)}`);

export const cast = (id: number, body: Cast) => ask<Picked>("PUT", `/picks/${id}`, body);
