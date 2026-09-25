import * as api from "./api";
import { esc } from "./dom";
import { Swipe } from "./swipe";
import { Feature, tap } from "./track";
import { shortDate } from "./when";
import {
  ChipKind,
  ChipTone,
  InteractionKind,
  ItemKind,
  QuestionKind,
  type AskedQuestion,
  type Chip,
  type CodedIn,
} from "./types";

/** The drawer's third list: the questions the coach has asked that are still
 * open, food for thought first, then facts to find (approved open-questions
 * mockup). No counts and no states: a question is here or it is not. */

export const EMPTY = "When the coach asks you something that is still open, it waits here.";

const SECTIONS: [QuestionKind, string][] = [
  [QuestionKind.Thought, "Food for thought"],
  [QuestionKind.Fact, "Facts to find"],
];

/** Newest asked first; two asked the same day, the one made later first. */
const newestFirst = (a: AskedQuestion, b: AskedQuestion) =>
  b.asked_at.localeCompare(a.asked_at) || Number(b.id.slice(1)) - Number(a.id.slice(1));

/** A question as a reference in the message box: amber, because it is the
 * coach asking, and its words as the coach asked it. */
export const questionChip = (q: AskedQuestion): Chip => ({
  kind: ChipKind.Question,
  target: q.id,
  label: q.text,
  tone: ChipTone.Ask,
  bare: false,
});

/** The chip, then the day it was asked, which goes to where it was asked. A
 * question whose session is gone keeps its day as plain words. */
function row(q: AskedQuestion, now: Date): string {
  const day = `Asked ${shortDate(new Date(`${q.asked_at}T00:00:00`), now)}`;
  return (
    `<div class="qrow" data-q="${esc(q.id)}">` +
    `<button type="button" class="chip q ${ChipTone.Ask}" data-kind="${ChipKind.Question}" ` +
    `data-target="${esc(q.id)}">${esc(q.text)}</button><div class="qmeta">` +
    (q.asked_in
      ? `<button type="button" class="qwhen">${esc(day)} ›</button>`
      : `<span class="qwhen">${esc(day)}</span>`) +
    `</div></div>`
  );
}

export function questionsHtml(asked: AskedQuestion[], now: Date): string {
  const open = asked.filter((q) => q.open);
  if (!open.length) return `<div class="empty">${esc(EMPTY)}</div>`;
  return SECTIONS.map(([kind, title]) => {
    const rows = open.filter((q) => q.kind === kind).sort(newestFirst);
    return rows.length
      ? `<div class="qsec">${esc(title)}</div>` + rows.map((q) => row(q, now)).join("")
      : "";
  }).join("");
}

export interface QuestionHandlers {
  /** The reader tapped a question: it goes into the message box. */
  onChip(chip: Chip): void;
  /** The reader asked to see where a question was asked. */
  onAsked(where: CodedIn): void;
  /** A question was put away, so the record is read again. */
  onDismissed(): void;
  /** Every tap is learning data (R-0077). */
  record(kind: InteractionKind, item: ItemKind, id: string): void;
}

export class Questions {
  private asked: AskedQuestion[] = [];
  /** Swipe a question left to put it away. */
  private swipe: Swipe;

  constructor(
    private body: HTMLElement,
    private handlers: QuestionHandlers,
  ) {
    this.swipe = new Swipe(body, ".qrow", () => ({
      html: `<button class="fs-act del" type="button">Dismiss</button>`,
      wide: false,
    }));
    body.addEventListener("click", (e) => void this.onClick(e));
  }

  show(asked: AskedQuestion[]): void {
    this.asked = asked;
    this.swipe.forget();
    const top = this.body.scrollTop;
    this.body.innerHTML = questionsHtml(asked, new Date());
    this.body.scrollTop = top;
  }

  private async onClick(e: Event): Promise<void> {
    const target = e.target as Element;
    const row = target.closest<HTMLElement>(".qrow");
    if (row && target.closest(".fs-act")) return this.dismiss(this.find(row));
    if (this.swipe.claims() || !row) return;
    const q = this.find(row);
    const item = { kind: ItemKind.Question, id: q.id };
    if (target.closest(".chip")) {
      this.handlers.record(InteractionKind.ChipTap, ItemKind.Question, q.id);
      tap(Feature.QuestionChip, item);
      this.handlers.onChip(questionChip(q));
    } else if (target.closest("button.qwhen")) {
      tap(Feature.QuestionSession, item);
      this.handlers.onAsked(q.asked_in as CodedIn);
    }
  }

  private find(row: HTMLElement): AskedQuestion {
    const q = this.asked.find((one) => one.id === row.dataset.q);
    if (!q) throw new Error(`No question ${row.dataset.q} on the list`);
    return q;
  }

  private async dismiss(q: AskedQuestion): Promise<void> {
    this.handlers.record(InteractionKind.Dismiss, ItemKind.Question, q.id);
    tap(Feature.QuestionDismiss, { kind: ItemKind.Question, id: q.id });
    await api.dismissQuestion(q.id);
    this.handlers.onDismissed();
  }
}
