import * as api from "./api";
import type { ItemKind } from "./types";

/** Which features people use, read in Grafana from the product_events table.
 * These names are the only place they live; btcopilot/productevents.py
 * mirrors them and a test keeps the two equal. */
export enum Screen {
  Chat = "chat",
  Menu = "menu",
  Task = "task",
  Coding = "coding",
  Ballot = "ballot",
  Rules = "rules",
  Cut = "cut",
  Agenda = "agenda",
  Meeting = "meeting",
  Result = "result",
}

export enum Feature {
  ScreenOpen = "screen_open",
  SendMessage = "send_message",
  ChipTap = "chip_tap",
  MessageLook = "message_look",
  Play = "play",
  TraceToChat = "trace_to_chat",
  PictureUp = "picture_up",
  PictureInfo = "picture_info",
  PictureClear = "picture_clear",
  OpenMenu = "open_menu",
  CloseMenu = "close_menu",
  TabEvents = "tab_events",
  TabPeople = "tab_people",
  TabQuestions = "tab_questions",
  QuestionChip = "question_chip",
  QuestionSession = "question_session",
  QuestionDismiss = "question_dismiss",
  EventOpen = "event_open",
  PersonOpen = "person_open",
  PeopleOrder = "people_order",
  EventAdd = "event_add",
  PersonAdd = "person_add",
  EventSave = "event_save",
  EventDelete = "event_delete",
  PersonSave = "person_save",
  PersonDelete = "person_delete",
  ParentsSave = "parents_save",
  PairBondSave = "pair_bond_save",
  PairBondDelete = "pair_bond_delete",
  OpenSessions = "open_sessions",
  SessionOpen = "session_open",
  SessionNew = "session_new",
  SessionRename = "session_rename",
  SessionDelete = "session_delete",
  SessionToAgenda = "session_to_agenda",
  NoteNew = "note_new",
  UploadOpen = "upload_open",
  TaskOpen = "task_open",
  AgendaOpen = "agenda_open",
  OpenSettings = "open_settings",
  SettingChange = "setting_change",
  FamilySwitch = "family_switch",
  PasskeyAdd = "passkey_add",
  PasskeyRemove = "passkey_remove",
  SignOut = "sign_out",
  CodingDone = "coding_done",
  RulesOpen = "rules_open",
  Back = "back",
  BallotVote = "ballot_vote",
  BallotChange = "ballot_change",
  CutLine = "cut_line",
  CutConfirm = "cut_confirm",
  AgendaOpenItem = "agenda_open_item",
  AgendaAdd = "agenda_add",
  AgendaTakeOff = "agenda_take_off",
  AgendaNudge = "agenda_nudge",
  AgendaOpenVote = "agenda_open_vote",
  AgendaResult = "agenda_result",
  MeetingStart = "meeting_start",
  MeetingEnd = "meeting_end",
  MeetingKeep = "meeting_keep",
  MeetingChange = "meeting_change",
  MeetingUnresolved = "meeting_unresolved",
}

const FLUSH_MS = 5_000;

let session = "";
let here = Screen.Chat;
let diagramId: number | null = null;
let queue: api.ProductEvent[] = [];

function push(name: Feature, item?: { kind: ItemKind; id: string }): void {
  queue.push({
    screen: here,
    name,
    item_kind: item?.kind ?? null,
    item_id: item?.id ?? null,
    diagram_id: diagramId,
    at: new Date().toISOString(),
  });
}

export function screen(which: Screen): void {
  here = which;
  push(Feature.ScreenOpen);
}

export function tap(name: Feature, item?: { kind: ItemKind; id: string }): void {
  push(name, item);
}

/** The family the app is on, which a switch changes without a reload. */
export function diagram(id: number | null): void {
  diagramId = id;
}

function flush(): void {
  if (!queue.length) return;
  void api.productEvents(session, queue);
  queue = [];
}

/** One session per page load. getRandomValues rather than randomUUID, which a
 * phone on the plain-http dev server does not have. */
export function start(on: Screen, diagramOn: number | null): void {
  session = Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
  diagram(diagramOn);
  screen(on);
  setInterval(flush, FLUSH_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush();
  });
  window.addEventListener("pagehide", flush);
}
