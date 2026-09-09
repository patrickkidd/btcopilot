import "./theme.css";
import * as api from "./api";
import { Chat, wait, type PlayTap } from "./chat";
import { Picture, Target, type Tap } from "./picture";
import { Menu, Tab } from "./menu";
import { Sessions, sessionTitle, summaryOf } from "./sessions";
import { Settings } from "./settings";
import { aimedEvents, chips, itemKind } from "./chips";
import { StepKind, steps } from "./turn";
import {
  CHIP_KIND,
  PicEvent,
  REST,
  SelKind,
  reduce,
  type Outcome,
  type PicState,
  type Sel,
} from "./caption";
import { $ } from "./dom";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import { shortDate } from "./when";
import {
  ChipKind,
  ChipTone,
  InteractionKind,
  ItemKind,
  emptyTimeline,
  Role,
  StatementKind,
  type Chip,
  type CodedIn,
  type Diagram,
  type Session,
  type Statement,
  type Cluster,
  type Timeline,
} from "./types";

declare global {
  interface Window {
    BOOTSTRAP: {
      diagram: { id: number; name: string } | null;
      session: { id: number } | null;
      statements: Statement[];
    };
  }
}

enum Screen {
  Chat = "chat",
  Menu = "menu",
}

let timeline: Timeline = emptyTimeline();
let pic: PicState = REST;
let session: number | null = window.BOOTSTRAP.session?.id ?? null;
/** The sessions as the sheet last read them, for naming the one that coded a
 * moment. */
let known: Session[] = [];

/** A tap can only be recorded against a diagram; without one there is nothing to
 * record it on. */
function tapped(
  kind: InteractionKind,
  item: ItemKind,
  id: string | null = null,
): void {
  const diagram = window.BOOTSTRAP.diagram;
  if (diagram) void api.record(diagram.id, kind, item, id);
}

/** How long the thread takes to fade out for the session taking its place, the
 * same 150ms the stylesheet transitions it over. */
const FADE_MS = 150;

const picture = new Picture($("view"), { onTap: (tap: Tap) => onTap(tap) });

/** A tap on the wire steps through the moments under the thumb; a tap on the
 * words picks the one whose row was tapped; a tap on the shelf asks about what
 * has no date. */
function onTap(tap: Tap): void {
  // Empty ground on the picture puts it down: nothing selected, nothing named,
  // the whole line at a glance again.
  if (tap.target === Target.Ground) {
    putDown();
    return;
  }
  if (tap.target === Target.Explain) {
    const cluster = picture.showing();
    if (cluster) void explain(cluster);
    return;
  }
  if (tap.target === Target.Shelf) {
    apply(reduce(pic, PicEvent.Tap, { kind: SelKind.Shelf, id: "shelf" }));
    return;
  }
  // At rest the picture shows the whole line; a tap opens one cluster, which
  // is the one level change the reader makes for themselves.
  if (tap.target === Target.Cluster) {
    const ids = picture.inCluster(tap.index);
    if (ids.length) picture.spotlight(ids);
    pic = REST;
    actions();
    return;
  }
  // A label names one moment: tapping it picks that moment, and where a zone
  // holds several the tap steps to the next of them.
  const selected = picture.selection();
  const chosen =
    tap.target === Target.Zone
      ? picture.next(tap.index, selected)
      : picture.rowAt(tap.x, tap.y);
  // blank ground inside the label band: the same as blank wire
  if (tap.target === Target.Band && chosen === null) {
    putDown();
    return;
  }
  // The words of the moment already picked are the way to where it came from,
  // and which way depends on what the picture is showing. Only the words do
  // this: a dot picks and never travels, and a label naming some other moment
  // picks that one.
  const words = tap.target === Target.Band && chosen === selected && selected !== null;
  // inside one cluster: the moment's own editor
  if (words && picture.opened()) {
    screen(Screen.Menu);
    menu.goTo(Tab.Events, selected as number);
    return;
  }
  // on a line of moments that belong to no cluster: where it was said
  if (words) {
    const trace = codedIn(selected as number);
    if (trace) void traceTo(trace.where);
    return;
  }
  apply(
    reduce(
      pic,
      PicEvent.Tap,
      chosen === null ? undefined : { kind: SelKind.Event, id: String(chosen) },
    ),
  );
}

/** A chip the coach wrote without words of its own says what the record calls
 * it: a person's name, an event's line, a cluster's title. */
