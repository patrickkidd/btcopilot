import "./telemetry";
import "./theme.css";
import * as api from "./api";
import { Chat, type LiveBubble } from "./chat";
import { Picture, Target, Via, type Tap } from "./picture";
import { Menu, Tab } from "./menu";
import { Questions } from "./questions";
import { Ballot } from "./ballot";
import { Coding } from "./coding";
import { Cut } from "./cut";
import { Agenda } from "./agenda";
import { Pairs } from "./pairs";
import { Meeting } from "./meeting";
import { ResultScreen } from "./result";
import { CODER, OneTask, beforeMeeting, coder } from "./task";
import { Rules } from "./rules";
import { Sessions } from "./sessions";
import { sessionTitle } from "./search";
import { Thread, divider } from "./thread";
import { Page, Settings, type Sub } from "./settings";
import { Notices } from "./notices";
import { Strip } from "./strip";
import { aimedEvents, chips, itemKind, Lead } from "./chips";
import { feed } from "./turn";
import { Release } from "./release";
import { toolLine } from "./tools";
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
import { $, CLUSTER, pathRow, setTitle, slideOver } from "./dom";
import { Return, returnKey, touch } from "./keyboard";
import { Drawer } from "./drawer";
import { among, untold } from "./snapshots";
import { reopen, type Kept } from "./plays";
import { dragScroll } from "./drag";
import { toast } from "./toast";
import { ASK_MARK, BACK, IN_CHAT_MARK, listButton, PLAY_MARK, tok } from "./tokens";
import { offerHomeScreen, showHomeScreen, homeScreenBadge } from "./homescreen";
import { offerPasskey } from "./passkey";
import { PRO, WIDE } from "./pro";
import { shortDate } from "./when";
import * as speech from "./speech";
import { NOTES_TOOL, type Notes } from "./notes";
import { landing } from "./push";
import * as track from "./track";
import { Feature, Screen } from "./track";
import {
  ChipKind,
  ChipTone,
  Link,
  TaskKind,
  type Task,
  InteractionKind,
  ItemKind,
  Touch,
  emptyTimeline,
  Role,
  StatementKind,
  type View,
  ViewKind,
  type Chip,
  type CodedIn,
  type Diagram,
  type Session,
  type Started,
  type Statement,
  type Cluster,
  type Timeline,
  SessionKind,
  Spotlight,
  type Preferences,
} from "./types";

declare global {
  interface Window {
    BOOTSTRAP: {
      /** Patrick alone puts conversations on the agenda and opens the vote. */
      user: {
        username: string;
        admin: boolean;
        pro: boolean;
        /** Only an auditor takes part in the coding work (R-0311). */
        coder: boolean;
        prefs: Pick<Preferences, "spotlight">;
      } | null;
      diagram: { id: number; name: string } | null;
      session: { id: number; turn: string | null } | null;
      statements: api.Said[];
      version: string;
    };
  }
}

/** Which screens the coding title row belongs to. */
const CODING_SCREENS = [
  Screen.Coding,
  Screen.Ballot,
  Screen.Rules,
  Screen.Meeting,
  Screen.Result,
];

document.querySelectorAll(".backbtn").forEach((b) => (b.innerHTML = BACK));

let timeline: Timeline = emptyTimeline();
let pic: PicState = REST;
/** The sitting the coach is in, or was last: the one a page coming back asks
 * about a turn still running. */
let session: number | null = window.BOOTSTRAP.session?.id ?? null;
/** The sitting the newest words on screen belong to, so words that land in
 * another one get the line between them. */
let lastSitting: number | null = window.BOOTSTRAP.statements.at(-1)?.session_id ?? null;
/** The family's sittings, newest first, for naming the one that coded a
 * moment. */
let known: Session[] = [];

/** A tap can only be recorded against a diagram; without one there is nothing to
 * record it on. */
function tapped(kind: InteractionKind, item: ItemKind, id: string | null = null): void {
  const diagram = window.BOOTSTRAP.diagram;
  if (diagram) void api.record(diagram.id, kind, item, id);
}

const picture = new Picture(
  $("view"),
  { onTap: (tap: Tap) => onTap(tap) },
  window.BOOTSTRAP.user?.prefs.spotlight ?? Spotlight.Unified,
);

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
  if (tap.target === Target.Close) {
    climb(CLUSTER);
    return;
  }
  if (tap.target === Target.Shelf) {
    apply(reduce(pic, PicEvent.Tap, { kind: SelKind.Shelf, id: "shelf" }));
    return;
  }
  // At rest the picture shows the whole line; a tap opens one cluster, which
  // is the one level change the reader makes for themselves.
  if (tap.target === Target.Cluster) {
    const cluster = picture.clusterAt(tap.index);
    if (cluster) {
      picture.open(cluster.event_ids);
      // opening a cluster is a look at it, recorded like any other (R-0065)
      tapped(InteractionKind.Look, ItemKind.Cluster, cluster.id);
    }
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
    return (
      timeline.people.find((p) => String(p.id) === chip.target)?.name ?? chip.label
    );
  if (chip.kind === ChipKind.Event)
    return (
      timeline.events.find((e) => String(e.id) === chip.target)?.label ?? chip.label
    );
  if (chip.kind === ChipKind.Question || chip.kind === ChipKind.Impression)
    return (
      timeline.asked_questions.find((q) => q.id === chip.target)?.text ?? chip.label
    );
  if (chip.kind === ChipKind.PairBond)
    return (
      timeline.pair_bonds.find((b) => String(b.id) === chip.target)?.label ?? chip.label
    );
  return (
    timeline.clusters.find(
      (c) => c.id === chip.target || c.cluster_ids.includes(chip.target),
    )?.title ?? chip.label
  );
}

/** Each play-by-play on the thread, by its message, so a tap on it opens it
 * again. A walk told before snapshots has none and keeps its chips. */
const cases = new Map<number, Kept>();

/** The play-by-play drawer (R-0542): a tap on its path goes back to that step
 * of the picture: the whole timeline, or the case's cluster opened, whether
 * or not it was open when the drawer came up. */
