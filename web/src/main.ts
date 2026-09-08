import "./theme.css";
import * as api from "./api";
import { Chat, wait } from "./chat";
import { Picture, Target, type Tap } from "./picture";
import { Menu } from "./menu";
import { aimedEvents, chipText, itemKind } from "./chips";
import { StepKind, steps } from "./turn";
import {
  CHIP_KIND,
  PicEvent,
  REST,
  SelKind,
  playable,
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

const SEL_OF: Record<Target, SelKind> = {
  [Target.Cluster]: SelKind.Cluster,
  [Target.Event]: SelKind.Event,
  [Target.Count]: SelKind.Count,
  [Target.Question]: SelKind.Question,
  [Target.Shelf]: SelKind.Shelf,
};

const picture = new Picture($("view"), {
  onTap: (tap: Tap) =>
    apply(reduce(pic, PicEvent.Tap, { kind: SEL_OF[tap.target], id: tap.id })),
});

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
  const sel = pic.sel;
  picture.select(
    sel && sel.kind === SelKind.Cluster ? sel.id : chapterOfSel(sel),
    sel && sel.kind !== SelKind.Cluster ? eventIds(sel) : [],
  );
  caption();
  if (outcome.record)
    tapped(
      outcome.record.kind,
      outcome.record.item_kind,
      outcome.record.item_id,
    );
  if (outcome.insert)
    chat.insert({
      kind: CHIP_KIND[outcome.insert.kind],
      target: outcome.insert.id,
      label: selTitle(outcome.insert),
      tone: ChipTone.Data,
      bare: false,
    });
  if (outcome.play) void playThrough(outcome.play);
}

const eventIds = (sel: Sel | null): number[] =>
  sel ? sel.id.split(",").map(Number).filter(Number.isFinite) : [];

/** The stretch a mark sits inside, so tapping a moment also lights the stretch
 * it belongs to rather than leaving it orphaned on the line. */
function chapterOfSel(sel: Sel | null): string | null {
  const [first] = eventIds(sel);
  if (first === undefined) return null;
  return timeline.chapters.find((c) => c.event_ids.includes(first))?.id ?? null;
}

/** The words a selected mark says about itself. */
function selTitle(sel: Sel): string {
  switch (sel.kind) {
    case SelKind.Cluster: {
      const chapter = timeline.chapters.find((c) => c.id === sel.id);
      if (!chapter) return "this stretch";
      // A stretch no cluster has named has only its years for a title, and the
      // years are already the second line — so it says what it holds instead.
      return chapter.title === chapter.label
        ? `${chapter.count} moment${chapter.count === 1 ? "" : "s"}`
        : chapter.title;
    }
    case SelKind.Event:
      return (
        timeline.events.find((e) => String(e.id) === sel.id)?.sentence ??
        "this moment"
      );
    case SelKind.Count: {
      const ids = eventIds(sel);
      const dates = timeline.events
        .filter((e) => ids.includes(e.id) && e.dateTime)
        .map((e) => (e.dateTime as string).slice(0, 4));
      const when =
        dates.length && dates[0] !== dates[dates.length - 1]
          ? `${dates[0]}–${dates[dates.length - 1]}`
          : (dates[0] ?? "");
      return `${ids.length} moments${when ? `, ${when}` : ""}`;
    }
    case SelKind.Question: {
      const [id] = eventIds(sel);
      return (
        timeline.questions.find((q) => q.event_id === id)?.sentence ??
        "Which came first?"
      );
    }
    case SelKind.Shelf: {
      const n = timeline.shelf.length;
      return n
        ? `${n} thing${n === 1 ? "" : "s"} with no date yet`
        : "Nothing has a date yet";
    }
  }
}

/** The second line under the title: what the mark holds, in plain words. */
function selDetail(sel: Sel): string {
  if (sel.kind === SelKind.Cluster) {
    const chapter = timeline.chapters.find((c) => c.id === sel.id);
    if (!chapter) return "";
    const when =
      chapter.start.slice(0, 4) === chapter.end.slice(0, 4)
        ? chapter.start.slice(0, 4)
        : `${chapter.start.slice(0, 4)}–${chapter.end.slice(0, 4)}`;
    return chapter.title === chapter.label
      ? when
      : `${chapter.count} moment${chapter.count === 1 ? "" : "s"}, ${when}`;
  }
  if (sel.kind === SelKind.Shelf)
    return timeline.shelf.map((item) => item.label).join(" · ");
  return "";
}

/** First tap: the words, one amber chip, and Play where there is something to
 * play. Nothing has entered the chat yet — the chip is the second tap that
 * speaks (R-0073). */
function caption(): void {
  const host = $("caption");
  const sel = pic.sel;
  if (!sel) {
    host.innerHTML = "";
    host.hidden = true;
    return;
  }
  const detail = selDetail(sel);
  const ask = sel.kind === SelKind.Shelf ? "Ask when" : "Ask about this";
  // Play is about a stretch, and a moment inside one can be played from where
  // it sits — otherwise a dense stretch, whose band its own dots cover, could
  // never be played at all.
  const stretch = playable(sel)
    ? sel
    : ((id) => (id ? { kind: SelKind.Cluster, id } : null))(chapterOfSel(sel));
  host.hidden = false;
  host.innerHTML =
    `<div class="cap-words">` +
    `<span class="cap-t">${esc(chipText(selTitle(sel), 90).text)}</span>` +
    (detail ? `<span class="cap-d">${esc(chipText(detail, 70).text)}</span>` : "") +
    `</div>` +
    `<div class="cap-acts">` +
    `<button type="button" class="chip ask" id="cap-chip">${ask}</button>` +
    (stretch
      ? `<button type="button" class="btn play" id="cap-play">Play</button>`
      : "") +
    `</div>`;
  $("cap-chip").addEventListener("click", () =>
    apply(reduce(pic, PicEvent.TapChip)),
  );
  if (stretch)
    $("cap-play").addEventListener("click", () =>
      apply(reduce(pic, PicEvent.TapPlay, stretch as Sel)),
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
  pic = { ...pic, playing: null };
}

/** One turn. The coach's edits are already in the record by the time the reply
 * arrives, so the page says what it did, re-reads, and draws what it asked to
 * show — then types the words out, aiming the picture as each chip lands. */
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
    await chat.live().type(
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
