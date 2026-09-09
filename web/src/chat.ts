import { esc, el } from "./dom";
import { tokenize } from "./chips";
import { ChipTone, Role, type Chip, type Piece } from "./types";

/** Chat is the whole surface: coach and user messages both render their chips
 * as pills, and a pill the user taps lands in the composer as something they
 * type around (R-0072). While the coach's words type themselves out, each chip
 * lights as it lands and the picture draws what it names — pane A of the
 * approved play-by-play. */

/** A chip tapped inside a play-by-play: the cluster it walks, and which chip in
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
/** The beat between the last move's sentence and the question that closes the
 * reply, from the approved play-by-play. */
const ASK_MS = 260;
/** The closing question types faster than the narration it follows. */
const ASK_TICK_MS = 16;
/** The question that closes a reply is the last sentence written before the
 * first offered chip. */
const LAST_SENTENCE = /[^.?!]*[.?!]?\s*$/;

/** How a reply is laid out: the words, then the question that closes it set
 * apart in amber, then the answers the coach holds out. A reply with no offered
 * chips is words alone. */
interface Written {
  words: Piece[];
  ask: string;
  offers: Chip[];
  tail: Piece[];
}

function layout(pieces: Piece[]): Written {
  const first = pieces.findIndex(
    (p) => "chip" in p && p.chip.tone === ChipTone.Ask,
  );
  if (first < 0) return { words: pieces, ask: "", offers: [], tail: [] };
  const words = pieces.slice(0, first);
  let ask = "";
  const last = words[words.length - 1];
  if (last && !("chip" in last)) {
    const sentence = last.text.match(LAST_SENTENCE)?.[0] ?? "";
    ask = sentence.trim();
    words[words.length - 1] = {
      text: last.text.slice(0, last.text.length - sentence.length),
    };
  }
  const rest = pieces.slice(first);
  const lastOffer =
    rest.length -
    1 -
    [...rest]
      .reverse()
      .findIndex((p) => "chip" in p && p.chip.tone === ChipTone.Ask);
  return {
    words,
    ask,
    offers: rest
      .slice(0, lastOffer + 1)
      .flatMap((p) => ("chip" in p && p.chip.tone === ChipTone.Ask ? [p.chip] : [])),
    tail: rest.slice(lastOffer + 1),
  };
}
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

  /** A whole reply as it stands when nothing is typing: the words, the closing
   * question in amber, and the offers in their own row. A reopened session must
   * read exactly as the reply did when it was written. */
  private written(pieces: Piece[]): string {
    const { words, ask, offers, tail } = layout(pieces);
    return (
      this.render(words) +
      (ask ? `<div class="ask">${esc(ask)}</div>` : "") +
      (offers.length
        ? `<div class="offer">${offers.map((c) => this.pill(c)).join("")}</div>`
        : "") +
      this.render(tail)
    );
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
      role === Role.Coach
        ? `<div class="who">Coach</div>` + this.written(tokenize(text, tone))
        : // Only the coach offers; the same chip sent back by the user is words
          // in their own sentence.
          this.render(tokenize(text, tone)),
    );
    // The bubble carries its statement so a moment on the picture can point
    // back at the words that coded it.
    if (statementId !== null) bubble.dataset.statement = String(statementId);
    // A play-by-play carries the cluster it walks, so its chips step the board
    // instead of taking the picture back to the wire.
    if (play !== null) bubble.dataset.play = play;
    this.said.set(bubble, text);
    this.list.append(bubble);
    this.stuck = true;
    this.scroll();
    return bubble;
  }

  /** A line the app says rather than either speaker, centred between the
   * bubbles: what just happened to the thread. */
  system(line: string): void {
    this.list.append(el("div", "sys", esc(line)));
    this.stuck = true;
    this.scroll();
  }

  /** Something did not go through, said where it would have appeared and left
   * there until it is put right. It never types, never fades and never goes on
   * its own: the reader has to still find it when they look back.
   *
   * One at a time. A second failure says the same thing in the same place
   * rather than piling a second notice under the first. */
  warn(line: string, again: () => void): HTMLElement {
    this.settled();
    const note = el(
      "div",
      "sys warn",
      `<span>${esc(line)}</span>` +
        `<button type="button" class="chip retry">[try again]</button>`,
    );
    note.querySelector("button")?.addEventListener("click", () => {
      note.remove();
      again();
    });
    this.list.append(note);
    this.stuck = true;
    this.scroll();
    return note;
  }

  /** Something went through. Whatever did not go through before it is no longer
   * true, however it was put right — the retry, or simply saying something
   * else that landed. */
  settled(): void {
    for (const note of this.list.querySelectorAll(".sys.warn")) note.remove();
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
        const write = async (into: HTMLElement, run: string, tick: number) => {
          for (let i = 0; i < run.length; i += CHARS) {
            into.append(run.slice(i, i + CHARS));
            this.scroll();
            await wait(tick);
          }
        };
        const { words: said, ask, offers, tail } = layout(tokenize(text));
        for (const piece of said) {
          if ("chip" in piece) {
            await release();
            words.insertAdjacentHTML("beforeend", this.pill(piece.chip));
            (words.lastElementChild as HTMLElement).classList.add("lit");
            held = words.lastElementChild as HTMLElement;
            onChip(piece.chip);
          } else await write(words, piece.text, TICK_MS);
          this.scroll();
        }
        await release();
        // The question that closes the reply stands apart in amber, after a
        // beat, and the answers land under it one at a time.
        if (ask) {
          await wait(ASK_MS);
          const line = el("div", "ask");
          bubble.append(line);
          await write(line, ask, ASK_TICK_MS);
        }
        if (offers.length) {
          const row = el("div", "offer");
          bubble.append(row);
          for (const offer of offers) {
            row.insertAdjacentHTML("beforeend", this.pill(offer));
            onChip(offer);
            this.scroll();
            await wait(OFFER_MS);
          }
        }
        if (tail.length) {
          const after = el("span", "words");
          bubble.append(after);
          for (const piece of tail) {
            if ("chip" in piece) {
              after.insertAdjacentHTML("beforeend", this.pill(piece.chip));
              onChip(piece.chip);
            } else await write(after, piece.text, TICK_MS);
          }
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

  /** How long after a thread is put up it keeps putting itself back on its
   * last words. */
  private static readonly SETTLE_MS = 800;

  /** Open on the newest words and stay there while the page settles.
   *
   * Pinning once is not enough on a reload: the web fonts land after the
   * bubbles have been measured and every one of them grows, and the picture
   * takes its own height only when the record arrives, which shortens the
   * thread's own box. Either leaves the last bubble under the edge. This holds
   * the end in view until both have happened, and lets go the moment the
   * reader scrolls up to read something earlier. */
  toEnd(): void {
    this.stuck = true;
    this.scroll();
    const until = performance.now() + Chat.SETTLE_MS;
    const again = () => {
      if (!this.stuck) return;
      this.list.scrollTop = this.list.scrollHeight;
      if (performance.now() < until) requestAnimationFrame(again);
    };
    requestAnimationFrame(again);
    void document.fonts?.ready.then(() => {
      if (this.stuck) this.list.scrollTop = this.list.scrollHeight;
    });
  }
}

export interface LiveBubble {
  note(line: string): void;
  type(text: string, onChip: (chip: Chip) => void, pace?: number): Promise<void>;
}

export const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
