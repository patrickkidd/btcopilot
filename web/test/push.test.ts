import { expect, it } from "vitest";
import { plan, Plan, reach, Reach, type Device } from "../src/push";

const at = (d: Partial<Device>): Device => ({
  supported: true,
  installed: true,
  permission: "default",
  saved: false,
  declined: false,
  ...d,
});

// R-0832
it("asks with the card once the app is installed and nobody has been asked, and never in a browser tab or after Not now", () => {
  expect(plan(at({}))).toBe(Plan.Card);
  expect(plan(at({ installed: false }))).toBe(Plan.Nothing);
  expect(plan(at({ declined: true }))).toBe(Plan.Nothing);
  expect(plan(at({ permission: "denied" }))).toBe(Plan.Nothing);
  expect(plan(at({ supported: false }))).toBe(Plan.Nothing);
});

// R-0832
it("subscribes again without asking where permission was given and no subscription is saved, installed or not", () => {
  expect(plan(at({ permission: "granted" }))).toBe(Plan.Quiet);
  expect(plan(at({ permission: "granted", installed: false, declined: true }))).toBe(Plan.Quiet);
  expect(plan(at({ permission: "granted", saved: true }))).toBe(Plan.Nothing);
});

// R-0832
it("says on, off, blocked or not available for this device", () => {
  expect(reach(at({ permission: "granted", saved: true }))).toBe(Reach.On);
  expect(reach(at({ permission: "granted" }))).toBe(Reach.Off);
  expect(reach(at({}))).toBe(Reach.Off);
  expect(reach(at({ permission: "denied" }))).toBe(Reach.Blocked);
  expect(reach(at({ supported: false }))).toBe(Reach.Unavailable);
});
