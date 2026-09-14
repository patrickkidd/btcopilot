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
  it("finds a session by part of its title, whatever the case", () => {
    const whitlock = family("Whitlock", [
      session(1, "Marcus's move to Arizona"),
      session(2, "Corinne's second session"),
    ]);
    expect(matching(whitlock, "ARIZ").rows.map((s) => s.id)).toEqual([1]);
    expect(matching(whitlock, "corinne").rows.map((s) => s.id)).toEqual([2]);
  });

  it("finds a session by words in its summary", () => {
    const whitlock = family("Whitlock", [
      session(1, "Marcus's move to Arizona", "the year he left the mine"),
    ]);
    expect(matching(whitlock, "mine").rows.map((s) => s.id)).toEqual([1]);
  });

  it("keeps a family whose own name matches, even with no sessions on it", () => {
    const empty = family("Whitlock", []);
    expect(matching(empty, "whit")).toEqual({ rows: [], byName: true });
  });

  it("keeps every session of a family whose name matches", () => {
    const whitlock = family("Whitlock", [session(1, "Corinne's second session")]);
    expect(matching(whitlock, "whit").rows.map((s) => s.id)).toEqual([1]);
  });

  it("finds nothing when nothing carries the words", () => {
    const whitlock = family("Whitlock", [session(1, "Corinne's second session")]);
    expect(matching(whitlock, "ballot")).toEqual({ rows: [], byName: false });
  });

  it("names an untitled session by its clock time", () => {
    expect(sessionTitle(session(1, ""))).toMatch(/^Untitled · /);
  });
});
