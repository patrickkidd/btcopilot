import * as api from "./api";
import { el, esc } from "./dom";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import { shortDate } from "./when";
import {
  Mode,
  Proactive,
  Theme,
  type Account,
  type Diagram,
  type Preferences,
} from "./types";

/** The app-level view: an iOS-Settings list where every row pushes its own full
 * page with a back chevron in the title row (`settings-nested`, the owner's
 * pick). Every value here has exactly one home; the speak-replies row on the
 * chat view is the one named shortcut, and it writes this same value. */

const PANE_MS = 220;
const SEARCH_AT = 6;

const SILHOUETTE =
  `<svg viewBox="0 0 22 22" width="22" height="22" aria-hidden="true">` +
  `<circle cx="11" cy="7.5" r="4" fill="currentColor"/>` +
  `<path d="M3 20c0-4.4 3.6-7 8-7s8 2.6 8 7z" fill="currentColor"/></svg>`;

enum Page {
  Root = "root",
  Profile = "profile",
  Coach = "coach",
  Appearance = "appearance",
  Diagrams = "diagrams",
  Plan = "plan",
}

interface Built {
  title: string;
  pane: HTMLElement;
}

export interface SettingsHandlers {
  /** The title row shows the current pane's title, and the family name again
   * when the stack closes. */
  onTitle(title: string | null): void;
  /** Every read or write of the preferences, so a value with a shortcut
   * elsewhere on screen shows the same thing. */
  onPrefs(prefs: Preferences): void;
}

/** What a diagram row says under its name: how many sessions sit on it, when
 * that last happened, and whether it is the one in use. */
function diagramSub(diagram: Diagram, now: Date): string {
  const count = `${diagram.session_count} session${diagram.session_count === 1 ? "" : "s"}`;
  const when = diagram.last_activity
    ? shortDate(new Date(diagram.last_activity), now)
    : "nothing on it yet";
  return `${count} · ${when}${diagram.free ? " · in use" : ""}`;
}

export class Settings {
  private stack: { page: Page; title: string; pane: HTMLElement }[] = [];
  private open = false;
  private prefs: Preferences | null = null;
  private account: Account | null = null;
  private host = el("div", "sn-stack");

  constructor(
    private avatar: HTMLElement,
    private back: HTMLElement,
    overlay: HTMLElement,
    private handlers: SettingsHandlers,
  ) {
    this.host.hidden = true;
    overlay.append(this.host);
    this.back.hidden = true;
    this.avatar.addEventListener("click", () => void this.raise());
    this.back.addEventListener("click", () => this.pop());
  }

  /** The avatar carries the initial of whatever name the account has. */
  async load(): Promise<void> {
    [this.prefs, this.account] = await Promise.all([
      api.preferences(),
      api.account(),
    ]);
    this.avatar.innerHTML = this.initial() || SILHOUETTE;
    this.applyTheme();
    this.handlers.onPrefs(this.prefs);
    if (this.open) this.replaceTop();
  }

  /** Write one preference from somewhere other than a settings page — the
   * speak-replies shortcut on the chat view is the one ruled case. */
  async set(body: Partial<Preferences>): Promise<void> {
    await this.write(body);
  }

  private initial(): string {
    const name = `${this.prefs?.first_name ?? ""}${this.prefs?.last_name ?? ""}`;
    return name.trim().charAt(0).toUpperCase();
  }

  private async raise(): Promise<void> {
    if (this.open) return;
    await this.load();
    this.open = true;
    this.host.hidden = false;
    this.stack = [];
    this.push(Page.Root);
  }

  private push(page: Page): void {
    const under = this.stack[this.stack.length - 1];
    const { title, pane } = this.build(page);
    pane.classList.add("sn-pane");
    pane.dataset.page = page;
    this.host.append(pane);
    dragScroll(pane);
    void pane.offsetWidth;
    pane.classList.add("in");
    if (under) under.pane.classList.add("under");
    this.stack.push({ page, title, pane });
    this.handlers.onTitle(title);
    this.back.hidden = false;
  }

