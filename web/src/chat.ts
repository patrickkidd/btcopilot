import { esc, el, flash, shift } from "./dom";
import { askedChip, chipOf, face, LEAD, Lead, pill, token, tokenize } from "./chips";
import { hush, say } from "./speech";
import { INFO, notesView, type Notes } from "./notes";
import { html, type Line } from "./tools";
import { AWAY_PX, fit, fold, type Fold } from "./viewport";
import { IDLE_MS, Vote, type Host } from "./vote";
import { ChipKind, ChipTone, Role, type Chip, type Piece } from "./types";

/** Chat is the whole surface: coach and user messages both render their chips
 * as pills, and a pill the user taps lands in the composer as something they
 * type around (R-0072). While the coach's words type themselves out, each chip
 * lights as it lands and the picture draws what it names — pane A of the
 * approved play-by-play. */

export interface ChatHandlers {
  onChip(chip: Chip): void;
  /** A tap on a bubble's own words rather than on a chip inside it: the picture
   * lights what that message named. It is a look, so it costs no turn. */
  onBubble(text: string): void;
  /** A tap on a play-by-play's own words: open its drawer again, if it has a
   * told case to open; false when it has none. */
  onPlay(statement: number): boolean;
  /** What a chip should read as. The coach may write a reference with no words
   * of its own, and a name out of the record beats a pronoun in a sentence. */
  label(chip: Chip): string;
  /** The card that asks whether two people are one, drawn from the record. */
  merge(chip: Chip): string;
  /** The message box opened again after a vote: a message held while the coach
   * was replying goes now. */
  onOpen(): void;
}

/** The beat after a chip's sentence has been written, before the next chip
 * lights: long enough to look at what was just drawn. The owner tunes
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
/** The question that closes a reply is its last sentence, when that sentence
 * is a question. */
const LAST_SENTENCE = /[^.?!]*\?\s*$/;

/** How a reply is laid out: the words, then the question that closes it set
 * apart in amber (R-0358). Offered chips are no longer written (Patrick,
 * 2026-09-21: people type their own words), but an old transcript may still
 * hold some, so a run of them is still laid out after the question. */
interface Written {
  words: Piece[];
  ask: string;
  offers: Chip[];
  tail: Piece[];
}

/** Something the coach offers to say next. A question the reader brought back
 * is amber too, but it is their own words, not an offer. */
const isOffer = (p: Piece) => "chip" in p && p.chip.kind === ChipKind.Ask;


function layout(pieces: Piece[]): Written {
  const offered = pieces.findIndex(isOffer);
  const first = offered < 0 ? pieces.length : offered;
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
  if (!rest.length) return { words, ask, offers: [], tail: [] };
  const lastOffer = rest.length - 1 - [...rest].reverse().findIndex(isOffer);
  return {
    words,
    ask,
    offers: rest
      .slice(0, lastOffer + 1)
      .flatMap((p) => ("chip" in p && isOffer(p) ? [p.chip] : [])),
    tail: rest.slice(lastOffer + 1),
  };
}
/** A reply's closing question: the amber chip that answers it once the reply
 * is stored, the amber words before then. */
const asked = (ask: string, statementId: number | null) =>
  statementId === null ? esc(ask) : askedChip(statementId, ask);

/** The statement a bubble was stored as, once the server has said. */
const stamped = (bubble: HTMLElement) =>
  bubble.dataset.statement ? Number(bubble.dataset.statement) : null;

/** A reference the server has only half sent: it is held back until the rest
 * of it arrives, so the reader never sees brackets. */
