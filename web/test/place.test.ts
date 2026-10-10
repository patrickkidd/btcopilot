import { describe, expect, it } from "vitest";
import { address, APP, beyond, linked, on, parse, Place, settled, split, UNDATED } from "../src/place";
import { Link } from "../src/types";

/** A value for each kind of slot, so every place can be written out. */
const SAMPLE: Record<string, string[]> = {
  ":n": ["42", "7"],
  ":key": ["c-3f9a"],
  ":day": ["2026-10-06", UNDATED],
};

/** A diagram's public id, as the server makes them. */
const KEY = "k7m2x9pq4w";

/** Every address one place can have, with its slots filled each way. */
function addresses(place: Place): string[][] {
  const slots = place.split("/").filter((part) => part in SAMPLE);
  return slots.reduce<string[][]>(
    (all, slot) => all.flatMap((args) => SAMPLE[slot].map((one) => [...args, one])),
    [[]],
  );
}

describe("the addresses of the app", () => {
  // R-0055
  it("reads every address in the table back as the place and values it was written from", () => {
    for (const place of Object.values(Place))
      for (const args of addresses(place)) {
        const at = address(place, ...args);
        expect(parse(at)).toEqual({ place, args, diagram: null });
        expect(parse(`${at}/`)).toEqual({ place, args, diagram: null });
      }
  });

  // R-0055
  it("gives every place its own address", () => {
    const all = Object.values(Place).flatMap((place) =>
      addresses(place).map((args) => address(place, ...args)),
    );
    expect(new Set(all).size).toBe(all.length);
  });

  // R-0714
  it("gives the case report its own address", () => {
    expect(address(Place.CaseReport)).toBe("/app/case-report");
  });

  // R-0055
  it("reads no place from an address the app does not have", () => {
    for (const path of ["/app/nowhere", "/app/chat/abc", "/elsewhere/", "/app/account/meeting/soon"])
      expect(parse(path)).toBeNull();
  });

  // R-0055
  it("names the view a lit item sits in once its light has faded", () => {
    expect(settled(address(Place.Session, 5))).toBe(address(Place.Sessions));
    expect(settled(address(Place.Message, 9))).toBe(APP);
    expect(settled(address(Place.MeetingCut, "2026-10-06", 3))).toBe(
      address(Place.MeetingDay, "2026-10-06"),
    );
    expect(settled(address(Place.Coach))).toBe(address(Place.Coach));
    expect(settled(address(Place.Notice, 4))).toBe(address(Place.Notices));
  });

  // R-0055
  it("takes a notice's link as a fixed screen's name or an address", () => {
    expect(linked(Link.Coach)).toBe(address(Place.Coach));
    expect(linked("/app/account/notices")).toBe("/app/account/notices");
  });

  // R-0055
  it("names where a notice's link goes, and nothing for the account view or its Notices, which hold the notice already", () => {
    expect(beyond(Link.Coach)).toBe("Coach settings");
    expect(beyond(address(Place.Literature))).toBe("Auditor's Coding Guide");
    for (const link of [null, Link.Account, address(Place.Notices), address(Place.Notice, 4)])
      expect(beyond(link)).toBeNull();
  });
});

describe("the diagram every address is on", () => {
  // R-0NNN
  it("writes every place under the diagram the app is on, by its public id, never its number", () => {
    expect(on(KEY, address(Place.Chat))).toBe(`/app/diagram/${KEY}/`);
    expect(on(KEY, address(Place.Coach))).toBe(`/app/diagram/${KEY}/account/coach`);
    expect(on(KEY, address(Place.FamilyStep, 3))).toBe(`/app/diagram/${KEY}/family/3`);
    for (const place of Object.values(Place))
      for (const args of addresses(place)) {
        const at = on(KEY, address(place, ...args));
        expect(at.startsWith(`/app/diagram/${KEY}`)).toBe(true);
        expect(parse(at)).toEqual({ place, args, diagram: KEY });
      }
  });

  // R-0NNN
  it("reads a diagram's address back as its public id and the place under it", () => {
    expect(split(`/app/diagram/${KEY}/account/coach`)).toEqual({ diagram: KEY, under: "/app/account/coach" });
    expect(split(`/app/diagram/${KEY}`)).toEqual({ diagram: KEY, under: "/app" });
    expect(split(`/app/diagram/${KEY}/?notification=4`)).toEqual({ diagram: KEY, under: "/app/" });
    expect(parse(`/app/diagram/${KEY}`)).toEqual({ place: Place.Chat, args: [], diagram: KEY });
    expect(parse(`/app/diagram/${KEY}/`)).toEqual({ place: Place.Chat, args: [], diagram: KEY });
    expect(parse(`/app/diagram/${KEY}/cluster/c-3f9a`)).toEqual({
      place: Place.Cluster,
      args: ["c-3f9a"],
      diagram: KEY,
    });
    // the word alone, or a key of a shape the server never makes, is no address
    for (const path of ["/app/diagram", "/app/diagram/", "/app/diagram/K7/account", "/app/diagrams/3"])
      expect(parse(path)).toBeNull();
  });

  // R-0NNN
  it("reads an address without a diagram as that place on the diagram the app is on", () => {
    expect(split("/app/account/coach")).toEqual({ diagram: null, under: "/app/account/coach" });
    expect(parse("/app/")).toEqual({ place: Place.Chat, args: [], diagram: null });
    expect(parse("/app/?notification=4")).toEqual({ place: Place.Chat, args: [], diagram: null });
    expect(on(KEY, "/app/account/coach")).toBe(`/app/diagram/${KEY}/account/coach`);
    // an address already on a diagram is moved to the one the app is on
    expect(on(KEY, "/app/diagram/zzzz2222zz/account")).toBe(`/app/diagram/${KEY}/account`);
    // with no diagram open yet there is nothing to be under
    expect(on(null, `/app/diagram/${KEY}/account`)).toBe("/app/account");
  });

  // R-0NNN
  it("keeps the diagram when a lit item settles into its view", () => {
    expect(settled(on(KEY, address(Place.Session, 5)))).toBe(on(KEY, address(Place.Sessions)));
    expect(settled(on(KEY, address(Place.Message, 9)))).toBe(`/app/diagram/${KEY}/`);
    expect(settled(on(KEY, address(Place.Coach)))).toBe(on(KEY, address(Place.Coach)));
  });
});
