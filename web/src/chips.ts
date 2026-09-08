import { ChipKind, ChipTone, ItemKind, type Chip, type Piece } from "./types";

/** Reference markup as the coach writes it: `[[kind:target]]`, or
 * `[[kind:target|label]]` when it has words of its own. The label-bearing form
 * is what btcopilot/personal/refs.py already emits; the bare form is what a
 * user's own message carries after they tap a chip.
 *
 * A chip names one of three things — an event, a cluster, a person. The markup
 * the coach may write is wider than that, so it is narrowed here: `events` is a
 * list of events, `chapter` is what a cluster used to be called, and `range` is
 * a span of time that resolves to nothing the picture can go to, so it stays
 * plain words rather than becoming a chip that does nothing. */

enum Markup {
  Event = "event",
  Events = "events",
  Cluster = "cluster",
  Chapter = "chapter",
  Person = "person",
  Range = "range",
}

const NARROWED: Record<Markup, ChipKind | null> = {
  [Markup.Event]: ChipKind.Event,
  [Markup.Events]: ChipKind.Event,
  [Markup.Cluster]: ChipKind.Cluster,
  [Markup.Chapter]: ChipKind.Cluster,
  [Markup.Person]: ChipKind.Person,
  [Markup.Range]: null,
};

const TOKEN = new RegExp(
  `\\[\\[(${Object.values(Markup).join("|")}):([^|\\]]+)(?:\\|([^\\]]*))?\\]\\]`,
  "g",
);

const KIND_WORD: Record<ChipKind, string> = {
  [ChipKind.Event]: "this",
  [ChipKind.Cluster]: "this stretch",
  [ChipKind.Person]: "them",
};

const ITEM_OF: Record<ChipKind, ItemKind> = {
  [ChipKind.Event]: ItemKind.Event,
  [ChipKind.Cluster]: ItemKind.Cluster,
  [ChipKind.Person]: ItemKind.Person,
};

export const itemKind = (kind: ChipKind): ItemKind => ITEM_OF[kind];

/** A chip has to fit inside a chat bubble on a phone, and the record hands out
 * labels of any length — an event's whole first line, a four-part surname. Past
 * this many characters the chip shows the beginning and says the rest on tap.
 * The number is what fits on two lines of a 390px bubble. */
export const CHIP_MAX = 34;

export interface ChipText {
  text: string;
  clipped: boolean;
}

/** Cut at the last space before the limit so a chip never breaks a word, and
 * never leave a stub that is mostly ellipsis. */
export function chipText(label: string, max = CHIP_MAX): ChipText {
  const clean = label.replace(/\s+/g, " ").trim();
  if ([...clean].length <= max) return { text: clean, clipped: false };
  const cut = [...clean].slice(0, max).join("");
  const space = cut.lastIndexOf(" ");
  const kept = space > max * 0.6 ? cut.slice(0, space) : cut.trimEnd();
  return { text: `${kept}…`, clipped: true };
}

export function token(kind: ChipKind, target: string, label?: string): string {
  return label ? `[[${kind}:${target}|${label}]]` : `[[${kind}:${target}]]`;
}

/** Split text into words and chips. A chip with no label of its own falls back
 * to a plain word, never to raw markup: the user must never see brackets. */
export function tokenize(text: string, tone = ChipTone.Data): Piece[] {
  const pieces: Piece[] = [];
  let at = 0;
  TOKEN.lastIndex = 0;
  for (let m = TOKEN.exec(text); m !== null; m = TOKEN.exec(text)) {
    if (m.index > at) pieces.push({ text: text.slice(at, m.index) });
    const kind = NARROWED[m[1] as Markup];
    const label = (m[3] ?? "").trim();
    if (kind === null) pieces.push({ text: label });
    else
      pieces.push({
        chip: {
          kind,
          target: m[2].trim(),
          label: label || KIND_WORD[kind],
          tone,
          bare: !label,
        },
      });
    at = m.index + m[0].length;
  }
  if (at < text.length) pieces.push({ text: text.slice(at) });
  return pieces;
}

export function chips(text: string): Chip[] {
  return tokenize(text).flatMap((p) => ("chip" in p ? [p.chip] : []));
}

/** What the picture should aim at for one chip: the events it names. */
export function aimedEvents(
  chip: Chip,
  chapters: { id: string; cluster_ids: string[]; event_ids: number[] }[],
): number[] {
  switch (chip.kind) {
    case ChipKind.Event:
      return chip.target
        .split(",")
        .map((part) => Number(part.trim()))
        .filter((id) => Number.isFinite(id));
    case ChipKind.Cluster: {
      const chapter = chapters.find(
        (c) => c.id === chip.target || c.cluster_ids.includes(chip.target),
      );
      return chapter ? chapter.event_ids : [];
    }
    case ChipKind.Person:
      return [];
  }
}
