import { readFileSync } from "node:fs";
import { expect, it } from "vitest";
import { closeX, PAN, pathRow } from "../src/dom";
import { FIT, fitScale, leastScale, NAME } from "../src/diagram";
import { below, head, pointLine, shownBy, stepOf, topLine, yearsLine } from "../src/drawer";
import { family, familyStart, Told, untold, when } from "../src/snapshots";
import { DateCertainty } from "../src/certainty";
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

// R-0542, R-0540, R-0545, R-0767
it("opens with the path row, then the coach's point, and closes with the app's close button by the cluster step's route", () => {
  const top = head(told, "Leaving home · 1980–82");
  expect(top.indexOf('class="path"')).toBeGreaterThanOrEqual(0);
  expect(top.indexOf('class="path"')).toBeLessThan(top.indexOf('class="point"'));
  expect(top).toContain(closeX(' data-step="1"'));
  expect(top).toMatch(/data-step="1"><span>Leaving home · 1980–82</);
});

// R-0545
it("dims the years' other events and rings this snapshot's", () => {
  const line = yearsLine(tl, told, 1);
  expect([...line.matchAll(/class="wd dim"/g)]).toHaveLength(2);
  expect([...line.matchAll(/class="wnow"/g)]).toHaveLength(1);
  expect(line).toContain('class="wgap"');
});

// R-0796
it("takes whichever of the two fits is tighter, across or down", () => {
  const L = told.layout;
  expect(fitScale(L, L.vw * 0.8, L.h)).toBeCloseTo(0.8);
  expect(fitScale(L, L.vw * 0.9, L.h * 0.7)).toBeCloseTo(0.7);
});

// R-0796
it("never grows a small picture past its own size, and never shrinks its names under the least size, past which it pans", () => {
  const L = told.layout;
  expect(fitScale(L, L.vw * 3, L.h * 3)).toBe(1);
  expect(NAME * fitScale(L, 1, 1)).toBeCloseTo(FIT);
});

// "When showing the full Family Diagram view, I think it should just automatically scale to fill all available space." (Patrick, 2026-10-07)
// R-0796
it("grows a small picture to fill the space only when given no ceiling, as the Family view gives it; the play-by-play keeps its own size", () => {
  const L = told.layout;
  expect(fitScale(L, L.vw * 3, L.h * 2, Infinity)).toBeCloseTo(2);
  expect(fitScale(L, L.vw * 3, L.h * 2)).toBe(1);
});

// "the timeline should really stretch out to fit available horizontal space" (Patrick, 2026-10-07)
// R-0796
it("draws the years line across the width it is given, its ends and the last tap reaching the far edge", () => {
  const whole = new Told(tl, family(tl), true);
  const line = yearsLine(tl, whole, whole.length - 1, 1000);
  expect(line).toContain('viewBox="0 0 1000.0 62"');
  expect(line).toContain('<line class="wl" x1="26" y1="34" x2="974"');
  const last = [...line.matchAll(/<rect class="whit" x="([\d.]+)" y="0" width="([\d.]+)"/g)].at(-1)!;
  expect(Number(last[1]) + Number(last[2])).toBeCloseTo(1000, 0);
  expect(Number(line.match(/<text class="wlab" x="([\d.]+)"/)![1])).toBeGreaterThan(390);
});

