import { expect, it } from "vitest";
import { BRINGS, cards, dashboard, NOT_ASKED, NOT_ENOUGH, NOT_SAID, quoted, rail, UNSURE } from "../src/case";
import { Card, caseView, ORDER, TOO_LITTLE } from "../src/caseview";
import { esc } from "../src/dom";
import {
  CaseReportCard,
  ClusterSource,
  EventKind,
  EvidenceKind,
  QuestionKind,
  emptyTimeline,
  type AskedQuestion,
  type Cluster,
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
  datePrecision: null,
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
  expect(order(cards(v, true), "card")).toEqual(ORDER);
  expect(order(cards(v, false), "card")).toEqual(ORDER);
  expect(order(rail(v), "jump")).toEqual(ORDER);
});

// R-0821
it("titles the first card Executive Summary, on the card and on its strip item", () => {
  const v = caseView(halloran(), ONE, "Patrick");
  expect(cards(v, true)).toContain(`<p class="label">1 · Executive Summary</p>`);
  expect(rail(v)).toContain(`<b>1</b>Executive Summary</button>`);
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
  const guessCards = [Card.Main, Card.Family, Card.Couple, Card.Sides, Card.OwnPart];
  for (const card of guessCards) expect(html.split(`data-card="${card}"`)[1].split("</section>")[0]).toContain(NOT_ENOUGH);
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
  for (const line of [v.effort]) expect(line).not.toMatch(/\b(1[89]|20)\d\d\b|\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b/);
});

const on = (text: string, card: CaseReportCard, evidence: AskedQuestion["evidence"]) => ({ ...guess("n1", text, card), evidence });
const body = (html: string, card: Card) => html.split(`data-card="${card}"`)[1].split("</section>")[0];

// R-0850
it("shows on what brought the person the coach's card: their own words, whose and when, and no page-built events", () => {
  const tl = halloran();
  tl.asked_questions = [on("\u201cI don't sleep that well.\u201d", CaseReportCard.WhatBrought, [{ kind: EvidenceKind.Statement, id: 7, label: "You said, 21 Sep" }])];
  const card = body(cards(caseView(tl, ONE, ""), false), Card.Brought);
  expect(card).toContain('<div class="bub user">I don&#39;t sleep that well.</div>');
  expect(card).toContain("You said, 21 Sep");
  expect(card).not.toContain('data-kind="event"');
});

// R-0863
it("puts only the quoted words of what brought the person in the statement bubble, the coach's words around them as plain card text", () => {
  const tl = halloran();
  const text = "Nora came because of her sleep: \u201cI don't sleep that well.\u201d She wants to understand it.";
  tl.asked_questions = [on(text, CaseReportCard.WhatBrought, [{ kind: EvidenceKind.Statement, id: 7, label: "You said, 21 Sep" }])];
  const card = body(cards(caseView(tl, ONE, ""), false), Card.Brought);
  expect(card.match(/class="bub user"/g)).toHaveLength(1);
  expect(card).toContain('<p class="lead">Nora came because of her sleep:</p><div class="gbub"><div class="bub user">I don&#39;t sleep that well.</div></div><p class="lead">She wants to understand it.</p>');
  expect(quoted('He said "it\'s the work" twice.').filter((p) => p.quote).map((p) => p.words)).toEqual(["it's the work"]);
  expect(quoted("No quotation marks here.")).toEqual([{ quote: false, words: "No quotation marks here." }]);
});

// R-0850
it("says on what brought the person that it is not asked yet, with the dashed amber question", () => {
  const card = body(cards(caseView(halloran(), ONE, ""), false), Card.Brought);
  expect(card).toContain(NOT_ASKED);
  expect(card).toContain(`chip ask qmark dashed">? ${BRINGS}`);
});

// R-0850
it("gives the coach's guess one pattern, each cluster's for and against, the person's own period dashed, and what it needs as the dashed amber chip", () => {
  const tl = halloran();
  tl.clusters = [cluster(tl, "c1", "Walter's death", "2011-02-01", "2013-05-01"), { ...cluster(tl, "c2", "A hard time", "2005-01-01", "2006-06-01"), source: ClusterSource.User }];
  const text = "Distance between Nora and Frank, 2011 to 2013.\nFor c1: Walter died Feb 2011.\nAgainst c1: one event.\nOpen: Frank's own events in those years.";
  tl.asked_questions = [on(text, CaseReportCard.CoachGuess, [{ kind: EvidenceKind.Cluster, id: "c1", label: "" }])];
  const v = caseView(tl, ONE, "");
  expect(v.guess?.text).toBe("Distance between Nora and Frank, 2011 to 2013.");
  const card = body(cards(v, false), Card.Guesses);
  expect(card).toContain("<b>For</b><span>Walter died Feb 2011.</span><b>Against</b><span>one event.</span>");
  expect(card).toContain('<div class="cl his">');
  expect(card).toContain("Your suggestion: A hard time");
  expect(card).toContain(`chip ask qmark dashed">? Frank&#39;s own events in those years.`);
  expect(card).not.toContain("For c1");
});