const PART = /\[\[[^\]]*$/;

/** What the message box says while a vote is open (R-0636). */
const VOTE_FIRST = "Vote first, then type";
/** Under a message sent while the coach is still replying (R-0636). */
const HELD = "Sends when the coach finishes";

/** One thing the coach did, as a plain line above its words. */
const did = (line: Line) => el("div", "did", html(line));

/** A coach reply's own button that reads it aloud, whether or not replies are
 * spoken as they arrive. It sits under the bubble, never in it, so the bubble
 * is the same shape with or without it. */
const PLAY =
  `<button type="button" class="play" aria-label="Read aloud">` +
  `<svg viewBox="0 0 16 16" aria-hidden="true">` +
  `<path class="go" d="M4.5 2.75v10.5l8.5-5.25z"/>` +
  `<rect class="halt" x="3.5" y="3.5" width="9" height="9" rx="1"/></svg></button>`;

/** A bubble of tool lines alone, or a turn that failed, has no words to read. */
const playable = (bubble: HTMLElement, text: string) => {
  if (bubble.nextElementSibling?.matches(".play")) bubble.nextElementSibling.remove();
  if (text) bubble.insertAdjacentHTML("afterend", PLAY);
};

export class Chat {
  /** What each bubble was written from, chips and all, so a tap on its words
   * can light the same moments its chips name. */
  private said = new WeakMap<HTMLElement, string>();
  private typing: HTMLElement | null = null;
  /** The coach's notes on each turn that carries them, for admins and auditors. */
  private noted = new WeakMap<HTMLElement, Notes>();
  /** Whether the thread is following the newest words. */
  private stuck = true;
  /** True while this class is the one moving the scroll, so its own pinning is
   * not mistaken for the reader scrolling away. */
  private pinning = false;
  private strip: Fold;
  /** What the message box says when it is open. */
  private ph: string;
  /** How many other models answer each turn too. While any do, the reader
   * votes before typing again, and the coach's words are not shown until
   * then (R-0636). */
  shadows = 0;
  /** When the shadows turn themselves off unless a message comes first. */
  expires: number | null = null;
  /** The words in the box were sent while the coach was replying, and go the
   * moment the reply ends. */
  held = false;
  private bar: HTMLElement;
  private button: HTMLButtonElement;

  constructor(
    private list: HTMLElement,
    private composer: HTMLElement,
    private handlers: ChatHandlers,
  ) {
    const tap = (host: HTMLElement) => (e: Event) => {
      const play = (e.target as Element).closest<HTMLElement>(".play");
      if (play) return this.read(play);
      const info = (e.target as Element).closest<HTMLElement>(".info");
      if (info) return this.open(info.parentElement as HTMLElement);
      // [try again] looks like a chip but names nothing in the record.
      const button = (e.target as Element).closest<HTMLElement>("button.chip[data-kind]");
      if (!button) {
        if (host === this.composer) return;
        const bubble = (e.target as Element).closest<HTMLElement>(".bub");
        if (!bubble) return;
        // A play-by-play's own words open it again; an old prose walk has no
        // case to open, and its words are a look like any message's.
        if (bubble.dataset.play && bubble.dataset.statement && this.handlers.onPlay(Number(bubble.dataset.statement)))
          return;
        const said = this.said.get(bubble);
        if (said) this.handlers.onBubble(said);
        return;
      }
      e.preventDefault();
      if (host === this.composer) return this.caret(button);
      this.handlers.onChip(chipOf(button));
    };
    this.ph = composer.dataset.ph!;
    this.bar = composer.closest<HTMLElement>(".inbar")!;
    this.button = this.bar.querySelector<HTMLButtonElement>(".send")!;
    composer.after(el("div", "held", HELD));
    composer.addEventListener("input", () => {
      if (this.draft() === "") this.unhold();
      this.mark();
    });
    // the chat box stays above the phone's keyboard, however it came up
    fit();
    this.strip = fold(this.composer, this.list.closest<HTMLElement>(".screen")!, () => this.toEnd());
    this.watchScrolling();
    // the thread's box changes size after it is put up — a phone's toolbar
    // collapsing, the picture taking its height or folding — and stays on its
    // last words, or, scrolled up, keeps every bubble where it was over the
    // message box (R-0570)
    let high = this.list.clientHeight;
    new ResizeObserver(() => {
      const grew = this.list.clientHeight - high;
      high = this.list.clientHeight;
      if (this.stuck) return this.scroll();
      this.pinning = true;
      shift(this.list, -grew);
      requestAnimationFrame(() => {
        this.pinning = false;
      });
    }).observe(this.list);
    // The thread's height is only final once the web font has replaced the
    // fallback, so pin it again then: otherwise a thread opened before the font
    // lands sits partway up its own scroll.
    void document.fonts?.ready.then(() => this.scroll());
    this.list.addEventListener("click", tap(this.list));
    this.composer.addEventListener("click", tap(this.composer));
  }

  private pill(chip: Chip): string {
    return pill(chip, this.handlers.label(chip));
  }

  /** A chip as the coach's words carry it: two people asked about are their
   * card, anything else its pill. */
  private piece(chip: Chip): string {
    return chip.kind === ChipKind.Merge ? this.handlers.merge(chip) : this.pill(chip);
  }

  /** The thread is drawn before the record arrives, so a chip written with no
   * words of its own first says a stand-in word. Once the record is here it
   * says what the record calls the thing it names. */
  relabel(): void {
    for (const button of this.list.querySelectorAll<HTMLElement>("button.chip[data-bare]")) {
      const kind = button.dataset.kind as ChipKind;
      const full = this.handlers.label({
        kind,
        target: button.dataset.target ?? "",
        label: button.dataset.full ?? "",
        tone: button.classList.contains(ChipTone.Ask) ? ChipTone.Ask : ChipTone.Data,
        bare: true,
      });
      button.dataset.full = full;
      button.title = full;
      button.textContent = face(kind, full);
    }
    for (const card of this.list.querySelectorAll<HTMLElement>('.bub.coach button.chip[data-kind="merge"]'))
      card.outerHTML = this.handlers.merge(chipOf(card));
  }

  /** Words and chips; the coach's carry the card two people are asked
   * about on, the reader's the pill they sent it back as. */
  private render(pieces: Piece[], coach = true): string {
    return pieces
      .map((p) => ("chip" in p ? (coach ? this.piece(p.chip) : this.pill(p.chip)) : esc(p.text)))
      .join("");
  }

  /** A whole reply as it stands when nothing is typing: the words, the closing
   * question in amber, and the offers in their own row. A reopened session must
   * read exactly as the reply did when it was written. */
  private written(pieces: Piece[], statementId: number | null): string {
    const { words, ask, offers, tail } = layout(pieces);
    return (
      `<span class="words">${this.render(words)}</span>` +
      (ask ? `<div class="ask">${asked(ask, statementId)}</div>` : "") +
      (offers.length
        ? `<div class="offer">${offers.map((c) => this.pill(c)).join("")}</div>`
        : "") +
      (tail.length ? `<span class="words">${this.render(tail)}</span>` : "")
    );
  }

  /** The tap is itself the gesture iOS wants before it will speak. */
  private read(button: HTMLElement): void {
    if (button.classList.contains("on")) return hush();
    say(this.said.get(button.previousElementSibling as HTMLElement)!, () => button.classList.remove("on"));
    button.classList.add("on");
  }

  private open(bubble: HTMLElement): void {
    notesView(this.noted.get(bubble)!, bubble);
  }

  private annotate(bubble: HTMLElement, notes: Notes): void {
    this.noted.set(bubble, notes);
    if (!bubble.querySelector(":scope > .info")) bubble.insertAdjacentHTML("beforeend", INFO);
  }

  clear(): void {
    this.list.innerHTML = "";
    this.unhold();
    this.hold(false);
    this.stuck = true;
  }

  /** What to do on an empty session, where the bubbles will be: a heading and
   * a line or two saying what to type. It goes the moment the reader sends
   * their first words (R-0350). */
  prompt(title: string, lines: string[]): void {
    this.list.querySelector(".cta")?.remove();
    this.list.append(
      el(
        "div",
        "cta",
        `<div class="cta-t">${esc(title)}</div>` +
          lines.map((line) => `<p class="cta-p">${esc(line)}</p>`).join(""),
      ),
    );
  }

  add(
    role: Role,
    text: string,
    tone = ChipTone.Data,
    statementId: number | null = null,
    play: string | null = null,
    lines: Line[] = [],
    notes: Notes | null = null,
  ): HTMLElement {
    if (role === Role.User) this.list.querySelector(".cta")?.remove();
    const bubble = el(
      "div",
      `bub ${role}`,
      role === Role.Coach
        ? `<div class="who">Coach</div>` + this.written(tokenize(text, tone), statementId)
        : // Only the coach offers; the same chip sent back by the user is words
          // in their own sentence.
          this.render(tokenize(text, tone), false),
    );
    bubble.querySelector(".who")?.after(...lines.map(did));
    if (notes) this.annotate(bubble, notes);
    // The bubble carries its statement so a moment on the picture can point
    // back at the words that coded it.
    if (statementId !== null) bubble.dataset.statement = String(statementId);
    // A play-by-play carries the cluster it tells, so a tap on it opens it again.
    if (play !== null) bubble.dataset.play = play;
    this.said.set(bubble, text);
    this.list.append(bubble);
    if (role === Role.Coach) playable(bubble, text);
    this.stuck = true;
    this.scroll();
    return bubble;
  }

  private voter: Host = {
    written: (text) => this.written(tokenize(text), null),
    hold: (on) => this.hold(on),
    scroll: () => this.scroll(),
    end: () => this.toEnd(),
    voted: () => this.extend(),
  };

  /** A stored coach reply whose turn has `count` shadow replies (R-0636);
   * `last` when it is the thread's newest message. */
  kept(bubble: HTMLElement, turnId: string, count: number, last: boolean): Vote {
    return new Vote(bubble, turnId, count, this.voter).kept(last);
  }

  /** Whether the shadows are on and have not yet turned themselves off. */
  feedback(): boolean {
    return this.shadows > 0 && this.expires !== null && Date.now() <= this.expires;
  }

  /** The five minutes start again from now while the shadows are on: a reply
   * is there to read and vote on, or a vote was just saved (R-0637). */
  extend(): void {
    if (this.feedback()) this.expires = Date.now() + IDLE_MS;
  }

  /** A message goes out: shadows that turned themselves off stay off for it,
   * and ones still on last until IDLE_MS after it. True when they had lapsed. */
  sent(): boolean {
    const lapsed = this.shadows > 0 && !this.feedback();
    if (lapsed) this.shadows = 0;
    return lapsed;
  }

  /** The message box closed while a vote is open, and open again after. */
  private hold(on: boolean): void {
    this.bar.classList.toggle("off", on);
    this.composer.contentEditable = String(!on);
    this.composer.dataset.ph = on ? VOTE_FIRST : this.ph;
    this.button.disabled = on;
    if (!on && this.held) this.handlers.onOpen();
  }

  /** Whether a vote has the message box closed. */
  voting(): boolean {
    return this.bar.classList.contains("off");
  }

  /** While the coach replies the box stays open to type in, and its button
   * stops the reply unless there are new words in the box to send after it. */
  running(on: boolean): void {
    this.bar.classList.toggle("run", on);
    this.mark();
  }

  /** Whether a tap on the button stops the reply rather than sends. */
  stops(): boolean {
    return this.bar.classList.contains("run") && (this.held || this.draft() === "");
  }

  /** The words in the box wait for the reply to end. */
  keep(): void {
    this.held = true;
    this.bar.classList.add("hold");
    this.mark();
  }

  unhold(): void {
    this.held = false;
    this.bar.classList.remove("hold");
    this.mark();
  }

  private mark(): void {
    const stop = this.stops();
    this.bar.classList.toggle("stop", stop);
    this.button.setAttribute("aria-label", stop ? "Stop" : "Send");
  }

  /** A line the app says rather than either speaker, centred between the
   * bubbles: what just happened to the thread. */
  system(line: string): void {
    this.list.append(el("div", "sys", esc(line)));
    this.stuck = true;
    this.scroll();
  }

  /** A reply the reader stopped gives way to a grey line in its place: nothing
   * it began to say stays, and the dots end (R-0636). */
  stopped(bubble: HTMLElement | null, line: string): void {
    const at = bubble ?? this.typing;
    const note = el("div", "sys", esc(line));
    if (at?.nextElementSibling?.matches(".play")) at.nextElementSibling.remove();
    if (at) at.replaceWith(note);
    else this.list.append(note);
    this.typing = null;
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
   * `scrollIntoView`: the outer page must not move (UI_STANDARDS). A question
   * tracing back to where it was asked also lights the question itself. */
  trace(statementId: number, ask = false): boolean {
    const bubble = this.list.querySelector<HTMLElement>(
      `.bub[data-statement="${statementId}"]`,
    );
    if (!bubble) return false;
    for (const lit of this.list.querySelectorAll(".ask.hl")) lit.classList.remove("hl");
    if (ask) bubble.querySelector(".ask")?.classList.add("hl");
    flash(bubble);
    return true;
  }

  /** A coach bubble. It says what the coach did first, as a plain line each,
   * then types the words out so every chip lights its part of the picture as it
   * lands. */
  live(play: string | null = null): LiveBubble {
    const bubble = el(
      "div",
      `bub ${Role.Coach} typing${this.feedback() ? " blind fb" : ""}`,
      `<div class="who">Coach</div><span class="words"></span>`,
    );
    if (play !== null) bubble.dataset.play = play;
    this.list.append(bubble);
    this.typing = bubble;
    this.stuck = true;
    this.scroll();
    const words = bubble.querySelector(".words") as HTMLElement;
    // What the coach has said so far this turn, as the server has sent it. The
    // words are re-drawn from it on every delta, so a chip becomes a pill the
    // moment its reference is whole and never shows as brackets.
    let sofar = "";
    const seen = new Set<string>();
    const paint = (onChip: (chip: Chip) => void) => {
      const whole = sofar.replace(PART, "");
      const pieces = tokenize(whole);
      words.innerHTML = this.render(pieces);
      const lit = words.lastElementChild;
      if (lit?.classList.contains("chip")) lit.classList.add("lit");
      for (const piece of pieces) {
        if (!("chip" in piece)) continue;
        const at = `${piece.chip.kind}:${piece.chip.target}`;
        if (seen.has(at)) continue;
        seen.add(at);
        onChip(piece.chip);
      }
      this.scroll();
    };
    return {
      bubble,
      stamp: (statementId) => {
        bubble.dataset.statement = String(statementId);
      },
      note: (line) => {
        bubble.insertBefore(did(line), words);
        this.scroll();
      },
      notes: (notes) => this.annotate(bubble, notes),
      append: (text, onChip) => {
        sofar += text;
        paint(onChip);
      },
      reset: () => {
        sofar = "";
        seen.clear();
        words.innerHTML = "";
      },
      settle: (text, onChip) => {
        this.said.set(bubble, text);
        for (const extra of bubble.querySelectorAll(".ask, .offer, .words + .words"))
          extra.remove();
        const { words: said, ask, offers, tail } = layout(tokenize(text));
        words.innerHTML = this.render(said);
        if (ask) bubble.append(el("div", "ask", asked(ask, stamped(bubble))));
        if (offers.length) {
          const row = el("div", "offer");
          for (const offer of offers)
            row.insertAdjacentHTML("beforeend", this.pill(offer));
          bubble.append(row);
        }
        if (tail.length) {
          const after = el("span", "words");
          after.innerHTML = this.render(tail);
          bubble.append(after);
        }
        for (const chip of [...said, ...offers.map((c) => ({ chip: c })), ...tail])
          if ("chip" in chip) onChip(chip.chip);
        playable(bubble, text);
        bubble.classList.remove("typing", "blind");
        this.typing = null;
        this.scroll();
      },
      vote: (turnId) =>
        this.feedback() ? new Vote(bubble, turnId, this.shadows, this.voter).wait() : null,
      type: async (text, onChip, pace = READ_MS) => {
        this.said.set(bubble, text);
        // A move holds until the sentence about it has been written and there
        // has been a beat to look at it, not for a fixed count from the moment
        // it was named. The chip stays lit for as long as its moment is the
        // one on the picture.
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
            words.insertAdjacentHTML("beforeend", this.piece(piece.chip));
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
          line.innerHTML = asked(ask, stamped(bubble));
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
              after.insertAdjacentHTML("beforeend", this.piece(piece.chip));
              onChip(piece.chip);
            } else await write(after, piece.text, TICK_MS);
          }
        }
        playable(bubble, text);
        bubble.classList.remove("typing");
        this.typing = null;
      },
    };
  }

  /** Waiting is an empty coach bubble, which shows the three dots until the
   * words arrive. */
  busy(on: boolean): void {
    if (on && !this.typing) {
      this.typing = el(
        "div",
        `bub ${Role.Coach} typing wait`,
        `<div class="who">Coach</div><span class="words"></span>`,
      );
      this.list.append(this.typing);
      this.scroll();
    } else if (!on && this.typing?.classList.contains("wait")) {
      this.typing.remove();
      this.typing = null;
    }
  }

  /** Drop a chip into the composer at the caret, as an inline pill, with the
   * words that go before it and the words that follow it. A chip the coach
   * offered keeps its amber, so what the user is about to send still looks
   * like the thing they tapped. */
  insert(chip: Chip, lead: Lead, after = " "): void {
    if (this.composer.contentEditable === "false") return;
    this.composer.focus({ preventScroll: true });
    const selection = window.getSelection()!;
    if (
      !selection.rangeCount ||
      !this.composer.contains(selection.getRangeAt(0).commonAncestorContainer)
    ) {
      const end = document.createRange();
      end.selectNodeContents(this.composer);
      end.collapse(false);
      selection.removeAllRanges();
      selection.addRange(end);
    }
    const range = selection.getRangeAt(0);
    range.deleteContents();
    const fragment = range.createContextualFragment(
      (LEAD[lead] ? esc(`${LEAD[lead]} `) : "") + this.pill(chip) + esc(after),
    );
    // one piece in the words: the caret goes round it, never into its label,
    // and backspace takes it out whole
    for (const button of fragment.querySelectorAll<HTMLElement>(".chip")) button.contentEditable = "false";
    range.insertNode(fragment);
    selection.collapseToEnd();
    this.mark();
  }

  /** A chip in the chat box is a place in the words, not a control: a tap
   * puts the caret just after it, and only backspace or delete removes it. */
  private caret(chip: HTMLElement): void {
    const range = document.createRange();
    range.setStartAfter(chip);
    range.collapse(true);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    this.composer.focus({ preventScroll: true });
  }

  /** What the composer says, with its pills back as reference markup. A bare
   * chip on its own is a legitimate message. */
  draft(): string {
    let out = "";
    this.composer.childNodes.forEach((node) => {
      const kind = node instanceof HTMLElement ? (node.dataset.kind as ChipKind) : undefined;
      const at = (node as HTMLElement).dataset;
      // a message is no item of the record, so its question travels as its words
      out += kind
        ? token(kind, at.target!, kind === ChipKind.Message ? at.full : undefined)
        : (node.textContent ?? "");
    });
    return out.replace(/\u00a0/g, " ").trim();
  }

  resetDraft(): void {
    this.composer.innerHTML = "";
    this.unhold();
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

  /** The full picture, opened from the strip. */
  unfold(): void {
    this.strip.open();
  }

  private watchScrolling(): void {
    let was = this.list.scrollTop;
    this.list.addEventListener(
      "scroll",
      () => {
        const { scrollTop, scrollHeight, clientHeight } = this.list;
        const up = scrollTop < was;
        was = scrollTop;
        if (this.pinning) return;
        this.stuck = this.atBottom();
        this.strip.scrolled(this.stuck, up && scrollHeight - clientHeight - scrollTop > AWAY_PX);
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
    this.strip.scrolled(true, false);
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
  bubble: HTMLElement;
  /** The bubble carries its statement once the server has one, so a moment
   * coded in this very session can point back at it (review item 18). */
  stamp(statementId: number): void;
  note(line: Line): void;
  notes(notes: Notes): void;
  /** The next words off the wire, drawn as they land. */
  append(text: string, onChip: (chip: Chip) => void): void;
  /** The coach said those words again: what is on screen is dropped. */
  reset(): void;
  /** The reply as it will be stored: the words, the closing question, and the
   * offers, laid out for good. */
  settle(text: string, onChip: (chip: Chip) => void): void;
  /** Right after settle: the reply held back for a vote on it and its
   * shadows, while shadow replies are on; null when they are off. */
  vote(turnId: string): Vote | null;
  type(text: string, onChip: (chip: Chip) => void, pace?: number): Promise<void>;
}

export const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
