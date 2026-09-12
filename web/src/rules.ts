import * as api from "./api";
import { esc } from "./dom";
import { toast } from "./toast";
import { RuleSource, type Rule } from "./types";

/** The coding guidelines, reached from the (i) at the top of the coding screen
 * (R-0278). Every rule says where it came from, and anyone can flag one for
 * the next meeting (R-0276). A rule is never deleted, only retired. */

/** Where a rule came from, in words. */
function provenance(rule: Rule): string {
  const source = rule.source ?? {};
  const parts: string[] = [];
  if (rule.drafted_by === RuleSource.Ai) parts.push("drafted by the coach");
  else if (rule.drafted_by === RuleSource.Migration)
    parts.push("carried over from last year's meetings");
  else parts.push("written by a coder");
  if (source.cut_id) parts.push(`from the coding of cut ${source.cut_id}`);
  if (source.meeting) parts.push(`meeting ${source.meeting}`);
  parts.push(rule.ratified_at ? "agreed at a meeting" : "not agreed yet");
  return parts.join(" · ");
}

export class Rules {
  private rules: Rule[] = [];

  constructor(private body: HTMLElement) {
    this.body.addEventListener("click", (e) => {
      const button = (e.target as Element).closest<HTMLElement>(".rl-flag");
      if (button) void this.flag(Number(button.dataset.rule));
    });
  }

  async load(): Promise<void> {
    this.rules = await api.rules();
    this.render();
  }

  private async flag(id: number): Promise<void> {
    const flagged = await api.flagRule(id);
    this.rules = this.rules.map((rule) => (rule.id === id ? flagged : rule));
    this.render();
    toast("Flagged for the next meeting");
  }

  private render(): void {
    this.body.innerHTML = this.rules.length
      ? this.rules.map((rule) => this.row(rule)).join("")
      : `<div class="none">No coding guidelines yet.</div>`;
  }

  private row(rule: Rule): string {
    const flagged = (rule.flags ?? []).some((flag) => !flag.closed_at);
    return (
      `<div class="rl-row"><div class="rl-t">${esc(rule.text)}</div>` +
      `<div class="rl-m">${esc(provenance(rule))}</div>` +
      `<button class="rl-flag" type="button" data-rule="${rule.id}"` +
      `${flagged ? " disabled" : ""}>` +
      `${flagged ? "flagged for the next meeting" : "flag for next meeting"}` +
      `</button></div>`
    );
  }
}
