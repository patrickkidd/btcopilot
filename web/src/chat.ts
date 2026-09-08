import { esc, el } from "./dom";
import { tokenize } from "./chips";
import { ChipTone, Role, type Chip, type Piece } from "./types";

/** Chat is the whole surface: coach and user messages both render their chips
 * as pills, and a pill the user taps lands in the composer as something they
 * type around (R-0072). While the coach's words type themselves out, each chip
 * lights as it lands and the picture draws what it names — pane A of the
 * approved play-by-play. */

/** A chip tapped inside a play-by-play: the stretch it walks, and which chip in
 * that walk this is. The board is what such a chip steps, never the wire. */
export interface PlayTap {
  cluster: string;
  ordinal: number;
}

export interface ChatHandlers {
  onChip(chip: Chip, play: PlayTap | null): void;
  /** A tap on a bubble's own words rather than on a chip inside it: the picture
   * lights what that message named. It is a look, so it costs no turn. */
  onBubble(text: string): void;
  /** What a chip should read as. The coach may write a reference with no words
   * of its own, and a name out of the record beats a pronoun in a sentence. */
  label(chip: Chip): string;
}

/** The beat after a move's sentence has been written, before the next move
 * takes the board: long enough to look at what was just drawn. The owner tunes
 * this by feel, so it is one number in one place. */
const READ_MS = 2000;
/** The coach writes two characters at a time, on the approved cadence. */
const CHARS = 2;
const TICK_MS = 18;
/** An offer is not a move: the answers the coach holds out land 160ms apart. */
const OFFER_MS = 160;
/** How long a traced bubble stays outlined after a moment jumps to it. */
const TRACE_MS = 2200;

/** Where a tapped chip sits in its walk. Only a chip inside a play-by-play has
 * one, and the offers that close the walk are not moves, so they do not count
 * towards it. */
function playTap(button: HTMLElement): PlayTap | null {
  const bubble = button.closest<HTMLElement>(".bub");
  const cluster = bubble?.dataset.play;
  if (!bubble || !cluster) return null;
  const moves = [...bubble.querySelectorAll<HTMLElement>(`.chip.${ChipTone.Data}`)];
  return { cluster, ordinal: moves.indexOf(button) };
}

export class Chat {
  /** What each bubble was written from, chips and all, so a tap on its words
   * can light the same moments its chips name. */
  private said = new WeakMap<HTMLElement, string>();
  private typing: HTMLElement | null = null;
  /** Whether the thread is following the newest words. */
  private stuck = true;
  /** True while this class is the one moving the scroll, so its own pinning is
   * not mistaken for the reader scrolling away. */
  private pinning = false;

  constructor(
    private list: HTMLElement,
    private composer: HTMLElement,
    private handlers: ChatHandlers,
  ) {
    const tap = (host: HTMLElement) => (e: Event) => {
      const button = (e.target as Element).closest<HTMLElement>("button.chip");
      if (!button) {
        if (host === this.composer) return;
        const bubble = (e.target as Element).closest<HTMLElement>(".bub");
        // A play-by-play's own words never take the picture off its board.
        if (!bubble || bubble.dataset.play) return;
        const said = this.said.get(bubble);
        if (said) this.handlers.onBubble(said);
        return;
      }
      e.preventDefault();
      if (host === this.composer) return void button.remove();
      this.handlers.onChip(
        {
          kind: button.dataset.kind as Chip["kind"],
          target: button.dataset.target ?? "",
          label: button.dataset.full ?? "",
          tone: button.classList.contains(ChipTone.Ask)
            ? ChipTone.Ask
            : ChipTone.Data,
          bare: false,
        },
        playTap(button),
      );
    };
    this.watchScrolling();
    // The thread's height is only final once the web font has replaced the
    // fallback, so pin it again then: otherwise a thread opened before the font
    // lands sits partway up its own scroll.
    void document.fonts?.ready.then(() => this.scroll());
    this.list.addEventListener("click", tap(this.list));
    this.composer.addEventListener("click", tap(this.composer));
  }

