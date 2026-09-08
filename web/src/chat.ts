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

  add(role: Role, text: string, tone = ChipTone.Data): HTMLElement {
    const bubble = el(
      "div",
      `bub ${role}`,
      (role === Role.Coach ? `<div class="who">Coach</div>` : "") +
        this.render(tokenize(text, tone)),
    );
    this.list.append(bubble);
    this.scroll();
    return bubble;
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
            pill.classList.add("lit");
            onChip(piece.chip);
            await wait(pace);
            pill.classList.remove("lit");
          } else {
            for (const word of piece.text.split(/(\s+)/)) {
              words.append(word);
              this.scroll();
              if (word.trim()) await wait(28);
            }
          }
          this.scroll();
        }
        bubble.classList.remove("typing");
        this.typing = null;
      },
    };
  }

  busy(on: boolean): void {
    if (on && !this.typing) {
      this.typing = el("div", `bub ${Role.Coach} dots`, "<i></i><i></i><i></i>");
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
