import { Relationship } from "./editor";
import { isCoder } from "./dom";

/** The theory expert's concept pages, one per code, for coders alone (R-0541).
 * A page opens in a tab of its own, so the vote or the coding under it stays
 * where it was. */
export enum Concept {
  Symptom = "symptom",
  Anxiety = "anxiety",
  Functioning = "functioning",
  Conflict = "conflict",
  Distance = "distance",
  Cutoff = "cutoff",
  Reciprocity = "reciprocity",
  Projection = "projection",
  Triangles = "triangles",
  DefinedSelf = "definedself",
  TowardAway = "toward-away",
}

const NAMES: Record<Concept, string> = {
  [Concept.Symptom]: "symptom",
  [Concept.Anxiety]: "anxiety",
  [Concept.Functioning]: "functioning",
  [Concept.Conflict]: "conflict",
  [Concept.Distance]: "distance",
  [Concept.Cutoff]: "cutoff",
  [Concept.Reciprocity]: "over- and underfunctioning",
  [Concept.Projection]: "projection",
  [Concept.Triangles]: "triangles",
  [Concept.DefinedSelf]: "defined self",
  [Concept.TowardAway]: "toward and away",
};

const SHIFTS = [Concept.Symptom, Concept.Anxiety, Concept.Functioning];

/** Fusion has no page yet. */
const OF_RELATIONSHIP: Partial<Record<Relationship, Concept>> = {
  [Relationship.Conflict]: Concept.Conflict,
  [Relationship.Distance]: Concept.Distance,
  [Relationship.Cutoff]: Concept.Cutoff,
  [Relationship.Overfunctioning]: Concept.Reciprocity,
  [Relationship.Underfunctioning]: Concept.Reciprocity,
  [Relationship.Projection]: Concept.Projection,
  [Relationship.Inside]: Concept.Triangles,
  [Relationship.Outside]: Concept.Triangles,
  [Relationship.DefinedSelf]: Concept.DefinedSelf,
  [Relationship.Toward]: Concept.TowardAway,
  [Relationship.Away]: Concept.TowardAway,
};

export const INDEX_URL = "/app/theory";

/** The codes any of these versions of an event carry, in page order. */
export function conceptsOf(items: object[]): Concept[] {
  const found = new Set<Concept>();
  for (const item of items as Record<string, unknown>[]) {
    for (const shift of SHIFTS) if (item[shift]) found.add(shift);
    const move = OF_RELATIONSHIP[item.relationship as Relationship];
    if (move) found.add(move);
  }
  return Object.values(Concept).filter((one) => found.has(one));
}

const link = (href: string, words: string) =>
  `<a href="${href}" target="_blank" rel="noopener">${words}</a>`;

/** One line of links to the pages, or nothing when no code is named. */
export function conceptLinks(concepts: Concept[], index = false): string {
  if (!isCoder() || !concepts.length) return "";
  const links = concepts.map((one) => link(`${INDEX_URL}/${one}`, NAMES[one]));
  if (index) links.push(link(INDEX_URL, "all concept pages"));
  return `<div class="concepts">read: ${links.join(" · ")}</div>`;
}