const pbp = new Drawer(
  $("pbp"),
  (step, events) => {
    pbp.close();
    if (step) picture.open(events);
    else picture.back(0);
    pic = REST;
    actions();
  },
  (chip) => chipTap(chip),
);

/** A play-by-play message opened again, from its words or its cluster chip:
 * the stored telling while its cluster is unchanged, told through explain
 * once it has changed. False when the message holds no told case. */
function replay(statement: number): boolean {
  const kept = cases.get(statement);
  if (!kept) return false;
  reopen(kept, timeline.clusters, (told) => pbp.open(timeline, told, statement), (id) => void explain(id));
  return true;
}

/** A chip tapped in the thread or the drawer. Two kinds of chip, and the
 * colour says which. An amber chip is the coach asking: an old offer goes into
 * the message as words, and a question it asked goes in as the reference that
 * answers it (R-0587). A teal chip is a reference into the record, so it aims
 * the picture, except the cluster chip a play-by-play leads with, which opens
 * that play again as a tap on its words does. A chip in an
 * old prose walk is a chip like any other (R-0501, R-0570). */
function chipTap(chip: Chip): void {
  tapped(InteractionKind.ChipTap, itemKind(chip.kind), chip.target);
  track.tap(Feature.ChipTap, { kind: itemKind(chip.kind), id: chip.target });
  if (chip.play !== undefined && replay(chip.play)) return;
  if (offered(chip)) chat.insert(chip, chip.kind === ChipKind.Message ? Lead.Answer : Lead.None);
  else aim(chip);
}

const chat = new Chat($("chat"), $("composer"), {
  label: chipLabel,
  onChip: chipTap,
  // A tap on a message's own words is a look: the picture lights what that
  // message named, nothing enters the composer, and no turn is spent.
  onBubble: (text) => {
    const named = aimedFrom(text);
    if (!named.length) return;
    tapped(InteractionKind.Look, ItemKind.Event, String(named[0]));
    track.tap(Feature.MessageLook, { kind: ItemKind.Event, id: String(named[0]) });
    picture.spotlight(named);
    pic = REST;
    actions();
  },
  onPlay: replay,
});

/** An offer: the coach holding out something to say next, drawn amber. */
const offered = (chip: Chip) =>
  chip.kind === ChipKind.Ask || chip.tone === ChipTone.Ask;

const menu = new Menu($("menu-body"), load);

/** On a phone the drawer gets out of the way of the thread; pinned beside it,
 * it stays. */
const toThread = () => {
  if (!pinned()) screen(Screen.Chat);
};

/** A question or impression tapped in the drawer goes into the message as a
 * reference with the cursor after it, and nothing is sent (R-0072). */
const questions = new Questions($("menu-body"), {
  onChip: (chip, lead, after) => {
    toThread();
    chat.insert(chip, lead, after);
  },
  onAsked: (where, ask) => {
    toThread();
    void traceTo(where, ask);
  },
  onDismissed: () => void load(),
  busy: () => inFlight,
  say: (statement) => {
    toThread();
    post(statement);
  },
  record: tapped,
});
menu.questions = questions;

/** The sheet beside the message box, for the few who have work in it: a
 * professional's notes and recordings, and Patrick's list of the family's
 * conversations. Nobody opens, starts or switches a conversation there; the
 * family has one thread. */
const sessions = new Sessions(
  $("sessions-open"),
  $("overlay"),
  $("chat-screen"),
  $("inbar"),
  {
    onMade: (made) => {
      session = made.id;
      void reload().then(() => {
        if (!made.message_count) showPrompt(made.kind);
      });
    },
  },
);

/** ── Coding ───────────────────────────────────────────────────────────────
 * A coder is given one task at a time: read one conversation up to the cut
 * Patrick put on the agenda, and say what each line tells you happened
 * (R-0265, R-0267). Done is in the title row, never in the composer (R-0271).
 *
 * The task card, the agenda and what hangs off it, and the replies picked
 * blind open on the account view's stack like its own pages, and leave by its
 * back chevron to whatever opened them. */

const TASK: Sub = { title: "Your task", screen: $("task-screen"), name: Screen.Task };
const AGENDA: Sub = { title: "Next meeting", screen: $("agenda-screen"), name: Screen.Agenda };
const PICK: Sub = { title: "Pick a session", screen: $("pick-screen") };
const MEET: Sub = { title: "Meeting", screen: $("meet-screen") };
const CUT: Sub = { title: "", screen: $("cut-screen"), name: Screen.Cut };
const PAIRS: Sub = {
  title: "Better replies",
  screen: $("pairs-screen"),
  name: Screen.Pairs,
  wide: true,
};

const oneTask = new OneTask($("task-body"), {
  onStart: (task) => void startTask(task),
  onResult: (cutId) => void openResult(cutId, openTask),
});

const rules = new Rules($("rules-body"));

const coding = new Coding(
  $("coding-chat"),
  $("coding-composer"),
  $("coding-caption"),
  $("coding-send"),
  $("coding-rows"),
  $("coding-drawer"),
  $("coding-search") as HTMLInputElement,
  $("coding-tabs"),
  $("coding-add"),
  $("coding-view"),
  $("overlay"),
  {
    onDone: () => void openTask(),
    onGuidelines: () => void openRules(),
    onTitle: (title) => {
      setTitle(title);
    },
  },
);

/** The one task card read again, titled for the meeting it is for. */
async function readTask(): Promise<void> {
  voting = null;
  const found = await oneTask.load();
  TASK.title = beforeMeeting(found.task);
}

/** The one task card, which is what Done returns to and what a coder sees
 * first. */
async function openTask(): Promise<void> {
  await readTask();
  screen(Screen.Chat);
  await settings.show(TASK);
}

/** Starting a task is making your own coding of that cut, then opening the
 * conversation as a thread you cannot type into. */
async function startTask(task: Task): Promise<void> {
  const mine = task.coding_id ?? (await api.startCoding(task.cut_id)).id;
  if (task.kind === TaskKind.Vote) {
    await openBallot(task.cut_id, mine);
    return;
  }
  await coding.open(mine);
  screen(Screen.Coding);
}

