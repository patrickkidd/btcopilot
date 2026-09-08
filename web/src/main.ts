import "./theme.css";
import * as api from "./api";
import { Chat, wait, type PlayTap } from "./chat";
import { Picture, Target, type Tap } from "./picture";
import { Menu } from "./menu";
import { Sessions, sessionTitle } from "./sessions";
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
import { $, esc } from "./dom";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import { shortDate } from "./when";
import {
  ChipKind,
  ChipTone,
  InteractionKind,
  ItemKind,
  emptyTimeline,
  Freshness,
  Role,
  StatementKind,
  type Chip,
  type CodedIn,
  type Diagram,
  type Session,
  type Statement,
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

const picture = new Picture($("view"), { onTap: (tap: Tap) => onTap(tap) });

/** A tap on the wire steps through the moments under the thumb; a tap on the
 * words picks the one whose row was tapped; a tap on the shelf asks about what
 * has no date. */
function onTap(tap: Tap): void {
  if (tap.target === Target.Shelf) {
    apply(reduce(pic, PicEvent.Tap, { kind: SelKind.Shelf, id: "shelf" }));
    return;
  }
  // At rest the picture shows the whole line; a tap opens one chapter, which
  // is the one level change the reader makes for themselves.
  if (tap.target === Target.Chapter) {
    const ids = picture.inChapter(tap.index);
    if (ids.length) picture.spotlight(ids);
    pic = REST;
    actions();
    return;
  }
  const chosen =
    tap.target === Target.Zone
      ? picture.next(tap.index, picture.selection())
      : picture.rowAt(tap.y);
  apply(
    reduce(
      pic,
      PicEvent.Tap,
      chosen === null ? undefined : { kind: SelKind.Event, id: String(chosen) },
    ),
  );
}

/** A chip the coach wrote without words of its own says what the record calls
 * it: a person's name, an event's line, a stretch's title. */
function chipLabel(chip: Chip): string {
  if (!chip.bare) return chip.label;
  if (chip.kind === ChipKind.Person)
    return timeline.people.find((p) => String(p.id) === chip.target)?.name ?? chip.label;
  if (chip.kind === ChipKind.Event)
    return timeline.events.find((e) => String(e.id) === chip.target)?.label ?? chip.label;
  return (
    timeline.chapters.find(
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
    $("menu-open").hidden = title !== null;
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

/** One stored message back on the thread. A play-by-play keeps the stretch it
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
  chat.clear();
  for (const statement of statements) addStatement(statement);
  picture.clear();
  pic = REST;
  const last = [...statements].reverse().find((s) => s.role === Role.Coach);
  if (last) spotlightFrom(last.text);
  else actions();
}

/** The coach pointing: the moments its words name become the spotlight, and
 * everything else on the wire recedes. A chip only ever aims the picture; it
 * never changes the picture's level, so nothing below it moves (the owner:
 * chat bubbles must never move from a tap on a chip). The moves board is a
 * level change and is entered from Play. */
function aim(chip: Chip): void {
  const ids = aimedEvents(chip, timeline.chapters);
  if (!ids.length) return;
  picture.spotlight(ids);
  // A chip in the coach's words does exactly what a tap on the picture does:
  // there is one selection, wherever the reader touched it. A chip naming one
  // moment selects that moment; a chip naming a stretch selects the stretch,
  // so the caption offers Play for it.
  const stretch =
    ids.length > 1
      ? timeline.chapters.find((c) => ids.every((id) => c.event_ids.includes(id)))
      : undefined;
  apply(
    reduce(
      REST,
      PicEvent.Tap,
      stretch
        ? { kind: SelKind.Cluster, id: stretch.id }
        : { kind: SelKind.Event, id: String(ids[0]) },
    ),
  );
}

/** The nth chip of a walk steps the board to the nth move. The caption row
 * belongs to the wire, so it clears: the board carries its own. */
function stepBoard(play: PlayTap, chip: Chip): void {
  picture.playStep(play.cluster, aimedEvents(chip, timeline.chapters), play.ordinal);
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
    const stretch = timeline.chapters.find((c) => c.id === sel.id);
    if (stretch) picture.spotlight(stretch.event_ids);
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
  if (outcome.play) void playThrough(outcome.play);
}

function selLabel(sel: Sel): string {
  if (sel.kind === SelKind.Event)
    return (
      timeline.events.find((e) => String(e.id) === sel.id)?.label ?? "this moment"
    );
  if (sel.kind === SelKind.Cluster)
    return timeline.chapters.find((c) => c.id === sel.id)?.title ?? "this stretch";
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
function actions(): void {
  $("pin-state").textContent = picture.state();
  const host = $("caption");
  const sel = pic.sel;
  if (!sel) {
    host.innerHTML = "";
    return;
  }
  const stretch =
    sel.kind === SelKind.Event
      ? timeline.chapters.find((c) => c.event_ids.includes(Number(sel.id)))
      : sel.kind === SelKind.Cluster
        ? timeline.chapters.find((c) => c.id === sel.id)
        : undefined;
  const ask = sel.kind === SelKind.Shelf ? "Ask when" : "Ask about this";
  const trace = sel.kind === SelKind.Event ? codedIn(Number(sel.id)) : null;
  // The board entry button says how many moves it will draw, and is only
  // offered when the stretch has at least one the board can draw.
  const moves = stretch ? picture.countMoves(stretch.event_ids) : 0;
  host.innerHTML =
    `<button type="button" class="chip ask" id="cap-chip">[${esc(ask)}]</button>` +
    (moves
      ? `<button type="button" class="btn primary" id="cap-play">` +
        `&#9654; watch the ${moves} move${moves === 1 ? "" : "s"}</button>`
      : "") +
    (trace
      ? `<button type="button" class="chip data trace" id="cap-trace">${esc(trace.label)}</button>`
      : "");
  $("cap-chip").addEventListener("click", () =>
    apply(reduce(pic, PicEvent.TapChip)),
  );
  if (trace)
    $("cap-trace").addEventListener("click", () => void traceTo(trace.where));
  if (moves && stretch)
    $("cap-play").addEventListener("click", () =>
      apply(
        reduce(pic, PicEvent.TapPlay, { kind: SelKind.Cluster, id: stretch.id }),
      ),
    );
}

/** The board is its own level, and entering it is the one deliberate act that
 * changes the picture's height. It goes up before the coach's words are
 * written, and stays up until the reader taps back off it. */
async function playThrough(clusterId: string): Promise<void> {
  const stretch = timeline.chapters.find((c) => c.id === clusterId);
  // The board goes up on the tap, not when the coach comes back: a control
  // that starts something starts it immediately (UI_STANDARDS). The coach's
  // narration then lands on a board the reader is already looking at.
  if (stretch) picture.openBoard(stretch.event_ids, clusterId);
  chat.busy(true);
  const reply = await api.play(clusterId);
  chat.busy(false);
  await chat.live(reply.cluster_id).type(reply.statement, (chip) => {
    const ids = aimedEvents(chip, timeline.chapters);
    if (ids.length) picture.step(ids[0]);
  });
  pic = REST;
  actions();
}

/** One turn. The coach's edits are already in the record by the time the reply
 * arrives, so the page says what it did, re-reads, and draws what it asked to
 * show — then types the words out, and every chip lights as it lands. */
async function send(): Promise<void> {
  const statement = chat.draft();
  if (!statement) return;
  chat.add(Role.User, statement);
  chat.resetDraft();
  chat.busy(true);

  const reply = await api.say(statement, session);
  session = reply.discussion_id;
  chat.busy(false);

  const bubble = chat.live();
  for (const step of steps(reply)) {
    if (step.kind === StepKind.Note) bubble.note(step.line);
    else if (step.kind === StepKind.Reload) await load();
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
    for (const id of aimedEvents(chip, timeline.chapters))
      if (!out.includes(id)) out.push(id);
  return out;
}

/** What the page says while the record is behind the conversation. Nothing is
 * said when it is current. */
const BEHIND: Record<Freshness, string> = {
  [Freshness.Current]: "",
  [Freshness.Extracting]: "Updating the picture from your conversation\u2026",
  [Freshness.PendingReview]:
    "New details from your conversation are waiting to be added.",
  [Freshness.ChatAhead]: "The picture may be a little behind the conversation.",
};

function freshness(state: Freshness): void {
  const line = BEHIND[state] ?? "";
  $("fresh").textContent = line;
  $("fresh").hidden = !line;
}

async function load(): Promise<Timeline> {
  timeline = await api.timeline();
  freshness(timeline.extraction.state);
  picture.setData(timeline);
  menu.show(timeline);
  actions();
  return timeline;
}

/** The list is full screen with its own back button, so it takes the title row
 * over rather than stacking a second bar under it (ruling 2026-09-03 05:53). */
function screen(which: Screen): void {
  $("chat-screen").hidden = which !== Screen.Chat;
  $("menu-screen").hidden = which !== Screen.Menu;
  document.querySelector<HTMLElement>(".titlerow")!.hidden = which === Screen.Menu;
}

$("composer").addEventListener("keydown", (e) => {
  const key = e as KeyboardEvent;
  if (key.key === "Enter" && !key.shiftKey) {
    key.preventDefault();
    void send();
  }
});
$("send").addEventListener("click", () => void send());
$("menu-open").addEventListener("click", () => {
  screen(Screen.Menu);
});
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

for (const statement of window.BOOTSTRAP.statements) addStatement(statement);

void sessions.load(session);
void settings.load();

void load().then(async () => {
  const said = window.BOOTSTRAP.statements;
  if (!said.length) {
    await wait(300);
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

if ("serviceWorker" in navigator)
  window.addEventListener("load", () =>
    navigator.serviceWorker.register("/personal/sw.js", { scope: "/personal/" }),
  );
