import "./theme.css";
import * as api from "./api";
import { Chat, wait } from "./chat";
import { Picture, Target, type Tap } from "./picture";
import { Menu } from "./menu";
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
import {
  ChipKind,
  ChipTone,
  InteractionKind,
  ItemKind,
  Role,
  type Chip,
  type Statement,
  type Timeline,
} from "./types";

declare global {
  interface Window {
    COMPANION: {
      diagram_id: number | null;
      session: { id: number } | null;
      statements: Statement[];
    };
  }
}

enum Screen {
  Chat = "chat",
  Menu = "menu",
}

let timeline: Timeline = {
  people: [],
  events: [],
  chapters: [],
  questions: [],
  axis: null,
  shelf: [],
};
let pic: PicState = REST;
let session: number | null = window.COMPANION.session?.id ?? null;

/** A tap can only be recorded against a diagram; without one there is nothing to
 * record it on. */
function tapped(
  kind: InteractionKind,
  item: ItemKind,
  id: string | null = null,
): void {
  const diagram = window.COMPANION.diagram_id;
  if (diagram !== null) void api.record(diagram, kind, item, id);
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
  onChip: (chip) => {
    tapped(InteractionKind.ChipTap, itemKind(chip.kind), chip.target);
    // An offer names nothing in the record, so it goes in the message as words.
    if (chip.kind === ChipKind.Ask || chip.tone === ChipTone.Ask) chat.insert(chip);
    else aim(chip);
  },
});

const menu = new Menu($("menu-body"), load);

/** The coach pointing: the moments its words name become the spotlight, and
 * everything else on the wire recedes. A chip only ever aims the picture; it
 * never changes the picture's level, so nothing below it moves (the owner:
 * chat bubbles must never move from a tap on a chip). The moves board is a
 * level change and is entered from Play. */
function aim(chip: Chip): void {
  const ids = aimedEvents(chip, timeline.chapters);
  if (!ids.length) return;
  picture.spotlight(ids);
  pic = REST;
  actions();
}

/** One place turns a picture tap into its consequences: what the picture shows,
 * what goes in the composer, what gets recorded, what plays. */
function apply(outcome: Outcome): void {
  pic = outcome.state;
  const sel = pic.sel;
  picture.select(sel && sel.kind === SelKind.Event ? Number(sel.id) : null);
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

/** The row under the picture: what it is showing, and the two things a tap can
 * do about it. The words themselves live on the picture (converged mockup). */
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
      : undefined;
  const ask = sel.kind === SelKind.Shelf ? "Ask when" : "Ask about this";
  host.innerHTML =
    `<button type="button" class="chip ask" id="cap-chip">[${esc(ask)}]</button>` +
    (stretch
      ? `<button type="button" class="btn play" id="cap-play">Play</button>`
      : "");
  $("cap-chip").addEventListener("click", () =>
    apply(reduce(pic, PicEvent.TapChip)),
  );
  if (stretch)
    $("cap-play").addEventListener("click", () =>
      apply(
        reduce(pic, PicEvent.TapPlay, { kind: SelKind.Cluster, id: stretch.id }),
      ),
    );
}

async function playThrough(clusterId: string): Promise<void> {
  chat.busy(true);
  const reply = await api.play(clusterId);
  chat.busy(false);
  await chat.live().type(reply.statement, (chip) => {
    const ids = aimedEvents(chip, timeline.chapters);
    if (ids.length) picture.step(ids[0]);
  });
  picture.clear();
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

async function load(): Promise<Timeline> {
  timeline = await api.timeline();
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

for (const statement of window.COMPANION.statements)
  chat.add(statement.role, statement.text);

void load().then(async () => {
  const said = window.COMPANION.statements;
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
    navigator.serviceWorker.register("/companion/sw.js", { scope: "/companion/" }),
  );
