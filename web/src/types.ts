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
  gender: string | null;
  primary: boolean;
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

export interface Chapter {
  id: string;
  label: string;
  title: string;
  summary: string | null;
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
  chapters: Chapter[];
  questions: Question[];
  axis: { min: string; max: string } | null;
  shelf: { event_id: number; label: string; sentence: string }[];
  /** Where each moment was coded, by event id: the session, and the statement
   * inside it. Two-way traceability runs on this. */
  coded_in: Record<string, CodedIn>;
}

export interface CodedIn {
  discussion_id: number;
  statement_id: number | null;
}

export interface Statement {
  id: number | null;
  role: Role;
  text: string;
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
