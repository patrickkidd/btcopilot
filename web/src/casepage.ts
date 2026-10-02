import {
  basis,
  casePage,
  choiceBox,
  clusterChips,
  dateList,
  faint,
  familyPicture,
  gapLine,
  guessBox,
  level,
  line,
  nameChip,
  pin,
  pins,
  side,
  sublabel,
  wireCase,
  type CaseView,
  type ClusterView,
  type Guess,
  type SidePicture,
  type Still,
} from "./case";
import { chipOf } from "./chips";
import { draw } from "./diagram";
import { esc, slideOver } from "./dom";
import { Drawer } from "./drawer";
import { Lens } from "./lens";
import { Tab } from "./menu";
import { eventDivider, eventRow, fullName, personRow, sections } from "./rows";
import { Strip } from "./strip";
import { BACK } from "./tokens";
import { Feature } from "./track";
import { ChipKind, type Chip, type Person, type Timeline, type TimelineEvent } from "./types";
import { WIDE } from "./viewport";

/** The case page composed, level by level, in the ruled order (Patrick,
 * 2026-10-01), and mounted on the app's own picture region and drawer. The
 * words go where the thread goes; on a wide window the family picture stands in
 * the pinned column beside them, and the timeline either at the top of the
 * screen, where the app keeps it, or at its ruled place among the words. */

export interface PageOpts {
  /** Where things stand now, in facts, above the picture (a trial). */
  outcomeFirst: boolean;
  /** A professional's own reading in a box of its own, named. */
  proBox: boolean;
  /** The viewers' pinned questions under the timeline. */
  pins: boolean;
  /** The picture region's markup at level 5, or null when the line stands at the top of the screen. */
  lineAt5: string | null;
  /** Level 1 among the words, or not (it stands in the pinned column instead). */
  pictureAt1: boolean;
}

export const TITLES: Record<number, (v: CaseView) => string> = {
  1: () => "Who is in the family",
  2: (v) => `What brought ${v.subject.name}`,
  3: () => "The couple since they met",
  4: () => "Each parent's own family",
  5: () => "All of it on one timeline",
  6: () => "The reading, for the therapist",
  7: (v) => `${v.subject.name}'s own part`,
  8: () => "Where there was a choice",
  9: () => "What to work on, what to expect",
  10: () => "The effort",
};

const card = (n: number, v: CaseView, inner: string, cls = "") => level(n, TITLES[n](v), inner, cls);

/** Who may reject a guess: the person themself, or the person a professional presents. */
const rejecter = (v: CaseView) => (v.self ? "yours to reject" : `for ${v.subject.name} to reject`);

/** Facts and guesses in two visibly separate layers: a guess is an amber box
 * that says so, with what it rests on behind the first tap. The basis is the
 * record's own evidence for the guess, never a word match; a guess the record
 * gives no basis says so. A professional's own reading keeps the same shape and
 * the same amber: the label names whose it is. */
export function guess(v: CaseView, g: Guess, whose: string | null, extra = ""): string {
  const label = whose ? `A guess, ${whose}'s, ${rejecter(v)}` : `A guess, ${rejecter(v)}`;
  return guessBox(label, g.text, basis(g.rests.map((r) => nameChip(r))), extra) + g.gaps.map(gapLine).join("");
}

/** The family at rest, as it stands at the record's last date: the app's
 * layout and drawing, and nothing else. */
export function stillSvg(v: CaseView, still: Still): string {
  const L = still.layout;
  if (!L) return "";
  const bonds = L.bonds.map((b) => ({ a: b.a, b: b.b, st: b.st, married: b.married, fresh: false, hot: false }));
  return draw(L, { t: v.now, bonds, marks: [], died: new Set<string>(), moves: [], kin: [], label: still.label });
}

function pictureBox(v: CaseView, still: Still): string {
  if (!still.layout) return gapLine(`The app's layout cannot draw this picture: ${still.fault ?? "unknown"}.`);
  return familyPicture(stillSvg(v, still));
}

/** The ages are at the record's last date, which a closed record names. */
const legendText = (v: CaseView) =>
  "Solid line: a marriage in the record; dashed: no marriage date in the record. One slash: separated; two: divorced. X: died. " +
  `The number is the age ${v.recordEnd.closed ? `at the record's last date (${v.recordEnd.date})` : "now"}, ` +
  "or at death for someone marked X, where a birth date is in the record.";

/** The "?" note goes under the picture that draws the shape, not another. */
const UNKNOWN_NOTE = "?: the other parent is not in the record.";
const legend = (v: CaseView, still: Still) => faint(`${legendText(v)}${still.unknownParent ? ` ${UNKNOWN_NOTE}` : ""}`);

