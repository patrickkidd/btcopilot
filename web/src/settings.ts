import * as api from "./api";
import { Feature, tap, type Screen } from "./track";
import { $, el, esc, flash, isAdmin, isCoder, type Title } from "./dom";
import { INDEX_URL } from "./concepts";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import { Sheet } from "./sheet";
import { store } from "./store";
import { identify } from "./telemetry";
import { shortDate } from "./when";
import { markup } from "./markup";
import { addPasskey, available, deviceWords } from "./passkey";
import { IDLE_MS } from "./vote";
import { device, reach, Reach, subscribe } from "./push";
import { PRO, RECORD, RECORDS, Records } from "./pro";
import { address, beyond, NAMES, Place } from "./place";
import {
  BugReports,
  Mode,
  Proactive,
  Theme,
  type Account,
  type Delivery,
  type Diagram,
  type Passkey,
  type Preferences,
  type User,
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
const BUG_REPORTS_CHOICE: Record<BugReports, string> = {
  [BugReports.Ask]: "ask me",
  [BugReports.Always]: "always send",
};
const PROACTIVE_HINT: Record<Proactive, string> = {
  [Proactive.Never]: "The coach never messages first unless you ask it to.",
  [Proactive.Rarely]: writesFirst("month"),
  [Proactive.Weekly]: writesFirst("week"),
};
/** Said before the shadows are switched on, since every turn then costs more
 * (R-0637). */
const SHADOW_WARNING =
  "This runs extra models on every coach reply so you can vote on them. It costs Patrick money. " +
  "Check with Patrick before turning it on, and turn it off when you are done.";
const SHADOW_HINT =
  "Other models also answer each turn, unnamed. Each reply waits a few seconds for them. " +
  "You vote before you can type again.";
const SHADOW_LAPSE = `Turns off ${IDLE_MS / 60_000} minutes after the coach's last reply or your last vote`;
const cents = (usd: number) => `about ${Math.round(usd * 100)}¢ a turn`;
const dollars = (usd: number) => `$${usd.toFixed(2)}`;
const SEARCH_AT = 6;
/** Letters typed before the people search asks the server. */
const FIND_AT = 2;
const GUIDE = NAMES[Place.Literature];

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
  Notices = "notices",
}

/** A screen of the app's own that opens on this stack like one of its pages
 * and leaves by the same back chevron, to whatever it was opened from. */
export interface Sub {
  title: string | Title;
  screen: HTMLElement;
  /** Counted as a screen of its own in the product events. */
  name?: Screen;
  /** The app widens under it, as it does for two replies side by side. */
  wide?: boolean;
  /** Its address while it is on top (R-0055). */
  at?: string;
}

type Pane = Page | Sub;

interface Built {
  title: string | Title;
  pane: HTMLElement;
}

export interface SettingsHandlers {
  /** The title row shows the current pane's title, and the family name again
   * when the stack closes; a screen of the app's own on top comes with it. */
  onTitle(title: string | Title | null, sub?: Sub): void;
  /** Every read or write of the preferences, so a value with a shortcut
   * elsewhere on screen shows the same thing. */
  onPrefs(prefs: Preferences): void;
  /** Open a diagram: the page's one step for that (FD-366). */
  onOpen(id: number): Promise<void>;
  /** The coder's one task (R-0265). */
  onTask(): void;
  /** The agenda, which is Patrick's whole administration (R-0259). */
  onAgenda(): void;
  /** Every notice sent to this person, newest first (R-0613). */
  notices(): Delivery[];
  /** A notice tapped in the list: counted opened, then where it points when
   * there is more to see there. */
  onNotice(one: Delivery): Promise<void>;
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

/** What a diagram row says under its name: how many sessions sit on it, and
 * when that last happened; whether it is the one in use is marked from the
 * store. */
function diagramSub(diagram: Diagram, now: Date): string {
  const count = `${diagram.session_count} session${diagram.session_count === 1 ? "" : "s"}`;
  const when = diagram.last_activity
    ? shortDate(new Date(diagram.last_activity), now)
    : "nothing on it yet";
  return `${count} · ${when}`;
}

/** Every diagram row on the stack ticked from the store, and only the one
 * open: the admin's search results with the rest, whenever they were read,
 * so a stale tick cannot be drawn (FD-366). */
function tick(host: HTMLElement): void {
  const open = store.current().diagram?.id;
  for (const row of host.querySelectorAll<HTMLElement>(".sn-row[data-diagram]")) {
    const on = Number(row.dataset.diagram) === open;
    row.classList.toggle("cur", on);
    row.querySelector(".sn-tick")!.textContent = on ? "✓" : "";
    row.querySelector<HTMLElement>(".sn-use")!.hidden = !on;
  }
}

const REACH: Record<Reach, string> = {
  [Reach.On]: "On on this device",
  [Reach.Off]: "Off on this device",
  [Reach.Blocked]: "Blocked in this device's system settings",
  [Reach.Unavailable]: "Not available here. Open the app from your home screen",
};

/** Asked for inside the tap that lets the coach message first. A browser that
 * cannot be reached by push gets email instead, and the reader is told so. */
async function offerPush(): Promise<void> {
  if (!(await subscribe())) toast("The coach will email you instead");
}

export class Settings {
  private stack: { page: Pane; title: string | Title; pane: HTMLElement }[] = [];
  private open = false;
  private prefs: Preferences | null = null;
  private account: Account | null = null;
  private passkeys: Passkey[] = [];
  private canPasskey = false;
  private reach = Reach.Unavailable;
  private host = el("div", "sn-stack");
  /** The question before the shadows are switched on. */
  private ask: Sheet;
  /** The auditor's coding guide, read on this stack like any page of it. */
  readonly literature: Sub;
  /** The account read again once the view has slid in, which draws its top
   * page again; a light waits for it, so it is not drawn away. */
  private reloaded: Promise<void> = Promise.resolve();

