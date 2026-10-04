import { expect, it } from "vitest";
import { cards, NOT_ENOUGH, rail } from "../src/case";
import { Card, caseView, ORDER } from "../src/caseview";
import {
  CaseReportCard,
  EventKind,
  EvidenceKind,
  QuestionKind,
  emptyTimeline,
  type AskedQuestion,
  type Person,
  type Session,
  type Timeline,
  type TimelineEvent,
} from "../src/types";

const person = (id: number, name: string, gender: string, parents: number | null = null, primary = false): Person => ({
  id,
  name,
  last_name: null,
  gender,
  notes: null,
  primary,
  birth: null,
  birth_event: null,
  death_event: null,
  parents,
});

const event = (id: number, kind: EventKind, date: string | null, fields: Partial<TimelineEvent> = {}): TimelineEvent => ({
  id,
  label: fields.title ?? kind,
  sentence: "",
  person_name: "",
  person: null,
  dateTime: date,
  endDateTime: null,
  dateCertainty: date ? "certain" : "unknown",
  kind,
  title: null,
  description: null,
  notes: null,
  location: null,
  symptom: null,
  anxiety: null,
  functioning: null,
  relationship: null,
  relationshipTargets: [],
  relationshipTriangles: [],
  spouse: null,
  child: null,
  ...fields,
});

const guess = (id: string, text: string, card: CaseReportCard | null, events: number[] = [], open = true): AskedQuestion => ({
  id,
  text,
  kind: QuestionKind.Impression,
  open,
  asked_at: "2026-09-20",
  asked_in: null,
  evidence: events.map((e) => ({ kind: EvidenceKind.Event, id: e, label: "" })),
  pushback: null,
  case_report_card: card,
  answer: null,
});

/** Nora, her husband Daniel and daughter Lily, her parents Frank and Elaine,
 * Frank's parents Walter and June: invented. */
function halloran(): Timeline {
  return {
    ...emptyTimeline(),
    people: [
      person(1, "Nora", "female", 30, true),
      person(2, "Frank", "male", 31),
      person(3, "Elaine", "female"),
      person(4, "Walter", "male"),
      person(5, "June", "female"),
      person(8, "Sean", "male", 30),
      person(10, "Daniel", "male"),
      person(11, "Lily", "female", 33),
    ],
    pair_bonds: [
      { id: 30, person_a: 2, person_b: 3, married: true },
      { id: 31, person_a: 4, person_b: 5, married: true },
      { id: 33, person_a: 1, person_b: 10, married: true },
    ],
    events: [
      event(106, EventKind.Married, "1976-09-01", { person: 2, spouse: 3 }),
      event(111, EventKind.Married, "2009-06-01", { person: 1, spouse: 10 }),
      event(112, EventKind.Birth, "2012-05-01", { person: 1, spouse: 10, child: 11, person_name: "Lily" }),
      event(202, EventKind.Shift, "2004-09-01", { person: 1, title: "Stopped sleeping well", symptom: "up" }),
      event(209, EventKind.Shift, "2019-01-01", { person: 1, title: "Stopped visiting her mother", relationshipTargets: [3] }),
      event(210, EventKind.Shift, "2021-10-01", { person: 1, title: "Panic attacks at work", symptom: "up" }),
      event(211, EventKind.Noted, null, { person: 1, title: "Moved without telling anyone" }),
    ],
  };
}

const ONE: Session[] = [];

// R-0702, R-0713
it("draws the cards in the proposal's order, each with its strip item in the same place", () => {
  const v = caseView(halloran(), ONE, "Patrick");
  const order = (html: string, attr: string) => [...html.matchAll(new RegExp(`data-${attr}="([a-z_]+)"`, "g"))].map((m) => m[1]);
  expect(order(cards(v, true), "card")).toEqual(ORDER.filter((c) => c !== Card.Family));
  expect(order(cards(v, false), "card")).toEqual(ORDER);
  expect(order(rail(v), "jump")).toEqual(ORDER);
});

// R-0694
it("shows the couple card only for a marriage the picture draws solid, with both partners alive", () => {
  const tl = halloran();
  expect(caseView(tl, ONE, "").married).toBe(true);
  tl.events.push(event(300, EventKind.Separated, "2020-01-01", { person: 1, spouse: 10 }));
  const parted = caseView(tl, ONE, "");
  expect(parted.married).toBe(false);
  expect(parted.stages.map((row) => row.label)).toEqual(["Frank and Elaine, her parents", "Nora and Daniel"]);
  const widowed = halloran();
  widowed.events.push(event(301, EventKind.Death, "2023-01-01", { person: 10 }));
  widowed.people.find((p) => p.id === 10)!.death_event = 301;
  expect(caseView(widowed, ONE, "").married).toBe(false);
});

// R-0710
it("gives each parent a side, the father's first, with the parent's own parents drawn", () => {
  const v = caseView(halloran(), ONE, "");
  expect(v.sides.map((s) => s.label)).toEqual(["Her father's side", "Her mother's side"]);
  // R-0733: one picture a side, the parent once, the other parent joined to them
  const drawn = (i: number) => Object.keys(v.sides[i].still.layout!.P).sort();
  expect(drawn(0)).toEqual(["2", "3", "4", "5"]);
  expect(drawn(1)).toEqual(["2", "3"]);
});

