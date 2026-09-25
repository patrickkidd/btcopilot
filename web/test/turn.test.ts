import { describe, expect, it } from "vitest";
import { toolLine, ToolName } from "../src/tools";
import { ViewKind } from "../src/types";

const line = (
  name: ToolName,
  args: Record<string, unknown>,
  names: Record<string, string | string[]> = {},
) => toolLine({ name, args, names });

describe("what a tool call says in plain words", () => {
  // R-0186
  it("says added, and names what the call made", () => {
    expect(line(ToolName.EditPerson, { name: "Walter" }, { it: "Walter" })).toBe(
      "Added Walter",
    );
    expect(
      line(
        ToolName.EditEvent,
        { kind: "birth", child: 7, person: 3, date: "1931" },
        { it: "Walter's birth", child: "Walter", person: "Ada" },
      ),
    ).toBe("Added Walter's birth, 1931");
    expect(
      line(
        ToolName.EditEvent,
        { kind: "noted", description: "Moved to Denver", date: "1994-06-01" },
        { it: "Moved to Denver" },
      ),
    ).toBe("Added Moved to Denver, Jun 1994");
    expect(
      line(
        ToolName.EditPairBond,
        { person_a: 1, person_b: 2, married: true },
        { it: "Ada & Ben's pair bond", person_a: "Ada", person_b: "Ben" },
      ),
    ).toBe("Added Ada & Ben's pair bond, married");
  });

  // R-0186
  it("names what a change touched and what it changed, in words", () => {
    expect(
      line(ToolName.EditPerson, { id: 1, version: 4, name: "Adeline" }, { it: "Ada" }),
    ).toBe("Changed Ada: name Adeline");
    expect(
      line(
        ToolName.EditPerson,
        { id: 2, version: 4, last_name: "Hale", gender: "female" },
        { it: "Nell" },
      ),
    ).toBe("Changed Nell: last name Hale, gender female");
    expect(
      line(
        ToolName.EditEvent,
        { id: 5, version: 4, date: "1994-06-01", date_certainty: "approximate" },
        { it: "Moved to Denver" },
      ),
    ).toBe("Changed Moved to Denver: date Jun 1994, date is approximate");
    expect(
      line(
        ToolName.EditEvent,
        { id: 6, version: 4, relationship_targets: [1, 2], notes: "A long note." },
        { it: "Ben's conflict", relationship_targets: ["Ada", "Nell"] },
      ),
    ).toBe("Changed Ben's conflict: toward Ada and Nell, notes");
    expect(
      line(
        ToolName.EditPairBond,
        { id: 8, version: 4, married: false },
        { it: "Ada & Ben's pair bond" },
      ),
    ).toBe("Changed Ada & Ben's pair bond: not married");
    expect(
      line(
        ToolName.EditCluster,
        { id: "c1", version: 4, event_ids: [5, 9] },
        { it: "the cluster Nell leaves", event_ids: ["Moved to Denver", "Drinking got worse"] },
      ),
    ).toBe("Changed the cluster Nell leaves: events Moved to Denver and Drinking got worse");
  });

  // R-0186
  it("names what it removed, and says so when a thing is gone", () => {
    expect(
      line(ToolName.Remove, { item_kind: "person", item_id: "4", version: 4 }, { it: "Walter" }),
    ).toBe("Removed Walter");
    expect(
      line(
        ToolName.EditPerson,
        { id: 9, version: 4, name: "Wren" },
        { it: "a person no longer in the record" },
      ),
    ).toBe("Changed a person no longer in the record: name Wren");
  });

  // R-0478
  it("says what the coach looked at", () => {
    expect(line(ToolName.ReadPeople, {})).toBe("Looked at people");
    expect(line(ToolName.ReadChanges, {})).toBe("Looked at recent changes");
    expect(line(ToolName.ReadEvents, {})).toBe("Looked at events");
    expect(line(ToolName.ReadEvents, { person: 3 }, { person: "Ada" })).toBe(
      "Looked at Ada's events",
    );
    expect(
      line(ToolName.ReadEvents, { ids: [5, 9] }, { ids: ["Moved to Denver", "Drinking got worse"] }),
    ).toBe("Looked at Moved to Denver and Drinking got worse");
    expect(line(ToolName.ReadEvents, { start: "1994-01-01", end: "1996" })).toBe(
      "Looked at events from Jan 1994 to 1996",
    );
    expect(line(ToolName.ReadNotes, { event: 5 }, { event: "Moved to Denver" })).toBe(
      "Looked at the notes on Moved to Denver",
    );
  });

  // R-0478
  it("says what the coach showed, by name", () => {
    expect(
      line(
        ToolName.Show,
        { kind: ViewKind.Triangle, persons: [1, 2, 3] },
        { persons: ["Ada", "Nell", "Ben"] },
      ),
    ).toBe("Showed the triangle of Ada, Nell and Ben");
    expect(
      line(
        ToolName.Show,
        { kind: ViewKind.Compare, event_a: 5, event_b: 9 },
        { event_a: "Moved to Denver", event_b: "Drinking got worse" },
      ),
    ).toBe("Showed Moved to Denver beside Drinking got worse");
    expect(line(ToolName.Show, { kind: ViewKind.Span, start: "1994-06-01", end: "1996" })).toBe(
      "Showed Jun 1994 to 1996",
    );
    expect(
      line(ToolName.Show, { kind: ViewKind.Cluster, cluster: "c1" }, { cluster: "the cluster Nell leaves" }),
    ).toBe("Showed the cluster Nell leaves");
  });
});