// R-0850
it("shows on the couple card the coach's statement on the person's own couple with one chip per event it rests on, the unsure date hollow", () => {
  const tl = halloran();
  tl.events = tl.events.map((e) => (e.id === 112 ? { ...e, dateCertainty: "approximate" } : e));
  tl.asked_questions = [guess("c1", "You and Daniel married in 2009; within three years Lily was born.", CaseReportCard.Couple, [111, 112, 211])];
  const card = body(cards(caseView(tl, ONE, ""), false), Card.Couple);
  expect(card).toContain("You and Daniel married in 2009; within three years Lily was born.</div>");
  const chip = (id: number) => card.split(`data-kind="event" data-target="${id}"`)[1].split("</button>")[0];
  expect(chip(111)).not.toContain(UNSURE);
  expect(chip(112)).toContain(UNSURE);
  expect(card.match(/data-kind="event"/g)).toHaveLength(2);
  expect(card).not.toContain('data-kind="person"');
});

// R-0850
it("says on the couple card that there is not enough in the diagram yet, with what it still needs as the dashed amber chip", () => {
  const tl = halloran();
  tl.asked_questions = [guess("c1", `${TOO_LITTLE}: when you met, how each of you was with your own family then.`, CaseReportCard.Couple)];
  const v = caseView(tl, ONE, "");
  expect(v.couple).toEqual({ guess: null, needs: "when you met, how each of you was with your own family then" });
  const card = body(cards(v, false), Card.Couple);
  expect(card).toContain(`${TOO_LITTLE}.</div>`);
  expect(card).toContain(`chip ask qmark dashed">? when you met, how each of you was with your own family then</span>`);
});

// R-0850
it("states on the part card the other way it could have gone, and draws no card of the choice", () => {
  const tl = halloran();
  tl.asked_questions = [guess("i1", "In 2011 you stopped calling your father.\nOther way: could contact have stayed light?", CaseReportCard.OwnPart, [202])];
  const html = cards(caseView(tl, ONE, ""), false);
  const card = body(html, Card.OwnPart);
  expect(card).toContain("In 2011 you stopped calling your father.</div>");
  expect(card).toContain("? could contact have stayed light?");
  expect(html).not.toContain('data-card="choice"');
});

// R-0850
it("gives what to work on its prognosis as its own sentence and the aim in the person's words", () => {
  const tl = halloran();
  tl.asked_questions = [guess("w1", "More contact with your father.\nPrognosis: more trouble near the next loss.\nAim: call him weekly", CaseReportCard.WorkOn, [210])];
  const v = caseView(tl, ONE, "");
  const card = body(cards(v, false), Card.WorkOn);
  expect(card).toContain('<p class="prognosis">more trouble near the next loss.</p>');
  expect(card).toContain("You said: call him weekly");
  expect(v.work.aim).toBeNull();
});

// R-0855
it("draws a fact chip whose date is approximate or unknown with the picture's hollow dot, and a certain one without", () => {
  const tl = halloran();
  tl.events = tl.events.map((e) =>
    e.id === 209 ? { ...e, dateCertainty: "approximate" } : e.id === 210 ? { ...e, dateCertainty: "unknown" } : e,
  );
  tl.asked_questions = [guess("i1", "Distance from her mother.", CaseReportCard.MainGuess, [202, 209, 210])];
  const card = body(cards(caseView(tl, ONE, ""), false), Card.Main);
  const chip = (id: number) => card.split(`data-target="${id}"`)[1].split("</button>")[0];
  expect(chip(202)).not.toContain(UNSURE);
  expect(chip(209)).toContain(`${UNSURE}2019 · Stopped visiting her mother`);
  expect(chip(210)).toContain(`${UNSURE}2021 · Panic attacks at work`);
});

// R-0709
it("shows on the coach's guess card only the guesses the coach chose for it", () => {
  const tl = halloran();
  tl.asked_questions = [...Array(13).keys()].map((n) => guess(`i${n}`, `Guess ${n}.`, n === 4 || n === 9 ? CaseReportCard.CoachGuess : null, [202]));
  expect(caseView(tl, ONE, "").guess?.text).toBe("Guess 9.");
  tl.asked_questions = tl.asked_questions.map((q) => ({ ...q, case_report_card: null }));
  const none = caseView(tl, ONE, "");
  expect(none.guess).toBeNull();
  expect(cards(none, false).split(`data-card="${Card.Guesses}"`)[1].split("</section>")[0]).toContain(NOT_ENOUGH);
});