// R-0699, R-0713
it("says on every guess card that there is not enough yet, and never picks a main guess itself", () => {
  const tl = halloran();
  tl.asked_questions = [guess("i9", "A guess on no card.", null, [202])];
  const v = caseView(tl, ONE, "");
  expect(v.main).toBeNull();
  const html = cards(v, false);
  const guessCards = [Card.Main, Card.OwnPart, Card.Choice, Card.WorkOn];
  for (const card of guessCards) expect(html.split(`data-card="${card}"`)[1].split("</section>")[0]).toContain(NOT_ENOUGH);
  const thin = cards(caseView({ ...emptyTimeline(), people: [person(1, "Ines", "female", null, true)] }, ONE, ""), false);
  expect(thin.split(`data-card="${Card.Couple}"`)[1].split("</section>")[0]).not.toContain("<p class=\"lead\">");
});

// R-0709
it("shows the coach's newest guess on a card, and at most three on what to work on", () => {
  const tl = halloran();
  tl.asked_questions = [
    guess("i1", "The older main guess.", CaseReportCard.MainGuess, [202]),
    guess("i2", "The newer main guess.", CaseReportCard.MainGuess, [209]),
    ...[1, 2, 3, 4].map((n) => guess(`w${n}`, `Work ${n}.`, CaseReportCard.WorkOn, [210])),
  ];
  const v = caseView(tl, ONE, "");
  expect(v.main?.text).toBe("The newer main guess.");
  expect(v.work.guesses.map((g) => g.text)).toEqual(["Work 2.", "Work 3.", "Work 4."]);
  expect(v.work.aim?.id).toBe(210);
  // the aim is the first guess's first evidence, not its earliest event
  tl.asked_questions = [guess("w1", "Work.", CaseReportCard.WorkOn, [210, 202])];
  expect(caseView(tl, ONE, "").work.aim?.id).toBe(210);
  tl.asked_questions = [guess("w1", "Work.", CaseReportCard.WorkOn, [211, 202])];
  expect(caseView(tl, ONE, "").work.aim).toBeNull();
});

// R-0708
it("puts the person's own answer on the own part card, as their own view", () => {
  const tl = halloran();
  tl.asked_questions = [
    guess("i2", "My guess is you stop visiting.", CaseReportCard.OwnPart, [209]),
    {
      ...guess("q1", "What do you think your own part was?", CaseReportCard.OwnPart),
      kind: QuestionKind.Thought,
      open: false,
      answer: { kind: EvidenceKind.Statement, id: 7, label: "", text: "I go quiet and stay away." },
    },
  ];
  const v = caseView(tl, ONE, "");
  expect(v.ownPart).toEqual({ guess: expect.objectContaining({ text: "My guess is you stop visiting." }), ask: null, answer: "I go quiet and stay away." });
  expect(cards(v, false)).toContain("Nora&#39;s own view");
});

// R-0696
it("never puts an undated event on a chip, and writes no NaN or undefined", () => {
  const tl = halloran();
  tl.asked_questions = [guess("i1", "A guess.", CaseReportCard.MainGuess, [211, 202])];
  const v = caseView(tl, ONE, "");
  expect(v.main?.facts.map((f) => f.id)).toEqual([202]);
  const html = cards(v, false) + rail(v);
  expect(html).not.toMatch(/NaN|undefined|null/);
  expect(html).not.toContain("Moved without telling anyone");
});

// R-0711
it("refuses a record whose couple has a marriage event but is not marked married", () => {
  const tl = halloran();
  tl.pair_bonds[2].married = false;
  expect(() => caseView(tl, ONE, "")).toThrow(/record fault/);
});

// R-0696
it("keeps every date inside a chip: no lead line names a year or a month", () => {
  const tl = halloran();
  tl.people.find((p) => p.id === 2)!.birth_event = 106;
  const v = caseView(tl, [{ last_activity: "2026-10-01T10:00:00" } as Session], "");
  const parted = halloran();
  parted.events.push(event(300, EventKind.Separated, "2020-01-01", { person: 1, spouse: 10 }));
  const leads = [v.brought.lead, v.brought.asked, v.couple.lead, v.effort, ...v.sides.map((s) => s.lead), ...caseView(parted, ONE, "").stages.map((r) => r.label)];
  for (const line of leads) expect(line).not.toMatch(/\b(1[89]|20)\d\d\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b/);
  expect(v.brought.lead).toBe("Nora's symptoms appear in 2 events in the record.");
});

// R-0709
it("shows on the coach's guess card only the guesses the coach chose for it", () => {
  const tl = halloran();
  tl.asked_questions = [...Array(13).keys()].map((n) => guess(`i${n}`, `Guess ${n}.`, n === 4 || n === 9 ? CaseReportCard.CoachGuess : null, [202]));
  expect(caseView(tl, ONE, "").guesses.map((g) => g.text)).toEqual(["Guess 4.", "Guess 9."]);
  tl.asked_questions = tl.asked_questions.map((q) => ({ ...q, case_report_card: null }));
  const none = caseView(tl, ONE, "");
  expect(none.guesses).toEqual([]);
  expect(cards(none, false).split(`data-card="${Card.Guesses}"`)[1].split("</section>")[0]).toContain(NOT_ENOUGH);
});