function chipLabel(chip: Chip): string {
  if (!chip.bare) return chip.label;
  if (chip.kind === ChipKind.Person)
    return timeline.people.find((p) => String(p.id) === chip.target)?.name ?? chip.label;
  if (chip.kind === ChipKind.Event)
    return timeline.events.find((e) => String(e.id) === chip.target)?.label ?? chip.label;
  return (
    timeline.clusters.find(
      (c) => c.id === chip.target || c.cluster_ids.includes(chip.target),
    )?.title ?? chip.label
  );
}

const chat = new Chat($("chat"), $("composer"), {
  label: chipLabel,
  onChip: (chip, play) => {
    tapped(InteractionKind.ChipTap, itemKind(chip.kind), chip.target);
    // Two kinds of chip, and the colour says which. An amber chip is an offer:
    // it names nothing in the record, so it goes into the message as words. A
    // teal chip is a reference into the record, so it aims the picture.
    if (offered(chip)) chat.insert(chip);
    // A teal chip inside a play-by-play is a step of that walk: it moves the
    // board and never takes the picture back to the wire (owner review 1).
    else if (play) stepBoard(play, chip);
    else aim(chip);
  },
  // A tap on a message's own words is a look: the picture lights what that
  // message named, nothing enters the composer, and no turn is spent.
  onBubble: (text) => {
    const named = aimedFrom(text);
    if (!named.length) return;
    tapped(InteractionKind.Look, ItemKind.Event, String(named[0]));
    picture.spotlight(named);
    pic = REST;
    actions();
  },
});

/** An offer: the coach holding out something to say next, drawn amber. */
const offered = (chip: Chip) =>
  chip.kind === ChipKind.Ask || chip.tone === ChipTone.Ask;

const menu = new Menu($("menu-body"), load);

/** The session door beside the message box. The sheet lists every session and a
 * tap swaps the chat to it (family-sections, the owner's pick). */
const sessions = new Sessions(
  $("sessions-open"),
  $("overlay"),
  $("chat-screen"),
  $("inbar"),
  {
    onPick: (picked) => {
      session = picked.id;
      void openSession(picked.id);
    },
    onList: (list) => {
      known = list;
      actions();
    },
    onDiagram: (diagram, how) => onDiagram(diagram, how),
  },
);

/** Another family is another record and another set of sessions, so the chat,
 * the picture and the title all start again on it. Opening on a family only
 * names it; nothing is thrown away. */
function onDiagram(diagram: Diagram, how = { switched: true }): void {
  familyTitle = diagram.name;
  // The settings stack owns the title while it is open, so only write it when
  // the chat is what the title row is naming.
  if ($("settings-back").hidden) $("title").textContent = familyTitle;
  if (!how.switched) return;
  session = null;
  chat.clear();
  picture.clear();
  pic = REST;
  void load();
}

/** The title row shows the current view's title, and the family's name again
 * when the settings stack closes. The name follows whichever family the app is
 * on. */
let familyTitle = window.BOOTSTRAP.diagram?.name ?? $("title").textContent ?? "Your family";
$("title").textContent = familyTitle;

/** Speak replies is the one ruled duplicate: this row and the Coach settings
 * page are two doors onto the same value. */
const speak = $("speak") as HTMLInputElement;

const settings = new Settings($("account"), $("settings-back"), $("overlay"), {
  onTitle: (title) => {
    // The title row belongs to whatever is on top of it, so the chat's own
    // controls step aside while the settings stack is up.
    $("title").textContent = title ?? familyTitle;
    $("account").hidden = title !== null;
  },
  onPrefs: (prefs) => {
    speak.checked = prefs.speak;
  },
  onDiagram: (diagram, how) => {
    onDiagram(diagram, how);
    if (how.switched) void sessions.load(null);
  },
});

speak.addEventListener("change", () => void settings.set({ speak: speak.checked }));

// Every scroll area takes wheel, trackpad, touch AND mouse drag (UI_STANDARDS).
for (const id of ["chat", "menu-body"]) dragScroll($(id));

/** One stored message back on the thread. A play-by-play keeps the cluster it
 * walked, so its chips still step the board a week later. */
function addStatement(statement: Statement): void {
  chat.add(
    statement.role,
    statement.text,
    ChipTone.Data,
    statement.id,
    statement.kind === StatementKind.Play ? statement.cluster_id : null,
  );
}

/** Opening a session replaces the thread with its statements and puts the
 * picture back where that session's last coach message left it. */
