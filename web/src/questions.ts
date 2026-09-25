import * as api from "./api";
import { itemKind, token } from "./chips";
import { esc } from "./dom";
import { Swipe } from "./swipe";
import { Feature, tap } from "./track";
import { toast } from "./toast";
import { shortDate } from "./when";
import {
  ChipKind,
  ChipTone,
  EvidenceKind,
  InteractionKind,
  ItemKind,
  Pushback,
  QuestionKind,
  QuestionOutcome,
  QuestionState,
  type AskedQuestion,
  type Chip,
  type CodedIn,
  type Evidence,
} from "./types";

/** The drawer's third list, what the coach has for the reader: the questions
 * it asked that are still open, food for thought first, then facts to find,
 * then what it noticed (approved open-questions and impressions mockups). No
 * counts and no states: a question or an impression is here or it is not. */

export const EMPTY = "Nothing from the coach yet.";

const SECTIONS: [QuestionKind, string][] = [
  [QuestionKind.Thought, "Food for thought"],
  [QuestionKind.Fact, "Facts to find"],
  [QuestionKind.Impression, "Impressions"],
];

/** What the reader writes when an impression is only partly right: the rest
 * of the sentence is theirs. */
export const PARTLY = " — partly, because ";

/** Newest asked first; two asked the same day, the one made later first. */
const newestFirst = (a: AskedQuestion, b: AskedQuestion) =>
  b.asked_at.localeCompare(a.asked_at) || Number(b.id.slice(1)) - Number(a.id.slice(1));

const day = (date: string, now: Date) => shortDate(new Date(`${date}T00:00:00`), now);

/** A question as a reference in the message box is amber, because it is the
 * coach asking; an impression is teal, because it is about the record. Each
 * in the words the coach used. */
export const questionChip = (q: AskedQuestion): Chip =>
  q.kind === QuestionKind.Impression
    ? { kind: ChipKind.Impression, target: q.id, label: q.text, tone: ChipTone.Data, bare: false }
    : { kind: ChipKind.Question, target: q.id, label: q.text, tone: ChipTone.Ask, bare: false };

/** A thing an impression rests on, as a chip into the message box. A message
 * is not a chip there: it opens where it was said. */
const EVIDENCE_CHIP: Record<Exclude<EvidenceKind, EvidenceKind.Statement>, ChipKind> = {
  [EvidenceKind.Person]: ChipKind.Person,
  [EvidenceKind.PairBond]: ChipKind.PairBond,
  [EvidenceKind.Event]: ChipKind.Event,
  [EvidenceKind.Cluster]: ChipKind.Cluster,
};

export const evidenceChip = (e: Evidence): Chip => ({
  kind: EVIDENCE_CHIP[e.kind as Exclude<EvidenceKind, EvidenceKind.Statement>],
  target: String(e.id),
  label: e.label,
  tone: ChipTone.Data,
  bare: false,
});

/** A chip for each thing an impression rests on, named by the record. A
 * message whose session is gone keeps its name as plain words. */
const evidence = (e: Evidence, n: number) =>
  e.kind === EvidenceKind.Statement && !e.discussion_id
    ? `<span class="blabel">${esc(e.label)}</span>`
    : `<button type="button" class="chip ${ChipTone.Data}" data-ev="${n}">${esc(e.label)}</button>`;

/** The day it was asked, which goes to where it was asked. One whose session
 * is gone keeps its day as plain words. */
function when(q: AskedQuestion, verb: string, now: Date): string {
  const said = `${verb} ${day(q.asked_at, now)}`;
  return q.asked_in
    ? `<button type="button" class="qwhen">${esc(said)} ›</button>`
    : `<span class="qwhen">${esc(said)}</span>`;
}

function questionRow(q: AskedQuestion, now: Date): string {
  return (
    `<div class="qrow" data-q="${esc(q.id)}">` +
    `<button type="button" class="chip q ${ChipTone.Ask}" data-kind="${ChipKind.Question}" ` +
    `data-target="${esc(q.id)}">${esc(q.text)}</button>` +
    `<div class="qmeta">${when(q, "Asked", now)}</div></div>`
  );
}

/** What the coach noticed, in its words, what it rests on, and the day it was
 * raised; behind it, the two ways to push back. */
function impressionRow(q: AskedQuestion, now: Date): string {
  const chips = q.evidence.map(evidence).join("");
  return (
    `<div class="irow" data-q="${esc(q.id)}"><div class="islide">` +
    `<div class="itext" role="button" tabindex="0">${esc(q.text)}</div>` +
    `<div class="based"><span class="blabel">Based on:</span>${chips}</div>` +
    `<div class="imeta">${when(q, "Raised", now)}` +
    `<button type="button" class="rmore" aria-label="push back">⋯</button></div></div>` +
    `<div class="iacts"><button type="button" class="iact nofit">Doesn't fit</button>` +
    `<button type="button" class="iact partly">Partly</button></div></div>`
  );
}

export function questionsHtml(asked: AskedQuestion[], now: Date): string {
  const open = asked.filter((q) => q.open);
  if (!open.length) return `<div class="empty">${esc(EMPTY)}</div>`;
  return SECTIONS.map(([kind, title]) => {
    const rows = open.filter((q) => q.kind === kind).sort(newestFirst);
    const row = kind === QuestionKind.Impression ? impressionRow : questionRow;
    return rows.length ? `<div class="qsec">${esc(title)}</div>` + rows.map((q) => row(q, now)).join("") : "";
  }).join("");
}

