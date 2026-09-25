import { when } from "./rows";
import { type ToolCall, ViewKind } from "./types";

/** What a tool call says in plain words, as the one line the chat shows for it,
 * live and after a reload (R-0478). The line names what the call touched, by
 * the names the record gave it when the call was made, never by its id. A
 * call with no id is making something; a call with one is changing what is
 * already there, and says what it changed. */

export enum ToolName {
  ReadPeople = "read_people",
  ReadEvents = "read_events",
  ReadNotes = "read_notes",
  ReadChanges = "read_changes",
  EditPerson = "edit_person",
  EditPairBond = "edit_pair_bond",
  EditEvent = "edit_event",
  EditCluster = "edit_cluster",
  Remove = "remove",
  Undo = "undo",
  Show = "show",
  AddQuestion = "add_question",
  SetQuestion = "set_question",
  ReadQuestions = "read_questions",
}

const FIELD = new Map([
  ["name", "name"],
  ["last_name", "last name"],
  ["gender", "gender"],
  ["parents", "parents"],
  ["person_a", "partner"],
  ["person_b", "partner"],
  ["kind", "kind"],
  ["date", "date"],
  ["end_date", "end date"],
  ["date_certainty", "date is"],
  ["description", "description"],
  ["notes", "notes"],
  ["location", "place"],
  ["person", "person"],
  ["spouse", "spouse"],
  ["child", "child"],
  ["anxiety", "anxiety"],
  ["symptom", "symptom"],
  ["functioning", "functioning"],
  ["relationship", "relationship"],
  ["relationship_targets", "toward"],
  ["relationship_triangles", "triangle with"],
  ["summary", "summary"],
  ["event_ids", "events"],
]);
const DATES = new Set(["date", "end_date"]);
/** Free text too long for one line: the line says it changed, not to what. */
const LONG = new Set(["notes", "summary"]);

function list(items: string[]): string {
  return items.length < 2
    ? items.join("")
    : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;
}

function said({ args, names }: ToolCall, arg: string): string {
  const name = names[arg];
  if (name !== undefined) return Array.isArray(name) ? list(name) : name;
  return DATES.has(arg) ? when(args[arg] as string) : String(args[arg]);
}

function changes(call: ToolCall): string {
  return Object.keys(call.args)
    .flatMap((arg) => {
      if (arg === "married") return call.args.married ? "married" : "not married";
      const field = FIELD.get(arg);
      if (field === undefined) return [];
      return LONG.has(arg) ? field : `${field} ${said(call, arg)}`;
    })
    .join(", ");
}

function added({ args }: ToolCall): string[] {
  return [
    args.date ? when(args.date as string) : "",
    args.married ? "married" : "",
  ].filter(Boolean);
}

/** What a refused show was asked to draw: its ids may not name anything. */
const SHOWING = new Map([
  [ViewKind.Triangle, "a triangle"],
  [ViewKind.Span, "a stretch of time"],
  [ViewKind.Compare, "two events side by side"],
  [ViewKind.Sequence, "events in order"],
  [ViewKind.Cluster, "a cluster"],
]);

function shown({ args, names, refusal }: ToolCall): string {
  if (refusal) return SHOWING.get(args.kind as ViewKind) ?? "the picture";
  switch (args.kind as ViewKind) {
    case ViewKind.Triangle:
      return `the triangle of ${list(names.persons as string[])}`;
    case ViewKind.Span:
      return `${when(args.start as string)} to ${when(args.end as string)}`;
    case ViewKind.Compare:
      return `${names.event_a} beside ${names.event_b}`;
    case ViewKind.Sequence:
      return `${list(names.events as string[])} in order`;
    case ViewKind.Cluster:
      return names.cluster as string;
    default:
      return "the picture";
  }
}

function events({ args, names }: ToolCall): string {
  if (names.ids) return list(names.ids as string[]);
  if (names.cluster) return `the events in ${names.cluster}`;
  if (names.person) return `${names.person}'s events`;
  const span = [
    args.start ? `from ${when(args.start as string)}` : "",
    args.end ? `to ${when(args.end as string)}` : "",
  ].filter(Boolean);
  return ["events", ...span].join(" ");
}

