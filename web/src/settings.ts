import * as api from "./api";
import { Feature, tap } from "./track";
import { $, el, esc, isAdmin, isCoder } from "./dom";
import { INDEX_URL } from "./concepts";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import { identify } from "./telemetry";
import { shortDate } from "./when";
import { addPasskey, available, deviceWords } from "./passkey";
import { subscribe } from "./push";
import { PRO, RECORD, RECORDS, Records } from "./pro";
import {
  Mode,
  Proactive,
  Theme,
  type Account,
  type Delivery,
  type Diagram,
  type Passkey,
  type Preferences,
} from "./types";

/** The app-level view: an iOS-Settings list where every row pushes its own full
 * page with a back chevron in the title row (`settings-nested`, the owner's
 * pick). Every value here has exactly one home; the speak-replies row on the
 * chat view is the one named shortcut, and it writes this same value. */

const PANE_MS = 240;
/** How often the coach may message first is a most, never a schedule: the
 * choices say so, and the hint says what makes it write. */
const PROACTIVE_CHOICE: Record<Proactive, string> = {
  [Proactive.Never]: "never",
  [Proactive.Rarely]: "at most monthly",
  [Proactive.Weekly]: "at most weekly",
};
const writesFirst = (often: string) =>
  `Never more than once a ${often}, and only when the coach notices a pattern in your family's events or follows up on something you agreed to.`;
const PROACTIVE_HINT: Record<Proactive, string> = {
  [Proactive.Never]: "The coach never messages first unless you ask it to.",
  [Proactive.Rarely]: writesFirst("month"),
  [Proactive.Weekly]: writesFirst("week"),
};
const SEARCH_AT = 6;

const SILHOUETTE =
  `<svg viewBox="0 0 22 22" width="24" height="24" aria-hidden="true">` +
  `<circle cx="11" cy="7.5" r="4" fill="currentColor"/>` +
  `<path d="M3 20c0-4.4 3.6-7 8-7s8 2.6 8 7z" fill="currentColor"/></svg>`;

export enum Page {
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
  /** Which family the app is on. `switched` is false when this is simply the
   * family it opened on, and true when the reader moved it. */
  onDiagram(diagram: Diagram, how: { switched: boolean }): void;
  /** The coder's one task (R-0265). */
  onTask(): void;
  /** The agenda, which is Patrick's whole administration (R-0259). */
  onAgenda(): void;
  /** Two replies to the same words, picked blind (R-0599). */
  onPairs(): void;
  /** Every notice sent to this person, newest first (R-0611). */
  notices(): Delivery[];
  /** A notice tapped in the list: counted opened, then where it points. */
  onNotice(one: Delivery): void;
}

/** A stored user agent is unreadable, so the row names the phone it came from. */
function deviceLabel(userAgent: string): string {
  for (const [pattern, name] of [
    [/iphone/i, "iPhone"],
    [/ipad/i, "iPad"],
    [/macintosh|mac os/i, "Mac"],
    [/android/i, "Android phone"],
    [/windows/i, "Windows PC"],
  ] as [RegExp, string][])
    if (pattern.test(userAgent)) return name;
  return "This device";
}

/** What a diagram row says under its name: how many sessions sit on it, when
 * that last happened, and whether it is the one in use. */
function diagramSub(diagram: Diagram, now: Date): string {
  const count = `${diagram.session_count} session${diagram.session_count === 1 ? "" : "s"}`;
  const when = diagram.last_activity
    ? shortDate(new Date(diagram.last_activity), now)
    : "nothing on it yet";
  return `${count} · ${when}${diagram.current ? " · in use" : ""}`;
}

/** Asked for inside the tap that lets the coach message first. A browser that
 * cannot be reached by push gets email instead, and the reader is told so. */
async function offerPush(): Promise<void> {
  if (!(await subscribe())) toast("The coach will email you instead");
}

