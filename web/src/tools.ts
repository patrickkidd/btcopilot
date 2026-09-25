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

function shown({ args, names }: ToolCall): string {
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

export function toolLine(call: ToolCall): string | null {
  const tool = Object.values(ToolName).includes(call.name as ToolName)
    ? (call.name as ToolName)
    : null;
  if (tool === null) return null;
  const it = call.names.it as string;
  switch (tool) {
    case ToolName.ReadPeople:
      return "Looked at people";
    case ToolName.ReadEvents:
      return `Looked at ${events(call)}`;
    case ToolName.ReadNotes:
      return call.names.event ? `Looked at the notes on ${call.names.event}` : "Looked at notes";
    case ToolName.ReadChanges:
      return "Looked at recent changes";
    case ToolName.Show:
      return `Showed ${shown(call)}`;
    case ToolName.Remove:
      return `Removed ${it}`;
    case ToolName.Undo:
      return "Put that back";
    default:
      return call.args.id === undefined
        ? [`Added ${it}`, ...added(call)].join(", ")
        : `Changed ${it}: ${changes(call)}`;
  }
}
