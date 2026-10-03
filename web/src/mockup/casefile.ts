/** The case files under fd-corpus/design/fd336/cases, in the shape the
 * case-data brief gave them. Read-only input: the page maps them onto the
 * app's own shapes (Timeline, Cast, Case) and never writes them back. Every
 * word of a family lives in those files and in the page file beside each
 * (<case>.page.json); none lives in this code. */

export type Layer = "fact" | "hypothesis";

/** A date the record holds as a year, a month or a day ("1971", "1971-04",
 * "1971-04-09"); `unknown` when the record says the thing happened but holds
 * no date for it. */
export type CDate = string | null;

export const UNKNOWN = "unknown";

export interface CPerson {
  id: string;
  /** The name the page draws: the first name where no one else in the record shares it. */
  name: string;
  /** The name as the record stores it, where it differs. */
  fullName?: string;
  sex: "M" | "F" | "unknown";
  birth: CDate;
  death: CDate;
  parents: string | null;
  siblingOrder: number | null;
  isSubject: boolean;
}

export interface CBond {
  id: string;
  a: string | null;
  b: string | null;
  /** When the couple got together, where the record dates it before the marriage. */
  bonded?: CDate;
  married: CDate;
  separated: CDate;
  divorced: CDate;
}

export interface CEvent {
  id: string;
  date: CDate;
  /** Where the record holds one, the date the event ran to. */
  end?: CDate;
  kind: string;
  person: string;
  others: string[];
  text: string;
  layer: Layer;
  source: string;
  /** The record's own codes on the event, as the app stores them (moves.ts
   * Move and Shift); null where the record holds none. */
  symptom?: string | null;
  anxiety?: string | null;
  functioning?: string | null;
  relationship?: string | null;
  /** The place the record notes on the event, as stored. */
  location?: string | null;
}

/** One of several sayings a level quotes (the coach's impressions), each with
 * the record's own evidence for it, so that what is shown rests on its own. */
export interface CPart {
  id: string;
  text: string;
  rests?: string[];
}

export interface CLevel {
  text: string;
  layer: Layer;
  source: string;
  /** What a guess rests on: the ids of the people and events in this file,
   * from the record's own evidence list. A guess with none says so. */
  rests?: string[];
  /** The level's sayings one by one, where it quotes several; `text` is all of
   * them and `rests` the union. */
  parts?: CPart[];
  /** Lines of what the record does not hold about this level. */
  gaps?: string[];
}

export interface CChoice {
  date: string;
  step: string;
  facts: string[];
  /** A question on the step, where the record holds one written by the coach
   * or the professional; null when it holds none. */
  opening: string | null;
  layer: Layer;
  source: string;
  /** The event the step is the words of. */
  event?: string | null;
  /** True only when `step` is the person's own words as the record holds them. */
  quote?: boolean;
}

export interface CStep {
  who: string;
  toward: string;
  line: string;
  source: string;
  /** The dated event in this file the step is the words of; null when the
   * record dates nothing the step says. */
  event: string | null;
}

/** A cluster: its years, its title and the steps its telling walks. */
export interface CCluster {
  id: string;
  from: string;
  to: string;
  title: string;
  steps: CStep[];
}

export interface CLevels {
  "2_whatBrought": CLevel;
  "3_couple": CLevel;
  "4_hisSide": CLevel;
  "4_herSide": CLevel;
  "6_reading": CLevel;
  "7_ownPart": CLevel;
  "8_choice": CChoice;
  "9_workOn": CLevel;
  "10_effort": CLevel;
}

export interface CaseFile {
  case: string;
  title: string;
  presenter: "self" | "professional";
  provenance: string;
  people: CPerson[];
  pairBonds: CBond[];
  events: CEvent[];
  levels: CLevels;
  outcome: CLevel;
  unknowns: string[];
  clusters: CCluster[];
}

/** The small picture a side of the family is drawn around: the couple, and who
 * stands at its index. */
export interface SidePic {
  bond: string;
  index: string;
  sub?: string;
}

export interface Side {
  label: string;
  text: keyof Pick<CLevels, "4_hisSide" | "4_herSide">;
  pics: SidePic[];
}

export type PinTo = { kind: "cluster"; id: string } | { kind: "person"; id: string };

export interface Pin {
  to: PinTo;
  text: string;
}

/** The page file beside a case file (<case>.page.json): how the page presents
 * that case. Whose page it is, the lines of the family level 4 draws, the
 * questions viewers pinned, the record's last date, and the two lists the
 * page's one wording rule needs: theory words replaced inside a quote, and
 * sentences that say what caused what, which the page leaves out. */
export interface PageFile {
  case: string;
  /** The title row. */
  title: string;
  /** The gallery's heading for this case, and the line in its introduction. */
  heading: string;
  lede: string;
  presenter: string;
  pronoun: { he: string; his: string; him: string };
  /** The tinted line at the top of a professional's page; none on a person's own. */
  header: string | null;
  /** The last line of the page: whose account this is. */
  account: string;
  /** Level 2's first line: who asked for help, and when, as far as the record says. */
  asked: string;
  /** Under the choice box: whose words the step is in, when not the person's own. */
  noted: string | null;
  sides: Side[];
  /** Links the record states in words and the picture draws: a file that names
   * grandparents by role without a parents link. */
  derived: { bonds: CBond[]; parents: Record<string, string> };
  pins: Pin[];
  /** The professional whose reading gets a box of its own, when the page gives it one. */
  pro: string | null;
  /** The record's last date, from its provenance: the pictures' "now". */
  recordEnd: string;
  /** A closed record ends on that date; an open one runs on. */
  closed: boolean;
  /** Exact substrings of the case file and what the page shows for each. */
  reword: [string, string][];
  /** Exact substrings of the case file the page leaves out, and why. */
  cut: { from: string; why: string }[];
  /** The state each gallery frame of this case is published in, by frame id:
   * which cluster is open, which step of its telling, whether the drawer is up,
   * and the level whose guess box shows what it rests on. */
  published?: Record<string, { cluster?: string; step?: number; speak?: boolean; rests?: number }>;
}

/** What the record attaches a tracked question to: an event, a person or a
 * pair bond, by this file's id for it. */
export interface CAttached {
  kind: "event" | "person" | "pairBond";
  id: string;
}

/** One of the coach's tracked questions, as the record stores it (kind fact or
 * thought; state raised, asked or resolved), with what it is attached to and
 * that thing's own people and event, by this file's ids. */
export interface CQuestion {
  id: string;
  kind: "fact" | "thought";
  state: "raised" | "asked" | "resolved";
  outcome: string | null;
  askedAt: string;
  attached: CAttached | null;
  text: string;
  people: string[];
  events: string[];
}

/** The questions file beside a case file (<case>.questions.json): the coach's
 * tracked questions, and how many impressions the record holds besides. */
export interface QuestionsFile {
  case: string;
  source: string;
  impressions: number;
  questions: CQuestion[];
}

/** A case as the gallery is given it: the record, the page beside it, and the
 * coach's tracked questions where the gallery reads them (version 5). */
export interface CaseInput {
  file: CaseFile;
  page: PageFile;
  questions?: QuestionsFile;
}

/** "p12" → 12, "e7" → 7, "pb3" → 3: the app's ids are numbers. */
export const num = (id: string): number => Number(id.replace(/^\D+/, ""));

/** A date the record holds with at least a year. */
export const known = (d: CDate | undefined): d is string => !!d && d !== UNKNOWN;