// R-0711
it("counts only chats as the person talking with the coach, never a note or a recording", () => {
  const notes = [SessionKind.Note, SessionKind.Recording].map((kind) => ({ kind }) as Session);
  const v = caseView(halloran(), notes, "");
  expect(v.effort).toBe("");
  const chatted = caseView(halloran(), [...notes, { kind: SessionKind.Chat } as Session], "");
  expect(chatted.effort).toBe("Nora has talked with the coach in one session.");
});

/** A cluster over two events of its own, at its start and at its end, put on the timeline. */
function cluster(tl: Timeline, id: string, title: string, start: string, end: string): Cluster {
  const ids = [start, end].map((date, i) => {
    const n = 900 + tl.events.length;
    tl.events.push(event(n, EventKind.Shift, date, { person: 4, title: `${title} ${i}` }));
    return n;
  });
  return {
    id,
    label: start.slice(0, 4) === end.slice(0, 4) ? start.slice(0, 4) : `${start.slice(0, 4)}\u2013${end.slice(0, 4)}`,
    title,
    summary: null,
    reason: null,
    cluster_ids: [id],
    start,
    end,
    event_ids: ids,
    play_ids: ids,
    count: 3,
    digest: "",
  };
}

// R-0853
it("writes an app period's years once on its hypothesis chip, though its stored name ends in them", () => {
  const tl = halloran();
  tl.clusters = [cluster(tl, "c1", "The move north, 2004", "2004-03-01", "2004-11-01"), cluster(tl, "c2", "After Walter's death, 2011\u20132013", "2011-02-01", "2013-05-01")];
  const v = caseView(tl, ONE, "");
  expect(v.hypotheses.map((c) => c.label)).toEqual(["Hypothesis: The move north \u00b7 2004", "Hypothesis: After Walter's death \u00b7 2011\u20132013"]);
});

// R-0698, R-0201
it("adds every cluster to the coach's guess card as a hypothesis chip, in date order, that opens it", () => {
  const tl = halloran();
  tl.asked_questions = [guess("i1", "Guess one.", CaseReportCard.CoachGuess, [202])];
  const before = cards(caseView(tl, ONE, ""), false).split(`data-card="${Card.Guesses}"`)[1].split("</section>")[0];
  tl.clusters = [cluster(tl, "c2", "After Walter's death", "2011-02-01", "2013-05-01"), cluster(tl, "c1", "The move north", "2004-03-01", "2004-11-01")];
  const v = caseView(tl, ONE, "");
  expect(v.hypotheses.map((c) => c.label)).toEqual(["Hypothesis: The move north \u00b7 2004", "Hypothesis: After Walter's death \u00b7 2011\u20132013"]);
  const card = cards(v, false).split(`data-card="${Card.Guesses}"`)[1].split("</section>")[0];
  expect(card.startsWith(before.split("</div></div>")[0])).toBe(true);
  const targets = [...card.matchAll(/data-kind="cluster" data-target="(c\d)"/g)].map((m) => m[1]);
  expect(targets).toEqual(["c1", "c2"]);
  tl.clusters = [];
  expect(caseView(tl, ONE, "").hypotheses).toEqual([]);
});

// R-0853
it("writes a period's years on its chip as the server stored them, not from the span drawn on the line", () => {
  const tl = halloran();
  const p = { ...cluster(tl, "p1", "When Lily came", "2009-09-01", "2010-11-01"), source: ClusterSource.User };
  tl.clusters = [{ ...p, label: "2009\u20132011" }];
  expect(caseView(tl, ONE, "").hypotheses.map((c) => c.label)).toEqual(["Your suggestion: When Lily came · 2009–2011"]);
});

// R-0865
it("labels a period the person named as their suggestion, never as their period", () => {
  const tl = halloran();
  tl.clusters = [{ ...cluster(tl, "p1", "A hard time", "2005-01-01", "2006-06-01"), source: ClusterSource.User }, cluster(tl, "c1", "Walter's death", "2011-02-01", "2013-05-01")];
  const labels = caseView(tl, ONE, "").hypotheses.map((c) => c.label);
  expect(labels[0]).toMatch(/^Your suggestion: A hard time/);
  expect(labels[1]).toMatch(/^Hypothesis: /);
  expect(labels.join(" ")).not.toContain("Your period");
});

const side = (id: string, text: string, people: number[], events: number[] = []): AskedQuestion => ({
  ...guess(id, text, CaseReportCard.Sides, events),
  evidence: [
    ...people.map((p) => ({ kind: EvidenceKind.Person, id: p, label: "" })),
    ...events.map((e) => ({ kind: EvidenceKind.Event, id: e, label: "" })),
  ],
});

