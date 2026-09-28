import { esc } from "./dom";
import { ChipKind, ChipTone, ItemKind, type Chip, type Piece } from "./types";

/** Reference markup as the coach writes it: `[[kind:target]]`, or
 * `[[kind:target|label]]` when it has words of its own. The label-bearing form
 * is what btcopilot/refs.py already emits; the bare form is what a
 * user's own message carries after they tap a chip.
 *
 * A chip names one of three things — an event, a cluster, a person. The markup
 * the coach may write is wider than that, so it is narrowed here: `events` is a
 * list of events, and `range` is a span of time that resolves to nothing the
 * picture can go to, so it stays plain words rather than becoming a chip that
 * does nothing. */

enum Markup {
  Event = "event",
  Events = "events",
  Cluster = "cluster",
  Person = "person",
  Range = "range",
  /** What the coach offers to talk about next. It names nothing in the record,
   * so it goes in the composer as words rather than aiming the picture — the
   * offered chips that close the approved play-by-play. */
  Ask = "ask",
  /** A question the coach asked, brought back by the reader from the list of
   * open ones. */
  Question = "question",
  /** What the coach noticed, brought back by the reader. */
  Impression = "impression",
  PairBond = "pair_bond",
  /** The question a coach message ended on, answered by the reader. */
  Message = "message",
}

const NARROWED: Record<Markup, ChipKind | null> = {
  [Markup.Event]: ChipKind.Event,
  [Markup.Events]: ChipKind.Event,
  [Markup.Cluster]: ChipKind.Cluster,
  [Markup.Person]: ChipKind.Person,
  [Markup.Range]: null,
  [Markup.Ask]: ChipKind.Ask,
  [Markup.Question]: ChipKind.Question,
  [Markup.Impression]: ChipKind.Impression,
  [Markup.PairBond]: ChipKind.PairBond,
  [Markup.Message]: ChipKind.Message,
};

const TOKEN = new RegExp(
  `\\[\\[(${Object.values(Markup).join("|")}):([^|\\]]+)(?:\\|([^\\]]*))?\\]\\]`,
  "g",
);

const KIND_WORD: Record<ChipKind, string> = {
  [ChipKind.Event]: "this",
  [ChipKind.Cluster]: "this cluster",
  [ChipKind.Person]: "them",
  [ChipKind.Ask]: "this",
  [ChipKind.Question]: "this question",
  [ChipKind.Impression]: "this",
  [ChipKind.PairBond]: "them",
  [ChipKind.Message]: "this question",
};

const ITEM_OF: Record<ChipKind, ItemKind> = {
  [ChipKind.Event]: ItemKind.Event,
  [ChipKind.Cluster]: ItemKind.Cluster,
  [ChipKind.Person]: ItemKind.Person,
  [ChipKind.Ask]: ItemKind.Diagram,
  [ChipKind.Question]: ItemKind.Question,
  // an impression is stored as a question of its own kind
  [ChipKind.Impression]: ItemKind.Question,
  [ChipKind.PairBond]: ItemKind.PairBond,
  // a message is not an item of the record, as an offer is not
  [ChipKind.Message]: ItemKind.Diagram,
};

const ASKING = new Set([ChipKind.Ask, ChipKind.Question, ChipKind.Message]);

export const itemKind = (kind: ChipKind): ItemKind => ITEM_OF[kind];

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
          label: label || (kind === ChipKind.Ask ? m[2].trim() : KIND_WORD[kind]),
          // An offer or a question is the coach asking, and asking is always
          // amber.
          tone: ASKING.has(kind) ? ChipTone.Ask : tone,
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
  clusters: { id: string; cluster_ids: string[]; event_ids: number[] }[],
): number[] {
  switch (chip.kind) {
    case ChipKind.Event:
      return chip.target
        .split(",")
        .map((part) => Number(part.trim()))
        .filter((id) => Number.isFinite(id));
    case ChipKind.Cluster: {
      const cluster = clusters.find(
        (c) => c.id === chip.target || c.cluster_ids.includes(chip.target),
      );
      return cluster ? cluster.event_ids : [];
    }
    case ChipKind.Person:
    case ChipKind.Ask:
    case ChipKind.Question:
    case ChipKind.Impression:
    case ChipKind.PairBond:
    case ChipKind.Message:
      return [];
  }
}

/** An offer wears square brackets around its words. */
export const face = (kind: ChipKind, full: string) => (kind === ChipKind.Ask ? `[${full}]` : full);

/** One size, the whole label, never cut. The coach's labels are capped at the
 * source, so a chip that needs shortening is a bug upstream rather than
 * something for the reader to expand. */
export const pill = (chip: Chip, full: string): string =>
  `<button type="button" class="chip ${chip.tone}" ` +
  `data-kind="${chip.kind}" data-target="${esc(chip.target)}" ` +
  `data-full="${esc(full)}" title="${esc(full)}"${chip.bare ? " data-bare" : ""}>` +
  `${esc(face(chip.kind, full))}</button>`;

/** The chip a tapped pill stands for. */
export const chipOf = (button: HTMLElement): Chip => ({
  kind: button.dataset.kind as ChipKind,
  target: button.dataset.target ?? "",
  label: button.dataset.full ?? "",
  tone: button.classList.contains(ChipTone.Ask) ? ChipTone.Ask : ChipTone.Data,
  bare: false,
});

/** The question a coach message ended on, as the amber chip that answers it:
 * the closing question of a reply and the play-by-play's own (R-0587). */
export const askedChip = (statementId: number, words: string): string =>
  pill({ kind: ChipKind.Message, target: String(statementId), label: words, tone: ChipTone.Ask, bare: false }, words);

/** What was tapped to put a chip in the message box, for the words that go
 * before it. */
export enum Lead {
  None = "none",
  Answer = "answer",
  Thought = "thought",
  Fact = "fact",
  Ask = "ask",
}

/** The words before a chip in the message box, which the reader may change
 * before sending (R-0586). */
export const LEAD: Record<Lead, string> = {
  [Lead.None]: "",
  [Lead.Answer]: "To answer your question",
  [Lead.Thought]: "About your question",
  [Lead.Fact]: "Here's what I know about",
  [Lead.Ask]: "I want to ask about",
};
