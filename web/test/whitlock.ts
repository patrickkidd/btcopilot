import type { Case, PairBond, Person, Timeline, TimelineEvent } from "../src/types";

/** The Whitlock stand-in family (doc/mockups/family.md), wholly invented, as a
 * record the play-by-play reads, with the cases the approved stand-in page
 * tells (design/playbyplay-snapshots/cases.json). */

const person = (
  id: number,
  name: string,
  gender: string | null,
  birth: string | null,
  over: Partial<Person> = {},
): Person => ({
  id,
  name,
  last_name: null,
  gender,
  notes: null,
  primary: false,
  birth,
  birth_event: null,
  death_event: null,
  parents: null,
  ...over,
});

export const ERROL = 1;
export const ODILE = 2;
export const MARCUS = 3;
export const DELPHINE = 4;
export const CORINNE = 5;
export const THEO = 6;
export const PARTNER = 7;

const GRANDPARENTS = 20;
const PARENTS = 21;
const COUPLE = 22;

export const people = (): Person[] => [
  person(ERROL, "Errol", "male", "1924-06-01", { death_event: 119 }),
  person(ODILE, "Odile", "female", "1926-06-01", { death_event: 130 }),
  person(MARCUS, "Marcus", "male", "1951-10-01", { parents: GRANDPARENTS }),
  person(DELPHINE, "Delphine", "female", "1953-06-01"),
  person(CORINNE, "Corinne", "female", "1975-06-01", { primary: true, parents: PARENTS }),
  person(THEO, "Theo", "male", "1979-06-01", { parents: PARENTS }),
  person(PARTNER, "partner", "male", null),
];

export const bonds = (): PairBond[] => [
  { id: GRANDPARENTS, person_a: ERROL, person_b: ODILE, married: true },
  { id: PARENTS, person_a: MARCUS, person_b: DELPHINE, married: true },
  { id: COUPLE, person_a: PARTNER, person_b: CORINNE, married: false },
];

export const event = (
  id: number,
  dateTime: string,
  kind: string,
  who: number | null,
  over: Partial<TimelineEvent> = {},
): TimelineEvent => ({
  id,
  label: "",
  sentence: "",
  person_name: "",
  person: who,
  dateTime,
  endDateTime: null,
  dateCertainty: "certain",
  kind,
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
  ...over,
});

export const events = (): TimelineEvent[] => [
  event(103, "1948-06-01", "married", ERROL, { spouse: ODILE }),
  event(109, "1970-06-01", "married", MARCUS, { spouse: DELPHINE }),
  event(119, "1989-06-01", "death", ERROL),
  // 1980–82: a couple comes apart, and the trouble lands on one person
  event(201, "1980-09-15", "separated", MARCUS, { spouse: DELPHINE }),
  event(202, "1980-09-15", "noted", MARCUS, { description: "Took a room over the hardware store" }),
  event(203, "1981-01-15", "shift", MARCUS, { symptom: "up", description: "Drinking most nights" }),
  event(204, "1981-06-15", "divorced", MARCUS, { spouse: DELPHINE }),
  event(205, "1981-09-15", "shift", THEO, { description: "Started at the church day care" }),
  event(206, "1982-04-15", "shift", MARCUS, { symptom: "down", description: "Stopped drinking" }),
  event(207, "1982-09-15", "shift", CORINNE, { description: "Started school" }),
  event(208, "1982-11-15", "shift", CORINNE, { symptom: "up", description: "Her teacher called Delphine" }),
  // 1998–99: three people after a death
  event(130, "1998-03-15", "death", ODILE),
  event(131, "1998-05-15", "shift", DELPHINE, {
    relationship: "toward",
    relationshipTargets: [CORINNE],
    description: "Started calling Corinne every night",
  }),
  event(132, "1998-07-15", "shift", CORINNE, {
    relationship: "away",
    relationshipTargets: [MARCUS],
    description: "Stopped opening Marcus's letters",
  }),
  event(133, "1998-09-15", "shift", null, { description: "The family left the house on Bluff Street" }),
  event(135, "1999-02-15", "shift", DELPHINE, { symptom: "down", description: "Scans came back clear" }),
  event(136, "1999-05-15", "shift", MARCUS, { symptom: "up", description: "In the hospital with chest pains" }),
];

