import * as api from "./api";
import { el, esc } from "./dom";
import { toast } from "./toast";
import { PickChoice, PickSource, type Shadows } from "./types";

/** While shadow replies are on, a coach reply waits for the other models' and
 * the reader votes on all of them unnamed before they type again (R-0636).
 * The reply that is the coach's is only said once the vote is in, and no model
 * is ever named. */

/** How long a reply waits for its shadows: what has come by then is voted
 * on, and with none the reply is shown alone. */
const PATIENCE_MS = 60_000;
/** Shadow replies turn themselves off this long after the last message, or
 * after being turned on with none since (R-0637). */
export const IDLE_MS = 5 * 60_000;
/** How often the review is asked whether the shadows have finished. */
const POLL_MS = 2000;
const NOTE_CAP = 200;
const HELP = "One or two sentences, optional";

const FOLD =
  `<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2.5" y="5.5" width="9" height="8" rx="1.5"/>` +
  `<path d="M5 3h7.5a1.5 1.5 0 0 1 1.5 1.5V11"/></svg>`;

interface Voted {
  ok: Set<string>;
  best: string | null;
  note: string;
}

/** An unacceptable reply never wins; of two acceptable ones the best does,
 * and with no best between them, or neither acceptable, it is a tie. */
export function choose(left: string, right: string, voted: Voted): PickChoice {
  const l = voted.ok.has(left);
  const r = voted.ok.has(right);
  if (l && !r) return PickChoice.Left;
  if (r && !l) return PickChoice.Right;
  if (l && voted.best === left) return PickChoice.Left;
  if (r && voted.best === right) return PickChoice.Right;
  return PickChoice.Tie;
}

const verdict = (key: string, voted: Voted) =>
  voted.ok.has(key)
    ? `<div class="vt-voted">✓ acceptable${voted.best === key ? " · ★ best" : ""}</div>`
    : `<div class="vt-voted no">not acceptable</div>`;

/** What the vote needs of the thread it sits in. */
export interface Host {
  /** A reply's words laid out as a coach reply is, with nothing to say which
   * one the coach's is. */
  written(text: string): string;
  /** The message box, closed while the vote is open. */
  hold(on: boolean): void;
  /** The thread follows the bubble down as it grows. */
  scroll(): void;
}

export class Vote {
  private voted: Voted = { ok: new Set(), best: null, note: "" };
  private replies: Shadows["replies"] = [];
  private realKey = "";
  private ballot: HTMLElement | null = null;

  constructor(
    private bubble: HTMLElement,
    private turnId: string,
    /** How many shadow models answer each turn: one pick each when all are in. */
    private models: number,
    private host: Host,
  ) {
    bubble.classList.add("blind");
    bubble.append(el("div", "vt-wait dots3", "Waiting for other replies"));
    host.hold(true);
    host.scroll();
    void this.start();
  }

  private async start(): Promise<void> {
    let shadows: Shadows | null;
    try {
      shadows = await this.ready();
    } catch (error) {
      this.alone();
      throw error;
    }
    if (shadows) this.show(shadows);
  }

  /** The turn's replies once every shadow has its pick, or whatever is in at
   * the deadline; null when the thread was put away meanwhile. */
  private async ready(): Promise<Shadows | null> {
    const until = Date.now() + PATIENCE_MS;
    for (;;) {
      if (!this.bubble.isConnected) return null;
      const shadows = await api.shadows(this.turnId);
      if (shadows.picks.length >= this.models || Date.now() + POLL_MS > until) return shadows;
      await new Promise((go) => setTimeout(go, POLL_MS));
    }
  }

  private show(shadows: Shadows): void {
    // only a reply in a pick is voted on
    const picked = new Set(shadows.picks.flatMap((p) => [p.left_key, p.right_key]));
    this.replies = shadows.replies.filter((r) => picked.has(r.key));
    if (this.replies.length < 2) return this.alone();
    this.realKey = shadows.real_key!;
    this.open(shadows.picks);
  }

  /** No shadow came in time: the coach's reply alone, as on any other turn. */
  private alone(): void {
    this.bubble.querySelector(".vt-wait")?.remove();
    this.bubble.classList.remove("blind");
    this.host.hold(false);
  }

