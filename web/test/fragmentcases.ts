/** The sixteen hostile fragments the conventions sheet demands, plus the small
 * ones the open rules are judged on. Names come from the stand-in family in
 * doc/mockups/family.md; no real person appears here. */

import { Sex, Kind, type Fragment, type FragPerson } from "../src/fragment";

const person = (
  id: number,
  name: string | null,
  gender: string | null,
  parents: number | null = null,
): FragPerson => ({ id, name, gender, parents });

const birth = (id: number, date: string) => ({
  kind: Kind.Birth,
  person: id,
  spouse: null,
  dateTime: date,
});

const death = (id: number, date: string) => ({
  kind: Kind.Death,
  person: id,
  spouse: null,
  dateTime: date,
});

const between = (kind: Kind, a: number, b: number, date: string) => ({
  kind,
  person: a,
  spouse: b,
  dateTime: date,
});

/** Marcus in the middle, Errol and Odile above, Delphine beside, Corinne and
 * Theo below — the family everything else is a variation of. */
export const plain = (): Fragment => ({
  center: 3,
  people: [
    person(1, "Errol", Sex.Male),
    person(2, "Odile", Sex.Female),
    person(3, "Marcus", Sex.Male, 10),
    person(4, "Delphine", Sex.Female),
    person(5, "Corinne", Sex.Female, 11),
    person(6, "Theo", Sex.Male, 11),
  ],
  bonds: [
    { id: 10, person_a: 1, person_b: 2, married: true },
    { id: 11, person_a: 3, person_b: 4, married: true },
  ],
  events: [
    birth(1, "1924-01-01"),
    birth(2, "1926-01-01"),
    birth(3, "1951-10-01"),
    birth(4, "1953-01-01"),
    birth(5, "1975-01-01"),
    birth(6, "1979-01-01"),
    between(Kind.Married, 1, 2, "1948-01-01"),
    between(Kind.Married, 3, 4, "1970-01-01"),
  ],
});

const with_ = (change: (f: Fragment) => void): Fragment => {
  const f = plain();
  change(f);
  return f;
};

