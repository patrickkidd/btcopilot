export enum ChipKind {
  Event = "event",
  Events = "events",
  Cluster = "cluster",
  Chapter = "chapter",
  Person = "person",
  Range = "range",
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

export enum Role {
  Coach = "coach",
  User = "user",
}

export interface Chip {
  kind: ChipKind;
  target: string;
  label: string;
  tone: ChipTone;
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

export interface Timeline {
  people: Person[];
  events: TimelineEvent[];
  chapters: Chapter[];
  axis: { min: string; max: string } | null;
  shelf: { event_id: number; label: string; sentence: string }[];
}

export interface Statement {
  id: number | null;
  role: Role;
  text: string;
}

export interface Reply {
  statement: string;
  discussion_id: number;
}

export interface PlayReply {
  statement: string;
  cluster_id: string;
}