  /** One size, the whole label, never cut. The coach's labels are capped at
   * the source, so a chip that needs shortening is a bug upstream rather than
   * something for the reader to expand. */
  private pill(chip: Chip): string {
    const full = this.handlers.label(chip);
    const offer = chip.tone === ChipTone.Ask;
    return (
      `<button type="button" class="chip ${chip.tone}" ` +
      `data-kind="${chip.kind}" data-target="${esc(chip.target)}" ` +
      `data-full="${esc(full)}" title="${esc(full)}">` +
      `${offer ? "[" : ""}${esc(full)}${offer ? "]" : ""}</button>`
    );
  }

  private render(pieces: Piece[]): string {
    return pieces
      .map((p) => ("chip" in p ? this.pill(p.chip) : esc(p.text)))
      .join("");
  }

  clear(): void {
    this.list.innerHTML = "";
    this.stuck = true;
  }

  add(
    role: Role,
    text: string,
    tone = ChipTone.Data,
    statementId: number | null = null,
    play: string | null = null,
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
    // A play-by-play carries the stretch it walks, so its chips step the board
    // instead of taking the picture back to the wire.
    if (play !== null) bubble.dataset.play = play;
    this.said.set(bubble, text);
    this.list.append(bubble);
    this.stuck = true;
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
  live(play: string | null = null): LiveBubble {
    const bubble = el(
      "div",
      `bub ${Role.Coach} typing`,
      `<div class="who">Coach</div><span class="words"></span>`,
    );
    if (play !== null) bubble.dataset.play = play;
    this.list.append(bubble);
    this.typing = bubble;
    this.stuck = true;
    this.scroll();
    const words = bubble.querySelector(".words") as HTMLElement;
    return {
      note: (line) => {
        bubble.insertBefore(el("div", "did", esc(line)), words);
        this.scroll();
      },
      type: async (text, onChip, pace = READ_MS) => {
        this.said.set(bubble, text);
        // A move holds until the sentence about it has been written and there
        // has been a beat to look at it, not for a fixed count from the moment
        // it was named. The chip stays lit for as long as its move is the one
        // on the board.
        let held: HTMLElement | null = null;
        const release = async () => {
          if (!held) return;
          await wait(pace);
          held.classList.remove("lit");
          held = null;
        };
        for (const piece of tokenize(text)) {
          if ("chip" in piece) {
            // an offer names nothing in the record, so nothing draws and the
            // next one follows straight after
            const offer = piece.chip.tone === ChipTone.Ask;
            if (!offer) await release();
            words.insertAdjacentHTML("beforeend", this.pill(piece.chip));
            const pill = words.lastElementChild as HTMLElement;
            onChip(piece.chip);
            if (offer) await wait(OFFER_MS);
            else {
              pill.classList.add("lit");
              held = pill;
            }
          } else {
            for (let i = 0; i < piece.text.length; i += CHARS) {
              words.append(piece.text.slice(i, i + CHARS));
              this.scroll();
              await wait(TICK_MS);
            }
          }
          this.scroll();
        }
        await release();
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

  /** How far from the bottom still counts as watching the newest words. */
  private static readonly STUCK_PX = 24;

  /** The thread follows the coach's words down while the reader is at the
   * bottom, and stops following the moment they scroll up to read something
   * earlier. Scrolling back down picks it up again. */
  private atBottom(): boolean {
    const { scrollTop, scrollHeight, clientHeight } = this.list;
    return scrollHeight - clientHeight - scrollTop <= Chat.STUCK_PX;
  }

  private watchScrolling(): void {
    this.list.addEventListener(
      "scroll",
      () => {
        if (!this.pinning) this.stuck = this.atBottom();
      },
      { passive: true },
    );
  }

  private scroll(): void {
    if (!this.stuck) return;
    this.pinning = true;
    this.list.scrollTop = this.list.scrollHeight;
    requestAnimationFrame(() => {
      this.pinning = false;
    });
  }
}

export interface LiveBubble {
  note(line: string): void;
  type(text: string, onChip: (chip: Chip) => void, pace?: number): Promise<void>;
}

export const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