/** The vote before the meeting: one disputed event per screen (R-0257). */
const ballot = new Ballot(
  $("ballot-view"),
  $("ballot-caption"),
  $("ballot-body"),
  $("overlay"),
  {
    onTitle: (title) => {
      setTitle(title);
    },
    onDone: () => void openTask(),
    onTranscript: (statementId) => void openLine(statementId),
  },
);

/** Which coding the ballot on screen belongs to, so the transcript it opens is
 * this coder's own thread of the same conversation. */
let voting: { cutId: number; codingId: number; itemId: number | null } | null = null;

async function openBallot(
  cutId: number,
  codingId: number,
  itemId: number | null = null,
): Promise<void> {
  voting = { cutId, codingId, itemId };
  await ballot.open(cutId, itemId);
  screen(Screen.Ballot);
}

/** The transcript at the line an item came from, which is the coder's own
 * thread of that conversation, read and not added to. */
async function openLine(statementId: number): Promise<void> {
  if (!voting) return;
  voting.itemId = ballot.onItem();
  await coding.open(voting.codingId, statementId);
  screen(Screen.Coding);
}

/** ── Patrick's own screens ────────────────────────────────────────────────
 * Putting a conversation on the agenda, placing the cut everyone codes up to,
 * and the agenda itself (R-0258, R-0267). Nobody but Patrick sees these. */

const placing = new Cut($("cut-chat"), $("cut-bar"), {
  onPlaced: () =>
    void agenda.load().then(() => settings.popTo(AGENDA)),
  onTitle: (title) => {
    CUT.title = title;
  },
});

const agenda = new Agenda($("agenda-body"), $("pick-body"), $("meet-body"), {
  onPick: () => settings.push(PICK),
  onPlace: (discussionId) => void placeCut(discussionId),
  onMeeting: (title) => {
    MEET.title = title;
    settings.push(MEET);
  },
  onRatify: (cutId) => void openMeeting(cutId),
  onResult: (cutId) => void openResult(cutId, openAgenda),
});

/** The meeting: the room decides what the vote left open and ratifies the cut
 * (R-0250, R-0257). Patrick's screen, reached from the meeting's page. */
const meeting = new Meeting(
  $("meeting-stats"),
  $("meeting-view"),
  $("meeting-key"),
  $("meeting-sort"),
  $("meeting-body"),
  $("meeting-bar"),
  $("overlay"),
  {
    onTitle: (title) => {
      setTitle(title);
    },
    onRatified: (cutId) => void openResult(cutId, openAgenda),
  },
);

/** What the meeting produced, which everyone who took part can read once the
 * cut is ratified (R-0275). */
const result = new ResultScreen($("result-stats"), $("result-body"), {
  onTitle: (title) => {
    setTitle(title);
  },
});

async function openMeeting(cutId: number): Promise<void> {
  await meeting.open(cutId);
  screen(Screen.Meeting);
}

/** Where the result's back arrow goes: whatever opened it. */
let resultBack = openTask;

async function openResult(cutId: number, back: () => Promise<void>): Promise<void> {
  resultBack = back;
  await result.open(cutId);
  screen(Screen.Result);
}

async function placeCut(discussionId: number): Promise<void> {
  await placing.open(discussionId, agenda.nextDate());
  settings.push(CUT);
}

/** The agenda from outside the stack: a notice, or back from a result. */
async function openAgenda(): Promise<void> {
  await agenda.load();
  screen(Screen.Chat);
  await settings.show(AGENDA);
}

/** Back from the room to the page of the meeting it was run from. */
async function backToMeeting(): Promise<void> {
  await agenda.load();
  MEET.title = await agenda.meet(agenda.meeting);
  screen(Screen.Chat);
  await settings.show(AGENDA, MEET);
}

/** Two replies to the same words, picked blind (R-0599). Patrick's. */
const pairs = new Pairs($("pairs-body"));

/** Where the guidelines go back to when closed: the coding screen mid-task,
 * the one task card between meetings. */
let rulesBack: () => void;

async function openRules(): Promise<void> {
  rulesBack =
    here === Screen.Coding ? () => screen(Screen.Coding) : () => void openTask();
  await rules.load();
  screen(Screen.Rules);
}

$("coding-done").addEventListener("click", () => {
  track.tap(Feature.CodingDone);
  coding.confirm();
});
$("coding-info").addEventListener("click", () => {
  track.tap(Feature.RulesOpen);
  void openRules();
});
$("rules-close").addEventListener("click", () => rulesBack());
$("coding-back").addEventListener("click", () => {
  track.tap(Feature.Back);
  // Reading the transcript is a step out of the ballot, so it steps back into
  // it on the item it was left on.
  if (here === Screen.Coding && voting)
    void openBallot(voting.cutId, voting.codingId, voting.itemId);
  else if (here === Screen.Coding || here === Screen.Ballot) void openTask();
  else if (here === Screen.Meeting) void backToMeeting();
  else if (here === Screen.Result) void resultBack();
});

/** Another family is another record and another set of sessions, so the chat,
 * the picture and the title all start again on it. Opening on a family only
 * names it; nothing is thrown away. */
function onDiagram(diagram: Diagram, how = { switched: true }): void {
  track.diagram(diagram.id);
  familyTitle = diagram.name;
  $("menu-title").textContent = familyTitle;
  // The settings stack owns the title while it is open, so only write it when
  // the chat is what the title row is naming.
  if ($("settings-back").hidden) $("title").textContent = familyTitle;
  if (!how.switched) return;
  session = null;
  void load().then(reload);
}

/** The title row shows the current view's title, and the family's name again
 * when the settings stack closes. The name follows whichever family the app is
 * on. */
let familyTitle =
  window.BOOTSTRAP.diagram?.name ?? $("title").textContent ?? "Your family";
$("title").textContent = familyTitle;
// the drawer is the family's too, so it carries the same name (frame 2)
$("menu-title").textContent = familyTitle;

/** Speak replies is the one ruled duplicate: this row and the Coach settings
 * page are two doors onto the same value. */
const speak = $("speak") as HTMLInputElement;

/** Which of the app's own screens on the account view's stack was last
 * counted, so the product events see it open and close like any screen. */