export interface QuestionHandlers {
  /** A reference goes into the message box, with any words after it. */
  onChip(chip: Chip, after?: string): void;
  /** The reader asked to see where something was said; `ask` lights the
   * question that closes that reply. */
  onAsked(where: CodedIn, ask: boolean): void;
  /** Something was put away, so the record is read again. */
  onDismissed(): void;
  /** Whether the coach is still answering, when nothing more can be sent. */
  busy(): boolean;
  /** Words the reader says to the coach, sent as their message. */
  say(statement: string): void;
  /** Every tap is learning data (R-0077). */
  record(kind: InteractionKind, item: ItemKind, id: string): void;
}

export class Questions {
  private asked: AskedQuestion[] = [];
  /** Swipe a question left to put it away, or an impression to push back. */
  private swipe: Swipe;
  /** Impressions the reader has begun to answer "partly" and not yet sent. */
  private partly = new Set<string>();

  constructor(
    private body: HTMLElement,
    private handlers: QuestionHandlers,
  ) {
    this.swipe = new Swipe(body, ".qrow, .irow", (row) =>
      row.classList.contains("irow")
        ? null
        : { html: `<button class="fs-act del" type="button">Dismiss</button>`, wide: false },
    );
    body.addEventListener("click", (e) => void this.onClick(e));
  }

  show(asked: AskedQuestion[]): void {
    this.asked = asked;
    this.swipe.forget();
    const top = this.body.scrollTop;
    this.body.innerHTML = questionsHtml(asked, new Date());
    this.body.scrollTop = top;
  }

  /** The reader is sending what they wrote: a "partly" is only a push-back
   * once the reply that says why is sent with the impression still in it
   * (R-0073), and it is stored before the coach reads the reply. */
  async sending(draft: string): Promise<void> {
    const ids = [...this.partly].filter((id) => draft.includes(token(ChipKind.Impression, id)));
    this.partly.clear();
    await Promise.all(ids.map((id) => api.saveQuestion(id, { pushback: Pushback.Partly })));
  }

  private async onClick(e: Event): Promise<void> {
    const target = e.target as Element;
    const row = target.closest<HTMLElement>(".qrow, .irow");
    if (row && target.closest(".fs-act")) return this.dismiss(this.find(row));
    if (row && target.closest(".nofit")) return this.doesntFit(this.find(row));
    if (row && target.closest(".partly")) return this.partlyRight(this.find(row));
    if (row && target.closest(".rmore")) return this.swipe.toggle(row);
    if (this.swipe.claims() || !row) return;
    const q = this.find(row);
    const item = { kind: ItemKind.Question, id: q.id };
    const ev = target.closest<HTMLElement>("[data-ev]");
    if (ev) return this.evidence(q.evidence[Number(ev.dataset.ev)]);
    if (target.closest(".chip, .itext")) {
      this.handlers.record(InteractionKind.ChipTap, ItemKind.Question, q.id);
      const impression = q.kind === QuestionKind.Impression;
      tap(impression ? Feature.ImpressionText : Feature.QuestionChip, item);
      this.handlers.onChip(questionChip(q));
    } else if (target.closest("button.qwhen")) {
      const impression = q.kind === QuestionKind.Impression;
      tap(impression ? Feature.ImpressionSession : Feature.QuestionSession, item);
      this.handlers.onAsked(q.asked_in as CodedIn, !impression);
    }
  }

  private evidence(e: Evidence): void {
    tap(Feature.ImpressionEvidence, { kind: ItemKind.Question, id: String(e.id) });
    if (e.kind === EvidenceKind.Statement) {
      this.handlers.onAsked(
        { discussion_id: e.discussion_id as number, statement_id: Number(e.id) },
        false,
      );
      return;
    }
    const chip = evidenceChip(e);
    this.handlers.record(InteractionKind.ChipTap, itemKind(chip.kind), chip.target);
    this.handlers.onChip(chip);
  }

  private find(row: HTMLElement): AskedQuestion {
    const q = this.asked.find((one) => one.id === row.dataset.q);
    if (!q) throw new Error(`No question ${row.dataset.q} on the list`);
    return q;
  }

  private async dismiss(q: AskedQuestion): Promise<void> {
    this.handlers.record(InteractionKind.Dismiss, ItemKind.Question, q.id);
    tap(Feature.QuestionDismiss, { kind: ItemKind.Question, id: q.id });
    await api.saveQuestion(q.id, {
      state: QuestionState.Resolved,
      outcome: QuestionOutcome.DeclinedByUser,
    });
    this.handlers.onDismissed();
  }

  /** Stored first, so the coach's next turn already reads it as not fitting;
   * then said, with the impression as a reference the coach can name. */
  private async doesntFit(q: AskedQuestion): Promise<void> {
    if (this.handlers.busy()) return toast("The coach is still answering");
    this.partly.delete(q.id);
    await api.saveQuestion(q.id, {
      state: QuestionState.Resolved,
      outcome: QuestionOutcome.DoesntFit,
    });
    this.handlers.record(InteractionKind.DoesntFit, ItemKind.Question, q.id);
    tap(Feature.ImpressionDoesntFit, { kind: ItemKind.Question, id: q.id });
    this.handlers.say(`That doesn't fit: ${token(ChipKind.Impression, q.id)}`);
    this.handlers.onDismissed();
  }

  /** The impression goes in the message box with the start of a reply after
   * it. The tap is a look until that reply is sent. */
  private partlyRight(q: AskedQuestion): void {
    this.handlers.record(InteractionKind.Look, ItemKind.Question, q.id);
    tap(Feature.ImpressionPartly, { kind: ItemKind.Question, id: q.id });
    this.partly.add(q.id);
    this.swipe.close();
    this.handlers.onChip(questionChip(q), PARTLY);
  }
}