  private pop(): void {
    const top = this.stack.pop();
    if (!top) return;
    if (!this.stack.length) {
      this.stack.push(top);
      this.close();
      return;
    }
    top.pane.classList.remove("in");
    window.setTimeout(() => top.pane.remove(), PANE_MS);
    const under = this.stack[this.stack.length - 1];
    under.pane.classList.remove("under");
    this.handlers.onTitle(under.title);
  }

  private close(): void {
    this.open = false;
    this.back.hidden = true;
    this.handlers.onTitle(null);
    const panes = this.stack.map((entry) => entry.pane);
    this.stack = [];
    for (const pane of panes) pane.classList.remove("in");
    window.setTimeout(() => {
      if (this.open) return;
      this.host.replaceChildren();
      this.host.hidden = true;
    }, PANE_MS);
  }

  /** Re-draw the pane on top in place, so a value written on it shows at once
   * without the pane sliding again. */
  private replaceTop(): void {
    const top = this.stack.pop();
    if (!top) return;
    top.pane.remove();
    const { title, pane } = this.build(top.page);
    pane.classList.add("sn-pane", "in");
    pane.dataset.page = top.page;
    this.host.append(pane);
    this.stack.push({ page: top.page, title, pane });
    this.handlers.onTitle(title);
  }

  private async write(body: Partial<Preferences>): Promise<void> {
    this.prefs = await api.setPreferences(body);
    this.avatar.innerHTML = this.initial() || SILHOUETTE;
    this.applyTheme();
    this.handlers.onPrefs(this.prefs);
    if (this.open) this.replaceTop();
  }

  /** The theme the account chose wins over the device's, which is what the
   * page falls back to when nothing is chosen. */
  applyTheme(): void {
    const theme = this.prefs?.theme ?? Theme.System;
    if (theme === Theme.System) delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }

  // ---- the pieces every page is made of ----

  private group(rows: HTMLElement[], head?: string): HTMLElement {
    const wrap = el("div");
    if (head) wrap.append(el("div", "sn-hd", esc(head)));
    const box = el("div", "sn-grp");
    box.append(...rows);
    wrap.append(box);
    return wrap;
  }

  private pushRow(label: string, value: string, page: Page): HTMLElement {
    const row = el("div", "sn-row push");
    row.append(
      el("div", "sn-lbl", esc(label)),
      el("div", "sn-val", esc(value)),
      el("div", "sn-chev", "›"),
    );
    row.addEventListener("click", () => this.push(page));
    return row;
  }

  private valueRow(label: string, value: string): HTMLElement {
    const row = el("div", "sn-row");
    row.append(el("div", "sn-lbl", esc(label)), el("div", "sn-val ink", esc(value || "—")));
    return row;
  }

  private inputRow(
    label: string,
    value: string,
    placeholder: string,
    type: string,
    commit: (value: string) => void,
  ): HTMLElement {
    const row = el("div", "sn-row");
    const field = document.createElement("input");
    field.className = "sn-in";
    field.type = type;
    field.value = value;
    field.placeholder = placeholder;
    field.setAttribute("aria-label", label);
    field.addEventListener("focus", () => field.classList.add("typing"));
    field.addEventListener("blur", () => {
      field.classList.remove("typing");
      if (field.value !== value) commit(field.value);
    });
    row.append(el("div", "sn-lbl", esc(label)), field);
    return row;
  }