let stacked: Screen | null = null;

const settings = new Settings($("account"), $("settings-back"), $("overlay"), {
  onTitle: (title, sub) => {
    // The title row belongs to whatever is on top of it, so the chat's own
    // controls step aside while the settings stack is up.
    if (title === null) $("title").textContent = familyTitle;
    else setTitle(title);
    $("account").hidden = title !== null;
    // the guidelines are read from the task card too (R-0275, R-0278)
    $("coding-info").hidden = sub !== TASK && here !== Screen.Coding;
    widen(here, sub);
    const on = sub?.name ?? null;
    if (on !== stacked) track.screen(on ?? here);
    stacked = on;
  },
  onPrefs: (prefs) => {
    speak.checked = prefs.speak;
  },
  onDiagram: (diagram, how) => onDiagram(diagram, how),
  onTask: () => void readTask().then(() => settings.push(TASK)),
  onAgenda: () => void agenda.load().then(() => settings.push(AGENDA)),
  onPairs: () => void pairs.load().then(() => settings.push(PAIRS)),
  notices: () => notices.list,
  // one that points nowhere is only counted read, which its row then shows
  onNotice: async (one) => {
    await notices.open(one);
    if (!one.link) await settings.show();
  },
});

/** The screen each notice points to (R-0611). */
const GO: Record<Link, () => void> = {
  [Link.Account]: () => void settings.show(),
  [Link.Coach]: () => void settings.show(Page.Coach),
  [Link.Task]: () => void openTask(),
  [Link.Agenda]: () => void openAgenda(),
};

const go = (link: Link) => GO[link]();

const notices = new Notices(new Strip($("speakrow")), $("account"), go);

speak.addEventListener("change", () => {
  track.tap(Feature.SettingChange);
  void settings.set({ speak: speak.checked });
});

// Every scroll area takes wheel, trackpad, touch AND mouse drag (UI_STANDARDS).
for (const id of ["chat", "menu-body"]) dragScroll($(id));

/** The bubble of a turn that failed, drawn live or from the store. Picking
 * the turn up reads it again from its first event, so this one gives way. */
let stopped: { turn: string; bubble: HTMLElement } | null = null;

/** The stored messages back on the thread, each coach reply under the lines
 * of what it did (R-0478), and a line where each sitting starts. A
 * play-by-play keeps its told case, so a tap on it opens it again a week
 * later. A turn that failed shows what it did before it stopped, and on the
 * newest page, as the last message, it can be picked up again (R-0477). */
function addStatements(statements: api.Said[], newest = false): void {
  for (const statement of statements) {
    if (statement.sitting)
      $("chat").append(divider(statement.sitting.started, statement.sitting.previous_started));
    const coach = statement.role === Role.Coach;
    if (statement.case && statement.id !== null)
      cases.set(statement.id, { case: statement.case, digest: statement.digest });
    const lines = statement.tools.map(toolLine).filter((line) => line !== null);
    const notes = statement.tools.find((tool) => tool.name === NOTES_TOOL);
    chat.add(
      statement.role,
      statement.text,
      ChipTone.Data,
      statement.id,
      statement.kind === StatementKind.Play ? statement.cluster_id : null,
      coach ? lines : [],
      coach && notes ? (notes.args as unknown as Notes) : null,
    );
    if (statement.unfinished && lines.length) {
      const bubble = chat.add(Role.Coach, "", ChipTone.Data, null, null, lines);
      if (newest) stopped = { turn: statement.turn_id!, bubble };
    }
  }
  const last = statements.at(-1);
  if (newest && last?.unfinished)
    chat.warn(last.failure!, () => void resume(last.turn_id!));
}

const thread = new Thread($("chat"), (page) => addStatements(page));

/** Words that went into another sitting than the newest on screen start it:
 * the line goes in above them, dated now, and the thread stays on its foot,
 * where the reader just wrote. The newest line on screen is the sitting before
 * it, and there is none when that sitting started further back than the
 * thread has read. */
function sat(sittingId: number, words: Element | null): void {
  if (sittingId === lastSitting) return;
  lastSitting = sittingId;
  const before = [...$("chat").querySelectorAll<HTMLElement>(".sitting")].at(-1);
  words?.before(divider(new Date().toISOString(), before?.dataset.started ?? null));
  chat.toEnd();
}

/** The family's sittings read again, which name the session that coded a
 * moment. */
async function refreshKnown(): Promise<void> {
  known = await api.sessionIndex();
  actions();
  // the list says what kind of session the empty one is
  if ($("chat").querySelector(".cta")) showPrompt();
}

/** The empty session's call to action, worded for what the session is: a
 * note is the clinician writing up a session after the fact, a professional's
 * session is about a case, and a personal session is about your own family
 * (R-0350). */
function showPrompt(kind?: SessionKind): void {
  kind ??= known.find((s) => s.id === session)?.kind ?? SessionKind.Chat;
  if (kind === SessionKind.Note)
    chat.prompt("Write up the session", [
      `Tell the coach what happened in the session you just had with the ${familyTitle} family: who was there, what came up, what changed.`,
      "The coach puts it into the record the way a session's own words would be.",
    ]);
  else if (PRO)
    chat.prompt("Start the session", [
      `Talk to the coach about the ${familyTitle} case. Who is in the family, and what brought them in?`,
      "You can also tap the mic on your keyboard and say it.",
    ]);
  else
    chat.prompt("Tell your coach who is on your mind", [
      "Start with a name and what has been going on with them. The coach asks what a coach asks, and the picture above grows as you talk.",
      "You can also tap the mic on your keyboard and say it.",
    ]);
}

/** The newest page of the family's thread in place of what is on screen, and
 * the picture back where its last coach message left it. */
async function reload(): Promise<void> {
  redraw(await api.thread());
}

/** The newest statement the thread on screen holds. */
let newest: number | null = window.BOOTSTRAP.statements.at(-1)?.id ?? null;

