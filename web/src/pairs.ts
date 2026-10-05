import * as api from "./api";
import { Feature, tap } from "./track";
import { esc } from "./dom";
import { toast } from "./toast";
import { WIDE } from "./viewport";
import { PickChoice, Who, type ModelPicks, type Pair } from "./types";

/** Blind pairs: two replies to the same words, the conversation before them
 * once, and no model named until Patrick has picked left, right or a tie with
 * a one-line note (R-0599). Under it, each model's picks so far. */

export const NOTE_CAP = 200;

/** A side is named left and right where the two stand side by side, and first
 * and second where a phone stacks them. */
const side = (wide: string, narrow: string) =>
  `<span class="pr-wide">${wide}</span><span class="pr-narrow">${narrow}</span>`;

export class Pairs {
  private waiting: Pair[] = [];
  private picks: ModelPicks[] = [];

  constructor(private body: HTMLElement) {
    this.body.addEventListener("click", (e) => void this.onClick(e));
  }

  async load(): Promise<void> {
    [this.waiting, this.picks] = await Promise.all([api.pairs(), api.modelPicks()]);
    this.render();
  }

  private async onClick(e: Event): Promise<void> {
    const button = (e.target as Element).closest<HTMLButtonElement>(".pr-pick");
    if (!button) return;
    tap(Feature.PairPick);
    const pair = this.waiting[0];
    const note = this.body.querySelector<HTMLInputElement>(".pr-note")!.value;
    const seen = await api.pick(pair.id, button.dataset.choice as PickChoice, note);
    const [one, two] = matchMedia(WIDE).matches
      ? ["Left", "right"]
      : ["First", "second"];
    toast(`${one} was ${seen.left}, ${two} was ${seen.right}`);
    await this.load();
  }

  private render(): void {
    const pair = this.waiting[0];
    this.body.innerHTML =
      `<div class="plnote">${this.waiting.length} left to pick</div>` +
      (pair ? this.pair(pair) : `<div class="none">Nothing to compare yet.</div>`) +
      this.summary();
    // the words both replies answer are the last line, so it opens there
    const ctx = this.body.querySelector<HTMLElement>(".pr-ctx");
    if (ctx) requestAnimationFrame(() => (ctx.scrollTop = ctx.scrollHeight));
  }

  private pair(pair: Pair): string {
    const lines = pair.context
      .map(
        (line) =>
          `<div class="pr-line${line.who === Who.Coach ? " coach" : ""}">` +
          `<div class="pr-who">${line.who === Who.Coach ? "Coach" : "Said"}</div>` +
          `${esc(line.text)}</div>`,
      )
      .join("");
    const reply = (wide: string, narrow: string, text: string) =>
      `<div class="pr-card"><div class="pr-who">${side(wide, narrow)}</div>` +
      `<div class="pr-text">${esc(text)}</div></div>`;
    const button = (choice: PickChoice, label: string) =>
      `<button class="nudge pr-pick" type="button" data-choice="${choice}">${label}</button>`;
    return (
      `<div class="sn-hd">The conversation</div>` +
      `<div class="pr-ctx">${lines}</div>` +
      `<div class="sn-hd">Two replies</div>` +
      `<div class="pr-two">` +
      reply("Left", "First", pair.left) +
      reply("Right", "Second", pair.right) +
      `</div>` +
      `<input class="pr-note" type="text" maxlength="${NOTE_CAP}" ` +
      `placeholder="One line on why, if you like" aria-label="A note on this pick">` +
      `<div class="pr-picks">` +
      button(PickChoice.Left, `${side("Left", "First")} is better`) +
      button(PickChoice.Tie, "Tie") +
      button(PickChoice.Right, `${side("Right", "Second")} is better`) +
      `</div>`
    );
  }

  private summary(): string {
    if (!this.picks.length) return "";
    return (
      `<div class="sn-hd">Picks so far</div>` +
      this.picks
        .map(
          (row) =>
            `<div class="sn-row"><div class="sn-lbl">${esc(row.model)}</div>` +
            `<div class="sn-val">won ${row.won} · lost ${row.lost} · tied ${row.tied}</div></div>`,
        )
        .join("")
    );
  }
}