export class Settings {
  private stack: { page: Page; title: string; pane: HTMLElement }[] = [];
  private open = false;
  private prefs: Preferences | null = null;
  private account: Account | null = null;
  private passkeys: Passkey[] = [];
  private canPasskey = false;
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
    this.avatar.addEventListener("click", () => {
      tap(Feature.OpenSettings);
      void this.raise();
    });
    this.back.addEventListener("click", () => this.pop());
  }

  /** The avatar carries the initial of whatever name the account has. */
  async load(): Promise<void> {
    [this.prefs, this.account, this.passkeys, this.canPasskey] = await Promise.all([
      api.preferences(),
      api.account(),
      api.passkeys().catch(() => []),
      available(),
    ]);
    identify(this.account.email);
    this.mark();
    this.applyTheme();
    this.handlers.onPrefs(this.prefs);
    // The title row names the family the app is on, not a stock phrase.
    const here = this.account?.diagrams.find((d) => d.current);
    if (here) this.handlers.onDiagram(here, { switched: false });
    if (this.open) this.replaceTop();
  }

  /** Write one preference from somewhere other than a settings page — the
   * speak-replies shortcut on the chat view is the one ruled case. */
  async set(body: Partial<Preferences>): Promise<void> {
    await this.write(body);
  }

  /** The disc behind the mark is a positioned pseudo-element, so a bare text
   * node would paint under it; the initial goes in its own element. */
  private mark(): void {
    const initial = this.initial();
    this.avatar.innerHTML = initial ? `<span>${initial}</span>` : SILHOUETTE;
  }

  private initial(): string {
    const name = `${this.prefs?.first_name ?? ""}${this.prefs?.last_name ?? ""}`;
    return name.trim().charAt(0).toUpperCase();
  }

  /** The account view at one of its pages, which is where a notice points:
   * opened on it, or drawn again where it stands with what just changed. */
  async show(page: Page): Promise<void> {
    if (this.open) this.replaceTop();
    else await this.raise();
    if (page !== Page.Root && this.stack.at(-1)?.page !== page) this.push(page);
  }

  private async raise(): Promise<void> {
    if (this.open) return;
    // The account is already in hand from the load at start-up, so the view
    // opens on the tap rather than after two round trips. What comes back
    // redraws the page where it stands.
    const first = !this.account;
    if (first) await this.load();
    this.open = true;
    this.host.hidden = false;
    this.stack = [];
    this.push(Page.Root);
    // ...and the fresh account arrives after the page has landed: redrawing it
    // mid-slide replaces the pane that is moving and the slide stops dead.
    if (!first) window.setTimeout(() => void this.load(), PANE_MS);
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

  close(): void {
    if (!this.open) return;
    this.open = false;
    this.back.hidden = true;
    this.handlers.onTitle(null);
    const panes = this.stack.map((entry) => entry.pane);
    this.stack = [];
    // every page leaves to the right, the one underneath included, so what
    // was on screen is uncovered rather than revealed behind a page parked
    // off to the left
    for (const pane of panes) pane.classList.remove("in", "under");
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
    this.mark();
    this.applyTheme();
    this.handlers.onPrefs(this.prefs);
    // The title row names the family the app is on, not a stock phrase.
    const here = this.account?.diagrams.find((d) => d.current);
    if (here) this.handlers.onDiagram(here, { switched: false });
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
    return this.tapRow(label, value, () => this.push(page));
  }

  /** A row that leaves the account view for a screen of its own. */
  private screenRow(label: string, feature: Feature, go: () => void): HTMLElement {
    return this.tapRow(label, "", () => {
      tap(feature);
      this.close();
      go();
    });
  }

  private tapRow(label: string, value: string, go: () => void): HTMLElement {
    const row = el("div", "sn-row push");
    row.append(
      el("div", "sn-lbl", esc(label)),
      el("div", "sn-val", esc(value)),
      el("div", "sn-chev", "›"),
    );
    row.addEventListener("click", go);
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
    words: (value: T) => string = (value) => value,
  ): HTMLElement {
    const row = el("div", "sn-row");
    const seg = el("div", "sn-seg");
    for (const option of options) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = option === current ? "on" : "";
      button.textContent = words(option);
      button.addEventListener("click", () => {
        tap(Feature.SettingChange);
        pick(option);
      });
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
    button.addEventListener("click", () => {
      tap(Feature.SettingChange);
      set(!on);
    });
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

    const notices = this.handlers.notices();
    if (notices.length)
      pane.append(this.group(notices.map((one) => this.noticeRow(one)), "Notices"));

    pane.append(
      this.group([
        this.pushRow("Coach", `speak ${prefs.speak ? "on" : "off"}`, Page.Coach),
        this.pushRow("Appearance", prefs.theme, Page.Appearance),
      ]),
      this.group([
        this.pushRow(
          PRO ? Records : "Your diagrams",
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

    // Coding and its meeting are for coders, and the meeting and the replies
    // picked blind are Patrick's; none of it hangs on the family the app is
    // on. The concept pages open in a tab of their own (R-0567).
    const admin = isAdmin();
    if (isCoder())
      pane.append(
        this.group(
          [
            this.screenRow("Your coding task", Feature.TaskOpen, () => this.handlers.onTask()),
            ...(admin
              ? [this.screenRow("Next meeting", Feature.AgendaOpen, () => this.handlers.onAgenda())]
              : []),
            this.tapRow("Concept pages", "", () =>
              window.open(INDEX_URL, "_blank", "noopener"),
            ),
          ],
          "Coding",
        ),
      );
    if (admin)
      pane.append(
        this.group(
          [this.screenRow("Better reply", Feature.PairsOpen, () => this.handlers.onPairs())],
          "Quality",
        ),
        el("div", "sn-hint", "Pick the better of two coach replies"),
      );

    const out = document.createElement("button");
    out.type = "button";
    out.className = "sn-out";
    out.textContent = "Sign out";
    out.addEventListener("click", () => {
      tap(Feature.SignOut);
      void signOut(account.email);
    });
    const last = el("div", "sn-grp");
    last.append(out);
    pane.append(last, el("div", "sn-foot", "Family Diagram · beta"));
    return { title: "Account", pane };
  }

  /** A notice: unread ones carry the account button's mark, and a tap opens
   * where it points, or only counts it read when it points nowhere. */
  private noticeRow(one: Delivery): HTMLElement {
    const unread = one.opened_at === null;
    const row = el("div", `sn-row${one.link || unread ? " push" : ""}`);
    if (unread) row.append(el("span", "sn-unread"));
    const main = el("div", "sn-m");
    const when = shortDate(new Date(one.created_at), new Date());
    main.append(
      el("div", "sn-t", esc(one.title)),
      el("div", "sn-s", esc(`${when} · ${one.body}`)),
    );
    row.append(main);
    if (one.link) row.append(el("div", "sn-chev", "›"));
    if (one.link || unread)
      row.addEventListener("click", () => this.handlers.onNotice(one));
    return row;
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
      this.group(this.passkeyRows(), "This device"),
    );
    return { title: "Profile", pane };
  }

  /** The keys that sign this account in without an emailed code, and the way to
   * make one when there are none. */
  private passkeyRows(): HTMLElement[] {
    const rows = this.passkeys.map((passkey) => {
      const row = el("div", "sn-row");
      const main = el("div", "sn-m");
      main.append(
        el("div", "sn-t", esc(deviceLabel(passkey.name))),
        el(
          "div",
          "sn-s",
          esc(
            passkey.last_used_at
              ? `last used ${shortDate(new Date(passkey.last_used_at), new Date())}`
              : "not used yet",
          ),
        ),
      );
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "sn-manage";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        tap(Feature.PasskeyRemove);
        void this.dropPasskey(passkey);
      });
      row.append(main, remove);
      return row;
    });
    if (!this.passkeys.length && this.canPasskey) {
      const row = el("div", "sn-row push");
      row.append(el("div", "sn-lbl", esc(`Set up ${deviceWords()}`)), el("div", "sn-chev", "\u203a"));
      row.addEventListener("click", () => {
        tap(Feature.PasskeyAdd);
        void this.makePasskey();
      });
      rows.push(row);
    }
    if (!rows.length) rows.push(el("div", "sn-hint", "This device signs in by email."));
    return rows;
  }

  private async makePasskey(): Promise<void> {
    try {
      await addPasskey();
    } catch {
      toast("That did not work");
      return;
    }
    await this.load();
  }

  private async dropPasskey(passkey: Passkey): Promise<void> {
    await api.revokePasskey(passkey.id);
    await this.load();
  }

  private coach(prefs: Preferences): Built {
    const pane = el("div");
    const often = this.segRow(
      "messages first",
      [Proactive.Never, Proactive.Rarely, Proactive.Weekly],
      prefs.proactive,
      (proactive) => {
        if (proactive !== Proactive.Never) void offerPush();
        void this.write({ proactive });
      },
      (proactive) => PROACTIVE_CHOICE[proactive],
    );
    // the choices are too long to stand beside their label on a phone
    often.classList.add("below");
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
        often,
      ]),
      el("div", "sn-hint", PROACTIVE_HINT[prefs.proactive]),
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
      const row = el("div", `sn-row push${diagram.current ? " cur" : ""}`);
      row.dataset.name = diagram.name.toLowerCase();
      const main = el("div", "sn-m");
      main.append(
        el("div", "sn-t", esc(diagram.name)),
        el("div", "sn-s", esc(diagramSub(diagram, now))),
      );
      row.append(main, el("span", "sn-tick", diagram.current ? "✓" : ""));
      if (!diagram.current)
        row.addEventListener("click", () => {
          tap(Feature.FamilySwitch);
          void this.switchTo(diagram);
        });
      box.append(row);
    }

    if (PRO) box.append(this.newCaseRow());

    if (account.diagrams.length >= SEARCH_AT) {
      const wrap = el("div", "sn-srch");
      const field = document.createElement("input");
      field.type = "search";
      field.placeholder = `Search ${RECORDS}`;
      field.setAttribute("aria-label", `Search ${RECORDS}`);
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
          PRO
            ? "Each case has its own sessions and its own picture."
            : account.diagrams.length
              ? "One family, one record — it grows as you talk."
              : "No diagrams yet.",
        ),
      );
    }
    return { title: PRO ? Records : "Your diagrams", pane };
  }

  /** A new case: an empty record the app is put on straight away, so the title
   * row names it before anything is said into it (R-0243). */
  private newCaseRow(): HTMLElement {
    const row = el("div", "sn-row push");
    const label = el("div", "sn-lbl", `+ new ${RECORD}`);
    row.append(label, el("div", "sn-chev", "\u203a"));
    row.addEventListener("click", () => {
      if (row.querySelector("input")) return;
      const field = document.createElement("input");
      field.className = "rename";
      field.placeholder = `What is this ${RECORD} called?`;
      label.replaceChildren(field);
      field.focus({ preventScroll: true });
      field.addEventListener("keydown", (e) => {
        const key = (e as KeyboardEvent).key;
        if (key === "Enter") void this.addCase(field.value.trim());
        else if (key === "Escape") label.textContent = `+ new ${RECORD}`;
      });
    });
    return row;
  }

  private async addCase(name: string): Promise<void> {
    if (!name) return;
    const made = await api.newDiagram(name);
    await this.load();
    this.close();
    this.handlers.onDiagram(made, { switched: true });
    toast(`Now on ${made.name}`);
  }

  /** Put the app on another family. Everything the app shows is about one
   * diagram, so the whole surface is re-read afterwards. */
  private async switchTo(diagram: Diagram): Promise<void> {
    await api.selectDiagram(diagram.id);
    await this.load();
    this.close();
    this.handlers.onDiagram(diagram, { switched: true });
    toast(`Now on ${diagram.name}`);
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

/** Signing out clears the session cookie and then covers the shell with the
 * signed-out screen, which is a state of the app rather than leaving it. Sign
 * in goes to the app's own sign-in page. */
async function signOut(who: string): Promise<void> {
  await fetch("/app/logout", {
    method: "POST",
    headers: {
      "X-CSRFToken":
        document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ??
        "",
    },
  });
  $("signedout-who").textContent = `signed out \u2014 ${who}`;
  $("signedout").hidden = false;
  $("signedout-in").addEventListener(
    "click",
    () => (window.location.href = "/app/login"),
    { once: true },
  );
}
