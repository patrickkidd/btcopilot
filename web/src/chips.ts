import { ChipKind, ChipTone, type Chip, type Piece } from "./types";

/** Reference markup as the coach writes it: `[[kind:target]]`, or
 * `[[kind:target|label]]` when it has words of its own. The label-bearing form
 * is what btcopilot/personal/refs.py already emits; the bare form is what a
 * user's own message carries after they tap a chip. */
const TOKEN = new RegExp(
  `\\[\\[(${Object.values(ChipKind).join("|")}):([^|\\]]+)(?:\\|([^\\]]*))?\\]\\]`,
  "g",
);

const KIND_WORD: Record<ChipKind, string> = {
  [ChipKind.Event]: "this",
  [ChipKind.Events]: "these",
  [ChipKind.Cluster]: "this stretch",
  [ChipKind.Chapter]: "this stretch",
  [ChipKind.Person]: "them",
  [ChipKind.Range]: "then",
};

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
    const kind = m[1] as ChipKind;
    const label = (m[3] ?? "").trim();
    pieces.push({
      chip: { kind, target: m[2].trim(), label: label || KIND_WORD[kind], tone },
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
    case ChipKind.Events:
      return chip.target
        .split(",")
        .map((part) => Number(part.trim()))
        .filter((id) => Number.isFinite(id));
    case ChipKind.Cluster:
    case ChipKind.Chapter: {
      const chapter = chapters.find(
        (c) => c.id === chip.target || c.cluster_ids.includes(chip.target),
      );
      return chapter ? chapter.event_ids : [];
    }
    default:
      return [];
  }
}
