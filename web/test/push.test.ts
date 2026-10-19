import { beforeEach, expect, it, vi } from "vitest";
import { answer, device, landing, plan, Plan, reach, Reach, type Device } from "../src/push";
import { Failed, openNotification } from "../src/api";

vi.mock("../src/track", () => ({ Feature: { NotificationsOn: "on" }, tap: () => {} }));
vi.mock("../src/api", () => ({
  call: () => new Promise(() => {}),
  openNotification: vi.fn(),
  Failed: class extends Error {
    constructor(readonly status: number) {
      super(String(status));
    }
  },
}));

const at = (d: Partial<Device>): Device => ({
  supported: true,
  installed: true,
  permission: "default",
  saved: false,
  asked: false,
  ...d,
});

// R-0832
it("asks with the card once the app is installed and nobody has been asked, and never in a browser tab or after it was answered", () => {
  expect(plan(at({}))).toBe(Plan.Card);
  expect(plan(at({ installed: false }))).toBe(Plan.Nothing);
  expect(plan(at({ asked: true }))).toBe(Plan.Nothing);
  expect(plan(at({ permission: "denied" }))).toBe(Plan.Nothing);
  expect(plan(at({ supported: false }))).toBe(Plan.Nothing);
});

// R-0832
it("subscribes again without asking where permission was given and no subscription is saved, installed or not", () => {
  expect(plan(at({ permission: "granted" }))).toBe(Plan.Quiet);
  expect(plan(at({ permission: "granted", installed: false, asked: true }))).toBe(Plan.Quiet);
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

/** An iPhone's home-screen app: no display-mode match, only navigator.standalone. */
function phone(standalone: boolean, says: NotificationPermission = "default") {
  const stored = new Map<string, string>();
  const requestPermission = vi.fn(async () => says);
  vi.stubGlobal("window", {
    PushManager: class {},
    Notification: { permission: "default", requestPermission },
    matchMedia: () => ({ matches: false }),
    localStorage: {
      getItem: (k: string) => stored.get(k) ?? null,
      setItem: (k: string, v: string) => void stored.set(k, v),
    },
  });
  vi.stubGlobal("Notification", window.Notification);
  vi.stubGlobal("navigator", { standalone, serviceWorker: {} });
  return requestPermission;
}

beforeEach(() => vi.unstubAllGlobals());

// R-0832
it("asks once on a home-screen iPhone, with the system question inside the tap, and not again after it is dismissed", async () => {
  const requestPermission = phone(true);
  expect(plan(await device())).toBe(Plan.Card);
  answer(true);
  expect(requestPermission).toHaveBeenCalledTimes(1);
  await Promise.resolve();
  expect(plan(await device())).toBe(Plan.Nothing);
});

// R-0832
it("never asks in a browser tab, and Not now spends the ask too", async () => {
  phone(false);
  expect(plan(await device())).toBe(Plan.Nothing);
  const requestPermission = phone(true);
  answer(false);
  expect(requestPermission).not.toHaveBeenCalled();
  expect(plan(await device())).toBe(Plan.Nothing);
});

// R-0614
it("opens the app on a tapped push whose notification row is gone, with nothing rejected", async () => {
  const rejected = vi.fn();
  process.on("unhandledRejection", rejected);
  vi.mocked(openNotification).mockRejectedValueOnce(new (Failed as any)(404));
  vi.stubGlobal("location", { search: "?notification=15", pathname: "/app/", hash: "" });
  vi.stubGlobal("history", { replaceState: vi.fn() });
  vi.stubGlobal("navigator", {});
  const land = vi.fn(async () => {});
  landing(land);
  await new Promise((r) => setTimeout(r, 0));
  process.off("unhandledRejection", rejected);
  expect(openNotification).toHaveBeenCalledWith(15);
  expect(land).not.toHaveBeenCalled();
  expect(rejected).not.toHaveBeenCalled();
});