async function openSession(id: number): Promise<void> {
  const { statements } = await api.session(id);
  // One thread fades out before the next one takes its place, so the swap does
  // not read as words rewriting themselves.
  const thread = $("chat");
  thread.style.opacity = "0";
  await wait(FADE_MS);
  chat.clear();
  for (const statement of statements) addStatement(statement);
  picture.clear();
  pic = REST;
  // Picking up an older thread says so, so the words above the composer are
  // not mistaken for the ones just written.
  const picked = known.find((s) => s.id === id);
  if (picked && statements.length)
    chat.system(`Resumed · ${sessionTitle(picked)} — ${summaryOf(picked)}`);
  const last = [...statements].reverse().find((s) => s.role === Role.Coach);
  if (last) spotlightFrom(last.text);
  else actions();
  thread.style.opacity = "";
  chat.toEnd();
}

/** The coach pointing: the moments its words name become the spotlight, and
 * everything else on the wire recedes. A chip only ever aims the picture; it
 * never changes the picture's level, so nothing below it moves (the owner:
 * chat bubbles must never move from a tap on a chip). The moves board is a
 * level change and is entered from Play. */
function aim(chip: Chip): void {
  const ids = aimedEvents(chip, timeline.clusters);
  if (!ids.length) return;
  picture.spotlight(ids);
  // A chip in the coach's words does exactly what a tap on the picture does:
  // there is one selection, wherever the reader touched it. A chip naming one
  // moment selects that moment; a chip naming a cluster selects the cluster,
  // so the caption offers Play for it.
  const cluster =
    ids.length > 1
      ? timeline.clusters.find((c) => ids.every((id) => c.event_ids.includes(id)))
      : undefined;
  apply(
    reduce(
      REST,
      PicEvent.Tap,
      cluster
        ? { kind: SelKind.Cluster, id: cluster.id }
        : { kind: SelKind.Event, id: String(ids[0]) },
    ),
  );
}

/** The nth chip of a walk steps the board to the nth move. The caption row
 * belongs to the wire, so it clears: the board carries its own. */
function stepBoard(play: PlayTap, chip: Chip): void {
  picture.playStep(play.cluster, aimedEvents(chip, timeline.clusters), play.ordinal);
  pic = REST;
  actions();
}

/** One place turns a picture tap into its consequences: what the picture shows,
 * what goes in the composer, what gets recorded, what plays. */
function apply(outcome: Outcome): void {
  pic = outcome.state;
  const sel = pic.sel;
  picture.select(sel && sel.kind === SelKind.Event ? Number(sel.id) : null);
  if (sel?.kind === SelKind.Cluster) {
    const cluster = timeline.clusters.find((c) => c.id === sel.id);
    if (cluster) picture.spotlight(cluster.event_ids);
  }
  actions();
  if (outcome.record)
    tapped(outcome.record.kind, outcome.record.item_kind, outcome.record.item_id);
  if (outcome.insert)
    chat.insert({
      kind: CHIP_KIND[outcome.insert.kind],
      target: outcome.insert.id,
      label: selLabel(outcome.insert),
      tone: ChipTone.Data,
      bare: false,
    });
  if (outcome.play) enterBoard(outcome.play);
}

function selLabel(sel: Sel): string {
  if (sel.kind === SelKind.Event)
    return (
      timeline.events.find((e) => String(e.id) === sel.id)?.label ?? "this moment"
    );
  if (sel.kind === SelKind.Cluster)
    return timeline.clusters.find((c) => c.id === sel.id)?.title ?? "this cluster";
  const n = timeline.shelf.length;
  return n ? `${n} thing${n === 1 ? "" : "s"} with no date yet` : "what has no date";
}

/** Traceability runs both ways: a moment on the picture says which session
 * coded it, and tapping that says which words. */
const TRACE_TITLE_CAP = 30;

function codedIn(
  eventId: number,
): { label: string; where: CodedIn } | null {
  const where = timeline.coded_in[String(eventId)];
  if (!where) return null;
  const found = known.find((s) => s.id === where.discussion_id);
  const title = found ? sessionTitle(found) : "an earlier session";
  const cut =
    title.length > TRACE_TITLE_CAP
      ? `${title.slice(0, TRACE_TITLE_CAP - 1)}…`
      : title;
  const when = found ? shortDate(new Date(found.last_activity), new Date()) : "";
  return { label: `coded in: ${cut}${when ? ` · ${when}` : ""} →`, where };
}

/** Jump to the words that coded this moment: the session if it is not the one
 * on screen, then the bubble itself, outlined while it settles. */
