import { expect, it } from "vitest";
import { cards, NOT_ENOUGH, NOT_SAID, rail } from "../src/case";
import { Card, caseView, ORDER } from "../src/caseview";
import { esc } from "../src/dom";
import {
  CaseReportCard,
  EventKind,
  EvidenceKind,
  QuestionKind,
  emptyTimeline,
  type AskedQuestion,
  type Person,
  SessionKind,
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

// R-0821
it("titles the first card Executive Summary, on the card and on its strip item", () => {
  const v = caseView(halloran(), ONE, "Patrick");
  expect(cards(v, true)).toContain(`<p class="label">1 · Executive Summary</p>`);
  expect(rail(v)).toContain(`<b>1</b>Executive Summary</button>`);
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
  const guessCards = [Card.Main, Card.OwnPart, Card.Choice];
  for (const card of guessCards) expect(html.split(`data-card="${card}"`)[1].split("</section>")[0]).toContain(NOT_ENOUGH);
  const thin = cards(caseView({ ...emptyTimeline(), people: [person(1, "Ines", "female", null, true)] }, ONE, ""), false);
  expect(thin.split(`data-card="${Card.Couple}"`)[1].split("</section>")[0]).not.toContain("<p class=\"lead\">");
});

// R-0740
it("says on what to work on that the person has not said yet what they are working on", () => {
  const tl = halloran();
  tl.asked_questions = [guess("i9", "A guess on no card.", null, [202])];
  const work = cards(caseView(tl, ONE, ""), false).split(`data-card="${Card.WorkOn}"`)[1].split("</section>")[0];
  expect(work).toContain(esc(NOT_SAID));
  expect(work).not.toContain(NOT_ENOUGH);
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
  const v = caseView(tl, [{ kind: SessionKind.Chat, last_activity: "2026-10-01T10:00:00" } as Session], "");
  const parted = halloran();
  parted.events.push(event(300, EventKind.Separated, "2020-01-01", { person: 1, spouse: 10 }));
  const leads = [v.brought.lead, v.brought.asked, v.couple.lead, v.couple.needs, v.effort, ...v.sides.map((s) => s.lead), ...caseView(parted, ONE, "").stages.map((r) => r.label)];
  for (const line of leads) expect(line).not.toMatch(/\b(1[89]|20)\d\d\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b/);
  expect(v.brought.lead).toBe("Nora's symptoms appear in 2 events in the diagram.");
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

// R-0711
it("counts only chats as the person talking with the coach, never a note or a recording", () => {
  const notes = [SessionKind.Note, SessionKind.Recording].map((kind) => ({ kind }) as Session);
  const v = caseView(halloran(), notes, "");
  expect([v.brought.asked, v.effort]).toEqual(["", ""]);
  const chatted = caseView(halloran(), [...notes, { kind: SessionKind.Chat } as Session], "");
  expect(chatted.effort).toBe("Nora has talked with the coach in one session.");
});

/** Lena and Omar, invented, since their courtship: Lena's parents Harold and
 * Ruth and her sister Dana; Omar's parents Samir and Farida and his brother
 * Karim; their children Noor and Eli; Noor's husband Jonah; Omar's earlier
 * wife Celia and their son Milo. */
function lenaOmar(): Timeline {
  const shift = (id: number, date: string, who: number, title: string, fields: Partial<TimelineEvent> = {}) =>
    event(id, EventKind.Shift, date, { person: who, title, ...fields });
  const noted = (id: number, date: string | null, who: number, title: string, fields: Partial<TimelineEvent> = {}) =>
    event(id, EventKind.Noted, date, { person: who, title, ...fields });
  return {
    ...emptyTimeline(),
    people: [
      person(1, "Lena", "female", 40, true),
      person(2, "Omar", "male", 41),
      person(3, "Ruth", "female"),
      person(4, "Harold", "male"),
      person(5, "Dana", "female", 40),
      person(6, "Farida", "female"),
      person(7, "Samir", "male"),
      person(8, "Karim", "male", 41),
      person(9, "Noor", "female", 42),
      person(10, "Eli", "male", 42),
      person(11, "Celia", "female"),
      person(12, "Milo", "male", 43),
      person(13, "Jonah", "male"),
    ],
    pair_bonds: [
      { id: 40, person_a: 4, person_b: 3, married: true },
      { id: 41, person_a: 7, person_b: 6, married: true },
      { id: 42, person_a: 1, person_b: 2, married: true },
      { id: 43, person_a: 2, person_b: 11, married: true },
      { id: 44, person_a: 9, person_b: 13, married: true },
    ],
    events: [
      // Omar's earlier marriage, and his drinking before he met Lena
      event(330, EventKind.Married, "1989-05-01", { person: 2, spouse: 11 }),
      event(331, EventKind.Birth, "1991-03-01", { person: 2, spouse: 11, child: 12, person_name: "Milo" }),
      shift(333, "1993-01-01", 2, "Drank heavily", { symptom: "up" }),
      event(332, EventKind.Divorced, "1994-02-01", { person: 2, spouse: 11 }),
      // the couple
      noted(300, "1995-05-01", 1, "First date with Omar", { relationshipTargets: [2] }),
      event(301, EventKind.Bonded, "1996-08-01", { person: 1, spouse: 2 }),
      shift(303, "1997-04-01", 1, "Anxious before the wedding", { anxiety: "up" }),
      noted(302, "1997-12-01", 1, "Engaged"),
      event(304, EventKind.Married, "1998-06-01", { person: 1, spouse: 2, location: "Portland" }),
      shift(305, "1998-06-01", 6, "Did not come to the wedding", { relationship: "distance", relationshipTargets: [2] }),
      noted(306, "1999-03-01", 2, "Moved to Tucson for Omar's job", { location: "Tucson" }),
      shift(307, "1999-09-01", 1, "Anxious", { anxiety: "up" }),
      event(308, EventKind.Birth, "2000-02-01", { person: 1, spouse: 2, child: 9, person_name: "Noor" }),
      shift(309, "2000-05-01", 2, "Working late every night", { functioning: "down" }),
      shift(310, "2001-09-01", 4, "Heart attack", { symptom: "up" }),
      noted(311, "2002-01-01", 1, "Lost her job at the clinic"),
      event(312, EventKind.Birth, "2003-07-01", { person: 1, spouse: 2, child: 10, person_name: "Eli" }),
      noted(325, "2004-01-01", 2, "Worked in another state for six months"),
      event(313, EventKind.Death, "2005-03-01", { person: 3, person_name: "Ruth" }),
      shift(314, "2005-06-01", 1, "Migraines back", { symptom: "up" }),
      shift(315, "2005-08-01", 2, "Distant", { relationship: "distance", relationshipTargets: [1] }),
      shift(316, "2005-09-01", 9, "Refused school for a month", { symptom: "up" }),
      event(321, EventKind.Married, "2006-05-01", { person: 5 }),
      event(319, EventKind.Divorced, "2008-06-01", { person: 8 }),
      event(317, EventKind.Death, "2009-01-01", { person: 7, person_name: "Samir" }),
      shift(318, "2012-04-01", 2, "Closer to his mother", { relationship: "toward", relationshipTargets: [6] }),
      shift(322, "2013-05-01", 6, "Stroke", { symptom: "up" }),
      noted(323, "2013-06-01", 6, "Moved into the spare room", { location: "Tucson" }),
      shift(324, "2014-03-01", 1, "Conflict with Farida", { relationship: "conflict", relationshipTargets: [6] }),
      shift(334, "2016-01-01", 2, "Lent Karim money", { relationship: "toward", relationshipTargets: [8] }),
      noted(336, "2016-09-01", 8, "Moved to Tucson", { location: "Tucson" }),
      event(337, EventKind.Married, "2023-01-01", { person: 8 }),
      noted(328, "2018-08-01", 9, "Left for college", { location: "Eugene" }),
      event(326, EventKind.Married, "2024-06-01", { person: 9, spouse: 13 }),
      shift(327, "2025-02-01", 9, "Burned out at work", { functioning: "down" }),
      noted(335, null, 1, "Moved without telling anyone"),
    ],
  };
}

const faces = (v: ReturnType<typeof caseView>) => v.couple.stages.map((st) => [st.head.face, ...st.facts.map((f) => f.face)]);
const under = (v: ReturnType<typeof caseView>, head: string) => faces(v).find((row) => row[0].endsWith(` · ${head}`))!.slice(1);

// R-0833
it("begins the couple card at the Bonded event, the courtship, and holds everything of theirs from then on", () => {
  const v = caseView(lenaOmar(), ONE, "");
  expect(v.married).toBe(true);
  expect(v.couple.lead).toBe("Lena and Omar are married.");
  const all = faces(v).flat().join("\n");
  expect(all).not.toContain("First date with Omar");
  expect(all).not.toContain("Drank heavily");
  // every event of either partner from the courtship to the wedding, aimed at no one or anyone
  expect(under(v, "got together")).toEqual(["Apr 1997 · Anxious before the wedding", "Dec 1997 · Engaged"]);
});

// R-0833
it("shows an earlier marriage of either partner and its children before the couple, as Kerr places them", () => {
  const v = caseView(lenaOmar(), ONE, "");
  expect(faces(v)[0]).toEqual(["May 1989 · Omar and Celia married", "Mar 1991 · Milo · birth", "Feb 1994 · Omar · divorced"]);
  expect(faces(v)[1][0]).toBe("Aug 1996 · got together");
});

// R-0833
it("puts every shift of either partner on the card, aimed at the other, at a relative or at no one", () => {
  const v = caseView(lenaOmar(), ONE, "");
  const all = faces(v).flat();
  expect(all).toContain("Sep 1999 · Anxious");
  expect(all).toContain("May 2000 · Omar · Working late every night");
  expect(all).toContain("Aug 2005 · Omar · Distant");
  expect(all).toContain("Jun 2005 · Migraines back");
  // a partner's event aimed at their own parent or an in-law is the couple's own
  expect(all).toContain("Apr 2012 · Omar · Closer to his mother");
  expect(all).toContain("Mar 2014 · Conflict with Farida");
});

// R-0835
it("opens a stage at each child's birth and keeps the shifts around it under it, with moves, work and time apart as chips", () => {
  const v = caseView(lenaOmar(), ONE, "");
  expect(under(v, "Noor born")).toEqual([
    "May 2000 · Omar · Working late every night",
    "Sep 2001 · Harold · Heart attack",
    "Jan 2002 · Lost her job at the clinic",
  ]);
  expect(under(v, "married").slice(0, 2)).toEqual(["Jun 1998 · Farida · Did not come to the wedding", "Mar 1999 · Omar · Moved to Tucson for Omar's job"]);
  expect(under(v, "Eli born")[0]).toBe("Jan 2004 · Omar · Worked in another state for six months");
});

// R-0833
it("shows a child's marked shifts and moves while at home, and a grown child's marriage as a stage of its own", () => {
  const v = caseView(lenaOmar(), ONE, "");
  const all = faces(v).flat();
  expect(all).toContain("Sep 2005 · Noor · Refused school for a month");
  expect(all).toContain("Aug 2018 · Noor · Left for college");
  expect(faces(v).map((row) => row[0])).toContain("Jun 2024 · Noor married");
  // once married, Noor's own life is her own card
  expect(all).not.toContain("Burned out at work");
});

// R-0834
it("always shows a death or serious illness of either partner's parent or sibling, named, wherever they live", () => {
  const v = caseView(lenaOmar(), ONE, "");
  const all = faces(v).flat();
  expect(all).toContain("Sep 2001 · Harold · Heart attack");
  expect(all).toContain("Mar 2005 · Ruth · death");
  expect(all).toContain("May 2013 · Farida · Stroke");
  // Samir's death falls more than two years from any event of the couple's own, and is shown all the same
  expect(all).toContain("Jan 2009 · Samir · death");
});

// R-0834
it("shows any other relative's event only when the record ties them to a partner and it falls within two years of an event of the couple's own", () => {
  const v = caseView(lenaOmar(), ONE, "");
  const all = faces(v).flat();
  // tied by her distance aimed at Omar, on the wedding's own day
  expect(all).toContain("Jun 1998 · Farida · Did not come to the wedding");
  // tied, and within two years of Noor's wedding
  expect(all).toContain("Jan 2023 · Karim · married");
  // tied, but near only Omar's own shift toward her, not an event of the couple's own
  expect(all).not.toContain("Jun 2013 · Farida · Moved into the spare room");
  // tied by Omar's loan, but no event of the couple's own within two years of his divorce
  expect(all).not.toContain("Jun 2008 · Karim · divorced");
  // within two years of Noor's school refusal, but nothing in the record ties Dana to either partner
  expect(all.join("\n")).not.toContain("Dana · ");
});

// R-0834
it("measures the two years from the couple's own events only, never from a partner's or a child's own shifts and moves", () => {
  const v = caseView(lenaOmar(), ONE, "");
  const all = faces(v).flat();
  // Karim's move: eight months after Omar's own shift toward him, but years from every event of the couple's own
  expect(all).not.toContain("Sep 2016 · Karim · Moved to Tucson");
  // the same relative's marriage, a year and a half before Noor's wedding: shown
  expect(all).toContain("Jan 2023 · Karim · married");
  const tl = lenaOmar();
  // a child's marked shift near the relative's move does not open the window either
  tl.events.push(event(338, EventKind.Shift, "2016-06-01", { person: 10, title: "Failed a year at school", functioning: "down" }));
  const again = faces(caseView(tl, ONE, "")).flat();
  expect(again).toContain("Jun 2016 · Eli · Failed a year at school");
  expect(again).not.toContain("Sep 2016 · Karim · Moved to Tucson");
});

// R-0835
it("groups the couple card under Bowen's stage heads in date order, the same heads the unmarried card uses", () => {
  const tl = lenaOmar();
  const heads = caseView(tl, ONE, "").couple.stages.map((st) => st.head.face);
  expect(heads).toEqual([
    "May 1989 · Omar and Celia married",
    "Aug 1996 · got together",
    "Jun 1998 · married",
    "Feb 2000 · Noor born",
    "Jul 2003 · Eli born",
    "Jun 2024 · Noor married",
  ]);
  const dates = (ids: number[]) => ids.map((id) => tl.events.find((e) => e.id === id)!.dateTime!);
  for (const st of caseView(tl, ONE, "").couple.stages) expect(dates(st.facts.map((f) => f.id))).toEqual([...dates(st.facts.map((f) => f.id))].sort());
  // the same words the unmarried card gives its stages
  tl.events.push(event(400, EventKind.Separated, "2026-01-01", { person: 1, spouse: 2 }));
  const unmarried = caseView(tl, ONE, "").stages.find((r) => r.label === "Lena and Omar")!;
  expect(unmarried.stages.map((st) => st.head.face).slice(0, 4)).toEqual(heads.slice(1, 5));
  const html = cards(caseView(lenaOmar(), ONE, ""), false).split(`data-card="${Card.Couple}"`)[1].split("</section>")[0];
  expect(html.match(/<div class="chips">/g)).toHaveLength(6);
  expect(html).toContain(`data-book="3"`);
});

// R-0835
it("says what the couple card still needs of the floor: the marriage date, each partner's place among brothers and sisters, the children in order", () => {
  const full = caseView(lenaOmar(), ONE, "");
  expect(full.couple.needs).toBe("");
  // Daniel's parents are not in the record
  expect(caseView(halloran(), ONE, "").couple.needs).toBe("This card still needs where Daniel stands among his brothers and sisters.");
  const thin: Timeline = {
    ...emptyTimeline(),
    people: [person(1, "Ines", "female", null, true), person(2, "Theo", "male")],
    pair_bonds: [{ id: 50, person_a: 1, person_b: 2, married: true }],
  };
  const v = caseView(thin, ONE, "");
  expect(v.married).toBe(true);
  expect(v.couple.stages).toEqual([]);
  expect(v.couple.needs).toBe("This card still needs when Ines and Theo married, where each of them stands among their brothers and sisters, and the children, in order.");
  const html = cards(v, false).split(`data-card="${Card.Couple}"`)[1].split("</section>")[0];
  expect(html).toContain("This card still needs");
  expect(html).not.toContain("not in the record");
});

// R-0696
it("never puts an undated event on the couple card", () => {
  const all = faces(caseView(lenaOmar(), ONE, "")).flat().join("\n");
  expect(all).not.toContain("Moved without telling anyone");
  expect(all).not.toMatch(/NaN|undefined|null/);
});