  private open(picks: Shadows["picks"]): void {
    this.bubble.querySelector(".vt-wait")?.remove();
    this.bubble.classList.add("voting");
    this.bubble.querySelector(".who")!.textContent = `${this.replies.length} replies`;
    const ballot = el(
      "div",
      "vt-ballot",
      this.replies
        .map(
          (r) =>
            `<div class="vt-reply" data-key="${esc(r.key)}">${this.host.written(r.text)}` +
            `<div class="vt-marks">` +
            `<button class="vt-mark" type="button" data-mark="ok" aria-pressed="false">✓ acceptable</button>` +
            `<button class="vt-mark" type="button" data-mark="best" aria-pressed="false">☆ best</button>` +
            `</div></div>`,
        )
        .join("") +
        `<div class="vt-cast">` +
        `<input class="vt-note" type="text" maxlength="${NOTE_CAP}" aria-label="Note" placeholder="${HELP}">` +
        `<div class="vt-row"><span class="vt-count">${HELP}</span>` +
        `<button class="btn primary vt-go" type="button">Vote</button></div></div>`,
    );
    const note = ballot.querySelector<HTMLInputElement>(".vt-note")!;
    const count = ballot.querySelector<HTMLElement>(".vt-count")!;
    note.addEventListener("input", () => {
      count.textContent = note.value ? `${note.value.length}/${NOTE_CAP}` : HELP;
    });
    // the words of a reply are not a look at the picture while it is unnamed
    ballot.addEventListener("click", (e) => {
      e.stopPropagation();
      const target = e.target as Element;
      const mark = target.closest<HTMLElement>(".vt-mark");
      if (mark) return this.mark(mark.closest<HTMLElement>(".vt-reply")!.dataset.key!, mark.dataset.mark!);
      const go = target.closest<HTMLButtonElement>(".vt-go");
      if (go) void this.cast(go, picks, note.value.trim());
    });
    this.bubble.append(ballot);
    this.ballot = ballot;
    this.host.scroll();
  }

  /** Acceptable on its own; best is one reply at most, and is acceptable too. */
  private mark(key: string, which: string): void {
    const { ok } = this.voted;
    if (which === "best") {
      this.voted.best = this.voted.best === key ? null : key;
      if (this.voted.best) ok.add(key);
    } else if (ok.has(key)) {
      ok.delete(key);
      if (this.voted.best === key) this.voted.best = null;
    } else ok.add(key);
    for (const reply of this.ballot!.querySelectorAll<HTMLElement>(".vt-reply")) {
      const fine = ok.has(reply.dataset.key!);
      const best = this.voted.best === reply.dataset.key;
      reply.classList.toggle("ok", fine);
      const [okMark, bestMark] = reply.querySelectorAll<HTMLElement>(".vt-mark");
      okMark.classList.toggle("on", fine);
      okMark.setAttribute("aria-pressed", String(fine));
      bestMark.classList.toggle("on", best);
      bestMark.setAttribute("aria-pressed", String(best));
      bestMark.textContent = `${best ? "★" : "☆"} best`;
    }
  }

  private async cast(go: HTMLButtonElement, picks: Shadows["picks"], note: string): Promise<void> {
    this.voted.note = note;
    go.disabled = true;
    try {
      await Promise.all(
        picks.map((p) =>
          api.cast(p.id, {
            choice: choose(p.left_key, p.right_key, this.voted),
            left_acceptable: this.voted.ok.has(p.left_key),
            right_acceptable: this.voted.ok.has(p.right_key),
            note,
            source: PickSource.Chat,
          }),
        ),
      );
    } catch (error) {
      go.disabled = false;
      toast(api.whatFailed(error));
      return;
    }
    this.close();
  }

  /** The vote is in: the coach's own reply, headed Coach, and the others
   * folded behind a mark beside the notes, with how each was voted. */
  private close(): void {
    this.ballot!.remove();
    this.ballot = null;
    this.bubble.classList.remove("blind", "voting");
    this.bubble.querySelector(".who")!.textContent = "Coach";
    const fold = el(
      "button",
      "vt-fold",
      `${FOLD}<span class="n">${this.replies.length - 1}</span>`,
    );
    fold.setAttribute("type", "button");
    fold.setAttribute("aria-label", "Shadow replies");
    fold.setAttribute("aria-expanded", "false");
    fold.addEventListener("click", (e) => {
      e.stopPropagation();
      this.unfold(fold);
    });
    this.bubble.append(fold);
    this.host.hold(false);
  }

  private unfold(fold: HTMLElement): void {
    const shown = this.bubble.querySelector(":scope > .vt-open");
    fold.classList.toggle("on", !shown);
    fold.setAttribute("aria-expanded", String(!shown));
    if (shown) return shown.remove();
    const { note } = this.voted;
    this.bubble.append(
      el(
        "div",
        "vt-open",
        verdict(this.realKey, this.voted) +
          this.replies
            .filter((r) => r.key !== this.realKey)
            .map(
              (r) =>
                `<div class="vt-shadow"><div class="who">Shadow reply</div>` +
                this.host.written(r.text) +
                verdict(r.key, this.voted) +
                `</div>`,
            )
            .join("") +
          (note ? `<div class="vt-said">Your note: ${esc(note)}</div>` : ""),
      ),
    );
    this.host.scroll();
  }
}
