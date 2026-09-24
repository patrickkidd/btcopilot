import { describe, expect, it } from "vitest";
import { matching, sessionTitle, type Family } from "../src/search";
import type { Diagram, Session } from "../src/types";

const session = (id: number, title: string, summary = ""): Session =>
  ({
    id,
    title,
    summary,
    message_count: 4,
    last_activity: "2026-09-12T09:00:00Z",
  }) as Session;

const family = (name: string, sessions: Session[]): Family => ({
  diagram: { id: 1, name } as Diagram,
  sessions,
});

describe("searching the sessions sheet", () => {
  // R-0347
  it("finds a session by part of its title, whatever the case", () => {
    const whitlock = family("Whitlock", [
      session(1, "Marcus's move to Arizona"),
      session(2, "Corinne's second session"),
    ]);
    expect(matching(whitlock, "ARIZ").rows.map((s) => s.id)).toEqual([1]);
    expect(matching(whitlock, "corinne").rows.map((s) => s.id)).toEqual([2]);
  });

  // R-0347, R-0097
  it("finds a session by words in its summary", () => {
    const whitlock = family("Whitlock", [
      session(1, "Marcus's move to Arizona", "the year he left the mine"),
    ]);
    expect(matching(whitlock, "mine").rows.map((s) => s.id)).toEqual([1]);
  });


  // R-0347
  it("finds nothing when nothing carries the words", () => {
    const whitlock = family("Whitlock", [session(1, "Corinne's second session")]);
    expect(matching(whitlock, "ballot")).toEqual({ rows: [], byName: false });
  });

  // R-0097
  it("names an untitled session by the first words said in it", () => {
    const said = { ...session(1, ""), preview: "It has been tense since my mother moved in with us" };
    expect(sessionTitle(said)).toBe("It has been tense since my…");
    expect(sessionTitle(session(1, ""))).toBe("New session");
  });
});
