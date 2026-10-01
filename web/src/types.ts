/** The three things a chip may name. The coach's markup is wider than this for
 * historical reasons; the tokenizer narrows it to these on the way in. */
export enum ChipKind {
  Event = "event",
  Cluster = "cluster",
  Person = "person",
  /** Something the coach offers to talk about next. It names nothing in the
   * record: tapping it puts its words in the composer. */
  Ask = "ask",
  /** A question the coach asked and the reader brought back to talk about. */
  Question = "question",
  /** What the coach noticed, brought back by the reader. */
  Impression = "impression",
  PairBond = "pair_bond",
  /** The question a coach message ended on, which the reader is answering
   * (R-0587). */
  Message = "message",
  /** An address in the app, which a tap goes to (R-0055). */
  Place = "place",
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
  Question = "question",
}

/** What a tool call did to an event, weakest first: the colour the event
 * takes on the line until the next message (R-0539). */
export enum Touch {
  Read = "read",
  Change = "change",
  Add = "add",
  Remove = "remove",
}

export enum InteractionKind {
  Look = "look",
  Say = "say",
  ChipTap = "chip_tap",
  Play = "play",
  Dismiss = "dismiss",
  DoesntFit = "doesnt_fit",
}

export { DateCertainty } from "./certainty";

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
  /** The play-by-play message a cluster chip was tapped in, when the chip
   * names that play's own cluster: the tap plays its telling again. */
  play?: number;
}

export type Piece = { text: string } | { chip: Chip };

export interface Person {
  id: number;
  name: string;
  last_name: string | null;
  gender: string | null;
  /** What the desktop app has always kept on a person, and keeps here. */
  notes: string | null;
  primary: boolean;
  /** When they were born, which the record holds as an event about them
   * rather than a field on them. Null when it holds none. */
  birth: string | null;
  /** Those two events themselves, so the reader can be sent to them. */
  birth_event: number | null;
  death_event: number | null;
  /** The pair bond they were born into, which is how the record holds who
   * somebody's parents are. */
  parents: number | null;
}

/** The bond between two people. There is one ever between any two of them, it
 * says whether they married, and a child is born into it (R-0326). */
export interface PairBond {
  id: number;
  person_a: number | null;
  person_b: number | null;
  married: boolean;
  label?: string;
}