function redraw(page: api.Said[]): void {
  newest = page.at(-1)?.id ?? null;
  chat.clear();
  addStatements(page, true);
  thread.start(page);
  lastSitting = page.at(-1)?.session_id ?? null;
  session ??= lastSitting;
  if (!page.length) showPrompt();
  picture.clear();
  pic = REST;
  leftAt(page);
  chat.toEnd();
  void refreshKnown();
}

/** The coach pointing: the moments its words name become the spotlight, and
 * everything else on the wire recedes. A chip only ever aims the picture; it
 * never changes the picture's level, so nothing below it moves (the owner:
 * chat bubbles must never move from a tap on a chip). */
function aim(chip: Chip): void {
  const ids = aimedEvents(chip, timeline.clusters);
  if (!ids.length) return;
  // A chip in the coach's words does exactly what a tap on the picture does:
  // there is one selection, wherever the reader touched it. A chip naming an
  // event no cluster claims selects that event; a chip naming a cluster, or an
  // event inside one, selects the cluster, since an event in a cluster has no
  // mark of its own on the line (R-0543).
  const cluster = timeline.clusters.find((c) => ids.every((id) => c.event_ids.includes(id)));
  if (cluster) {
    apply(reduce(REST, PicEvent.Tap, { kind: SelKind.Cluster, id: cluster.id }));
    // a chip may name a cluster off screen, so the line goes to it
    picture.spotlight(cluster.event_ids);
  } else
    apply(reduce(REST, PicEvent.Tap, { kind: SelKind.Event, id: String(ids[0]) }), ids);
}

/** One place turns a picture tap into its consequences: what the picture shows,
 * what goes in the composer, what gets recorded, what plays. `named` is what a
 * chip named, when the tap was on a chip rather than the picture. */
function apply(outcome: Outcome, named: number[] | null = null): void {
  pic = outcome.state;
  const sel = pic.sel;
  if (sel?.kind === SelKind.Event)
    picture.pick(Number(sel.id), named ?? [Number(sel.id)], named ? Via.Chip : Via.Dot);
  else picture.select(null);
  if (sel?.kind === SelKind.Cluster) {
    const cluster = timeline.clusters.find((c) => c.id === sel.id);
    if (cluster) picture.open(cluster.event_ids);
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
    }, Lead.Ask);
  if (outcome.play) void explain(outcome.play);
}

function selLabel(sel: Sel): string {
  if (sel.kind === SelKind.Event)
    return timeline.events.find((e) => String(e.id) === sel.id)?.label ?? "this event";
  if (sel.kind === SelKind.Cluster)
    return timeline.clusters.find((c) => c.id === sel.id)?.title ?? "this cluster";
  const n = timeline.shelf.length;
  return n ? `${n} thing${n === 1 ? "" : "s"} with no date yet` : "what has no date";
}

/** Traceability runs both ways: a moment on the picture says which session
 * coded it, and tapping that says which words. */
const TRACE_TITLE_CAP = 30;

function codedIn(eventId: number): { label: string; where: CodedIn } | null {
  const where = timeline.coded_in[String(eventId)];
  if (!where) return null;
  const found = known.find((s) => s.id === where.discussion_id);
  const title = found ? sessionTitle(found) : "an earlier session";
  const cut =
    title.length > TRACE_TITLE_CAP ? `${title.slice(0, TRACE_TITLE_CAP - 1)}…` : title;
  const when = found ? shortDate(new Date(found.last_activity), new Date()) : "";
  return { label: `coded in: ${cut}${when ? ` · ${when}` : ""} →`, where };
}

/** Jump to the words that coded this moment: the session if it is not the one
 * on screen, then the bubble itself, outlined while it settles. */
async function traceTo(where: CodedIn, ask = false): Promise<void> {
  if (where.statement_id === null) return;
  await thread.reach(where.statement_id);
  if (!chat.trace(where.statement_id, ask)) toast("Those words are no longer here");
}

// Hidden for now (Patrick, 2026-09-29: "the design is too busy and I'm not sure what value that brings yet").
const ASK_SHOWN = false;

/** The row under the picture: what it is showing, and the things a tap can do
 * about it. The words themselves live on the picture (converged mockup). */
function actions(): void {
  crumb();
  const host = $("caption");
  const sel = pic.sel;
  const open = picture.openCluster();
  // Nothing open and nothing picked: there is nothing to act on, so the row
  // says what a tap will do instead.
  if (!sel && !open) {
    // the about page is words already, and an empty picture has nothing to
    // tap; no hint under either
    const hint = picture.aboutOpen() || picture.empty() ? "" : "tap a cluster";
    host.innerHTML =
      `<span class="cta">${hint}</span>` + (pinned() ? "" : listButton("menu-open"));
    wireList();
    return;
  }

  // One cluster open: ask about it, or have it explained. Picked a moment
  // inside it: ask about that, or go to where it was said.
  const moment = sel?.kind === SelKind.Event ? Number(sel.id) : null;
  const trace = moment === null ? null : codedIn(moment);
  const moves = !sel && open ? picture.countDated(open.event_ids) : 0;

  host.innerHTML =
    (ASK_SHOWN ? tok("cap-chip", "", ASK_MARK, "ask", true) : "") +
    tok("cap-play", "g", PLAY_MARK, "explain", moves > 0) +
    tok("cap-trace", "data", IN_CHAT_MARK, "in chat", !!trace) +
    (pinned() ? "" : listButton("menu-open"));

  if (ASK_SHOWN)
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
    $("cap-trace").addEventListener("click", () => {
      track.tap(Feature.TraceToChat);
      void traceTo(trace.where);
    });
  if (moves && open)
    // explain opens the play-by-play drawer straight away (R-0542, R-0570)
    $("cap-play").addEventListener("click", () =>
      apply(reduce(pic, PicEvent.TapPlay, { kind: SelKind.Cluster, id: open.id })),
    );
  wireList();
}

function wireList(): void {
  // on the wide layout the drawer is pinned open and no button is drawn (R-0352)
  if (pinned()) return;
  $("menu-open").addEventListener("click", () => {
    track.tap(Feature.OpenMenu);
    screen(Screen.Menu);
  });
}

