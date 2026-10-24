import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { FakeElement } from "./fakedom";
import { bonds, event, people, CORINNE, THEO } from "./whitlock";
import { emptyTimeline, QuestionKind, type AskedQuestion, type Timeline } from "../src/types";

vi.stubGlobal("window", { BOOTSTRAP: { user: { username: "corinne", pro: false } } });

const { Menu, Tab } = await import("../src/menu");
const { Questions } = await import("../src/questions");

beforeEach(() => {
  vi.stubGlobal("Element", FakeElement);
  vi.stubGlobal("document", { createElement: (tag: string) => new FakeElement(tag), querySelector: () => null });
});
afterEach(() => vi.unstubAllGlobals());

/** The rows a list shows, by the item each holds. */
const rows = (body: FakeElement, attr: string) => body.all().filter((one) => one.hasAttribute(attr));

/** The list drawn, scrolled, then drawn again from a record read anew. */
function reread(attr: string, first: () => void, again: () => void, body: FakeElement) {
  first();
  const before = rows(body, attr);
  body.scrollTop = 140;
  again();
  return { before, after: rows(body, attr) };
}

const noted = (id: number, date: string, who: number, what: string) =>
  event(id, date, "noted", who, { title: what, label: what, description: what });

/** The stand-in family with a few noted events, each saying what happened. */
const timeline = (): Timeline => ({
  ...emptyTimeline(),
  people: people(),
  pair_bonds: bonds(),
  events: [noted(201, "1981-09-01", CORINNE, "Started school"), noted(202, "1985-09-01", THEO, "Started school"), noted(203, "1993-06-01", CORINNE, "Left home")],
});

const menu = (body: FakeElement) =>
  new Menu(body as unknown as HTMLElement, async () => timeline(), () => 1);

// R-0937
it("keeps the events list's rows and where it was scrolled when the record is read again", () => {
  const body = new FakeElement("div");
  const list = menu(body);
  const more = timeline();
  more.events = [...more.events, noted(901, "1999-04-01", THEO, "Moved to Leeds")];
  const { before, after } = reread("data-event", () => list.show(timeline()), () => list.show(more), body);
  expect(before.length).toBeGreaterThan(0);
  expect(before.every((row) => row.parentNode !== null)).toBe(true);
  expect(after.length).toBe(before.length + 1);
  expect(body.scrollTop).toBe(140);
});

// R-0937
it("keeps the people list's rows and where it was scrolled when the record is read again", () => {
  const body = new FakeElement("div");
  const list = menu(body);
  list.open(Tab.People);
  const more = timeline();
  more.people = [...people(), { ...people().find((p) => p.id === CORINNE)!, id: 902, name: "Ines", primary: false }];
  const { before, after } = reread("data-person", () => list.show(timeline()), () => list.show(more), body);
  expect(before.length).toBeGreaterThan(0);
  expect(before.every((row) => row.parentNode !== null)).toBe(true);
  expect(after.length).toBe(before.length + 1);
  expect(body.scrollTop).toBe(140);
});

const asked = (id: string, text: string): AskedQuestion => ({
  id,
  text,
  kind: QuestionKind.Fact,
  open: true,
  asked_at: "2026-09-20",
  asked_in: { discussion_id: 7, statement_id: 70 },
  evidence: [],
  pushback: null,
  case_report_card: null,
  answer: null,
});

// R-0937
it("keeps the questions list's rows and where it was scrolled when the record is read again", () => {
  const body = new FakeElement("div");
  const handlers = { onChip() {}, onAsked() {}, onRef() {}, onDismissed() {}, busy: () => false, say() {}, record() {} };
  const list = new Questions(body as unknown as HTMLElement, handlers);
  const some = [asked("q1", "When did Theo leave home?"), asked("q2", "Who raised Corinne after 1980?")];
  const { before, after } = reread(
    "data-q",
    () => list.show(some),
    () => list.show([...some, asked("q3", "Where was Errol born?")]),
    body,
  );
  expect(before.length).toBe(2);
  expect(before.every((row) => row.parentNode !== null)).toBe(true);
  expect(after.length).toBe(3);
  expect(body.scrollTop).toBe(140);
});