export enum EventKind {
  Shift = "shift",
  Birth = "birth",
  Adopted = "adopted",
  Bonded = "bonded",
  Married = "married",
  Separated = "separated",
  Divorced = "divorced",
  Noted = "noted",
  Death = "death",
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
  /** Every event of the cluster in the coach's stored order, the undated ones
   * the wire draws no dot for included: what the play-by-play steps through. */
  play_ids: number[];
  count: number;
  /** What a play of this cluster told now would be told from. */
  digest: string;
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

/** What the coach keeps for the reader: two kinds of question, and what it
 * noticed. Mirrors `QuestionKind` on the server. */
export enum QuestionKind {
  Thought = "thought",
  Fact = "fact",
  Impression = "impression",
}

/** Mirrors `QuestionState` on the server. An impression is raised where a
 * question is asked. */
export enum QuestionState {
  Held = "held",
  Asked = "asked",
  Raised = "raised",
  Resolved = "resolved",
}

/** How a question or impression ended. Mirrors `QuestionOutcome`. */
export enum QuestionOutcome {
  Fact = "fact",
  Answered = "answered",
  Unknown = "unknown",
  DeclinedByUser = "declined_by_user",
  DeclinedInChat = "declined_in_chat",
  LetGo = "let_go",
  DoesntFit = "doesnt_fit",
  Revised = "revised",
}

export enum Pushback {
  Partly = "partly",
}

/** What an impression rests on. Mirrors `EvidenceKind` on the server. */
export enum EvidenceKind {
  Person = "person",
  PairBond = "pair_bond",
  Event = "event",
  Cluster = "cluster",
  Statement = "statement",
}

/** One thing an impression rests on, named as the record names it. A message
 * also says which session it was said in and on what day, both null once that
 * session is gone. */
export interface Evidence {
  kind: EvidenceKind;
  id: number | string;
  label: string;
  discussion_id?: number | null;
  at?: string | null;
}

/** A question the coach has asked, with where it was asked. Only the open ones
 * are listed; a closed one is here so a reference to it still reads as its
 * words. */
export interface AskedQuestion {
  id: string;
  text: string;
  kind: QuestionKind;
  open: boolean;
  asked_at: string;
  asked_in: CodedIn | null;
  /** What an impression rests on; a question rests on nothing. */
  evidence: Evidence[];
  pushback: Pushback | null;
}

export interface Timeline {
  people: Person[];
  pair_bonds: PairBond[];
  events: TimelineEvent[];
  clusters: Cluster[];
  questions: Question[];
  asked_questions: AskedQuestion[];
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
  pair_bonds: [],
  events: [],
  clusters: [],
  questions: [],
  asked_questions: [],
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
  /** A play-by-play's snapshots; null on every other message and on a play
   * told before snapshots. */
  case: Case | null;
  /** What a play-by-play was told from; null on every other message and on a
   * play kept before digests. */
  digest: string | null;
  turn_id: string | null;
  /** What the coach did in this statement's turn: behind a reply, or before a
   * turn failed with these words left unanswered. */
  tools: ToolCall[];
  unfinished: boolean;
  /** Why an unfinished turn stopped, in the words the page showed live. */
  failure: string | null;
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  /** What each id in the args is called, keyed by the arg, and what the call
   * touches under `it`, as the record named them when the call was made. */
  names: Record<string, string | string[]>;
  /** Why the record refused the call, in plain words; a refused call changed
   * and showed nothing. */
  refusal: string | null;
  /** The events a read looked at. */
  read?: number[];
}

/** The turn as it happens: words as they are written, the tool calls behind
 * them, the deltas already in the record, the views the picture should take,
 * and the persisted statement last. */
export enum TurnEventKind {
  ToolCall = "tool_call",
  RecordPatch = "record_patch",
  View = "view",
  /** The coach moved the app to an address in it (R-0055). */
  Navigate = "navigate",
  /** The coach offered to send what the person said about the app (R-0056). */
  Report = "report",
  /** The next words of the reply, as the coach says them. */
  Text = "text",
  /** The coach said those words again: drop what has been drawn. */
  TextReset = "text_reset",
  Done = "done",
  Failed = "failed",
  /** Every model declined the message: a sentence in the coach's voice, and
   * no retry, since the same words would be declined again. */
  Refused = "refused",
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
  | ({ type: TurnEventKind.ToolCall } & ToolCall)
  | { type: TurnEventKind.RecordPatch; deltas: Delta[]; turn_id: string }
  | { type: TurnEventKind.View; view: View }
  | { type: TurnEventKind.Navigate; address: string }
  | { type: TurnEventKind.Report; report: { kind: ReportKind; words: string } }
  | { type: TurnEventKind.Text; text: string }
  | { type: TurnEventKind.TextReset }
  | ({ type: TurnEventKind.Done } & Reply)
  | { type: TurnEventKind.Failed; message: string }
  | { type: TurnEventKind.Refused; message: string };

/** What a send answers with: the turn now running, to be followed on its own
 * stream. The words come later, down that stream. */
export interface Started {
  turn_id: string;
  discussion_id: number;
  statement_id: number;
}

export interface Delta {
  item_kind: ItemKind;
  item_id: string;
  /** Null for a whole item added or removed. */
  field: string | null;
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

/** One picture of a play-by-play: a date, the events on it, the fact line and
 * the coach's optional guess (btcopilot/case.py). */
export interface Snapshot {
  date: string;
  event_ids: number[];
  fact: string;
  guess: string | null;
}

/** A cluster as the coach told it in snapshots (R-0563), or a set of events
 * nobody told, with no cluster, point or question (R-0570). */
export interface Case {
  cluster_id: string | null;
  point: string;
  snapshots: Snapshot[];
  question: string;
}

export interface PlayReply {
  statement: string;
  statement_id: number | null;
  kind: StatementKind;
  cluster_id: string;
  case: Case;
  digest: string;
}

/** A session is a Discussion. The sheet lists them by recency; the coach titles
 * one after the first exchange and a hand-given title replaces that. */
/** One line of a transcript as the transcription service returns it: which
 * voice said it, and the words. */
export interface Utterance {
  speaker: string;
  text: string;
}

/** A voice in a recording before the reader has said who it is: its label and
 * the first thing it said. */
export interface Voice {
  label: string;
  said: string;
}

/** Who a voice turns out to be. The clinician's lines become the coach's side
 * of the thread; the client's become the reader's. */
export enum VoiceRole {
  Clinician = "expert",
  Client = "subject",
}

/** A session is a chat with the coach, a recording read in, or a note the
 * clinician made about the case after the fact (R-0281). */
export enum SessionKind {
  Chat = "chat",
  Recording = "recording",
  Note = "note",
}

export interface Session {
  id: number;
  title: string | null;
  kind: SessionKind;
  /** The day the session happened, which a recording carries and a chat does
   * not. */
  date: string | null;
  /** A hand-given title, which the coach will not overwrite and the row marks
   * with a pencil. */
  title_set_by_user: boolean;
  summary: string | null;
  /** The first thing the client said, one line, for the row under the title. */
  preview: string | null;
  last_activity: string;
  message_count: number;
  /** The turn the coach is running on this session, if one is running: a page
   * that has just loaded attaches to it instead of showing nothing. */
  turn: string | null;
  /** On a search, the newest line said in it that carries the words. */
  match?: string;
  /** The family it was said about, on the list of every family's sessions. */
  family?: string;
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

/** Someone with an account, as an admin's search finds them. */
export interface User {
  id: number;
  username: string;
  name: string;
}

export interface Account {
  email: string;
  sign_in_method: string;
  plan: string;
  diagrams: Diagram[];
  licenses: { id: number; policy: string; status: string }[];
  /** A professional licence: cases, recordings and notes (R-0237). */
  pro: boolean;
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

/** How the picture answers a tap on an event: a chip naming it and its dot
 * do one thing (R-0168), or, set per person by an admin, the old chip
 * spotlight. */
export enum Spotlight {
  Unified = "unified",
  Chip = "chip",
}

/** Whether a turn or the page breaking asks before its report is sent.
 * Mirrors `BugReports` on the server. */
export enum BugReports {
  Ask = "ask",
  Always = "always",
}

/** What the person can send from the app (R-0056). Mirrors `ReportKind` on
 * the server. */
export enum ReportKind {
  Bug = "bug",
  Feedback = "feedback",
}

/** Mirrors `ReportStatus` on the server. */
export enum ReportStatus {
  Sent = "sent",
  Declined = "declined",
}

/** A report as it is sent: one row of the reports table. */
export interface Report {
  kind: ReportKind;
  status: ReportStatus;
  release: string;
  /** The screen the page was on. */
  address: string;
  turn_id: string;
  /** The coach's reply that offered it. */
  statement_id: number;
  /** The words the coach offered to send; none once turned down. */
  words?: string;
}

export interface Preferences {
  speak: boolean;
  proactive: Proactive;
  mode: Mode;
  theme: Theme;
  spotlight: Spotlight;
  first_name: string | null;
  last_name: string | null;
  birthdate: string | null;
  how_it_works: boolean;
  line_hint: boolean;
  bug_reports: BugReports;
}

/** What a notification points at. Mirrors `NotificationKind` on the server. */
export enum NotificationKind {
  Coach = "coach",
  Task = "task",
  Reminder = "reminder",
  Notice = "notice",
}

/** The fixed screens a notification opens by name. A notice may instead
 * carry any address in the app (R-0055). */
export enum Link {
  Account = "account",
  Coach = "coach_settings",
  Task = "task",
  Agenda = "agenda",
}

/** One notification delivered to the signed-in person, and when they opened
 * it. */
export interface Delivery {
  id: number;
  kind: NotificationKind;
  title: string;
  /** A notice's words; the other kinds are their title alone. */
  body: string | null;
  /** A `Link`, or an address starting /app/. */
  link: string | null;
  /** A coach message's own place in the thread. */
  discussion_id: number | null;
  statement_id: number | null;
  created_at: string;
  opened_at: string | null;
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
  excludeCredentials?: {
    id: string;
    type: "public-key";
    transports?: string[];
  }[];
}

/** ── The review ─────────────────────────────────────────────────────────
 * Coding is stage one of reaching agreement: one task at a time, done blind,
 * on the conversation up to the cut Patrick put on the agenda (R-0265, R-0267). */

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
  /** Its cut is ratified, so the line opens what the meeting produced. */
  ratified: boolean;
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
/** One thing the coder typed about a turn, and the edit lines the scribe wrote
 * from it, which sit beneath those words. */
export interface Said {
  text: string;
  lines: string[];
  /** The record events those lines are. */
  event_ids: number[];
}

export interface CodingTurn {
  id: number;
  order: number;
  who: string;
  /** The client's turn, drawn as the user's bubble; otherwise the coach's. */
  client: boolean;
  text: string;
  /** What the coder typed about this turn, each with what the scribe wrote
   * from those words, oldest first. */
  said: Said[];
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
  /** Whether a flag for the next meeting stands on it right now. */
  flagged: boolean;
  ratified_at: string | null;
  retired_at: string | null;
}

/** ── The agenda ──────────────────────────────────────────────────────────
 * Patrick's whole administration: what is on the agenda, who is done, and the
 * one tap that opens the vote (R-0258, R-0259, R-0267). */

/** One window of a conversation, frozen and put on the agenda. */
/** A first and a last line in one family's thread, in one sitting or across
 * several. */
export interface Cut {
  id: number;
  diagram_id: number;
  /** The sitting its first line was said in, which the picker opens at. */
  sitting_id: number;
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
  /** How much of the cut the coders read the same way, on the first pass and
   * again after the room ratified it. */
  agreement: {
    first_pass?: Agreement | null;
    ratified?: Agreement | null;
  } | null;
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
 * on the agenda now. */
export interface CutLine {
  start_statement_id: number;
  statement_id: number;
  order: number;
  day: string;
  ratified: string | null;
}

export interface SessionTurn {
  id: number;
  /** Its place in the whole thread, counted from 1. */
  order: number;
  sitting_id: number;
  client: boolean;
  text: string;
  day: string;
}

/** One sitting of a family's thread, with what its divider is drawn from. */
export interface Sitting {
  id: number;
  /** Empty while the sitting has no title. */
  title: string;
  started: string;
  previous_started: string | null;
  first_statement_id: number;
}

/** A family's whole thread as the cut-placing screen reads it, opened at one
 * sitting. */
export interface SessionTurns {
  diagram_id: number;
  sitting_id: number;
  sittings: Sitting[];
  session: string;
  agreed: CutLine | null;
  on_agenda: CutLine | null;
  cut_id: number | null;
  turns: SessionTurn[];
}

/** The next meeting's agenda, which fills itself from the flagged rules
 * (R-0276, R-0308). An event the room left unresolved stays unresolved and is
 * never brought back to a later meeting (R-0312). */
export interface NextMeeting {
  meeting_date: string | null;
  cut_ids: number[];
  flagged_rules: Rule[];
}

/** One line of the transcript, as a version of an item points back at it. */
export interface TranscriptLine {
  statement_id: number;
  who: string;
  text: string;
}

/** One coder's reading of one item, without their name (R-0252). */
export interface Opinion {
  coding_id?: number;
  item_id?: number | string | null;
  /** The turn of the conversation this opinion was written from. */
  statement_id?: number | null;
  /** The transcript line that turn is, or null when nothing was stamped on it:
   * the coach's replay, or an edit made in the editor. */
  line?: TranscriptLine | null;
  /** The person this opinion is about, named on the record it was written on. */
  person_name?: string | null;
  /** Who wrote this opinion, which appears at the meeting and nowhere before it
   * (R-0252). */
  coder?: string;
  user_id?: number;
  item: Record<string, unknown>;
}

/** The family one coding was written on, which a person or a bond is drawn
 * against: the version being voted on stands in the middle of it (R-0326). */
export interface CodingRecord {
  coding_id: number;
  people: Person[];
  pair_bonds: PairBond[];
  events: TimelineEvent[];
}

/** How the snapshot found the coders reading one item: the same way, or not.
 * Decided and unresolved are what the meeting makes of it afterwards. */
export enum ItemStatus {
  Agreed = "agreed",
  Disputed = "disputed",
  Decided = "decided",
  Unresolved = "unresolved",
}

/** What one screen of the ballot is about. */
export interface BallotItem {
  id: number;
  cut_id: number;
  item_kind: ItemKind;
  item_id: string | null;
  status: ItemStatus;
  opinions: Opinion[];
  /** How many coders finished, and how many of them left this item out. */
  coders: number;
  not_coded: number;
  /** The people of the record the first opinion was written on, so an opinion of your
   * own can name one of them. */
  people: { id: number; name: string }[];
  /** The first version's transcript line, which an event shows for the whole
   * item. A person or a bond shows one line per version instead. */
  line: TranscriptLine | null;
  /** The matcher could not tell which person of another coding this is, so the
   * room decides who is who before anything else about them (R-0326). */
  ambiguous?: boolean;
  /** Who decided it, which only the meeting's own reading carries. */
  user_id?: number | null;
  /** Which coding's version the room kept, so the kept row lights again on
   * every reading of a decided item (R-0339). */
  kept_coding_id?: number | null;
}

/** Whose line of the conversation a blind pair shows above the replies. */
export enum Who {
  User = "user",
  Coach = "coach",
}

export enum PickChoice {
  Left = "left",
  Right = "right",
  Tie = "tie",
}

/** Two replies to the same words, with no model named (R-0599). */
export interface Pair {
  id: number;
  source: string;
  context: { who: Who; text: string }[];
  left: string;
  right: string;
}

/** A pick as stored, which is when the two model names are first sent. */
export interface Picked {
  id: number;
  choice: PickChoice;
  note: string | null;
  left: string;
  right: string;
}

export interface ModelPicks {
  model: string;
  won: number;
  lost: number;
  tied: number;
}

/** The three things a vote can say (R-0257). */
export enum VoteChoice {
  Opinion = "opinion",
  Change = "change",
  Drop = "drop",
}

export interface Vote {
  id: number;
  review_item_id: number;
  choice: VoteChoice;
  value: Record<string, unknown> | null;
  reason: string | null;
}

/** ── The meeting ───────────────────────────────────────────────────────
 * Where the vote is counted out loud, names appear for the first time and
 * every open item is given a choice before the cut is ratified (R-0252,
 * R-0257, R-0274). */

/** What the room does with one open item. Reopen puts a decided or agreed one
 * back in front of everybody. */
export enum Decision {
  Keep = "keep",
  Change = "change",
  Unresolved = "unresolved",
  Reopen = "reopen",
}

/** One vote as the meeting reads it: with the name of whoever cast it. */
export interface CastVote {
  user_id: number;
  name: string;
  choice: VoteChoice;
  value: Record<string, unknown> | null;
  reason: string | null;
}

export interface Tally {
  review_item_id: number;
  counts: Record<VoteChoice, number>;
  votes: CastVote[];
}

/** How the coach's own pass scored against the ratified record (R-0242). */
export interface CoachScore {
  agent: { model: string | null; prompt_version: unknown } | null;
  people: number;
  events: number;
  variables: number | null;
  by_variable: Record<string, number>;
}

/** How much of the cut the coders read the same way. */
export interface Agreement {
  codings: number;
  items: number;
  by_status: Record<string, number>;
  percent: number | null;
}

/** One place the coach read the cut differently from the room, with its own
 * reason. An audit, never a vote (R-0254). */
export interface Differed {
  review_item_id: number;
  item_kind: string;
  label: string;
  room: string;
  coach: string;
  reason: string | null;
}

/** What one coder tends to do differently from the others. */
export interface Tendency {
  user_id: number;
  name: string;
  items: number;
  left_out: number;
  apart: number;
  leans: string | null;
  leans_count: number;
}

/** What the meeting produced, with nothing left to choose. */
export interface Result {
  cut_id: number;
  /** The conversation the cut was taken from, which names the result. */
  conversation: string;
  ratified_at: string;
  items: number;
  ratified: number;
  unresolved: number;
  /** How much of the family the room settled, which is counted beside the
   * events rather than mixed into them (R-0326). */
  structure: {
    people: number;
    bonds: number;
    ratified: number;
    unresolved: number;
  } | null;
  first_pass: Agreement | null;
  after: Agreement | null;
  coach: CoachScore | null;
  rules: Rule[];
  differed: Differed[];
  coders: Tendency[];
}