async function traceTo(where: CodedIn): Promise<void> {
  if (where.statement_id === null) return;
  if (where.discussion_id !== session) {
    session = where.discussion_id;
    await openSession(where.discussion_id);
  }
  if (!chat.trace(where.statement_id)) toast("Those words are no longer here");
}

/** The row under the picture: what it is showing, and the things a tap can do
 * about it. The words themselves live on the picture (converged mockup). */
/** The three things the row under the picture can do, in the chat's own chip
 * (picked plate F): one mark and one word each, drawn as the chip the coach
 * writes into the messages below, so the row and the thread are plainly the
 * same object. The row is the same in every state; a chip with nothing to do
 * is dimmed rather than missing. */
const ASK_MARK =
  `<svg width="15" height="15" viewBox="0 0 18 18" aria-hidden="true">` +
  `<rect x="1.3" y="7" width="15.4" height="9" rx="4.5" fill="none" ` +
  `stroke="currentColor" stroke-width="1.4"/>` +
  `<rect x="4" y="9.8" width="7" height="3.4" rx="1.7" fill="currentColor"/>` +
  `<path d="M9 1v3.6M9 4.9 7.2 3.1M9 4.9l1.8-1.8" fill="none" ` +
  `stroke="currentColor" stroke-width="1.4" stroke-linecap="round" ` +
  `stroke-linejoin="round"/></svg>`;
const PLAY_MARK =
  `<svg width="12" height="12" viewBox="0 0 18 18" aria-hidden="true">` +
  `<path d="M4.8 2.6 15.2 9 4.8 15.4Z" fill="currentColor"/></svg>`;
const IN_CHAT_MARK =
  `<svg width="14" height="14" viewBox="0 0 18 18" aria-hidden="true">` +
  `<rect x="1.6" y="2.4" width="14.8" height="10.2" rx="3" fill="none" ` +
  `stroke="currentColor" stroke-width="1.5"/>` +
  `<path d="M5.6 12.6 4.6 16.2 8.6 12.6" fill="none" stroke="currentColor" ` +
  `stroke-width="1.5" stroke-linejoin="round"/></svg>`;

const tok = (id: string, kind: string, mark: string, word: string, live: boolean) =>
  `<button type="button" class="tok ${kind}${live ? "" : " dim"}" id="${id}"` +
  `${live ? "" : " disabled"}>${mark}${word}</button>`;

function actions(): void {
  crumb();
  const host = $("caption");
  const sel = pic.sel;
  const open = picture.openCluster();
  // The board has its own controls, and two rows saying explain is one too
  // many. Entering the board is the one level change allowed to move what is
  // under the picture, so the row goes outright rather than sitting there as
  // an empty strip with a hairline under it (owner ruling 2026-09-08).
  const onBoard = picture.onBoard();
  host.classList.toggle("gone", onBoard);
  if (onBoard) {
    host.innerHTML = "";
    return;
  }
  // Nothing open and nothing picked: there is nothing to act on, so the row
  // says what a tap will do instead.
  if (!sel && !open) {
    host.innerHTML = `<span class="cta">tap a cluster</span>` + LIST_BUTTON;
    wireList();
    return;
  }

  // One cluster open: ask about it, or have it explained. Picked a moment
  // inside it: ask about that, or go to where it was said.
  const moment = sel?.kind === SelKind.Event ? Number(sel.id) : null;
  const trace = moment === null ? null : codedIn(moment);
  const moves = !sel && open ? picture.countMoves(open.event_ids) : 0;

  host.innerHTML =
    tok("cap-chip", "", ASK_MARK, "ask", true) +
    tok("cap-play", "g", PLAY_MARK, "explain", moves > 0) +
    tok("cap-trace", "data", IN_CHAT_MARK, "in chat", !!trace) +
    LIST_BUTTON;

  $("cap-chip").addEventListener("click", () =>
    apply(
      sel
        ? reduce(pic, PicEvent.TapChip)
        : reduce(pic, PicEvent.TapChip, {
            kind: SelKind.Cluster,
            id: (open as Cluster).id,
          }),
    ),
  );
  if (trace)
    $("cap-trace").addEventListener("click", () => void traceTo(trace.where));
  if (moves && open)
    $("cap-play").addEventListener("click", () =>
      apply(reduce(pic, PicEvent.TapPlay, { kind: SelKind.Cluster, id: open.id })),
    );
  wireList();
}

