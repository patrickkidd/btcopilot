import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";

const SOURCE = readFileSync(new URL("../public/sw.js", import.meta.url), "utf8");

/** A window the browser has open, as the worker sees it. */
function tab(url: string) {
  return { url, postMessage: vi.fn(), focus: vi.fn(async () => undefined) };
}

/** The worker as the browser starts it for one release, with the caches the
 * phone already holds and the windows it has open. */
function worker(release: string, held: string[] = [], windows: ReturnType<typeof tab>[] = []) {
  const on: Record<string, (e: unknown) => void> = {};
  const caches = {
    keys: async () => held,
    delete: vi.fn(async () => true),
  };
  const shown = vi.fn(async (_title: string, _options: NotificationOptions) => undefined);
  const openWindow = vi.fn(async (_url: string) => undefined);
  runInNewContext(SOURCE, {
    URL,
    caches,
    self: {
      location: { href: `https://familydiagram.com/app/sw.js?release=${release}` },
      addEventListener: (kind: string, run: (e: unknown) => void) => (on[kind] = run),
      registration: { showNotification: shown, navigationPreload: { enable: async () => undefined } },
      clients: { claim: async () => undefined, matchAll: async () => windows, openWindow },
    },
  });
  /** One event, and the work it asked the browser to wait for. */
  const fire = (kind: string, event: object) => {
    let done: Promise<unknown> = Promise.resolve();
    on[kind]({ ...event, waitUntil: (work: Promise<unknown>) => (done = work) });
    return done;
  };
  return { fire, caches, shown, openWindow };
}

const tap = (id: number) => ({ notification: { data: { id }, close: vi.fn() } });

describe("the offline copy of the app", () => {
  // R-0486
  it("keeps only the release it serves, deleting the last one's files", async () => {
    const { fire, caches } = worker("3.2026.9.28.1", [
      "familydiagram-3.2026.9.27.1",
      "familydiagram-3.2026.9.28.1",
    ]);
    await fire("activate", {});
    expect(caches.delete.mock.calls).toEqual([["familydiagram-3.2026.9.27.1"]]);
  });
});

describe("a coach notification", () => {
  // R-0055
  it("shows the push's words under its kind's tag, so kinds never replace each other", async () => {
    const { fire, shown } = worker("1");
    for (const [id, kind, body] of [
      [7, "coach", "Your mother called."],
      [8, "task", "A coding task is waiting for you."],
      [9, "coach", "Sunday came up again."],
    ] as const)
      await fire("push", { data: { json: () => ({ id, kind, body }) } });
    expect(shown.mock.calls.map(([title, o]) => [title, o.body, o.tag, o.data])).toEqual([
      ["Coach", "Your mother called.", "coach", { id: 7 }],
      ["Coding task", "A coding task is waiting for you.", "task", { id: 8 }],
      ["Coach", "Sunday came up again.", "coach", { id: 9 }],
    ]);
  });

  // R-0055
  it("opens the app at the message it points to when the app is closed", async () => {
    const { fire, openWindow } = worker("1");
    await fire("notificationclick", tap(7));
    expect(openWindow.mock.calls).toEqual([["/app/?notification=7"]]);
  });

  // R-0055
  it("tells the open app which message to show, so a draft in it survives", async () => {
    const open = tab("https://familydiagram.com/app/");
    const { fire, openWindow } = worker("1", [], [open]);
    await fire("notificationclick", tap(7));
    expect(open.postMessage.mock.calls).toEqual([[{ notification: 7 }]]);
    expect(open.focus).toHaveBeenCalled();
    expect(openWindow).not.toHaveBeenCalled();
  });
});