  constructor(
    private avatar: HTMLElement,
    private back: HTMLElement,
    overlay: HTMLElement,
    private handlers: SettingsHandlers,
  ) {
    this.host.hidden = true;
    overlay.append(this.host);
    this.ask = new Sheet(overlay, "sh");
    this.ask.panel.addEventListener("click", (e) => {
      const act = (e.target as Element).closest<HTMLElement>("[data-act]")?.dataset.act;
      if (!act) return;
      this.ask.lower();
      if (act === "on") void this.write({ shadow_models: this.prefs!.shadow_candidates });
    });
    const frame = el("iframe");
    frame.id = "literature";
    frame.title = GUIDE;
    frame.src = INDEX_URL;
    this.literature = { title: GUIDE, screen: frame, at: address(Place.Literature) };
    this.back.hidden = true;
    this.avatar.addEventListener("click", () => {
      tap(Feature.OpenSettings);
      void this.raise();
    });
    this.back.addEventListener("click", () => this.pop());
    store.watch({ reset: () => {}, draw: () => tick(this.host) });
  }

  /** The avatar carries the initial of whatever name the account has. */
  async load(): Promise<void> {
    [this.prefs, this.account, this.passkeys, this.canPasskey, this.reach] = await Promise.all([
      api.preferences(),
      api.account(),
      api.passkeys().catch(() => []),
      available(),
      device().then(reach),
    ]);
    identify(this.account.email);
    this.mark();
    this.applyTheme();
    this.handlers.onPrefs(this.prefs);
    if (this.open) this.replaceTop();
  }

  /** Write one preference from somewhere other than a settings page — the
   * speak-replies shortcut on the chat view is the one ruled case. */
  async set(body: Partial<Preferences>): Promise<void> {
    await this.write(body);
  }