/** A wider window stands the events and people drawer beside the thread
 * instead of sliding it over (R-0243). Since 2026-09-22 that is for everyone,
 * not only a professional, so a phone turned on its side gets it too, to see
 * how it feels (R-0367). The one drawer moves between the full screen and the
 * pinned column, so both carry the same list, the same search and the same
 * editors rather than two of each. */
const wide = window.matchMedia(WIDE);

const pinned = () => wide.matches;

const DRAWER = ["menu-tabs", "menu-searchrow", "menu-body", "menu-foot"];

function pinDrawer(): void {
  const on = pinned();
  $("chat-drawer").hidden = !on;
  const host = on ? $("chat-drawer") : $("menu-screen");
  for (const id of DRAWER) host.append($(id));
  // The full-screen list has nothing left in it once the drawer is pinned, and
  // the app's own width follows which screen is up.
  if (here === Screen.Chat || (on && here === Screen.Menu)) screen(Screen.Chat);
}

wide.addEventListener("change", () => {
  pinDrawer();
  actions();
});

/** What the coach aimed the picture at. A triangle or a sequence has people
 * and moves to draw, so it opens the play-by-play drawer, told by nobody: the
 * coach's own words stay in the bubble that asked for it (R-0570). */
function shown(view: View): Promise<void> | void {
  const ids =
    view.kind === ViewKind.Triangle
      ? among(timeline, view.persons)
      : view.kind === ViewKind.Sequence
        ? view.events
        : null;
  if (ids === null) return picture.show(view);
  const told = untold(timeline, ids);
  if (told.snapshots.length) pbp.open(timeline, told, null);
}

/** Ask the coach to tell the cluster on screen. The case opens in its drawer
 * over the picture and the chat, and its point joins the thread, where a tap
 * opens it again. A record the picture cannot draw is refused in the
 * server's own words. */