/** Level 1: the person's own family on a picture, their place among brothers
 * and sisters, who else the record holds, and the key to the picture. */
export function level1(v: CaseView): string {
  return card(1, v, pictureBox(v, v.household) + line(v.siblings) + v.householdGaps.map(gapLine).join("") + (v.undrawn ? faint(v.undrawn) : "") + legend(v, v.household));
}

/** What brought the person, with the trouble's course dated: the record's own
 * events of the person that carry a symptom code, each flare-up and each
 * easing, as the ruled order asks (dates at each flare-up); the undated ones
 * as gap lines. */
function level2(v: CaseView): string {
  const course = v.flares.length ? sublabel("The trouble's course, dated") + dateList(v.flares) : gapLine("Dates of each flare-up: not in the record.");
  return card(2, v, line(v.asked) + line(v.whatBrought) + course + v.ownUndated.map(gapLine).join(""));
}

/** The couple since they met: the record's dated events of the two, their
 * children's births, their moves and jobs, and the record's own marks of how
 * each was doing; a gap line for whatever the record does not hold. */
function level3(v: CaseView): string {
  return card(3, v, line(v.couple.text) + (v.couple.rows.length ? dateList(v.couple.rows) : "") + v.couple.gaps.map(gapLine).join(""));
}

const sidePicture = (v: CaseView, p: SidePicture) =>
  (p.sub ? sublabel(p.sub) : "") + pictureBox(v, p.still) + (p.still.unknownParent ? faint(UNKNOWN_NOTE) : "") + (p.kids ? line(p.kids) : "") + p.gaps.map(gapLine).join("");

function level4(v: CaseView): string {
  const sides = v.sides.map((s) => side(s.label, line(s.text) + s.pics.map((p) => sidePicture(v, p)).join("") + s.undated.map(gapLine).join(""))).join("");
  return card(4, v, sides + v.looseUndated.map(gapLine).join(""));
}

/** The chip for a cluster: its years and its title. */
export const clusterRef = (cl: ClusterView) => ({ kind: ChipKind.Cluster as const, id: cl.cluster.id, label: `${cl.cluster.label} · ${cl.title}` });

/** The clusters under the line, each the app's own cluster chip: the tap aims
 * the line at the cluster, as a chip in the thread does. A cluster the app
 * cannot tell, or a step the record does not date, is said under them. */
function clusters(v: CaseView): string {
  const chips = v.clusters.map((cl) => nameChip(clusterRef(cl)));
  const notes = v.clusters.flatMap((cl) => [
    ...cl.undated.map((u) => gapLine(`${cl.cluster.label}: no date in the record for one step, ${u}; the telling leaves it out.`)),
    ...(cl.fault ? [gapLine(`${cl.cluster.label}: the app cannot tell this cluster: ${cl.fault}.`)] : []),
  ]);
  return clusterChips(chips) + notes.join("");
}

const pinned = (v: CaseView) => pins(v.pins.map((p) => pin(nameChip(p.to), p.text)));

/** Level 5: the line itself, unless it stands at the top of the screen; the
 * clusters as chips; the viewers' pins; what the record does not hold. */
function level5(v: CaseView, lineAt5: string | null, withPins: boolean): string {
  return card(
    5,
    v,
    (lineAt5 ?? "") +
      (v.stacked.length ? faint(v.stacked.join(" ")) : "") +
      clusters(v) +
      (withPins ? pinned(v) : "") +
      (v.notHeld.length ? `<div class="notheld">${sublabel("Not in the record")}<ul>${v.notHeld.map((u) => `<li>${esc(u)}</li>`).join("")}</ul></div>` : ""),
  );
}

/** The reading: the coach's as a guess, or on a professional's page the
 * professional's own, labelled with the name, the same two layers. A reading
 * the page's one rule leaves out whole is said as a note, with no box and no
 * basis: there is no guess on the page to rest on anything. */
function level6(v: CaseView, whose: string | null): string {
  if (!v.reading.text.trim()) return card(6, v, gapLine(`${v.presenter}'s reading: left off this page; every sentence of it says what produces what.`));
  const note = whose ? gapLine("The coach's reading: not in this record. The coach has not read this case.") : "";
  return card(6, v, note + guess(v, v.reading, whose));
}

function level7(v: CaseView, whose: string | null): string {
  return card(7, v, guess(v, v.ownPart, whose));
}

/** Where there was a choice: one dated step of the person's own, whose words it
 * is in, the facts under it, and a question on the step where the record holds
 * one, as a guess; else the gap. */
