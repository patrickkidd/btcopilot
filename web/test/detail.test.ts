import { afterEach, expect, it, vi } from "vitest";
import { eventDetail, notesSheet } from "../src/detail";
import type { TimelineEvent } from "../src/types";

afterEach(() => vi.unstubAllGlobals());

/** The card as the page builds it: its markup, and the buttons it wires by
 * what they are. */
function drawn() {
  const buttons: Record<string, { onclick: (() => void) | null; nextElementSibling?: { textContent: string } }> = {};
  const view = {
    className: "",
    innerHTML: "",
    querySelector(selector: string) {
      if (!this.innerHTML.includes(selector.replace(/^.* \./, "").replace(/^\./, ""))) return null;
      const notes = /<div class="r notes">.*?<div class="v">([\s\S]*?)<\/div><\/div>/.exec(this.innerHTML);
      return (buttons[selector] ??= { onclick: null, nextElementSibling: { textContent: notes?.[1] ?? "" } });
    },
    querySelectorAll: () => [],
  };
  vi.stubGlobal("document", { createElement: () => view });
  return { view, buttons };
}

const notes =
  "Mother stopped speaking to her sister in 1962.\nThe family moved twice that year.\n".repeat(30).trim();
const event = {
  id: 4,
  label: "Moved to Denver",
  kind: "noted",
  dateTime: "1962-06-01",
  datePrecision: null,
  endDateTime: null,
  dateCertainty: null,
  person: null,
  spouse: null,
  child: null,
  location: null,
  notes,
  symptom: null,
  anxiety: null,
  functioning: null,
  relationship: null,
  relationshipTargets: [],
  relationshipTriangles: [],
} as unknown as TimelineEvent;

// R-0899
it("puts an event's notes last on its card, whole and full width, with a way to read them full screen", () => {
  const { view, buttons } = drawn();
  const read: [string, string][] = [];
  eventDetail(event, [], undefined, {
    talk() {},
    cluster() {},
    person() {},
    event() {},
    back() {},
    said: () => null,
    notes: (title, text) => void read.push([title, text]),
  });
  expect(view.innerHTML).toMatch(/<div class="r notes"><div class="k">Notes<\/div><button type="button" class="notes-open">Full screen<\/button><div class="v">/);
  expect(view.innerHTML.indexOf('class="r notes"')).toBeGreaterThan(view.innerHTML.indexOf("When"));
  expect(view.innerHTML.indexOf('class="r notes"')).toBeLessThan(view.innerHTML.indexOf('class="foot"'));
  buttons[".notes-open"].onclick!();
  expect(read).toEqual([["Moved to Denver", notes]]);
});

// R-0899
it("shows the notes whole on their own page, under the event's name", () => {
  const page = notesSheet("Moved <to> Denver", "Line one\nLine <two>");
  expect(page).toContain('<div class="cf-t">Moved &lt;to&gt; Denver</div>');
  expect(page).toContain('<div class="fl-text">Line one\nLine &lt;two&gt;</div>');
  expect(page).toContain("cardx");
});