// R-0850, R-0866
it("shows on the family card the coach's line per household with a chip per person and event it rests on, and keeps the picture button on the phone", () => {
  const tl = halloran();
  tl.events = tl.events.map((e) => (e.id === 112 ? { ...e, dateCertainty: "approximate" } : e));
  const text = "You grew up with Frank, Elaine and Sean.\nYou live with Daniel and Lily; Lily was born around 2012.";
  tl.asked_questions = [{ ...guess("f1", text, CaseReportCard.Family, [112]), evidence: [{ kind: EvidenceKind.Person, id: 8, label: "" }, { kind: EvidenceKind.Event, id: 112, label: "" }] }];
  const v = caseView(tl, ONE, "");
  const card = body(cards(v, false), Card.Family);
  expect(card).toContain(`${esc(text)}</div>`);
  expect(card.split(`data-kind="event" data-target="112"`)[1].split("</button>")[0]).toContain(UNSURE);
  expect(card).toContain('data-kind="person" data-target="8"');
  expect(card).toContain('class="famcard"');
  expect(card).not.toContain(`class="fam"`);
  expect(body(cards(v, true), Card.Family)).not.toContain('class="famcard"');
});

// R-0850, R-0866
it("puts each note on each parent's family under the side whose people it rests on, whatever order the coach wrote them in", () => {
  const tl = halloran();
  tl.asked_questions = [
    side("s1", "On your father's side, Walter and June married young.", [4, 5]),
    side("s2", "On your mother's side, little is known.", [3]),
  ];
  const v = caseView(tl, ONE, "");
  expect(v.sideNotes.map((s) => [s.label, s.note.guess?.text])).toEqual([
    ["Her father's side", "On your father's side, Walter and June married young."],
    ["Her mother's side", "On your mother's side, little is known."],
  ]);
  const card = body(cards(v, false), Card.Sides);
  expect(card).toContain('<p class="sublabel">Her father&#39;s side</p>');
  expect(card).toContain('data-kind="person" data-target="4"');
  expect(card).not.toContain(`class="fam"`);
  expect(card).not.toContain("<details");
});

// R-0850, R-0866
it("never tells the sides apart by a word in the note: a note resting on no side's people takes the side left open, the mother's first in the order written", () => {
  const tl = halloran();
  tl.asked_questions = [
    side("s1", `${TOO_LITTLE}: your mother's parents' names.`, []),
    side("s2", "On your father's side, Walter and June married young.", [4]),
  ];
  const placed = caseView(tl, ONE, "").sideNotes;
  expect(placed[0].note.guess?.text).toBe("On your father's side, Walter and June married young.");
  expect(placed[1].note).toEqual({ guess: null, needs: "your mother's parents' names" });
  tl.asked_questions = [side("s1", "One side.", []), side("s2", "The other side.", [2, 3])];
  expect(caseView(tl, ONE, "").sideNotes.map((s) => s.note.guess?.text)).toEqual(["The other side.", "One side."]);
});

// R-0866
it("titles card four for the couple since they met only when the person has a pair-bond of their own, else the couple", () => {
  const bonded = caseView(halloran(), ONE, "");
  expect(cards(bonded, false)).toContain(`<p class="label">4 · The couple since they met</p>`);
  expect(rail(bonded)).toContain(`<b>4</b>The couple</button>`);
  const tl = halloran();
  tl.pair_bonds = tl.pair_bonds.filter((b) => b.id !== 33);
  const single = caseView(tl, ONE, "");
  expect(cards(single, false)).toContain(`<p class="label">4 · The couple</p>`);
  expect(rail(single)).toContain(`<b>4</b>The couple</button>`);
});

// R-0850
it("shows on the Executive Summary a chip only for the people its words name, by name or by what they are to the person, or the coach cited", () => {
  const tl = halloran();
  const summary = (text: string) => [on(text, CaseReportCard.MainGuess, [112, 209].map((id) => ({ kind: EvidenceKind.Event, id, label: "" })))];
  const shown = () => [...body(cards(caseView(tl, ONE, ""), false), Card.Main).matchAll(/data-kind="person" data-target="(\d+)"/g)].map((m) => m[1]);
  tl.asked_questions = summary("Nora's panic began after Lily was born.");
  expect(shown()).toEqual(["11"]);
  tl.asked_questions = summary("Your panic began after your daughter was born, and you stopped visiting your mother.");
  expect(shown()).toEqual(["11", "3"]);
  tl.asked_questions = summary("Your panic began after Lily was born.");
  tl.asked_questions[0].evidence.push({ kind: EvidenceKind.Person, id: 3, label: "" });
  expect(body(cards(caseView(tl, ONE, ""), false), Card.Main)).toContain('data-kind="person" data-target="3"');
});

// R-0697
it("leaves the card's title off the family picture beside the cards, so it shows once", () => {
  const v = caseView(halloran(), ONE, "");
  expect(dashboard(v)).not.toContain("Who is in the family");
  expect(cards(v, true)).toContain(`<p class="label">2 · Who is in the family</p>`);
});
