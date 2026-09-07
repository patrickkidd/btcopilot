import { esc, el } from "./dom";
import { tokenize } from "./chips";
import { ChipTone, Role, type Chip, type Piece } from "./types";

/** Chat is the whole surface: coach and user messages both render their chips
 * as pills, and a pill the user taps lands in the composer as something they
 * type around (R-0072). */

export interface ChatHandlers {
  onChip(chip: Chip): void;
  /** What a chip should read as. The coach may write a reference with no words
   * of its own, and a name out of the record beats a pronoun in a sentence. */
  label(chip: Chip): string;
}

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
      const source = host === this.composer;
      if (source) button.remove();
      else
        this.handlers.onChip({
          kind: button.dataset.kind as Chip["kind"],
          target: button.dataset.target ?? "",
          label: button.textContent ?? "",
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
    return (
      `<button type="button" class="chip ${chip.tone}" ` +
      `data-kind="${chip.kind}" data-target="${esc(chip.target)}">` +
      `${esc(this.handlers.label(chip))}</button>`
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
    const bubble = el("div", `bub ${role}`, this.render(tokenize(text, tone)));
    this.list.append(bubble);
    this.scroll();
    return bubble;
  }

  /** A coach bubble. It says what the coach did first, as a plain line each,
   * then types the words out so every chip can light its part of the picture
   * as it lands. */
  live(): LiveBubble {
    const bubble = el("div", `bub ${Role.Coach} typing`, '<span class="words"></span>');
    this.list.append(bubble);
    this.typing = bubble;
    this.scroll();
    const words = bubble.querySelector(".words") as HTMLElement;
    return {
      note: (line) => {
        bubble.insertBefore(el("div", "did", esc(line)), words);
        this.scroll();
      },
      type: async (text, onChip, pace = 260) => {
        for (const piece of tokenize(text)) {
          if ("chip" in piece) {
            words.insertAdjacentHTML("beforeend", this.pill(piece.chip));
            onChip(piece.chip);
            await wait(pace);
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

  /** Drop a chip into the composer at the caret, as an inline pill. */
  insert(chip: Chip): void {
    this.composer.focus();
    const selection = window.getSelection();
    const html = this.pill({ ...chip, tone: ChipTone.Data }) + " ";
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
