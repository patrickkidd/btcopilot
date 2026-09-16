import * as api from "./api";
import { esc, isAdmin } from "./dom";
import { toast } from "./toast";
import { RuleSource, type Rule } from "./types";

/** The coding guidelines, reached from the (i) at the top of the coding screen
 * (R-0278). Every rule says where it came from. Patrick alone flags one for
 * the next meeting, and the same tap takes the flag off; everyone else reads
 * that it is flagged (R-0276, R-0346). A rule is never deleted, only retired. */

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

/** The flag a guideline carries: Patrick taps it on and off, and everyone else
 * reads it as words, or reads nothing when no flag stands (R-0346). */
export function flagLine(rule: Rule, className: string): string {
  const words = rule.flagged ? "flagged for the next meeting" : "flag for next meeting";
  if (!isAdmin()) return rule.flagged ? `<div class="${className} said">${words}</div>` : "";
  return `<button class="${className}" type="button" data-rule="${rule.id}">${words}</button>`;
}

export class Rules {
  private rules: Rule[] = [];

  constructor(private body: HTMLElement) {
    this.body.addEventListener("click", (e) => {
      const button = (e.target as Element).closest<HTMLElement>("button.rl-flag");
      if (button) void this.flag(Number(button.dataset.rule));
    });
  }

  async load(): Promise<void> {
    this.rules = await api.rules();
    this.render();
  }

  private async flag(id: number): Promise<void> {
    const was = this.rules.find((rule) => rule.id === id)?.flagged === true;
    const after = await api.flagRule(id, !was);
    this.rules = this.rules.map((rule) => (rule.id === id ? after : rule));
    this.render();
    toast(after.flagged ? "Flagged for the next meeting" : "Flag taken off");
  }

  private render(): void {
    this.body.innerHTML = this.rules.length
      ? this.rules.map((rule) => this.row(rule)).join("")
      : `<div class="none">No coding guidelines yet.</div>`;
  }

  private row(rule: Rule): string {
    return (
      `<div class="rl-row"><div class="rl-t">${esc(rule.text)}</div>` +
      `<div class="rl-m">${esc(provenance(rule))}</div>` +
      flagLine(rule, "rl-flag") +
      `</div>`
    );
  }
}
