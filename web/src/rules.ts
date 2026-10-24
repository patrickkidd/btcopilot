import * as api from "./api";
import { conceptPages, heading } from "./concepts";
import { el, esc, isAdmin, isCoder } from "./dom";
import { frameBack, group, guideFrame, tapRow } from "./settingrows";
import { toast } from "./toast";
import { RuleSource, type Rule } from "./types";

/** The coding guidelines, reached from the (i) at the top of the coding screen
 * (R-0278). Every rule says where it came from. Patrick alone flags one for
 * the next meeting, and the same tap takes the flag off; everyone else reads
 * that it is flagged (R-0276, R-0346). A rule is never deleted, only retired.
 * Under them, the concept pages, each read inside the app (R-0541). */

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
  /** The concept page open over the list, which the back button closes first. */
  private page: HTMLIFrameElement | null = null;
  /** Opened from a link on another screen, so back leaves for that screen. */
  private alone = false;
  private named: string;

  constructor(
    private body: HTMLElement,
    private title: HTMLElement,
  ) {
    this.named = title.textContent ?? "";
    this.body.addEventListener("click", (e) => {
      const button = (e.target as Element).closest<HTMLElement>("button.rl-flag");
      if (button) void this.flag(Number(button.dataset.rule));
    });
  }

  async load(): Promise<void> {
    this.close();
    this.rules = await api.rules();
    this.render();
  }

  /** Back from a concept page to the list; false when there is no list to go
   * back to. */
  back(): boolean {
    if (this.page && frameBack(this.page)) return true;
    const over = !!this.page && !this.alone;
    this.close();
    return over;
  }

  /** One concept page on its own, from a link on another screen. */
  read(href: string, name: string): void {
    this.close();
    this.open(href, name);
    this.alone = true;
  }

  private open(href: string, name: string): void {
    this.page = guideFrame(href, name);
    this.body.after(this.page);
    this.body.hidden = true;
    this.title.textContent = name;
  }

  private close(): void {
    this.page?.remove();
    this.page = null;
    this.alone = false;
    this.body.hidden = false;
    this.title.textContent = this.named;
  }

  private async flag(id: number): Promise<void> {
    const was = this.rules.find((rule) => rule.id === id)?.flagged === true;
    const after = await api.flagRule(id, !was);
    this.rules = this.rules.map((rule) => (rule.id === id ? after : rule));
    this.render();
    toast(after.flagged ? "Flagged for the next meeting" : "Flag taken off");
  }

  private render(): void {
    const parts: HTMLElement[] = [];
    if (this.rules.length) {
      const list = el("div", "", this.rules.map((rule) => this.row(rule)).join(""));
      list.prepend(el("div", "sn-hd", "Guidelines"));
      parts.push(list);
    }
    if (isCoder()) {
      const rows = conceptPages().map(({ href, name }) =>
        tapRow(heading(name), "", () => this.open(href, heading(name))),
      );
      parts.push(group(rows, "Concept pages"));
    }
    this.body.replaceChildren(...parts);
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