/** Each verb as a refused call tries it, and as a call that worked says it. */
enum Verb {
  Look = "look at",
  Show = "show",
  Remove = "remove",
  Put = "put",
  Add = "add",
  Change = "change",
  Keep = "keep",
  Close = "close",
  LetGo = "let go of",
}
const DID = new Map([
  [Verb.Look, "Looked at"],
  [Verb.Show, "Showed"],
  [Verb.Remove, "Removed"],
  [Verb.Put, "Put"],
  [Verb.Add, "Added"],
  [Verb.Change, "Changed"],
  [Verb.Keep, "Kept"],
  [Verb.Close, "Closed"],
  [Verb.LetGo, "Let go of"],
]);

/** How a question the coach closed ended, said after its words. Mirrors
 * `QuestionOutcome` on the server; the reader's own dismissal is not a tool
 * call and has no line. */
enum QuestionOutcome {
  Fact = "fact",
  Answered = "answered",
  Unknown = "unknown",
  DeclinedInChat = "declined_in_chat",
  LetGo = "let_go",
}
const ENDED = new Map([
  [QuestionOutcome.Fact, "the answer is in the record"],
  [QuestionOutcome.Answered, "you answered it"],
  [QuestionOutcome.Unknown, "you don't know"],
  [QuestionOutcome.DeclinedInChat, "you'd rather not say"],
]);

enum QuestionState {
  Held = "held",
  Asked = "asked",
  Resolved = "resolved",
}

const quoted = (words: string) => `“${words}”`;

/** A question the coach keeps for later stays the coach's: the server keeps
 * its calls without its words, so the line says none. A refused close says
 * only what it tried to close, then why. */
function question(tool: ToolName, call: ToolCall): [Verb, string] {
  const state = call.args.state as QuestionState;
  if (tool === ToolName.AddQuestion && state === QuestionState.Held)
    return [Verb.Keep, "a question for later"];
  const words =
    call.names.it === undefined ? "a question kept for later" : quoted(call.names.it as string);
  if (state !== QuestionState.Resolved) return [Verb.Add, `${words} to your questions`];
  const outcome = call.args.outcome as QuestionOutcome;
  if (outcome === QuestionOutcome.LetGo) return [Verb.LetGo, words];
  const ended = ENDED.get(outcome);
  return [Verb.Close, call.refusal || !ended ? words : `${words}: ${ended}`];
}

function told(tool: ToolName, call: ToolCall): [Verb, string] {
  const it = call.names.it as string;
  switch (tool) {
    case ToolName.ReadPeople:
      return [Verb.Look, "people"];
    case ToolName.ReadEvents:
      return [Verb.Look, events(call)];
    case ToolName.ReadNotes:
      return [Verb.Look, call.names.event ? `the notes on ${call.names.event}` : "notes"];
    case ToolName.ReadChanges:
      return [Verb.Look, "recent changes"];
    case ToolName.Show:
      return [Verb.Show, shown(call)];
    case ToolName.Remove:
      return [Verb.Remove, it];
    case ToolName.Undo:
      return [Verb.Put, "that back"];
    case ToolName.ReadQuestions:
      return [Verb.Look, "questions"];
    case ToolName.AddQuestion:
    case ToolName.SetQuestion:
      return question(tool, call);
    default:
      return call.args.id === undefined
        ? [Verb.Add, [it, ...added(call)].join(", ")]
        : [Verb.Change, `${it}: ${changes(call)}`];
  }
}

export function toolLine(call: ToolCall): string | null {
  const tool = Object.values(ToolName).includes(call.name as ToolName)
    ? (call.name as ToolName)
    : null;
  if (tool === null) return null;
  const [verb, what] = told(tool, call);
  return call.refusal
    ? `Tried to ${verb} ${what}. ${call.refusal}`
    : `${DID.get(verb)} ${what}`;
}