function level8(v: CaseView, whose: string | null): string {
  const c = v.choice;
  const when = c.event ? nameChip({ kind: ChipKind.Event, id: c.event, label: c.date }) : `<span class="d">${esc(c.date)}</span>`;
  const question = c.question
    ? guessBox(whose ? `A question, ${whose}'s, ${rejecter(v)}` : `A question, ${rejecter(v)}`, c.question, basis([]))
    : gapLine("A question on this step: not in the record.");
  return card(8, v, choiceBox({ when, step: c.step, part: c.part, facts: c.facts, question }));
}

function level9(v: CaseView, whose: string | null): string {
  return card(9, v, guess(v, v.workOn, whose) + gapLine("What to expect: not in the record."));
}

function level10(v: CaseView, whose: string | null): string {
  const e = v.effort;
  return card(10, v, (e.guess ? guess(v, e.guess, whose) : line(e.text)) + e.gaps.map(gapLine).join(""));
}

/** Where things stand now, in facts: the record's last dated events. */
const outcome = (v: CaseView) => level(0, "Where things stand now: the record's last dated events", dateList(v.outcome), "now");

const header = (v: CaseView) => (v.header ? `<p class="header-note">${esc(v.header)}</p>` : "");
const account = (v: CaseView) => `<p class="account">${esc(v.account)}</p>`;

/** The words of the page in the ruled order, one to ten, for the thread's
 * place. On a professional's page with the box, every guess in the
 * professional's words is labelled with the name (a page a professional
 * presents must name whose guess the reading is). */
export function words(v: CaseView, o: PageOpts): string {
  const whose = o.proBox ? v.pro : null;
  return casePage(
    header(v) +
      (o.outcomeFirst ? outcome(v) : "") +
      (o.pictureAt1 ? level1(v) : "") +
      level2(v) +
      level3(v) +
      level4(v) +
      level5(v, o.lineAt5, o.pins) +
      level6(v, whose) +
      level7(v, whose) +
      level8(v, whose) +
      level9(v, whose) +
      level10(v, whose) +
      account(v),
  );
}

/** Level 1 alone, for the pinned column beside the words. */
export const column = (v: CaseView): string => casePage(level1(v));

/** The state a page is opened in. */
export interface PageState {
  cluster?: string;
  step?: number;
  speak?: boolean;
  /** The level whose guess box is open on what it rests on. */
  rests?: number;
}

/** The list screen's three tabs as the app's Menu (menu.ts) dresses them: the
 * search's words, the add button's words, and the feature counted. The
 * questions are the coach's, so that tab has neither. A copy of the Menu's
 * own table, kept here until the chat screen's files are refactored with a
 * real walk (2026-10-02). */
const TABS: [string, Tab, string | null, string | null, Feature][] = [
  ["tab-events", Tab.Events, "Search events", "+ Add event", Feature.TabEvents],
  ["tab-people", Tab.People, "Search people", "+ Add someone", Feature.TabPeople],
  ["tab-questions", Tab.Questions, null, null, Feature.TabQuestions],
];

/** Who is ordered by when they were born, and people the record has no birth
 * for come after everyone it does (menu.ts byBirth). */
function byBirth(a: Person, b: Person): number {
  if (!a.birth && !b.birth) return 0;
  if (!a.birth) return 1;
  if (!b.birth) return -1;
  return a.birth.localeCompare(b.birth);
}

const byName = (a: Person, b: Person) => a.name.localeCompare(b.name);

/** Every word of the search somewhere in the event's line, its person or the
 * people it was toward (menu.ts Menu.matches). */
function matches(event: TimelineEvent, names: Map<number, string>, query: string): boolean {
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const targets = [...event.relationshipTargets, ...event.relationshipTriangles].map((id) => names.get(id) ?? "");
  const hay = [event.label, event.person_name, ...targets].join(" ").toLowerCase();
  return words.every((word) => hay.includes(word));
}

/** The events list as the app's Menu renders it: the rows that match the
 * search, divided by cluster; or the one line that says why there are none. */
function eventList(data: Timeline, query: string): string {
  const names = new Map(data.people.map((p) => [p.id, p.name]));
  const shown = data.events.filter((event) => matches(event, names, query));
  const clusterOf = (id: number) => data.clusters.find((c) => c.event_ids.includes(id));
  let html = "";
  for (const { group, events } of sections(shown, clusterOf)) {
    html += eventDivider(group);
    for (const event of events) html += eventRow(event, names, data, false);
  }
  if (!shown.length) html = `<div class="none">${data.events.length ? "Nothing matches that search." : "Nothing on your timeline yet."}</div>`;
  return html;
}

