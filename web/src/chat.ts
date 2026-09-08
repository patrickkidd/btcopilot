import { esc, el } from "./dom";
import { chipText, tokenize } from "./chips";
import { ChipTone, Role, type Chip, type Piece } from "./types";

/** Chat is the whole surface: coach and user messages both render their chips
 * as pills, and a pill the user taps lands in the composer as something they
 * type around (R-0072). While the coach's words type themselves out, each chip
 * lights as it lands and the picture draws what it names — pane A of the
 * approved play-by-play. */

export interface ChatHandlers {
  onChip(chip: Chip): void;
  /** What a chip should read as. The coach may write a reference with no words
   * of its own, and a name out of the record beats a pronoun in a sentence. */
  label(chip: Chip): string;
}

/** How long a chip stays lit while its move draws (pane A). */
const LIT_MS = 1000;
/** The coach writes two characters at a time, on the approved cadence. */
const CHARS = 2;
const TICK_MS = 18;
/** An offer is not a move: the answers the coach holds out land 160ms apart. */
const OFFER_MS = 160;
/** How long a traced bubble stays outlined after a moment jumps to it. */
const TRACE_MS = 2200;

export class Chat {
  private typing: HTMLElement | null = null;

  constructor(
    private list: HTMLElement,
    private composer: HTMLElement,
    private handlers: ChatHandlers,
  ) {
    const tap = (host: HTMLElement) => (e: Event) => {
      const button = (e.target as Element).closest<HTMLElement>("button.chip");
      if (!button) return;
      e.preventDefault();
      if (host === this.composer) return void button.remove();
      // A label too long to fit shows its beginning; the first tap on one of
      // those is a look at the rest of the words, and the tap after it speaks.
      if (button.classList.contains("clip")) {
        button.classList.remove("clip");
        button.textContent = button.dataset.full ?? button.textContent;
        return;
      }
      this.handlers.onChip({
        kind: button.dataset.kind as Chip["kind"],
        target: button.dataset.target ?? "",
        label: button.dataset.full ?? "",
        tone: button.classList.contains(ChipTone.Ask)
          ? ChipTone.Ask
          : ChipTone.Data,
        bare: false,
      });
    };
    this.list.addEventListener("click", tap(this.list));
    this.composer.addEventListener("click", tap(this.composer));
  }

  private pill(chip: Chip): string {
    const full = this.handlers.label(chip);
    const { text, clipped } = chipText(full);
    const offer = chip.tone === ChipTone.Ask;
    return (
      `<button type="button" class="chip ${chip.tone}${clipped ? " clip" : ""}" ` +
      `data-kind="${chip.kind}" data-target="${esc(chip.target)}" ` +
      `data-full="${esc(full)}" title="${esc(full)}">` +
      `${offer ? "[" : ""}${esc(text)}${offer ? "]" : ""}</button>`
    );
  }

  private render(pieces: Piece[]): string {
    return pieces
      .map((p) => ("chip" in p ? this.pill(p.chip) : esc(p.text)))
      .join("");
  }

  clear(): void {
    this.list.innerHTML = "";
  }

  add(
    role: Role,
    text: string,
    tone = ChipTone.Data,
    statementId: number | null = null,
  ): HTMLElement {
    const bubble = el(
      "div",
      `bub ${role}`,
      (role === Role.Coach ? `<div class="who">Coach</div>` : "") +
        this.render(tokenize(text, tone)),
    );
    // The bubble carries its statement so a moment on the picture can point
    // back at the words that coded it.
    if (statementId !== null) bubble.dataset.statement = String(statementId);
    this.list.append(bubble);
    this.scroll();
    return bubble;
  }

