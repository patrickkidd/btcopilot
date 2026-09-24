/** What a tool call says in plain words, as the one line the chat shows for it,
 * live and after a reload (R-0478). A call with no id is making something; a
 * call with one is changing what is already there. */

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

const SUBJECT: Partial<Record<ToolName, string>> = {
  [ToolName.EditPerson]: "someone",
  [ToolName.EditPairBond]: "a couple",
  [ToolName.EditEvent]: "an event",
  [ToolName.EditCluster]: "a cluster",
};

function words(args: Record<string, unknown>): string {
  const said = [args.name, args.description, args.title, args.dateTime]
    .filter((v): v is string => typeof v === "string" && v.trim() !== "")
    .map((v) => v.trim());
  return said.slice(0, 2).join(", ");
}

export function toolLine(
  name: string,
  args: Record<string, unknown>,
): string | null {
  const tool = Object.values(ToolName).includes(name as ToolName)
    ? (name as ToolName)
    : null;
  if (tool === null) return null;
  switch (tool) {
    case ToolName.ReadPeople:
      return "Looked at people";
    case ToolName.ReadEvents:
      return "Looked at events";
    case ToolName.ReadNotes:
      return "Looked at notes";
    case ToolName.ReadChanges:
      return "Looked at recent changes";
    case ToolName.Show:
      return null;
    case ToolName.Remove:
      return "Removed it";
    case ToolName.Undo:
      return "Put that back";
    default: {
      const said = words(args);
      const subject = said || SUBJECT[tool] || "the record";
      return `${args.id === undefined ? "Added" : "Changed"} ${subject}`;
    }
  }
}