/** The people list as the app's Menu renders it: by birth until the reader
 * asks for names, with the line above it that says which and offers the
 * other; or the one line that says why there are none. */
function peopleList(data: Timeline, query: string, byNames: boolean): string {
  const words = query.trim().toLowerCase();
  const shown = data.people.filter((person) => fullName(person).toLowerCase().includes(words)).sort(byNames ? byName : byBirth);
  let html = `<div class="div"><span>${byNames ? "by name" : "by birth"}</span><span class="dcount" data-order="1" role="button" tabindex="0">${
    byNames ? "order by birth" : "order by name"
  }</span></div>`;
  for (const person of shown) html += personRow(person, false);
  if (!shown.length) html = `<div class="none">${data.people.length ? "Nobody matches that search." : "Nobody on your record yet."}</div>`;
  return html;
}

/** The lists behind the row's list glyph: the app's own list screen
 * (index.html) with the app's tab table and rows (rows.ts), read only. The
 * events in their clusters and the people by birth, each searched as the app
 * searches them. A row leads to the editor in the app and nowhere here. The
 * add button and the questions tab are the editor's and the coach's, which a
 * presented page has not: both are drawn as the app draws them and disabled,
 * until Patrick rules on a presented page's list. */
class ReadList {
  private tab = Tab.Events;
  private query = "";
  /** The people list is ordered by birth until the reader asks for names. */
  private byName = false;
  private readonly body: HTMLElement;
  private readonly field: HTMLInputElement;
  private readonly tabs: HTMLButtonElement[];
  private readonly add: HTMLButtonElement;

  constructor(
    private readonly screen: HTMLElement,
    private readonly tl: Timeline,
    title: string,
  ) {
    const q = <T extends HTMLElement>(sel: string): T => {
      const found = screen.querySelector<T>(sel);
      if (!found) throw new Error(`the list screen has no ${sel}`);
      return found;
    };
    q(".ovt").textContent = title;
    q(".ovbar .backbtn").addEventListener("click", () => this.close());
    this.tabs = [...screen.querySelectorAll<HTMLButtonElement>(".tabs .tab")];
    if (this.tabs.length !== TABS.length) throw new Error("the list screen's tabs are not the app's three");
    this.add = q<HTMLButtonElement>(".foot .addbtn");
    this.add.disabled = true;
    this.add.setAttribute("aria-disabled", "true");
    TABS.forEach(([, tab, placeholder], i) => {
      const button = this.tabs[i];
      if (placeholder === null) {
        button.disabled = true;
        button.setAttribute("aria-disabled", "true");
      } else button.addEventListener("click", () => this.show(tab));
    });
    this.field = q<HTMLInputElement>(".search input");
    this.field.addEventListener("input", () => {
      this.query = this.field.value;
      this.render();
    });
    this.body = q(".scroller");
  }

  /** Up over the page, on the events, as the glyph opens it. */
  open(): void {
    this.show(Tab.Events);
    slideOver(this.screen, true);
  }

  close(): void {
    this.field.value = "";
    this.query = "";
    slideOver(this.screen, false);
  }

  /** One of the two lists, fresh: no search; the search and the add button
   * say which list they are for, as the app dresses them (main.ts onTab). */
  private show(tab: Tab): void {
    this.tab = tab;
    this.query = "";
    this.field.value = "";
    const [, , placeholder, add] = TABS.find(([, which]) => which === tab)!;
    if (placeholder) {
      this.field.placeholder = placeholder;
      this.field.setAttribute("aria-label", placeholder);
    }
    if (add) this.add.textContent = add;
    this.tabs.forEach((t, i) => {
      const on = TABS[i][1] === tab;
      t.classList.toggle("on", on);
      t.setAttribute("aria-selected", String(on));
    });
    this.body.scrollTop = 0;
    this.render();
  }

  private render(): void {
    this.body.innerHTML = this.tab === Tab.People ? peopleList(this.tl, this.query, this.byName) : eventList(this.tl, this.query);
    this.body.querySelector("[data-order]")?.addEventListener("click", () => {
      this.byName = !this.byName;
      this.render();
    });
  }
}

/** What the message box says on a presented page (Patrick, 2026-10-01: a reply
 * box that posts to the coach is wrong). */
const NOTHING_POSTS = "Nothing here posts to the coach";