async function explain(clusterId: string): Promise<void> {
  track.tap(Feature.Play, { kind: ItemKind.Cluster, id: clusterId });
  chat.busy(true);
  let reply;
  try {
    reply = await api.play(clusterId);
  } catch (error) {
    chat.warn(api.whatFailed(error), () => void explain(clusterId));
    return;
  } finally {
    // answered or not, the row is back to what the cluster offers, explain again
    chat.busy(false);
    pic = REST;
    actions();
  }
  chat.settled();
  // a kept play already on the thread opens again; it is not said twice
  const id = reply.statement_id;
  if (id === null || !cases.has(id)) {
    const told = chat.add(Role.Coach, reply.statement, ChipTone.Data, id, reply.cluster_id);
    // a play told after a quiet spell starts the family's next sitting
    void refreshKnown().then(() => {
      if (known.length) sat(known[0].id, told);
    });
  }
  if (id !== null) cases.set(id, { case: reply.case, digest: reply.digest });
  pbp.open(timeline, reply.case, id);
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
let inFlight = false;

async function send(): Promise<void> {
  const statement = chat.draft();
  if (!statement || inFlight) return;
  await questions.sending(statement);
  chat.resetDraft();
  post(statement);
}

/** The reader's words go into the thread as theirs and on to the coach. */
function post(statement: string): void {
  if (!statement || inFlight) return;
  track.tap(Feature.SendMessage);
  chat.add(Role.User, statement);
  void deliver(statement);
}

async function deliver(statement: string): Promise<void> {
  const started = await begin(() => api.say(statement), () => void deliver(statement));
  if (!started) return;
  sat(started.discussion_id, [...$("chat").querySelectorAll(".bub.user")].at(-1) ?? null);
  follow(started.turn_id);
}

/** Try a failed turn again: the same turn goes on, and the words are not sent
 * a second time (R-0477). */
async function resume(turnId: string): Promise<void> {
  if (await begin(() => api.resume(turnId), () => void resume(turnId))) follow(turnId);
}

async function begin(
  ask: () => Promise<Started>,
  again: () => void,
): Promise<Started | null> {
  // One turn at a time: a second send while the coach is answering would store
  // the words again.
  inFlight = true;
  chat.busy(true);
  speech.hush();

  let started;
  try {
    started = await ask();
  } catch (error) {
    inFlight = false;
    chat.busy(false);
    chat.warn(whatFailed(error), again);
    return null;
  }
  session = started.discussion_id;
  return started;
}

/** The turn the coach is running, drawn as it happens. Everything the page
 * shows comes off the stream, so attaching to a turn already under way — after
 * a reload, or coming back to the app — reads it from its first event and
 * builds the same bubble. Nothing is ever shown twice: the bubble is built
 * again, not added to. */
let watching: EventSource | null = null;
let onTurn: string | null = null;

function follow(turnId: string): void {
  if (onTurn === turnId) return;
  stopFollowing();
  chat.settled();
  // the next message has arrived: what the last reply touched goes back to how
  // the line draws it (R-0539)
  picture.untouch();
  onTurn = turnId;
  inFlight = true;
  chat.busy(true);

  let bubble: LiveBubble | null = null;
  // The typing dots stay until the coach's first word or first step, and the
  // bubble takes their place, and that of a failed try at the same turn.
  const opened = () => {
    if (!bubble) {
      chat.busy(false);
      if (stopped?.turn === turnId) {
        if (stopped.bubble.nextElementSibling?.matches(".play"))
          stopped.bubble.nextElementSibling.remove();
        stopped.bubble.remove();
      }
      bubble = chat.live();
    }
    return bubble;
  };
  // The events are drawn in the order they happened, and re-reading the record
  // takes a moment, so each one waits for the one before it.
  let queue: Promise<void> = Promise.resolve();
  const step = (work: () => Promise<void> | void) => {
    queue = queue.then(work).catch((error) => console.warn(error));
  };

  const take = feed({
    note: (line) => step(() => void opened().note(line)),
    notes: (notes) => step(() => opened().notes(notes)),
    made: (items) =>
      step(async () => {
        // a removed event is gone from the record read back, so it is taken
        // from the one on screen, to stay where it was in its colour
        const removed = new Set(
          items
            .filter((one) => one.kind === ItemKind.Event && one.touch === Touch.Remove)
            .map((one) => Number(one.id)),
        );
        const gone = timeline.events.filter((e) => removed.has(e.id));
        await load();
        if (items.length) picture.light(items, gone);
      }),
    read: (ids) => step(() => picture.read(ids)),
    show: (view) => step(() => shown(view)),
    text: (text) => step(() => void opened().append(text, (chip) => aim(chip))),
    reset: () => step(() => void opened().reset()),
    done: (reply) =>
      step(async () => {
        const said = opened();
        said.stamp(reply.statement_id);
        newest = reply.statement_id;
        if (speak.checked) speech.say(reply.statement);
        said.settle(reply.statement, (chip) => aim(chip));
        stopFollowing();
        await load();
        void refreshKnown();
        void notices.refresh();
        // What the message named stays lit after it is written: the spotlight
        // is the resting state of the picture, not a flourish while it types.
        spotlightFrom(reply.statement);
      }),
    failed: (message) =>
      step(() => {
        stopFollowing();
        chat.busy(false);
        // What it did stays; the words it had begun are not kept, so they go.
        if (bubble) {
          bubble.settle("", () => {});
          stopped = { turn: turnId, bubble: bubble.bubble };
        }
        chat.warn(message, () => void resume(turnId));
      }),
    refused: (message) =>
      step(() => {
        stopFollowing();
        const said = opened();
        said.reset();
        said.settle(message, (chip) => aim(chip));
      }),
  });

  const source = api.turnEvents(turnId);
  watching = source;
  source.addEventListener("message", (event) => take(JSON.parse(event.data)));
  source.addEventListener("error", () => {
    // The browser reconnects on its own and says where it got to; only a turn
    // that has already ended leaves nothing to reconnect to.
    if (source.readyState === EventSource.CLOSED) stopFollowing();
  });
}

function stopFollowing(): void {
  watching?.close();
  watching = null;
  onTurn = null;
  inFlight = false;
}

/** A page that has just loaded, or come back to the front, attaches to the
 * turn the session says is running. */
async function reattach(): Promise<void> {
  if (watching) return;
  if (session !== null) {
    const { turn } = await api.session(session);
    if (turn) return follow(turn);
  }
  // A turn that finished while the page was away is read in with the rest.
  await catchUp();
}

const CATCH_UP_MS = 60_000;

/** Words written from outside the page — a coach message sent first — are
 * read in when the page comes back, after a notification is tapped, and once
 * a minute while it is in front: the thread is drawn again only when its
 * newest statement is not the newest on screen. */
async function catchUp(): Promise<void> {
  if (inFlight) return;
  const page = await api.thread();
  if (!inFlight && (page.at(-1)?.id ?? null) !== newest) redraw(page);
}

window.setInterval(() => {
  if (document.visibilityState === "visible") void catchUp();
}, CATCH_UP_MS);

/** The picture where the last coach message left it. A play-by-play's
 * cluster chip is there to play it again, so it aims nothing on the way back. */
function leftAt(statements: Statement[]): void {
  const last = [...statements].reverse().find((s) => s.role === Role.Coach);
  spotlightFrom(last && !last.case ? last.text : "");
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
  chat.relabel();
  actions();
  return timeline;
}

/** The path over the line: where the reader is, from the whole timeline
 * down, each earlier step the way back to it (R-0540). */
function crumb(): void {
  $("path").innerHTML = pathRow(picture.path());
  $("info").hidden = !picture.opened();
}

/** The list is full screen with its own back button, so it takes the title row
 * over rather than stacking a second bar under it (ruling 2026-09-03 05:53). */
function screen(which: Screen): void {
  // the account view's stack is over the chat, and every other screen is
  // opened instead of it
  if (which !== Screen.Chat) settings.close();
  if (which !== here) track.screen(which);
  // The list comes up over the chat rather than replacing it, so the chat is
  // still there underneath while the list travels (R-0345).
  $("chat-split").hidden = which !== Screen.Chat && which !== Screen.Menu;
  slideOver($("menu-screen"), which === Screen.Menu);
  $("ballot-screen").hidden = which !== Screen.Ballot;
  $("meeting-screen").hidden = which !== Screen.Meeting;
  $("result-screen").hidden = which !== Screen.Result;
  $("coding-screen").hidden = which !== Screen.Coding;
  $("rules-screen").hidden = which !== Screen.Rules;
  // The list covers the title row rather than taking its place: it is over
  // everything, with its own back arrow.
  document.querySelector<HTMLElement>(".titlerow")!.hidden = which === Screen.Rules;
  widen(which);
  // Done and the guidelines belong to the coding screen.
  // A submitted coding is read, not added to: no Done and nothing to type
  // into (R-0271). The ballot opens the transcript that way.
  const writing = which === Screen.Coding && !coding.finished();
  $("coding-done").hidden = !writing;
  $("coding-inbar").hidden = !writing;
  // The guidelines are read from the (i) at the top of the coding screen; the
  // task card's own is set when it comes to the top of the stack (R-0275,
  // R-0278).
  $("coding-info").hidden = which !== Screen.Coding;
  $("coding-back").hidden = !CODING_SCREENS.includes(which);
  $("account").hidden = which === Screen.Rules;
  // The sheet's door stands in the chat's own input bar, so it is only on the
  // chat, and only for those with something in the sheet; every other screen
  // carries the back arrow the frames draw instead.
  $("sessions-open").hidden = which !== Screen.Chat || !sessions.door;
  here = which;
}

/** The app is a phone everywhere else; it widens only where something stands
 * beside the thread — the coding screen, the chat screen for a professional
 * on a wide window — and where two replies stand side by side. */
function widen(which: Screen, sub?: Sub): void {
  document
    .querySelector<HTMLElement>(".app")!
    .classList.toggle(
      "wide",
      which === Screen.Coding || (which === Screen.Chat && pinned()) || !!sub?.wide,
    );
}

/** Which screen is up, so the title row and the back arrow say the same. */
let here = Screen.Chat;
track.start(here, window.BOOTSTRAP.diagram?.id ?? null);

/** Empty ground on the picture puts it down: the whole line at a glance. */
function putDown(): void {
  picture.dismiss();
  pic = REST;
  actions();
}

/** Back up to one step of the path: the path's own steps, and the about
 * page's close button, which goes where the cluster's step goes. */
function climb(step: number): void {
  track.tap(Feature.PictureUp);
  picture.back(step);
  pic = REST;
  actions();
}

$("path").addEventListener("click", (e) => {
  const step = (e.target as Element).closest<HTMLElement>("[data-step]");
  if (step) climb(Number(step.dataset.step));
});
$("info").addEventListener("click", () => {
  track.tap(Feature.PictureInfo);
  picture.about();
  pic = REST;
  actions();
});
// With a real keyboard Return sends; a new line is Shift- or Alt-Return, and
// on a touch screen Return, so a message can have paragraphs (R-0368). The
// break is a plain newline so the draft keeps it.
$("composer").addEventListener("keydown", (e) => {
  const key = e as KeyboardEvent;
  const act = returnKey(key, touch());
  if (!act) return;
  key.preventDefault();
  if (act === Return.Send) return void send();
  const selection = window.getSelection();
  if (!selection?.rangeCount) return;
  const range = selection.getRangeAt(0);
  range.deleteContents();
  const br = document.createTextNode("\n");
  range.insertNode(br);
  // A newline that ends the box draws no line of its own, so the next letters
  // would join the line above; a second one holds the line open, and the
  // draft trims it on send.
  let next = br.nextSibling;
  while (next instanceof Text && next.data === "") next = next.nextSibling;
  if (!next) br.after(document.createTextNode("\n"));
  range.setStartAfter(br);
  range.collapse(true);
  selection.removeAllRanges();
  selection.addRange(range);
});
$("send").addEventListener("click", () => void send());
$("menu-close").addEventListener("click", () => {
  track.tap(Feature.CloseMenu);
  const field = $("menu-search") as HTMLInputElement;
  field.value = "";
  menu.search("");
  screen(Screen.Chat);
});
$("menu-add").addEventListener("click", () => {
  track.tap(menu.showing() === Tab.People ? Feature.PersonAdd : Feature.EventAdd);
  menu.add();
});
$("menu-search").addEventListener("input", (e) =>
  menu.search((e.target as HTMLInputElement).value),
);

/** The lists behind the one button: what happened, who it happened to, and
 * what the coach asked that is still open. The search and the add button say
 * which list they are for; the questions are the coach's, so that list has
 * neither. */
const TABS: [string, Tab, string | null, string | null, Feature][] = [
  ["tab-events", Tab.Events, "Search events", "+ Add event", Feature.TabEvents],
  ["tab-people", Tab.People, "Search people", "+ Add someone", Feature.TabPeople],
  ["tab-questions", Tab.Questions, null, null, Feature.TabQuestions],
];

/** Dress the drawer for one of its lists. */
function onTab(tab: Tab): void {
  for (const [id, which, placeholder, add] of TABS) {
    const on = which === tab;
    $(id).classList.toggle("on", on);
    $(id).setAttribute("aria-selected", String(on));
    if (!on) continue;
    $("menu-searchrow").hidden = $("menu-foot").hidden = placeholder === null;
    if (placeholder === null) continue;
    const field = $("menu-search") as HTMLInputElement;
    field.value = "";
    field.placeholder = placeholder;
    field.setAttribute("aria-label", placeholder);
    $("menu-add").textContent = add;
  }
}

for (const [id, tab, , , feature] of TABS)
  $(id).addEventListener("click", () => {
    track.tap(feature);
    onTab(tab);
    menu.search("");
    menu.open(tab);
  });

// the drawer changes tab on its own when one thing sends the reader to another
menu.onTab = onTab;

pinDrawer();

addStatements(window.BOOTSTRAP.statements, true);
thread.start(window.BOOTSTRAP.statements);
chat.toEnd();

void refreshKnown();
void settings.load();
void notices.refresh();

// A turn the coach is still running when the page opens is drawn from its first
// event, so a reload lands back in the middle of it rather than on nothing.
const running = window.BOOTSTRAP.session?.turn ?? null;
if (running) follow(running);

// Coming back to the app — a phone returning to it, a tab shown again, the page
// restored from the back cache — attaches to whatever the coach is doing now.
// It also loads the release the server runs now, if a deploy happened while
// the page was away.
const release = new Release(
  window.BOOTSTRAP.version,
  api.version,
  () => inFlight || chat.draft() !== "" || !!$("coding-composer").textContent?.trim(),
  () => location.reload(),
);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible") return;
  void reattach();
  void release.check();
});
window.addEventListener("pageshow", (e) => {
  void reattach();
  if (e.persisted) void release.check();
});

