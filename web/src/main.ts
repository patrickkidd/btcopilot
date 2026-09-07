import "./theme.css";
import * as api from "./api";
import { Chat, wait } from "./chat";
import { Picture } from "./picture";
import { Menu } from "./menu";
import { aimedEvents, itemKind } from "./chips";
import { PicEvent, REST, reduce, type Outcome, type PicState } from "./caption";
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
  axis: null,
  shelf: [],
};
let pic: PicState = REST;

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

const picture = new Picture($("view"), {
  onCluster: (id) => apply(reduce(pic, PicEvent.TapCluster, id)),
});

const chat = new Chat($("chat"), $("composer"), {
  onChip: (chip) => {
    tapped(InteractionKind.ChipTap, itemKind(chip.kind), chip.target);
    if (chip.tone === ChipTone.Ask) chat.insert(chip);
    else aim(chip);
  },
});

const menu = new Menu($("menu-body"), load);

function aim(chip: Chip): void {
  const ids = aimedEvents(chip, timeline.chapters);
  if (ids.length) picture.aim(ids);
}

/** One place turns a picture tap into its consequences: what the caption shows,
 * what goes in the composer, what gets recorded, what plays. */
function apply(outcome: Outcome): void {
  pic = outcome.state;
  picture.setOpen(pic.open);
  caption();
  if (outcome.record)
    tapped(
      outcome.record.kind,
      outcome.record.item_kind,
      outcome.record.item_id,
    );
  if (outcome.insert)
    chat.insert({
      kind: ChipKind.Cluster,
      target: outcome.state.open ?? "",
      label: captionTitle() ?? "this stretch",
      tone: ChipTone.Data,
    });
  if (outcome.play) void playThrough(outcome.play);
}

function captionTitle(): string | null {
  const chapter = timeline.chapters.find((c) => c.id === pic.open);
  return chapter ? chapter.title : null;
}

/** First tap: the title, one amber chip, and Play. Nothing has entered the chat
 * yet — the chip is the second tap that speaks. */
function caption(): void {
  const host = $("caption");
  const chapter = timeline.chapters.find((c) => c.id === pic.open);
  if (!chapter) {
    host.innerHTML = "";
    host.hidden = true;
    return;
  }
  host.hidden = false;
  host.innerHTML =
    `<span class="cap-t">${esc(chapter.title)}</span>` +
    `<button type="button" class="chip ask" id="cap-chip">Ask about this</button>` +
    `<button type="button" class="btn play" id="cap-play">Play</button>`;
  $("cap-chip").addEventListener("click", () =>
    apply(reduce(pic, PicEvent.TapChip)),
  );
  $("cap-play").addEventListener("click", () =>
    apply(reduce(pic, PicEvent.TapPlay)),
  );
}

async function playThrough(clusterId: string): Promise<void> {
  chat.busy(true);
  const reply = await api.play(clusterId);
  chat.busy(false);
  await chat.type(reply.statement, (chip) => {
    const ids = aimedEvents(chip, timeline.chapters);
    if (ids.length) picture.step(ids[0]);
  });
  pic = { ...pic, playing: null };
}

async function send(): Promise<void> {
  const statement = chat.draft();
  if (!statement) return;
  chat.add(Role.User, statement);
  chat.resetDraft();
  tapped(InteractionKind.Say, ItemKind.Diagram);
  chat.busy(true);
  const reply = await api.say(statement);
  chat.busy(false);
  await chat.type(reply.statement, (chip) => aim(chip));
  timeline = await load();
}

async function load(): Promise<Timeline> {
  timeline = await api.timeline();
  picture.setData(timeline);
  menu.show(timeline);
  caption();
  return timeline;
}

function screen(which: Screen): void {
  $("chat-screen").hidden = which !== Screen.Chat;
  $("menu-screen").hidden = which !== Screen.Menu;
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
$("menu-close").addEventListener("click", () => screen(Screen.Chat));
$("menu-add").addEventListener("click", () => menu.add());

for (const statement of window.COMPANION.statements)
  chat.add(statement.role, statement.text);

void load().then(async () => {
  if (!window.COMPANION.statements.length) {
    await wait(300);
    await chat.type(
      "I'm here whenever you want to think out loud about your family. " +
        "Tell me who is on your mind.",
      () => undefined,
    );
  }
});

if ("serviceWorker" in navigator)
  window.addEventListener("load", () =>
    navigator.serviceWorker.register("/companion/sw.js", { scope: "/companion/" }),
  );