/** A case page mounted on the app's own frame: the Lens on the picture region
 * (the line, the row under it, the path, the (i)), the Drawer for the telling,
 * the Strip above the speak row, the list screen behind the row's list glyph,
 * and the page's own chips. What the app does with a tap that leads somewhere a
 * read-only page has not (the editor, the thread, the coach) is left undone. */
export class CasePage {
  readonly lens: Lens | null = null;
  readonly drawer: Drawer | null = null;
  readonly list: ReadList | null = null;

  constructor(
    readonly root: HTMLElement,
    readonly view: CaseView,
  ) {
    const q = (sel: string) => root.querySelector<HTMLElement>(sel);
    // the one back arrow every screen draws (R-0223), as the chat screen puts it in
    root.querySelectorAll<HTMLElement>(".backbtn").forEach((b) => (b.innerHTML = BACK));
    const listScreen = q(".screen.slideover");
    if (listScreen) this.list = new ReadList(listScreen, view.tl, view.title);
    // the message box as the app draws it, with nothing behind it: the words
    // cannot be typed into, the send button is dead, and the sessions glyph
    // is hidden as it is for a reader with no work in the sheet (main.ts)
    const inbar = q(".inbar");
    if (inbar) {
      const composer = inbar.querySelector<HTMLElement>("[contenteditable]");
      if (composer) {
        composer.setAttribute("contenteditable", "false");
        composer.dataset.ph = NOTHING_POSTS;
        composer.setAttribute("aria-label", NOTHING_POSTS);
      }
      const send = inbar.querySelector<HTMLButtonElement>(".send");
      if (send) {
        send.disabled = true;
        send.setAttribute("aria-disabled", "true");
      }
      const door = inbar.querySelector<HTMLElement>(".fs-glyph");
      if (door) door.hidden = true;
    }
    const wide = window.matchMedia(WIDE);
    const hosts = { view: q(".pic .view"), caption: q(".pic .caption"), path: q(".pic .path"), info: q(".pic .pl-btn") };
    if (hosts.view && hosts.caption && hosts.path && hosts.info) {
      const list = this.list;
      this.lens = new Lens(
        { view: hosts.view, caption: hosts.caption, path: hosts.path, info: hosts.info },
        {
          timeline: () => view.tl,
          // a read-only page records no taps, and no feature is counted
          record: () => {},
          track: () => {},
          // no editor, no thread to trace to, no message box
          edit: () => {},
          trace: () => null,
          insert: () => {},
          explain: (id) => this.explain(id),
          // the list glyph where the app draws it: not on the wide layout (R-0352)
          list: list ? { shown: () => !wide.matches, open: () => list.open() } : null,
        },
      );
      this.lens.picture.setData(view.tl);
    }
    const host = q("[data-pbp]");
    if (host && this.lens) {
      const lens = this.lens;
      // the drawer's path goes back to that step of the picture, as the chat
      // screen's does (main.ts): the whole timeline, or the case's cluster opened
      this.drawer = new Drawer(
        host,
        (step, events) => {
          this.drawer!.close();
          if (step) lens.picture.open(events);
          else lens.picture.back(0);
          lens.rest();
        },
        (chip) => this.chip(chip),
      );
    }
    const speak = q(".speakrow");
    if (speak) new Strip(speak);
    wireCase(root, (chip) => this.chip(chipOf(chip)));
    this.lens?.actions();
  }

  private clusterOf(id: string): ClusterView | null {
    return this.view.clusters.find((c) => c.cluster.id === id) ?? null;
  }

  /** A chip tapped on the page or in the drawer does what a chip does in the
   * app (main.ts chipTap): it aims the picture, and nothing else. The second
   * tap of the tap language is the row's own chip, explain. */
  private chip(chip: Chip): void {
    this.lens?.aim(chip);
  }

  /** The cluster's told case in the drawer, in place of the coach's reply; the
   * row is back to what the cluster offers. */
  private explain(clusterId: string): void {
    const cl = this.clusterOf(clusterId);
    if (cl && !cl.fault && this.drawer) this.drawer.open(this.view.tl, cl.told, null);
    this.lens?.rest();
  }

  /** The state the page is opened in. */
  start(state: PageState): void {
    if (state.rests) this.root.querySelector(`[data-level="${state.rests}"] .guessbox`)?.classList.add("open");
    if (!state.cluster || !this.lens) return;
    const cl = this.clusterOf(state.cluster);
    if (!cl) return;
    this.lens.picture.open(cl.cluster.event_ids);
    this.lens.rest();
    if (state.speak || state.step !== undefined) {
      this.explain(cl.cluster.id);
      if (state.step) this.drawer?.to(state.step);
    }
  }
}
