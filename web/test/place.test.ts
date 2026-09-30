import { describe, expect, it } from "vitest";
import { address, APP, beyond, linked, parse, Place, settled, UNDATED } from "../src/place";
import { Link } from "../src/types";

/** A value for each kind of slot, so every place can be written out. */
const SAMPLE: Record<string, string[]> = {
  ":n": ["42", "7"],
  ":key": ["c-3f9a"],
  ":day": ["2026-10-06", UNDATED],
};

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
        expect(parse(at)).toEqual({ place, args });
        expect(parse(`${at}/`)).toEqual({ place, args });
      }
  });

  // R-0055
  it("gives every place its own address", () => {
    const all = Object.values(Place).flatMap((place) =>
      addresses(place).map((args) => address(place, ...args)),
    );
    expect(new Set(all).size).toBe(all.length);
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