/** The way into the two lists, at the end of the row (owner review round 3). */
const LIST_BUTTON =
  `<button class="fs-glyph" id="menu-open" type="button" ` +
  `aria-label="open the timeline list">` +
  `<svg width="16" height="12" viewBox="0 0 16 12" aria-hidden="true">` +
  `<path d="M1 1h14M1 6h14M1 11h14" stroke="currentColor" stroke-width="1.6" ` +
  `stroke-linecap="round" fill="none"/></svg></button>`;

function wireList(): void {
  $("menu-open").addEventListener("click", () => screen(Screen.Menu));
}

/** The board is its own level, and entering it is the one deliberate act that
 * changes the picture's height. It goes up before the coach's words are
 * written, and stays up until the reader taps back off it. */
function enterBoard(clusterId: string): void {
  const cluster = timeline.clusters.find((c) => c.id === clusterId);
  if (cluster) picture.openBoard(cluster.event_ids, clusterId);
  pic = REST;
  actions();
}

/** The board's own control: ask the coach to talk through the cluster on
 * screen. The board is already up, so nothing here changes the picture's
 * height; the words land beneath it and step it as they are typed. */
async function explain(clusterId: string): Promise<void> {
  picture.explains(true);
  chat.busy(true);
  let reply;
  try {
    reply = await api.play(clusterId);
  } catch (error) {
    picture.explains(false);
    chat.warn(whatFailed(error), () => void explain(clusterId));
    return;
  } finally {
    chat.busy(false);
  }
  picture.explains(false);
  chat.settled();
  await chat.live(reply.cluster_id).type(reply.statement, (chip) => {
    const ids = aimedEvents(chip, timeline.clusters);
    if (ids.length) picture.step(ids[0]);
  });
  pic = REST;
  actions();
}

/** What went wrong, in the words the reader needs: nothing came back, the
 * server refused it, or the server broke. The status itself is kept on the
 * error and logged, so a timeout is never read as a rejection. */
function whatFailed(error: unknown): string {
  const failed = error instanceof api.Failed ? error : null;
  if (!failed) throw error;
  console.warn(failed.message);
  if (failed.silent) return "No answer from the server";
  if (failed.status >= 500) return "The server broke on that one";
  return "The server would not take that";
}

/** One turn. The coach's edits are already in the record by the time the reply
 * arrives, so the page says what it did, re-reads, and draws what it asked to
 * show — then types the words out, and every chip lights as it lands.
 *
 * When it does not go through, the words the reader typed stay in the thread
 * and a warning sits under them with the way to send them again. Nothing is
 * left half-typed and nothing looks like it is still coming. */
async function send(): Promise<void> {
  const statement = chat.draft();
  if (!statement) return;
  chat.add(Role.User, statement);
  chat.resetDraft();
  await deliver(statement);
}

async function deliver(statement: string): Promise<void> {
  chat.busy(true);

  let reply;
  try {
    reply = await api.say(statement, session);
  } catch (error) {
    chat.busy(false);
    chat.warn(whatFailed(error), () => void deliver(statement));
    return;
  }
  session = reply.discussion_id;
  chat.busy(false);
  chat.settled();

  const bubble = chat.live();
  for (const step of steps(reply)) {
    if (step.kind === StepKind.Note) {
      bubble.note(step.line);
      // what the line put in the record lights as the line lands, so the
      // reader sees the thing the coach is telling them about
      if (step.made.length) {
        await load();
        picture.light(step.made);
      }
    } else if (step.kind === StepKind.Reload) await load();
    else await picture.show(step.view);
  }
  await bubble.type(reply.statement, (chip) => aim(chip));
  await load();
  void sessions.load(session);
  // What the message named stays lit after it is written: the spotlight is the
  // resting state of the picture, not a flourish while it types.
  spotlightFrom(reply.statement);
}

function spotlightFrom(text: string): void {
  const named = aimedFrom(text);
  if (named.length) picture.spotlight(named);
  actions();
}

function aimedFrom(text: string): number[] {
  const out: number[] = [];
  for (const chip of chips(text))
    for (const id of aimedEvents(chip, timeline.clusters))
      if (!out.includes(id)) out.push(id);
  return out;
}

async function load(): Promise<Timeline> {
  timeline = await api.timeline();
  picture.setData(timeline);
  menu.show(timeline);
  actions();
  return timeline;
}

/** The name of the picture is also the way back to it, so while one cluster is
 * open it says so with the arrow in front of it (picked phone mockup). */