  private segRow<T extends string>(
    label: string,
    options: T[],
    current: T,
    pick: (value: T) => void,
  ): HTMLElement {
    const row = el("div", "sn-row");
    const seg = el("div", "sn-seg");
    for (const option of options) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = option === current ? "on" : "";
      button.textContent = option;
      button.addEventListener("click", () => pick(option));
      seg.append(button);
    }
    row.append(el("div", "sn-lbl", esc(label)), seg);
    return row;
  }

  /** A boolean is a switch of the ruled size, never a native checkbox. */
  private switchRow(
    label: string,
    on: boolean,
    set: (on: boolean) => void,
  ): HTMLElement {
    const row = el("div", "sn-row");
    const button = document.createElement("button");
    button.type = "button";
    button.className = `sw${on ? " on" : ""}`;
    button.setAttribute("role", "switch");
    button.setAttribute("aria-checked", String(on));
    button.setAttribute("aria-label", label);
    button.innerHTML = `<span class="sw-thumb"></span>`;
    button.addEventListener("click", () => set(!on));
    row.append(el("div", "sn-lbl", esc(label)), el("div", "sn-seg"), button);
    return row;
  }

  // ---- the pages ----

  private build(page: Page): Built {
    const prefs = this.prefs!;
    const account = this.account!;
    if (page === Page.Root) return this.root(prefs, account);
    if (page === Page.Profile) return this.profile(prefs, account);
    if (page === Page.Coach) return this.coach(prefs);
    if (page === Page.Appearance) return this.appearance(prefs);
    if (page === Page.Diagrams) return this.diagrams(account);
    return this.plan(account);
  }

  private root(prefs: Preferences, account: Account): Built {
    const pane = el("div");
    const name = [prefs.first_name, prefs.last_name].filter(Boolean).join(" ");

    const cell = el("div", "sn-cell");
    const face = el("div", "sn-face");
    if (this.initial()) face.textContent = this.initial();
    else face.innerHTML = SILHOUETTE;
    const who = el("div", "sn-who");
    who.append(
      el("div", `sn-name${name ? "" : " empty"}`, esc(name || "Add your name")),
      el("div", "sn-sub", esc(`${account.email} · ${account.plan}`)),
    );
    cell.append(face, who, el("div", "sn-chev", "›"));
    cell.addEventListener("click", () => this.push(Page.Profile));
    const first = el("div", "sn-grp");
    first.append(cell);
    pane.append(first);

    pane.append(
      this.group([
        this.pushRow("Coach", `speak ${prefs.speak ? "on" : "off"}`, Page.Coach),
        this.pushRow("Appearance", prefs.theme, Page.Appearance),
      ]),
      this.group([
        this.pushRow(
          "Your diagrams",
          String(account.diagrams.length),
          Page.Diagrams,
        ),
        this.pushRow(
          "Plan and licenses",
          `${account.licenses.length} licence${account.licenses.length === 1 ? "" : "s"}`,
          Page.Plan,
        ),
      ]),
    );

    const out = document.createElement("button");
    out.type = "button";
    out.className = "sn-out";
    out.textContent = "Sign out";
    out.addEventListener("click", () => signOut());
    const last = el("div", "sn-grp");
    last.append(out);
    pane.append(last, el("div", "sn-foot", "Family Diagram · beta"));
    return { title: "Account", pane };
  }

  private profile(prefs: Preferences, account: Account): Built {
    const pane = el("div");
    pane.append(
      this.group(
        [
          this.inputRow("first name", prefs.first_name ?? "", "first", "text", (v) =>
            void this.write({ first_name: v }),
          ),
          this.inputRow("last name", prefs.last_name ?? "", "last", "text", (v) =>
            void this.write({ last_name: v }),
          ),
          this.inputRow(
            "birthdate",
            prefs.birthdate ?? "",
            "yyyy-mm-dd",
            "date",
            (v) => void this.write({ birthdate: v || null }),
          ),
        ],
        "You",
      ),
      el("div", "sn-hint", "Your birthdate anchors your own line on the picture."),
      this.group(
        [
          this.valueRow("email", account.email),
          this.valueRow("sign in", account.sign_in_method),
        ],
        "Email and login",
      ),
    );
    return { title: "Profile", pane };
  }

  private coach(prefs: Preferences): Built {
    const pane = el("div");
    pane.append(
      this.group([
        this.switchRow(
          "Speak replies",
          prefs.speak,
          (on) => void this.write({ speak: on }),
        ),
        this.segRow(
          "replies in",
          [Mode.Text, Mode.Voice],
          prefs.mode,
          (mode) => void this.write({ mode }),
        ),
        this.segRow(
          "messages first",
          [Proactive.Never, Proactive.Rarely, Proactive.Weekly],
          prefs.proactive,
          (proactive) => void this.write({ proactive }),
        ),
      ]),
      el(
        "div",
        "sn-hint",
        "The coach never messages first unless you ask it to.",
      ),
    );
    return { title: "Coach", pane };
  }

  private appearance(prefs: Preferences): Built {
    const pane = el("div");
    pane.append(
      this.group([
        this.segRow(
          "theme",
          [Theme.System, Theme.Light, Theme.Dark],
          prefs.theme,
          (theme) => void this.write({ theme }),
        ),
      ]),
    );
    return { title: "Appearance", pane };
  }

  private diagrams(account: Account): Built {
    const pane = el("div");
    const box = el("div", "sn-grp");
    const now = new Date();
    for (const diagram of account.diagrams) {
      const row = el("div", `sn-row${diagram.free ? " cur" : ""}`);
      row.dataset.name = diagram.name.toLowerCase();
      const main = el("div", "sn-m");
      main.append(
        el("div", "sn-t", esc(diagram.name)),
        el("div", "sn-s", esc(diagramSub(diagram, now))),
      );
      row.append(main, el("span", "sn-tick", diagram.free ? "✓" : ""));
      box.append(row);
    }

    if (account.diagrams.length >= SEARCH_AT) {
      const wrap = el("div", "sn-srch");
      const field = document.createElement("input");
      field.type = "search";
      field.placeholder = "Search diagrams";
      field.setAttribute("aria-label", "Search diagrams");
      field.addEventListener("input", () => {
        const query = field.value.trim().toLowerCase();
        for (const row of [...box.children] as HTMLElement[])
          row.hidden = !!query && !row.dataset.name?.includes(query);
      });
      wrap.append(field);
      pane.append(wrap, box);
    } else {
      pane.append(
        box,
        el(
          "div",
          "sn-hint",
          account.diagrams.length
            ? "One family, one record — it grows as you talk."
            : "No diagrams yet.",
        ),
      );
    }
    return { title: "Your diagrams", pane };
  }

  private plan(account: Account): Built {
    const pane = el("div");
    const plan = el("div", "sn-plan");
    plan.append(
      el("span", "sn-badge", "beta"),
      el("div", "sn-price", esc(account.plan)),
    );
    const manage = document.createElement("button");
    manage.type = "button";
    manage.className = "sn-manage";
    manage.textContent = "Manage plan";
    manage.addEventListener("click", () => toast("pricing lands before launch"));
    plan.append(manage);
    const planBox = el("div", "sn-grp");
    planBox.append(plan);

    const licenceBox = el("div", "sn-grp");
    if (!account.licenses.length)
      licenceBox.append(el("div", "sn-hint", "No licenses on this account."));
    for (const licence of account.licenses) {
      const row = el("div", "sn-row");
      const main = el("div", "sn-m");
      main.append(
        el("div", "sn-t", esc(licence.policy)),
        el("div", "sn-s", esc(licence.status)),
      );
      row.append(
        main,
        el(
          "span",
          `sn-chip ${licence.status === "active" ? "on" : "off"}`,
          esc(licence.status),
        ),
      );
      licenceBox.append(row);
    }

    pane.append(
      el("div", "sn-hd", "Plan"),
      planBox,
      el("div", "sn-hd", "Licenses"),
      licenceBox,
    );
    return { title: "Plan and licenses", pane };
  }
}

/** Signing out is a form post so the server can clear the session cookie. */
function signOut(): void {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "/logout";
  const token = document.createElement("input");
  token.type = "hidden";
  token.name = "csrf_token";
  token.value =
    document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? "";
  form.append(token);
  document.body.append(form);
  form.submit();
}
