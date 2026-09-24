/** People and pair bonds as the review reads them.
 *
 * A version of a person says almost nothing on its own: the argument is who
 * they are bonded to and whose child they are. So each version is drawn as a
 * family fragment against the record the coder wrote it on, with the version
 * itself standing in the middle (R-0326, ballot 3b).
 */

import { render, type FragBond, type Fragment, type FragPerson } from "./fragment";
import { ItemKind, type CodingRecord, type Opinion, type PairBond, type Person } from "./types";

/** The kinds of item that carry family structure rather than a moment in time. */
export const STRUCTURE = [ItemKind.Person, ItemKind.PairBond];

export const isStructure = (kind: ItemKind): boolean => STRUCTURE.includes(kind);

const asPerson = (one: Person): FragPerson => ({
  id: one.id,
  name: one.name,
  gender: one.gender,
  parents: one.parents ?? null,
});

const asBond = (one: PairBond): FragBond => ({
  id: one.id,
  person_a: one.person_a,
  person_b: one.person_b,
  married: one.married ?? null,
});

/** What one version of a person or a bond is drawn as: the coder's own family
 * with this version in it, centred on the person being argued over. */
export function fragmentOf(
  record: CodingRecord | undefined,
  kind: ItemKind,
  item: Record<string, unknown>,
): Fragment | null {
  if (!record) return null;
  const id = Number(item.id);
  if (!Number.isFinite(id)) return null;

  const people = record.people.map(asPerson);
  const bonds = record.pair_bonds.map(asBond);
  let centre: number | null = null;

  if (kind === ItemKind.Person) {
    const mine = asPerson(item as unknown as Person);
    const at = people.findIndex((one) => one.id === id);
    if (at < 0) people.push(mine);
    else people[at] = mine;
    centre = id;
  } else {
    const mine = asBond(item as unknown as PairBond);
    const at = bonds.findIndex((one) => one.id === id);
    if (at < 0) bonds.push(mine);
    else bonds[at] = mine;
    centre = mine.person_a ?? mine.person_b;
  }
  if (centre === null || !people.some((one) => one.id === centre)) return null;

  // A bond with a side the record does not hold is a fault, and the renderer
  // says so rather than drawing around it; here it is simply not drawn.
  const known = new Set(people.map((one) => one.id));
  const whole = bonds.filter(
    (one) =>
      one.person_a !== null &&
      one.person_b !== null &&
      known.has(one.person_a) &&
      known.has(one.person_b),
  );
  const bondIds = new Set(whole.map((one) => one.id));
  const loose = people
    .filter((one) => one.parents !== null && !bondIds.has(one.parents))
    .map((one) => one.id);

  return {
    center: centre,
    people: people.map((one) =>
      one.parents !== null && !bondIds.has(one.parents)
        ? { ...one, parents: null }
        : one,
    ),
    bonds: whole,
    events: record.events.map((one) => ({
      kind: one.kind ?? "",
      person: one.person,
      spouse: one.spouse,
      dateTime: one.dateTime,
    })),
    loose: loose.filter((one) => one !== centre),
  };
}

/** One version's drawing, at the size a version card holds. */
export const drawVersion = (
  records: Map<number, CodingRecord>,
  kind: ItemKind,
  opinion: Opinion,
): string => {
  const fragment = fragmentOf(
    records.get(opinion.coding_id ?? -1),
    kind,
    opinion.item,
  );
  return fragment ? render(fragment, { u: 34 }) : "";
};

/** The fields two versions of a person, or of a bond, can differ by, in the
 * order they read. */
export const PERSON_FIELDS = ["name", "last_name", "gender", "parents"] as const;
export const BOND_FIELDS = ["person_a", "person_b", "married"] as const;

export const fieldsOf = (kind: ItemKind): readonly string[] =>
  kind === ItemKind.Person ? PERSON_FIELDS : BOND_FIELDS;

/** What one version says, in the record's own words: a bond said by the two
 * names, and who somebody was born to said by the couple rather than by the
 * number the record holds it as. */
export function versionWords(
  record: CodingRecord | undefined,
  item: Record<string, unknown>,
  fields: readonly string[],
): string {
  const named = (id: unknown) =>
    record?.people.find((one) => one.id === Number(id))?.name ?? "someone";
  const said = fields.map((field) => {
    const value = item[field];
    if (field === "parents") {
      const bond = record?.pair_bonds.find((one) => one.id === Number(value));
      return bond
        ? `born to ${named(bond.person_a)} & ${named(bond.person_b)}`
        : "no parents recorded";
    }
    if (field === "person_a" || field === "person_b") return named(value);
    if (field === "married") return value ? "married" : "together, not married";
    return value === null || value === undefined ? "" : String(value);
  });
  return said.filter(Boolean).join(" · ");
}

/** How a person or a bond is named in a list, which is all a row has room for. */
export function structureName(
  kind: ItemKind,
  item: Record<string, unknown>,
  people: { id: number; name: string }[],
): string {
  if (kind === ItemKind.Person)
    return String(item.name ?? "") || "somebody with no name yet";
  const named = (id: unknown) =>
    people.find((one) => one.id === Number(id))?.name ?? "someone";
  return `${named(item.person_a)} & ${named(item.person_b)}`;
}