/** The name row says which view the reader is in: the whole line at rest, and
 * the cluster's own name once a cluster or its board is open. A green arrow
 * stands beside the name whenever there is a view above this one, and the
 * arrow and the name do the same thing (owner ruling 2026-09-08). */
function crumb(): void {
  const deep = picture.deep();
  const name = $("crumb");
  name.textContent = picture.title() ?? "Family timeline";
  name.classList.toggle("deep", deep);
  name.setAttribute("aria-hidden", "false");
  if (deep) {
    name.setAttribute("role", "button");
    name.setAttribute("tabindex", "0");
  } else {
    name.removeAttribute("role");
    name.removeAttribute("tabindex");
  }
  $("up").hidden = !deep;
}

/** Up exactly one level: the board to the cluster it is showing, an open
 * cluster to the whole line. */
function upOne(): void {
  picture.up();
  pic = REST;
  actions();
}

/** The list is full screen with its own back button, so it takes the title row
 * over rather than stacking a second bar under it (ruling 2026-09-03 05:53). */
function screen(which: Screen): void {
  $("chat-screen").hidden = which !== Screen.Chat;
  $("menu-screen").hidden = which !== Screen.Menu;
  document.querySelector<HTMLElement>(".titlerow")!.hidden = which === Screen.Menu;
}

/** The name of the picture is also the way back to it: tapping it puts the
 * picture down, the same as tapping empty ground on it. */
function putDown(): void {
  picture.dismiss();
  pic = REST;
  actions();
}

$("up").addEventListener("click", upOne);
$("crumb").addEventListener("click", () => {
  if (picture.deep()) upOne();
});
$("crumb").addEventListener("keydown", (e) => {
  const key = (e as KeyboardEvent).key;
  if ((key === "Enter" || key === " ") && picture.deep()) {
    e.preventDefault();
    upOne();
  }
});

$("composer").addEventListener("keydown", (e) => {
  const key = e as KeyboardEvent;
  if (key.key === "Enter" && !key.shiftKey) {
    key.preventDefault();
    void send();
  }
});
$("send").addEventListener("click", () => void send());
$("menu-close").addEventListener("click", () => {
  const field = $("menu-search") as HTMLInputElement;
  field.value = "";
  menu.search("");
  screen(Screen.Chat);
});
$("menu-add").addEventListener("click", () => menu.add());
$("menu-search").addEventListener("input", (e) =>
  menu.search((e.target as HTMLInputElement).value),
);

/** The two lists behind the one button: what happened, and who it happened to.
 * The search and the add button say which one they are for. */
const TABS: [string, Tab, string, string][] = [
  ["tab-events", Tab.Events, "Search events", "+ Add event"],
  ["tab-people", Tab.People, "Search people", "+ Add someone"],
];

/** Dress the drawer for one of its two lists. */
function onTab(tab: Tab): void {
  for (const [id, which, placeholder, add] of TABS) {
    const on = which === tab;
    $(id).classList.toggle("on", on);
    $(id).setAttribute("aria-selected", String(on));
    if (!on) continue;
    const field = $("menu-search") as HTMLInputElement;
    field.value = "";
    field.placeholder = placeholder;
    field.setAttribute("aria-label", placeholder);
    $("menu-add").textContent = add;
  }
}

for (const [id, tab] of TABS)
  $(id).addEventListener("click", () => {
    onTab(tab);
    menu.search("");
    menu.open(tab);
  });

// the drawer changes tab on its own when one thing sends the reader to another
menu.onTab = onTab;

for (const statement of window.BOOTSTRAP.statements) addStatement(statement);
chat.toEnd();

void sessions.load(session);
void settings.load();

void load().then(async () => {
  const said = window.BOOTSTRAP.statements;
  if (!said.length) {
    // the ratified opening beat: 320ms before the coach starts typing
    await wait(320);
    await chat.live().type(
      "I'm here whenever you want to think out loud about your family. " +
        "Tell me who is on your mind.",
      () => undefined,
    );
    return;
  }
  // Coming back a week later, the picture is where the last message left it.
  const last = [...said].reverse().find((s) => s.role === Role.Coach);
  if (last) spotlightFrom(last.text);
});

// Never while developing: the worker answers a reload out of its own cache,
// so a saved edit would never reach the page.
if (import.meta.env.PROD && "serviceWorker" in navigator)
  window.addEventListener("load", () =>
    navigator.serviceWorker.register("/personal/sw.js", { scope: "/personal/" }),
  );