void load().then(async () => {
  const said = window.BOOTSTRAP.statements;
  if (!said.length) {
    showPrompt();
    return;
  }
  // Coming back a week later, the picture is where the last message left it.
  leftAt(said);
}).then(() =>
  // a task or notice opened from its push no longer holds the strip or the mark
  landing(
    (where) => catchUp().then(() => traceTo(where)),
    (link) => void notices.refresh().then(() => go(link)),
  ),
);

// The dev server too: push needs the worker, and the worker asks the network
// first, so a saved edit still reaches the page.
if ("serviceWorker" in navigator)
  window.addEventListener("load", () =>
    navigator.serviceWorker.register(
      `/app/sw.js?release=${encodeURIComponent(window.BOOTSTRAP.version)}`,
      { scope: "/app/" },
    ),
  );

// A coder opens on their one task rather than on the chat (R-0265, frame f1),
// and still does between meetings, when the card carries what they finished
// instead. Only an auditor is a coder (R-0311): a professional or a plain
// subscriber never asks for a task and opens on the chat. A reader who has
// never coded never sees the card, and a server without the review tables
// leaves the chat exactly as it was.
if (CODER) {
  void api
    .tasks()
    .then((found) => {
      if (coder(found)) void openTask();
    })
    .catch((error) => {
      if (!(error instanceof api.Failed)) throw error;
      console.warn(error.message);
    });
}

// The page is only served to a signed-in reader, so this is the moment to ask
// about a key on this device, and then about the home screen — one card at a
// time, never both at once.
void offerPasskey(offerHomeScreen);
homeScreenBadge($("homescreen"), showHomeScreen);
