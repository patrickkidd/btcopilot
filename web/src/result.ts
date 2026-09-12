import * as api from "./api";
import { esc, type Title } from "./dom";
import { toast } from "./toast";
import type { Differed, Result, Rule, Tendency } from "./types";

/** After ratification: what the meeting produced, with nothing to choose.
 *
 * How many events were ratified and how many were left unresolved, agreement
 * before the ballot and after ratification side by side, how the coach's own
 * pass scored against the agreed record, the guideline changes the AI wrote
 * with the settle each came from, where its reading differed from the room,
 * and what each coder tends to do (R-0242, R-0249, R-0254, R-0259).
 */

export interface ResultHandlers {
  onTitle(title: string | Title): void;
}

const day = (value: string): string =>
  new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });

/** A rule's provenance in the words of the settle it came from. */
function from(rule: Rule): string {
  const source = rule.source as {
    label?: string;
    margin?: string | null;
    meeting_date?: string | null;
  };
  const said = [
    source.label ? `from ${source.label}` : "from this meeting",
    source.margin ? `settled ${source.margin}` : null,
  ].filter(Boolean);
  return said.join(" · ");
}

/** What one coder tends to do, said as a sentence rather than a score. */
function tends(one: Tendency): string[] {
  const said: string[] = [];
  if (one.left_out)
    said.push(
      `${one.name} left out ${one.left_out} of ${one.items} items the others coded.`,
    );
  if (one.apart)
    said.push(
      `${one.name} read ${one.apart} of ${one.items} differently from what the room settled.`,
    );
  if (one.leans)
    said.push(
      `${one.name} differs on ${one.leans} more than anything else (${one.leans_count} times).`,
    );
  return said;
}

export class ResultScreen {
  private result: Result | null = null;

  constructor(
    private stats: HTMLElement,
    private body: HTMLElement,
    private handlers: ResultHandlers,
  ) {
    this.body.addEventListener("click", (clicked) => void this.onTap(clicked));
  }

  async open(cutId: number): Promise<void> {
    this.result = await api.result(cutId);
    this.render();
  }

  private render(): void {
    const found = this.result;
    if (!found) return;
    this.handlers.onTitle(`ratified ${day(found.ratified_at)}`);
    this.stats.innerHTML = this.figures(found);
    this.body.innerHTML =
      this.rules(found) + this.differed(found) + this.coders(found);
  }

  /** The counts, and the two agreement figures side by side. */
  private figures(found: Result): string {
    const percent = (value: number | null | undefined) =>
      value === null || value === undefined ? "—" : `${value}%`;
    const coach = found.coach;
    return (
      `<span>${found.items} items</span>` +
      `<span>${found.ratified} ratified</span>` +
      `<span>${found.unresolved} unresolved</span>` +
      `<span>agreement first pass <b>${percent(found.first_pass?.percent)}</b></span>` +
      `<span>after ratification <b>${percent(found.after?.percent)}</b></span>` +
      (coach
        ? `<span>the coach's pass against the ratified record: ` +
          `events <b>${coach.events}</b> · people <b>${coach.people}</b>` +
          (coach.variables === null
            ? ""
            : ` · variables <b>${coach.variables}</b>`) +
          `</span>`
        : "")
    );
  }

  /** The guideline changes the AI wrote, each with the settle it came from and
   * a link that puts it on the next meeting's agenda (R-0259, R-0276). */
  private rules(found: Result): string {
    if (!found.rules.length)
      return (
        `<div class="rcard"><h4>Guidelines changed by this meeting · 0</h4>` +
        `<div class="prov">Nothing the room settled asked for a new rule.</div>` +
        `</div>`
      );
    return (
      `<div class="rcard"><h4>Guidelines changed by this meeting · ` +
      `${found.rules.length}</h4>` +
      found.rules
        .map(
          (rule) =>
            `<div class="rule">${esc(rule.text)}</div>` +
            `<div class="prov">${esc(from(rule))}</div>` +
            `<div><span class="flag rs-flag" data-rule="${rule.id}">` +
            `${rule.flags.some((one) => !one.closed_at) ? "flagged for next meeting" : "flag for next meeting"}` +
            `</span></div>`,
        )
        .join("") +
      `<div class="prov" style="margin-top:12px">flagged rules and unresolved ` +
      `items go on the next meeting's agenda by themselves</div></div>`
    );
  }

  /** Where the AI's reading differed from the room, with its reason. An audit
   * rather than a vote (R-0254). */
  private differed(found: Result): string {
    if (!found.differed.length) return "";
    return (
      `<div class="acard"><h4>Where the AI's proposal differed from the ` +
      `room · ${found.differed.length}</h4>` +
      found.differed.map((one) => this.arow(one)).join("") +
      `</div>`
    );
  }

  private arow(one: Differed): string {
    return (
      `<div class="arow"><span>${esc(one.label)}</span>` +
      `<span class="s2">the room: ${esc(one.room)}</span>` +
      `<span class="s2">the AI: ${esc(one.coach)}</span>` +
      `<span>${esc(one.reason ?? "no reason was given")}</span></div>`
    );
  }

  private coders(found: Result): string {
    const lines = found.coders.flatMap(tends);
    if (!lines.length) return "";
    return (
      `<div class="rcard"><h4>What each coder tends to do</h4>` +
      lines.map((said) => `<div class="who2">${esc(said)}</div>`).join("") +
      `</div>`
    );
  }

  /** Flagging a rule does one thing: it puts that rule on the next meeting's
   * agenda (R-0276). */
  private async onTap(clicked: Event): Promise<void> {
    const flag = (clicked.target as Element).closest<HTMLElement>(".rs-flag");
    if (!flag) return;
    await api.flagRule(Number(flag.dataset.rule));
    toast("On the next meeting's agenda");
    if (this.result) await this.open(this.result.cut_id);
  }
}