  /** Read the preferences again, which the server changes by itself when the
   * shadows turn themselves off (R-0637). */
  async refresh(): Promise<void> {
    this.took(await api.preferences());
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

  /** The account view with these pushed on its root in order, which is where
   * a notice points and where a screen of the app's own is opened from
   * outside the stack: opened on them, or back at its root, drawn again with
   * what just changed, and on from there. */
  async show(...path: Pane[]): Promise<void> {
    if (this.open) {
      for (const entry of this.stack.splice(1)) entry.pane.remove();
      this.stack[0].pane.classList.remove("under");
      this.replaceTop();
    } else await this.raise();
    for (const page of path) this.push(page);
  }

  /** Down the stack to a screen on it, the way its back chevron goes. */
  popTo(sub: Sub): void {
    while (this.stack.length > 1 && this.stack.at(-1)!.page !== sub) this.pop();
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
    if (!first)
      this.reloaded = new Promise((done) =>
        window.setTimeout(() => void this.load().then(done), PANE_MS),
      );
  }

  /** The page or screen on top, while the view is open. */
  top(): Pane | null {
    return this.open ? (this.stack.at(-1)?.page ?? null) : null;
  }

  /** Light one item on the page on top, the way a message is lit in the
   * thread (R-0055). False when the page has no such item. */
  async light(selector: string): Promise<boolean> {
    await this.reloaded;
    const item = this.stack.at(-1)?.pane.querySelector<HTMLElement>(selector);
    if (item) flash(item);
    return !!item;
  }

  /** A page, or a screen of the app's own, slid in on top. */
  push(page: Pane): void {
    const under = this.stack[this.stack.length - 1];
    const { title, pane } = this.build(page);
    pane.classList.add("sn-pane");
    pane.dataset.page = typeof page === "string" ? page : page.screen.id;
    this.host.append(pane);
    // a screen of the app's own scrolls inside itself
    if (typeof page === "string") dragScroll(pane);
    void pane.offsetWidth;
    pane.classList.add("in");
    if (under) under.pane.classList.add("under");
    this.stack.push({ page, title, pane });
    this.retitle();
    this.back.hidden = false;
  }

  private retitle(): void {
    const { title, page } = this.stack[this.stack.length - 1];
    this.handlers.onTitle(title, typeof page === "string" ? undefined : page);
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
    this.stack[this.stack.length - 1].pane.classList.remove("under");
    this.retitle();
  }

  close(): void {
    if (!this.open) return;
    this.open = false;
    this.finding = undefined;
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
   * without the pane sliding again. A screen of the app's own draws itself. */
  private replaceTop(): void {
    const top = this.stack.at(-1);
    if (!top || typeof top.page !== "string") return;
    this.stack.pop();
    top.pane.remove();
    const { title, pane } = this.build(top.page);
    pane.classList.add("sn-pane", "in");
    pane.dataset.page = top.page;
    this.host.append(pane);
    this.stack.push({ page: top.page, title, pane });
    this.retitle();
  }

  private async write(body: Partial<Preferences>): Promise<void> {
    this.took(await api.setPreferences(body));
  }

  private took(prefs: Preferences): void {
    this.prefs = prefs;
    this.mark();
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
    return this.tapRow(label, value, () => this.push(page));
  }

  /** A row that opens a screen of the app's own on this stack. */
  private screenRow(label: string, feature: Feature, go: () => void): HTMLElement {
    return this.tapRow(label, "", () => {
      tap(feature);
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

  private valueRow(label: string, value: string, ink = true): HTMLElement {
    const row = el("div", "sn-row");
    row.append(
      el("div", "sn-lbl", esc(label)),
      el("div", `sn-val${ink ? " ink" : ""}`, esc(value || "—")),
    );
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

  private build(page: Pane): Built {
    if (typeof page !== "string") {
      const pane = el("div", "host");
      page.screen.hidden = false;
      pane.append(page.screen);
      return { title: page.title, pane };
    }
    const prefs = this.prefs!;
    const account = this.account!;
    if (page === Page.Root) return this.root(prefs, account);
    if (page === Page.Profile) return this.profile(prefs, account);
    if (page === Page.Coach) return this.coach(prefs);
    if (page === Page.Appearance) return this.appearance(prefs);
    if (page === Page.Diagrams) return this.diagrams(account);
    if (page === Page.Notices) return this.notices();
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
    const unread = notices.filter((one) => one.opened_at === null).length;
    if (notices.length)
      pane.append(this.group([this.pushRow("Notices", unread ? String(unread) : "", Page.Notices)]));

    pane.append(
      this.group([
        this.pushRow("Coach", `speak ${prefs.speak ? "on" : "off"}`, Page.Coach),
        this.pushRow("Appearance", prefs.theme, Page.Appearance),
      ]),
      this.group([this.notificationsRow()]),
      this.group([
        this.pushRow(
          PRO ? Records : "Diagrams",
          String(account.diagrams.length),
          Page.Diagrams,
        ),
        this.pushRow(
          "Your Plan",
          `${account.licenses.length} licence${account.licenses.length === 1 ? "" : "s"}`,
          Page.Plan,
        ),
      ], "Data"),
    );

    // Coding and its meeting are for coders, and the meeting is Patrick's;
    // none of it hangs on the family the app is on. Each opens on this stack,
    // the coding guide too (R-0567).
    const admin = isAdmin();
    if (isCoder())
      pane.append(
        this.group(
          [
            this.screenRow("Your coding task", Feature.TaskOpen, () => this.handlers.onTask()),
            ...(admin
              ? [this.screenRow("Next meeting", Feature.AgendaOpen, () => this.handlers.onAgenda())]
              : []),
            this.tapRow(GUIDE, "", () => this.push(this.literature)),
          ],
          "Coding",
        ),
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

  /** Every notice sent to this person, newest first (R-0613). */
  private notices(): Built {
    const pane = el("div");
    const rows = this.handlers.notices().map((one) => this.noticeRow(one));
    pane.append(rows.length ? this.group(rows) : el("div", "sn-hint", "No notices yet."));
    return { title: "Notices", pane };
  }

  /** A notice: unread ones carry the account button's mark, and a tap opens
   * where it points, or only counts it read, in place, when there is nothing
   * more to see there. */
  private noticeRow(one: Delivery): HTMLElement {
    const unread = one.opened_at === null;
    const goes = beyond(one.link) !== null;
    const row = el("div", `sn-row${goes || unread ? " push" : ""}`);
    row.dataset.notice = String(one.id);
    if (unread) row.append(el("span", "sn-unread"));
    const main = el("div", "sn-m");
    const when = shortDate(new Date(one.created_at), new Date());
    main.append(
      el("div", "sn-t", esc(one.title)),
      el("div", "sn-s sn-wrap", `${esc(when)} · ${markup(one.body ?? "")}`),
    );
    row.append(main);
    if (goes) row.append(el("div", "sn-chev", "›"));
    if (goes || unread)
      row.addEventListener("click", (e) => {
        if ((e.target as Element).closest("a")) return;
        void this.handlers.onNotice(one).then(() => {
          if (!goes) this.replaceTop();
        });
      });
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
  /** This device's notifications, for everyone, whatever the coach's
   * "messages first" says (R-0802). */
  private notificationsRow(): HTMLElement {
    const row = el("div", "sn-row");
    row.id = "notifications";
    const main = el("div", "sn-m");
    main.append(el("div", "sn-t", "Notifications"), el("div", "sn-s sn-wrap", esc(REACH[this.reach])));
    row.append(main);
    if (this.reach === Reach.Off) {
      const on = document.createElement("button");
      on.type = "button";
      on.className = "sn-manage";
      on.textContent = "Turn on";
      on.addEventListener("click", () => {
        tap(Feature.NotificationsOn);
        void subscribe().then(() => this.load());
      });
      row.append(on);
    }
    return row;
  }

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
      this.group([
        this.segRow(
          "Bug reports",
          [BugReports.Ask, BugReports.Always],
          prefs.bug_reports,
          (bug_reports) => void this.write({ bug_reports }),
          (choice) => BUG_REPORTS_CHOICE[choice],
        ),
      ]),
    );
    if (isAdmin() || isCoder()) pane.append(...this.shadows(prefs));
    return { title: "Coach", pane };
  }

  /** Other models answer each turn too, for a vote in the chat; staff only,
   * and what it costs only for admins (R-0636, R-0637). */
  private shadows(prefs: Preferences): HTMLElement[] {
    const on = prefs.shadow_models.length > 0;
    const cost = prefs.shadow_cost;
    return [
      this.group(
        [
          this.switchRow("Conversation Feedback", on, (want) =>
            want ? this.confirmShadows() : void this.write({ shadow_models: [] }),
          ),
          ...(cost
            ? [
                this.valueRow("Extra cost", cents(cost.per_turn_usd), false),
                this.valueRow("Spent this month", dollars(cost.month_usd), false),
              ]
            : []),
        ],
        // an auditor has the switch too, but the Admin group is for admins
        isAdmin() ? "Admin" : undefined,
      ),
      ...(on ? [el("div", "sn-hint", esc(SHADOW_LAPSE))] : []),
      el("div", "sn-hint", esc(SHADOW_HINT)),
    ];
  }

  private confirmShadows(): void {
    this.ask.show(
      `<div class="cf-t">Turn on Conversation Feedback?</div>` +
        `<p class="cf-p">${esc(SHADOW_WARNING)}</p>` +
        `<div class="cf-btns">` +
        `<button class="cf-go" type="button" data-act="on">Turn on</button>` +
        `<button class="cf-no" type="button" data-act="cancel">Cancel</button>` +
        `</div>`,
    );
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
    const mine = el("div");
    if (isAdmin()) {
      this.finding ??= this.finder();
      pane.append(this.finding.box);
      mine.append(el("div", "sn-hd", PRO ? Records : "Diagrams"));
      this.finding.mine = mine;
      mine.hidden = this.finding.field.value.trim().length >= FIND_AT;
    }
    pane.append(mine);
    const box = el("div", "sn-grp");
    const now = new Date();
    for (const diagram of account.diagrams) box.append(this.diagramRow(diagram, now));
    tick(box);

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
      mine.append(wrap, box);
    } else {
      mine.append(
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
    return { title: PRO ? Records : "Diagrams", pane };
  }

  /** Kept across a re-draw of the page and under a person's diagrams, so the
   * search and its matches are there again on the way back (R-0630). */
  private finding?: { box: HTMLElement; field: HTMLInputElement; mine?: HTMLElement };

  /** The Diagrams page with the search empty and ready to type in, where
   * Next meeting's "Select a cut for the agenda" lands. */
  seek(): void {
    const finding = this.finding;
    if (!finding) return;
    finding.field.value = "";
    finding.field.dispatchEvent(new Event("input"));
    finding.field.focus({ preventScroll: true });
  }

  private diagramRow(diagram: Diagram, now: Date): HTMLElement {
    const row = el("div", "sn-row push");
    row.dataset.name = diagram.name.toLowerCase();
    row.dataset.diagram = String(diagram.id);
    const main = el("div", "sn-m");
    main.append(
      el("div", "sn-t", esc(diagram.name)),
      el("div", "sn-s", `${esc(diagramSub(diagram, now))}<span class="sn-use"> · in use</span>`),
    );
    row.append(main, el("span", "sn-tick"));
    row.addEventListener("click", () => {
      if (diagram.id !== store.current().diagram?.id) {
        tap(Feature.FamilySwitch);
        return void this.switchTo(diagram);
      }
      this.close();
      void this.handlers.onOpen(diagram.id);
    });
    return row;
  }

  /** An admin finds anyone by name: the admin's own diagrams give way to the
   * people found while there is a name typed (R-0630). */
  private finder(): { box: HTMLElement; field: HTMLInputElement } {
    const box = el("div", "sn-find");
    const wrap = el("div", "sn-srch");
    const field = document.createElement("input");
    field.type = "search";
    field.placeholder = "Find a person";
    field.setAttribute("aria-label", "Find a person");
    wrap.append(field);
    const found = el("div");
    field.addEventListener("input", async () => {
      const words = field.value.trim();
      if (this.finding?.mine) this.finding.mine.hidden = words.length >= FIND_AT;
      if (words.length < FIND_AT) return found.replaceChildren();
      const people = await api.users(words);
      if (field.value.trim() !== words) return;
      const list = el("div", "sn-grp");
      for (const person of people) {
        const row = el("div", "sn-row push");
        row.dataset.user = String(person.id);
        const main = el("div", "sn-m");
        main.append(
          el("div", "sn-t", esc(person.name || person.username)),
          el("div", "sn-s", esc(person.username)),
        );
        row.append(main, el("div", "sn-chev", "\u203a"));
        row.addEventListener("click", () => void this.theirs(person));
        list.append(row);
      }
      found.replaceChildren(
        people.length ? list : el("div", "sn-hint", "No one by that name."),
      );
    });
    box.append(wrap, found);
    return { box, field };
  }

  /** The person tapped, slid in as a page of its own over the search, which
   * waits underneath as it was (R-0630). Their diagrams open read-only. */
  private async theirs(person: User): Promise<void> {
    const diagrams = await api.diagrams(person.id);
    const screen = el("div", "sn-theirs");
    screen.id = `theirs-${person.id}`;
    const box = el("div", "sn-grp");
    const now = new Date();
    for (const diagram of diagrams) box.append(this.diagramRow(diagram, now));
    tick(box);
    screen.append(diagrams.length ? box : el("div", "sn-hint", "No diagrams yet."));
    this.push({
      title: person.name || person.username,
      screen,
      at: address(Place.Theirs, person.id),
    });
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
    this.close();
    await this.handlers.onOpen(made.id);
    void this.load();
    toast(`Now on ${made.name}`);
  }

  /** Put the app on another family. Everything the app shows is about one
   * diagram, so the whole surface is opened afresh; the list's counts are read
   * again after. */
  private async switchTo(diagram: Diagram): Promise<void> {
    this.close();
    await this.handlers.onOpen(diagram.id);
    void this.load();
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
    return { title: "Your Plan", pane };
  }
}

/** Signing out clears the session cookie and then covers the shell with the
 * signed-out screen, which is a state of the app rather than leaving it. Sign
 * in goes to the app's own sign-in page. */
async function signOut(who: string): Promise<void> {
  await fetch("/app/logout", { method: "POST", headers: { "X-CSRFToken": api.csrf() } });
  $("signedout-who").textContent = `signed out \u2014 ${who}`;
  $("signedout").hidden = false;
  $("signedout-in").addEventListener(
    "click",
    () => (window.location.href = "/app/login"),
    { once: true },
  );
}