export const timeline = (): Timeline => ({
  people: people(),
  pair_bonds: bonds(),
  events: events(),
  clusters: [
    {
      id: "apart",
      label: "1980–82",
      title: "A couple comes apart",
      summary: null,
      reason: null,
      cluster_ids: [],
      start: "1980-09-15",
      end: "1982-11-15",
      event_ids: [201, 202, 203, 204, 205, 206, 207, 208],
      play_ids: [201, 202, 203, 204, 205, 206, 207, 208],
      count: 8,
      digest: "apart-now",
    },
    {
      id: "death",
      label: "1998–99",
      title: "After a death",
      summary: null,
      reason: null,
      cluster_ids: [],
      start: "1998-03-15",
      end: "1999-05-15",
      event_ids: [130, 131, 132, 133, 135, 136],
      play_ids: [130, 131, 132, 133, 135, 136],
      count: 6,
      digest: "death-now",
    },
  ],
  questions: [],
  asked_questions: [],
  axis: null,
  shelf: [],
  coded_in: {},
});

export const apart = (): Case => ({
  cluster_id: "apart",
  point: "As Marcus drank less, school got hard for you.",
  snapshots: [
    {
      date: "1980-09-15", event_ids: [201, 202],
      fact: "Marcus and Delphine separated, and Marcus took a room over the hardware store. You were five; Theo was one.",
      guess: null,
    },
    { date: "1981-01-15", event_ids: [203], fact: "Marcus was drinking “most nights,” as Delphine put it later.", guess: null },
    { date: "1981-06-15", event_ids: [204], fact: "The divorce went through in June.", guess: null },
    { date: "1982-04-15", event_ids: [206], fact: "Marcus “hadn’t had a drink since Easter.”", guess: null },
    {
      date: "1982-11-15", event_ids: [208],
      fact: "Your teacher called Delphine: you had stopped talking in class.",
      guess: "My guess: the trouble moved from Marcus to you as his drinking eased.",
    },
  ],
  question: "Theo started day care that autumn. Who was looking after the two of you?",
});

export const death = (): Case => ({
  cluster_id: "death",
  point: "After Odile died, Delphine called you every night.",
  snapshots: [
    { date: "1998-03-15", event_ids: [130], fact: "Your grandmother Odile died in Marquette.", guess: null },
    { date: "1998-05-15", event_ids: [131], fact: "Delphine started calling you every night, “sometimes twice.”", guess: null },
    {
      date: "1998-07-15", event_ids: [132],
      fact: "You stopped opening Marcus’s letters.",
      guess: "My guess: you moved further from Marcus as Delphine moved closer to you.",
    },
    { date: "1999-02-15", event_ids: [135], fact: "Delphine’s scans came back clear.", guess: null },
    { date: "1999-05-15", event_ids: [136], fact: "Marcus went into the hospital in Marquette with chest pains.", guess: null },
  ],
  question: "Seven months pass between the letters and the clear scan. Where were you living that autumn?",
});

/** A record as sparse as a first session leaves it: the reader and her
 * mother, with no parent link and no bond between them. */
export const sparse = (): Timeline => ({
  ...timeline(),
  people: [
    person(CORINNE, "Corinne", "female", "1975-06-01", { primary: true }),
    person(DELPHINE, "Delphine", "female", null),
  ],
  pair_bonds: [],
  events: [
    event(301, "2019-03-15", "shift", CORINNE, { symptom: "up", description: "Couldn't sleep" }),
    event(302, "2019-10-15", "shift", DELPHINE, { description: "Moved in with her sister" }),
  ],
  clusters: [
    {
      ...timeline().clusters[0],
      id: "alone",
      label: "2019",
      start: "2019-03-15",
      end: "2019-10-15",
      event_ids: [301, 302],
      play_ids: [301, 302],
      count: 2,
    },
  ],
});

export const alone = (): Case => ({
  cluster_id: "alone",
  point: "You stopped sleeping months before Delphine moved.",
  snapshots: [
    { date: "2019-03-15", event_ids: [301], fact: "You couldn't sleep that March.", guess: null },
    { date: "2019-10-15", event_ids: [302], fact: "Delphine moved in with her sister.", guess: null },
  ],
  question: "Who else was in the house that year?",
});
