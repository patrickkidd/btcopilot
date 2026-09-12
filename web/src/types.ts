/** The three things a chip may name. The coach's markup is wider than this for
 * historical reasons; the tokenizer narrows it to these on the way in. */
export enum ChipKind {
  Event = "event",
  Cluster = "cluster",
  Person = "person",
  /** Something the coach offers to talk about next. It names nothing in the
   * record: tapping it puts its words in the composer. */
  Ask = "ask",
}

/** Teal is a reference to something the record holds; amber is the coach or the
 * picture asking. DRAWABILITY: one amber treatment, used only for asking. */
export enum ChipTone {
  Data = "data",
  Ask = "ask",
}

/** What the record can be pointed at, as the Interaction model stores it. Chip
 * kinds are markup and are wider than this: several of them name the same kind
 * of item. */
export enum ItemKind {
  Person = "person",
  Event = "event",
  PairBond = "pair_bond",
  Emotion = "emotion",
  Cluster = "cluster",
  Diagram = "diagram",
}

export enum InteractionKind {
  Look = "look",
  Say = "say",
  ChipTap = "chip_tap",
  Play = "play",
}

/** How sure the record is of a date. Unknown means the date matches anything,
 * so the event has no place on the line and belongs on the undated shelf. */
export enum DateCertainty {
  Unknown = "unknown",
  Approximate = "approximate",
  Certain = "certain",
}

export enum Role {
  Coach = "coach",
  User = "user",
}

export interface Chip {
  kind: ChipKind;
  target: string;
  label: string;
  tone: ChipTone;
  /** True when the coach wrote the reference with no words of its own, so the
   * label is a stand-in the record can better. */
  bare: boolean;
}

export type Piece = { text: string } | { chip: Chip };

export interface Person {
  id: number;
  name: string;
  last_name: string | null;
  gender: string | null;
  primary: boolean;
  /** When they were born, which the record holds as an event about them
   * rather than a field on them. Null when it holds none. */
  birth: string | null;
  /** Those two events themselves, so the reader can be sent to them. */
  birth_event: number | null;
  death_event: number | null;
}

export interface TimelineEvent {
  id: number;
  label: string;
  /** The event saying itself in a plain sentence, which is what a tap shows. */
  sentence: string;
  person_name: string;
  person: number | null;
  dateTime: string | null;
  endDateTime: string | null;
  dateCertainty: string | null;
  kind: string | null;
  description: string | null;
  notes: string | null;
  location: string | null;
  symptom: string | null;
  anxiety: string | null;
  functioning: string | null;
  relationship: string | null;
  relationshipTargets: number[];
  relationshipTriangles: number[];
  spouse: number | null;
  child: number | null;
}

export interface Cluster {
  id: string;
  label: string;
  title: string;
  summary: string | null;
  /** Why these moments are one episode, in the coach's own sentence. Null for
   * a cluster the reader regrouped or renamed themselves. */
  reason: string | null;
  cluster_ids: string[];
  start: string;
  end: string;
  event_ids: number[];
  count: number;
}

/** A place the record cannot tell which of two things came first. One amber
 * treatment, used only for asking (DRAWABILITY). */
export interface Question {
  lane: string;
  date: string;
  event_id: number;
  other_event_id: number;
  sentence: string;
}

export interface Timeline {
  people: Person[];
  events: TimelineEvent[];
  clusters: Cluster[];
  questions: Question[];
  axis: { min: string; max: string } | null;
  shelf: { event_id: number; label: string; sentence: string }[];
  /** Where each moment was coded, by event id: the session, and the statement
   * inside it. Two-way traceability runs on this. */
  coded_in: Record<string, CodedIn>;
}

/** A record with nothing in it yet, which is what every surface starts on. A
 * fresh one each time, so two surfaces never share one object. */
export const emptyTimeline = (): Timeline => ({
  people: [],
  events: [],
  clusters: [],
  questions: [],
  axis: null,
  shelf: [],
  coded_in: {},
});

export interface CodedIn {
  discussion_id: number;
  statement_id: number | null;
}

/** What kind of message a statement is, which is how the page routes a tap on
 * its chips: a chip in a play-by-play steps the moves board, a chip anywhere
 * else selects the moment it names. Mirrors `StatementKind` on the server. */
