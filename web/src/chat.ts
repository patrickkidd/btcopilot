import { esc, el } from "./dom";
import { tokenize } from "./chips";
import { ChipTone, Role, type Chip, type Piece } from "./types";

/** Chat is the whole surface: coach and user messages both render their chips
 * as pills, and a pill the user taps lands in the composer as something they
 * type around (R-0072). */

export interface ChatHandlers {
  onChip(chip: Chip): void;
}

function pill(chip: Chip): string {
  return (
    `<button type="button" class="chip ${chip.tone}" ` +
    `data-kind="${chip.kind}" data-target="${esc(chip.target)}">${esc(chip.label)}</button>`
  );
}

function render(pieces: Piece[]): string {
  return pieces
    .map((p) => ("chip" in p ? pill(p.chip) : esc(p.text)))
    .join("");
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
        });
    };
    this.list.addEventListener("click", tap(this.list));
    this.composer.addEventListener("click", tap(this.composer));
  }

  clear(): void {
    this.list.innerHTML = "";
  }

  add(role: Role, text: string, tone = ChipTone.Data): HTMLElement {
    const bubble = el("div", `bub ${role}`, render(tokenize(text, tone)));
    this.list.append(bubble);
    this.scroll();
    return bubble;
  }

  /** The coach's words arrive whole and are typed out, one piece at a time, so
   * each chip can light its part of the picture as it lands. `onChip` fires as
   * every chip appears. */
  async type(
    text: string,
    onChip: (chip: Chip) => void,
    pace = 260,
  ): Promise<void> {
    const bubble = el("div", `bub ${Role.Coach} typing`, "");
    this.typing = bubble;
    this.list.append(bubble);
    for (const piece of tokenize(text)) {
      if ("chip" in piece) {
        bubble.insertAdjacentHTML("beforeend", pill(piece.chip));
        onChip(piece.chip);
        await wait(pace);
      } else {
        for (const word of piece.text.split(/(\s+)/)) {
          bubble.insertAdjacentText("beforeend", word);
          this.scroll();
          if (word.trim()) await wait(28);
        }
      }
      this.scroll();
    }
    bubble.classList.remove("typing");
    this.typing = null;
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
    const html = pill({ ...chip, tone: ChipTone.Data }) + " ";
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

export const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
