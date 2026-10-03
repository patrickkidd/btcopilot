import { expect, it } from "vitest";
import { closeX, pathRow } from "../src/dom";
import { below, head, leastScale, pictureHeight, pointLine, yearsLine } from "../src/drawer";
import { Told, untold } from "../src/snapshots";
import { alone, apart, CORINNE, DELPHINE, sparse, timeline } from "./whitlock";

/** The play-by-play drawer's own words and controls, read off its markup. */

const tl = timeline();
const told = new Told(tl, apart());

// R-0562
it("steps by hand: Back is off on the first snapshot, Next on the last, and only the lit dot says where", () => {
  const first = below(told, 0, null);
  expect(first).toMatch(/data-act="back" disabled/);
  const last = below(told, 4, null);
  expect(last).toMatch(/data-act="next" disabled/);
  expect([...last.matchAll(/class="dot( on)?"/g)].map((m) => !!m[1])).toEqual([false, false, false, false, true]);
  expect(last).not.toContain(" of 5");
});

// R-0679
it("shows the kind word in a step's text the way the list does", () => {
  expect(below(told, 2, null)).toContain('<p class="fact">The <span class="kw">divorce</span> went through in June.</p>');
});

// R-0563
it("keeps the guess apart from the fact, and asks the question only on the last snapshot", () => {
  const last = below(told, 4, null);
  expect(last).toMatch(/<p class="fact">Your teacher called Delphine/);
  expect(last).toMatch(/<p class="guess">My guess: /);
  expect(last).toMatch(/<p class="ask">Theo started day care/);
  expect(below(told, 3, null)).not.toContain('class="ask"');
  expect(below(told, 0, null)).not.toContain('class="guess"');
});

// R-0542, R-0540
it("leads the path row back to the timeline and to the years", () => {
  expect(pathRow(["Timeline", "1980–82", "explain"])).toMatch(/data-step="0"><span>Timeline<.*data-step="1"><span>1980–82<.*<span class="here">explain</);
});

// R-0542, R-0540, R-0545
it("opens with the path row, then the coach's point, and closes with the app's close button by the years step's route", () => {
  const top = head(told, "1980–82");
  expect(top.indexOf('class="path"')).toBeGreaterThanOrEqual(0);
  expect(top.indexOf('class="path"')).toBeLessThan(top.indexOf('class="point"'));
  expect(top).toContain(closeX(' data-step="1"'));
  expect(top).toMatch(/data-step="1"><span>1980–82</);
});

// R-0545
it("dims the years' other events and rings this snapshot's", () => {
  const line = yearsLine(tl, told, 1);
  expect([...line.matchAll(/class="wd dim"/g)]).toHaveLength(2);
  expect([...line.matchAll(/class="wnow"/g)]).toHaveLength(1);
  expect(line).toContain('class="wgap"');
});

// R-0561
it("shrinks the picture to leave the caption room, down to a floor, then lets the drawer scroll", () => {
  expect(pictureHeight(300, 500, [100], 250)).toBe(300);
  expect(pictureHeight(300, 500, [240], 250)).toBe(260);
  expect(pictureHeight(300, 500, [300], 250)).toBe(250);
  expect(pictureHeight(300, 500, [450], 250)).toBe(250);
});

// R-0561, R-0546
it("sizes the picture once for the case, by its longest caption, so nothing moves between snapshots", () => {
  expect(pictureHeight(300, 500, [100, 320, 150], 0)).toBe(pictureHeight(300, 500, [320], 0));
});

// R-0547, R-0558, R-0561
it("stops shrinking where labels reach 13px, shapes 36px or the margin 20px", () => {
  const L = told.layout;
  const least = leastScale(L, 4);
  expect(13 * least).toBeGreaterThanOrEqual(13);
  expect(L.w * least).toBeGreaterThanOrEqual(36);
  expect(L.my * least + 4).toBeGreaterThanOrEqual(20);
  expect(pictureHeight(300, 100, [90], 1000)).toBe(300);
});

// R-0570
it("tells a case nobody told with no point line and no closing question", () => {
  const quiet = new Told(tl, untold(tl, [203, 204]));
  expect(below(quiet, quiet.length - 1, null)).not.toContain('class="ask"');
  expect(pointLine(quiet)).toBe("");
  expect(pointLine(told)).toContain("As Marcus drank less");
});

// R-0545, R-0563
it("draws a sparse record's person with no family tie beside the reader, and ends on the question", () => {
  const thin = new Told(sparse(), alone());
  const L = thin.layout;
  expect(L.bonds).toHaveLength(0);
  expect(L.gen[String(DELPHINE)]).toBe(L.gen[String(CORINNE)]);
  expect(L.x[String(DELPHINE)]).toBeGreaterThan(L.x[String(CORINNE)]);
  expect(below(thin, 1, null)).toMatch(/<p class="ask">Who else was in the house that year\?/);
  expect(below(thin, 0, null)).not.toContain('class="ask"');
});