export enum StatementKind {
  Turn = "turn",
  Play = "play",
}

export interface Statement {
  id: number | null;
  role: Role;
  text: string;
  kind: StatementKind;
  /** The cluster a play-by-play narrates. Null on every other kind. */
  cluster_id: string | null;
}

/** The turn as it happens: words as they are written, the tool calls behind
 * them, the deltas already in the record, the views the picture should take,
 * and the persisted statement last. */
export enum TurnEventKind {
  ToolCall = "tool_call",
  RecordPatch = "record_patch",
  View = "view",
}

export enum ViewKind {
  Triangle = "triangle",
  Span = "span",
  Compare = "compare",
  Sequence = "sequence",
  Cluster = "cluster",
}

export type View =
  | { kind: ViewKind.Triangle; persons: number[] }
  | { kind: ViewKind.Span; start: string; end: string }
  | { kind: ViewKind.Compare; event_a: number; event_b: number }
  | { kind: ViewKind.Sequence; events: number[] }
  | { kind: ViewKind.Cluster; cluster: string };

export type TurnEvent =
  | { type: TurnEventKind.ToolCall; name: string; args: Record<string, unknown> }
  | { type: TurnEventKind.RecordPatch; deltas: Delta[]; turn_id: string }
  | { type: TurnEventKind.View; view: View };

export interface Delta {
  item_kind: ItemKind;
  item_id: string;
  field: string;
  before: unknown;
  after: unknown;
}

/** One agent-loop turn: the coach's words with their chips, and what it did
 * behind them in the order it happened. */
export interface Reply {
  statement: string;
  statement_id: number;
  views: View[] | null;
  events: TurnEvent[];
  turn_id: string;
  discussion_id: number;
}

export interface PlayReply {
  statement: string;
  statement_id: number | null;
  kind: StatementKind;
  cluster_id: string;
}

/** A session is a Discussion. The sheet lists them by recency; the coach titles
 * one after the first exchange and a hand-given title replaces that. */
export interface Session {
  id: number;
  title: string | null;
  /** A hand-given title, which the coach will not overwrite and the row marks
   * with a pencil. */
  title_set_by_user: boolean;
  summary: string | null;
  last_activity: string;
  message_count: number;
}

export interface Diagram {
  id: number;
  name: string;
  /** How many of this user's sessions sit on it. */
  session_count: number;
  last_activity: string | null;
  /** The one that is free of charge, which is a billing fact. */
  free: boolean;
  /** The one the app is on. */
  current: boolean;
  owned: boolean;
}

export interface Account {
  email: string;
  sign_in_method: string;
  plan: string;
  diagrams: Diagram[];
  licenses: { id: number; policy: string; status: string }[];
}

export enum Proactive {
  Never = "never",
  Rarely = "rarely",
  Weekly = "weekly",
}

export enum Mode {
  Text = "text",
  Voice = "voice",
}

export enum Theme {
  System = "system",
  Light = "light",
  Dark = "dark",
}

export interface Preferences {
  speak: boolean;
  proactive: Proactive;
  mode: Mode;
  theme: Theme;
  first_name: string | null;
  last_name: string | null;
  birthdate: string | null;
}

/** A key held by one device that signs the reader in without an emailed code. */
export interface Passkey {
  id: number;
  name: string;
  created_at: string;
  last_used_at: string | null;
}

/** What the server hands the browser to make a key with, base64url where the
 * browser wants bytes. */
export interface PasskeyCreationOptions {
  challenge: string;
  rp: { id: string; name: string };
  user: { id: string; name: string; displayName: string };
  pubKeyCredParams: { type: "public-key"; alg: number }[];
  timeout?: number;
  attestation?: string;
  authenticatorSelection?: Record<string, string>;
  excludeCredentials?: { id: string; type: "public-key"; transports?: string[] }[];
}

/** ── The review ─────────────────────────────────────────────────────────
 * Coding is stage one of reaching agreement: one task at a time, done blind,
 * on the conversation up to the cut Patrick put on the table (R-0265, R-0267). */

export enum TaskKind {
  Code = "code",
  Vote = "vote",
}