  /** Scroll one statement's bubble into the middle of the thread and mark it,
   * which is what a moment tracing back to where it was coded does. Never
   * `scrollIntoView`: the outer page must not move (UI_STANDARDS). */
  trace(statementId: number): boolean {
    const bubble = this.list.querySelector<HTMLElement>(
      `.bub[data-statement="${statementId}"]`,
    );
    if (!bubble) return false;
    const box = this.list.getBoundingClientRect();
    const at = bubble.getBoundingClientRect();
    this.list.scrollTop = Math.max(
      0,
      this.list.scrollTop + (at.top - box.top) - (box.height - at.height) / 2,
    );
    bubble.classList.remove("traced");
    void bubble.offsetWidth;
    bubble.classList.add("traced");
    window.setTimeout(() => bubble.classList.remove("traced"), TRACE_MS);
    return true;
  }

  /** A coach bubble. It says what the coach did first, as a plain line each,
   * then types the words out so every chip lights its part of the picture as it
   * lands. */
  live(): LiveBubble {
    const bubble = el(
      "div",
      `bub ${Role.Coach} typing`,
      `<div class="who">Coach</div><span class="words"></span>`,
    );
    this.list.append(bubble);
    this.typing = bubble;
    this.scroll();
    const words = bubble.querySelector(".words") as HTMLElement;
    return {
      note: (line) => {
        bubble.insertBefore(el("div", "did", esc(line)), words);
        this.scroll();
      },
      type: async (text, onChip, pace = LIT_MS) => {
        for (const piece of tokenize(text)) {
          if ("chip" in piece) {
            words.insertAdjacentHTML("beforeend", this.pill(piece.chip));
            const pill = words.lastElementChild as HTMLElement;
            // an offer names nothing in the record, so nothing draws and the
            // next one follows straight after
            const offer = piece.chip.tone === ChipTone.Ask;
            if (!offer) pill.classList.add("lit");
            onChip(piece.chip);
            await wait(offer ? OFFER_MS : pace);
            pill.classList.remove("lit");
          } else {
            for (let i = 0; i < piece.text.length; i += CHARS) {
              words.append(piece.text.slice(i, i + CHARS));
              this.scroll();
              await wait(TICK_MS);
            }
          }
          this.scroll();
        }
        bubble.classList.remove("typing");
        this.typing = null;
      },
    };
  }

  /** Waiting is the same caret that types: one bar, blinking, where the words
   * are about to appear. */
  busy(on: boolean): void {
    if (on && !this.typing) {
      this.typing = el(
        "div",
        `bub ${Role.Coach} typing dots`,
        `<div class="who">Coach</div>`,
      );
      this.list.append(this.typing);
      this.scroll();
    } else if (!on && this.typing?.classList.contains("dots")) {
      this.typing.remove();
      this.typing = null;
    }
  }

  /** Drop a chip into the composer at the caret, as an inline pill. A chip the
   * coach offered keeps its amber, so what the user is about to send still
   * looks like the thing they tapped. */
  insert(chip: Chip): void {
    this.composer.focus({ preventScroll: true });
    const selection = window.getSelection();
    const html = this.pill(chip) + " ";
    if (
      selection?.rangeCount &&
      this.composer.contains(selection.getRangeAt(0).commonAncestorContainer)
    ) {
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const fragment = range.createContextualFragment(html);
      range.insertNode(fragment);
      selection.collapseToEnd();
    } else {
      this.composer.insertAdjacentHTML("beforeend", html);
      const range = document.createRange();
      range.selectNodeContents(this.composer);
      range.collapse(false);
      selection?.removeAllRanges();
      selection?.addRange(range);
    }
  }

  /** What the composer says, with its pills back as reference markup. A bare
   * chip on its own is a legitimate message. */
  draft(): string {
    let out = "";
    this.composer.childNodes.forEach((node) => {
      const kind = node instanceof HTMLElement ? node.dataset.kind : undefined;
      out += kind
        ? `[[${kind}:${(node as HTMLElement).dataset.target}]]`
        : (node.textContent ?? "");
    });
    return out.replace(/\u00a0/g, " ").trim();
  }

  resetDraft(): void {
    this.composer.innerHTML = "";
  }

  private scroll(): void {
    this.list.scrollTop = this.list.scrollHeight;
  }
}

export interface LiveBubble {
  note(line: string): void;
  type(text: string, onChip: (chip: Chip) => void, pace?: number): Promise<void>;
}

export const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