// R-0744, R-0759
it("stops shrinking where labels reach 13px, shapes 36px or the margin 20px", () => {
  const L = told.layout;
  const least = leastScale(L, 4);
  expect(13 * least).toBeGreaterThanOrEqual(13);
  expect(L.w * least).toBeGreaterThanOrEqual(36);
  expect(L.my * least + 4).toBeGreaterThanOrEqual(20);
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

// R-0742
it("steps the whole family with Back and Next only, says where in its top line, and closes back to the timeline", () => {
  const whole = new Told(tl, family(tl), true);
  const last = whole.length - 1;
  expect(below(whole, last, null)).not.toContain('class="dot');
  expect(below(whole, last, null)).toMatch(/data-act="next" disabled/);
  expect(below(whole, 0, null)).toMatch(/data-act="back" disabled/);
  expect(below(whole, last, null)).not.toContain('class="fact"');
  const top = head(whole, "");
  // the path names whose family the frame is on, written as each date is drawn
  expect(top).toContain('<div class="path"></div>');
  expect(top).toContain(closeX(' data-step="0"'));
  expect(top).not.toContain('class="point"');
  expect(topLine(whole, 0)).toBe('<span class="words">Errol and Odile <span class="kw">married</span></span>');
  const toward = whole.told.snapshots.findIndex((s) => s.event_ids.includes(131));
  expect(topLine(whole, toward)).toBe('<span class="words">Delphine started calling Corinne every night</span>');
});

// R-0851, R-0782
it("puts ‹‹ First at Back's left in the Family view's row, off on the first meaningful date, and not in the play-by-play", () => {
  const whole = new Told(tl, family(tl), true);
  const first = familyStart(tl, whole.told);
  expect(first).toBeGreaterThan(-1);
  const row = below(whole, whole.length - 1, null, first);
  expect(row).toMatch(/<div class="left"><button class="stepbtn" type="button" data-act="first">‹‹ First<\/button><button class="stepbtn" type="button" data-act="back">/);
  expect(below(whole, first, null, first)).toMatch(/data-act="first" disabled/);
  expect(below(told, 2, null)).not.toContain('data-act="first"');
});

// R-0853
it("fades the not yet born and the marks carried from earlier dates to one value, 0.2, fainter than the 0.3 they had", () => {
  const css = readFileSync(new URL("../src/drawer.css", import.meta.url), "utf8");
  expect(css).toMatch(/\.pbp \{ --faded: 0\.2; \}/);
  expect(css).toContain(".pbp.whole .yet { opacity: var(--faded); }");
  expect(css).toContain(".pbp .draw .was { opacity: var(--faded); }");
});

// "Yes, build that change to reuse the main timeline in the full Diagram view. But we still need to be stepping through the timeline event by event just like we are right now." (Patrick, 2026-10-07)
// R-0796
it("steps the Family view to a tapped cluster's first step, to a tapped event's own step, and to the nearest by date for an event no step holds", () => {
  const whole = new Told(tl, family(tl), true);
  const cluster = tl.clusters[0];
  const first = whole.told.snapshots.findIndex((s) => s.event_ids.some((id) => cluster.event_ids.includes(id)));
  expect(stepOf(whole, when(cluster.start), cluster.event_ids)).toBe(first);
  const j = 3;
  const id = whole.told.snapshots[j].event_ids[0];
  expect(stepOf(whole, 0, [id])).toBe(j);
  expect(stepOf(whole, whole.steps[j].t + 0.01, [-1])).toBe(j);
  expect(shownBy(whole, j)).toBe(id);
});

// R-0742, R-0850
it("spans the whole family's years line over every dated event, this step ringed, earlier solid, later hollow, the current day with no dot of its own", () => {
  const whole = new Told(tl, family(tl), true);
  const line = yearsLine(tl, whole, 3);
  const dated = whole.told.snapshots.filter((s) => s.event_ids.length).length;
  expect(dated).toBe(whole.length - 1);
  expect([...line.matchAll(/class="wnow"/g)]).toHaveLength(1);
  expect([...line.matchAll(/class="wd"/g)]).toHaveLength(3);
  expect([...line.matchAll(/class="wahead"/g)]).toHaveLength(dated - 4);
  expect([...line.matchAll(/class="wd dim"/g)]).toHaveLength(tl.events.length - dated);
  expect(line).toContain(">1948</text>");
  // the line reaches the current day, the last step, past the newest event's 1999
  expect(line).toContain(`>${new Date().getFullYear()}</text>`);
});

// R-0742
it("says each whole family step's date once, over the years line, whole inside its frame at either end", () => {
  // the longest month's name at the line's very start
  const feb = { ...tl, events: tl.events.map((e) => (e.id === 103 ? { ...e, dateTime: "1948-02-01" } : e)) };
  const whole = new Told(feb, family(feb), true);
  expect(whole.steps[0].date).toBe("February 1948");
  [0, whole.length - 1].forEach((i) => {
    const date = whole.steps[i].date;
    expect(topLine(whole, i)).not.toContain(date);
    const x = Number(yearsLine(feb, whole, i).match(/<text class="wlab" x="([\d.]+)"/)![1]);
    // a 12px mono character is at most 7.2 wide
    expect(x - (date.length * 7.2) / 2).toBeGreaterThanOrEqual(0);
    expect(x + (date.length * 7.2) / 2).toBeLessThanOrEqual(390);
  });
});

// R-0778
it("travels to a step's people at about 1,200 px a second, from half a second to two, setting off and landing gently and never passing where it lands", () => {
  const at = Array.from({ length: 101 }, (_, i) => PAN.ease(i / 100));
  expect([PAN.ms(60), PAN.ms(-600), PAN.ms(1200), PAN.ms(2369), PAN.ms(9000)]).toEqual([500, 500, 1000, expect.closeTo(1974, 0), 2000]);
  expect([at[0], at[100]]).toEqual([0, 1]);
  expect(at.every((v, i) => v >= 0 && v <= 1 && (i === 0 || v >= at[i - 1]))).toBe(true);
  expect(at[5]).toBeLessThan(0.01);
  expect(1 - at[95]).toBeLessThan(0.01);
});

// "when I click next in the full family diagram view, the timeline sometimes jumps around to a destination with no selected event visible." (Patrick, 2026-10-07)
// R-0796
it("shows a step on the timeline by an event the line draws, and by none when every date it holds is unknown", () => {
  const unknown = structuredClone(tl);
  const whole = new Told(unknown, family(unknown), true);
  const j = 3;
  const id = whole.told.snapshots[j].event_ids[0];
  unknown.events.find((e) => e.id === id)!.dateCertainty = DateCertainty.Unknown;
  expect(shownBy(whole, j)).toBe(whole.told.snapshots[j].event_ids.find((other) => other !== id) ?? null);
});