/** The one card on the coder's screen. It is never a list. */
export interface Task {
  kind: TaskKind;
  cut_id: number;
  coding_id: number | null;
  meeting_date: string | null;
  title: string;
  detail: string;
  /** False while the task is waiting on something, which is shown greyed. */
  ready: boolean;
}

export interface FinishedTask {
  coding_id: number;
  cut_id: number;
  title: string;
  detail: string;
}

export interface Tasks {
  task: Task | null;
  done: FinishedTask[];
}

export interface Coding {
  id: number;
  cut_id: number;
  diagram_id: number;
  done_at: string | null;
}

/** One turn of the transcript, with what this coder has already written from
 * it. Nobody else's coding is ever here (R-0242). */
export interface CodingTurn {
  id: number;
  order: number;
  who: string;
  /** The client's turn, drawn as the user's bubble; otherwise the coach's. */
  client: boolean;
  text: string;
  lines: string[];
  /** Before the last ratified cut: read it, but coding happens below it. */
  above: boolean;
}

/** Where the last ratified cut ended, which is the faint hairline. */
export interface Agreed {
  order: number | null;
  day: string;
  ratified: string;
}

export interface CodingThread {
  coding_id: number;
  cut_id: number;
  diagram_id: number;
  done_at: string | null;
  meeting_date: string | null;
  session: string;
  cut_day: string;
  agreed: Agreed | null;
  turns: CodingTurn[];
}

/** What the scribe did with the coder's words: the lines it wrote, or the one
 * question it asks when it cannot tell which person is meant. */
export interface Scribed {
  lines: string[];
  asked: string;
  /** What the record now holds, so the picture lights it as the line lands. */
  made: { kind: ItemKind; id: string }[];
  turn_id: string;
}

export enum RuleSource {
  Ai = "ai",
  Migration = "migration",
  Human = "human",
}

export interface RuleFlag {
  user_id: number;
  reason: string | null;
  flagged_at: string;
  closed_at?: string;
}

export interface Rule {
  id: number;
  text: string;
  source: Record<string, unknown>;
  drafted_by: RuleSource;
  flags: RuleFlag[];
  ratified_at: string | null;
  retired_at: string | null;
}

/** ── The table ──────────────────────────────────────────────────────────
 * Patrick's whole administration: what is on the table, who is done, and the
 * one tap that opens the vote (R-0258, R-0259, R-0267). */

/** One window of a conversation, frozen and put on the table. */
export interface Cut {
  id: number;
  discussion_id: number;
  start_statement_id: number;
  end_statement_id: number;
  meeting_date: string | null;
  vote_opened_at: string | null;
  ratified_at: string | null;
  nudged_at: string | null;
  session: string;
  end_order: number | null;
  cut_day: string | null;
  /** Somebody has a coding of it, so it can no longer be taken off. */
  started: boolean;
}

export enum CoderState {
  NotStarted = "not started",
  Coding = "coding",
  Done = "done",
  Voted = "voted",
}

export interface CoderLine {
  user_id: number;
  name: string;
  state: CoderState;
  closed_out: boolean;
}

/** Where a line falls across a conversation: the last ratified cut, or the one
 * on the table now. */
export interface CutLine {
  statement_id: number;
  order: number;
  day: string;
  ratified: string | null;
}

export interface SessionTurn {
  id: number;
  order: number;
  client: boolean;
  text: string;
  day: string;
}

/** A whole conversation as the cut-placing screen reads it. */
export interface SessionTurns {
  discussion_id: number;
  session: string;
  agreed: CutLine | null;
  on_table: CutLine | null;
  cut_id: number | null;
  turns: SessionTurn[];
}

/** One line of the next meeting's agenda, which fills itself from flagged
 * rules, items left unresolved and coding nobody finished (R-0276). */
export interface AgendaLine {
  text: string;
  /** A flagged rule is the reader's own line to close; the rest are not. */
  rule_id: number | null;
}

export interface Agenda {
  meeting_date: string | null;
  cut_ids: number[];
  flagged_rules: Rule[];
  unresolved_items: { id: number; item_kind: string; takes: Take[] }[];
  unfinished_codings: { id: number; cut_id: number }[];
}

export interface Take {
  item: Record<string, unknown>;
}