export const cases: { key: string; title: string; fragment: Fragment }[] = [
  { key: "1", title: "One bond with children under it", fragment: plain() },
  {
    key: "2",
    title: "A bond that ended: one slash separated, two divorced",
    fragment: with_((f) => {
      f.events.push(between(Kind.Separated, 3, 4, "1980-01-01"));
      f.events.push(between(Kind.Divorced, 3, 4, "1981-01-01"));
    }),
  },
  {
    key: "3",
    title: "Two bonds in sequence, children under each",
    fragment: with_((f) => {
      f.people.push(person(7, "Nadine", Sex.Female));
      f.people.push(person(8, "Ines", Sex.Female, 12));
      f.bonds.push({ id: 12, person_a: 3, person_b: 7, married: false });
      f.events.push(between(Kind.Divorced, 3, 4, "1981-01-01"));
      f.events.push(between(Kind.Bonded, 3, 7, "1986-01-01"));
      f.events.push(birth(8, "1988-01-01"));
    }),
  },
  {
    key: "4",
    title: "A partner nobody named, held in the record as Marcus's partner",
    fragment: with_((f) => {
      f.people[3] = person(4, "Marcus's partner", null);
      f.bonds[1] = { id: 11, person_a: 3, person_b: 4, married: null };
      f.events = f.events.filter((e) => e.person !== 4 && e.spouse !== 4);
    }),
  },
  {
    key: "5",
    title: "A parent nobody named, held in the record as Marcus's mother",
    fragment: with_((f) => {
      f.people[1] = person(2, "Marcus's mother", null);
      f.events = f.events.filter(
        (e) => !(e.kind === Kind.Birth && e.person === 2),
      );
    }),
  },
  {
    key: "6",
    title: "A deceased person with an age, and one without",
    fragment: with_((f) => {
      f.events.push(death(1, "1989-01-01"));
      f.events.push(death(2, "1998-03-01"));
      f.events = f.events.filter(
        (e) => !(e.kind === Kind.Birth && e.person === 2),
      );
    }),
  },
  {
    key: "7",
    title: "A miscarriage among the children",
    fragment: with_((f) => {
      f.people.push(person(9, null, Sex.Miscarriage, 11));
      f.events.push(birth(9, "1977-01-01"));
    }),
  },
  {
    key: "8",
    title: "A miscarriage and an abortion side by side",
    fragment: with_((f) => {
      f.people.push(person(9, null, Sex.Miscarriage, 11));
      f.people.push(person(10, null, Sex.Abortion, 11));
      f.events.push(birth(9, "1977-01-01"));
      f.events.push(birth(10, "1978-01-01"));
    }),
  },
  {
    key: "9",
    title: "Twins: the shared line and the single riser",
    fragment: with_((f) => {
      f.people.push(person(11, "Jonas", Sex.Male, 11));
      f.events.push(birth(11, "1979-01-01"));
      f.twins = [[6, 11]];
    }),
  },
  {
    key: "10",
    title: "An adopted child",
    fragment: with_((f) => {
      f.events.push({
        kind: Kind.Adopted,
        person: 6,
        spouse: null,
        dateTime: "1981-01-01",
      });
    }),
  },
  {
    key: "11",
    title: "No gender recorded: the rounded box, no question inside",
    fragment: with_((f) => {
      f.people[5] = person(6, "Theo", null, 11);
    }),
  },
  {
    key: "12",
    title: "A child whose parents' bond is not in the record: they stand alone",
    fragment: with_((f) => {
      f.people.push(person(12, "Ines", Sex.Female, null));
      f.loose = [12];
    }),
  },
  {
    key: "13",
    title: "Two versions of one person that disagree",
    fragment: with_((f) => {
      f.people[5] = person(6, "Theo", null, 11);
      f.unsurePeople = [6];
      f.ask = [6];
    }),
  },
  {
    key: "14",
    title: "A forty-character name",
    fragment: with_((f) => {
      f.people[4] = person(5, "Corinnebartholomewinaverylongname1234", Sex.Female, 11);
    }),
  },
  {
    key: "15",
    title: "A name in non-Latin characters, and one with combining marks",
    fragment: with_((f) => {
      f.people[4] = person(5, "Ко́ринна", Sex.Female, 11);
      f.people[5] = person(6, "テオドール", Sex.Male, 11);
    }),
  },
  {
    key: "16",
    title: "All of it at once",
    fragment: with_((f) => {
      f.people.push(person(7, "Nadine", Sex.Female));
      f.people.push(person(8, "Ines", Sex.Female, 12));
      f.people.push(person(9, null, Sex.Miscarriage, 11));
      f.people.push(person(10, null, Sex.Abortion, 11));
      f.people.push(person(11, "Jonas", Sex.Male, 11));
      f.people.push(person(12, "Ко́ринна", Sex.Female, null));
      f.bonds.push({ id: 12, person_a: 3, person_b: 7, married: false });
      f.events.push(birth(8, "1988-01-01"));
      f.events.push(birth(9, "1977-01-01"));
      f.events.push(birth(10, "1978-01-01"));
      f.events.push(birth(11, "1979-01-01"));
      f.events.push(death(1, "1989-01-01"));
      f.events.push(between(Kind.Separated, 3, 4, "1980-01-01"));
      f.events.push(between(Kind.Divorced, 3, 4, "1981-01-01"));
      f.events.push(between(Kind.Bonded, 3, 7, "1986-01-01"));
      f.events.push({
        kind: Kind.Adopted,
        person: 8,
        spouse: null,
        dateTime: "1990-01-01",
      });
      f.twins = [[6, 11]];
      f.loose = [12];
      f.unsurePeople = [10];
      f.ask = [10];
    }),
  },
];

/** The middle person alone, for the rows that judge one rule at a time. */
export const twoBonds = () => cases.find((c) => c.key === "3")!.fragment;
export const ended = () => cases.find((c) => c.key === "2")!.fragment;
export const twins = () => cases.find((c) => c.key === "9")!.fragment;
export const adopted = () => cases.find((c) => c.key === "10")!.fragment;
export const nogender = () => cases.find((c) => c.key === "11")!.fragment;
export const loss = () => cases.find((c) => c.key === "8")!.fragment;
export const genericPartner = () => cases.find((c) => c.key === "4")!.fragment;
export const genericParent = () => cases.find((c) => c.key === "5")!.fragment;
export const orphan = () => cases.find((c) => c.key === "12")!.fragment;
export const longName = () => cases.find((c) => c.key === "14")!.fragment;
