import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { Part, Store, type Opened } from "../src/store";
import { Access } from "../src/types";

/** The server, answering each request when the test says so; an aborted
 * request fails the way a browser's does. */
interface Asked {
  url: string;
  answer: (body: unknown) => void;
  aborted: boolean;
}

let asked: Asked[] = [];

beforeEach(() => {
  asked = [];
  vi.stubGlobal("document", { querySelector: () => null });
  vi.stubGlobal(
    "fetch",
    (url: string, init: RequestInit) =>
      new Promise((resolve, reject) => {
        const one: Asked = {
          url,
          answer: (body) =>
            resolve(new Response(JSON.stringify(body), { status: 200 })),
          aborted: false,
        };
        init.signal?.addEventListener("abort", () => {
          one.aborted = true;
          reject(new DOMException("aborted", "AbortError"));
        });
        asked.push(one);
      }),
  );
});

afterEach(() => vi.unstubAllGlobals());

const diagram = (id: number, access = Access.Own) => ({
  id,
  name: `Family ${id}`,
  session_count: 0,
  last_activity: null,
  free: false,
  owned: true,
  access,
  owner: "Pat",
});

/** Answer every open request for one diagram by what it asks for. */
function answer(id: number, access = Access.Own): void {
  for (const one of asked.filter((a) => a.url.includes(`${id}`))) {
    if (one.url.includes("/select")) one.answer(diagram(id, access));
    else if (one.url.includes("/timeline")) one.answer({ people: [], events: [], id });
    else one.answer([]);
  }
  asked = asked.filter((a) => !a.url.includes(`${id}`));
}

const flush = () => new Promise((r) => setTimeout(r, 0));

/** What each screen was told, in order. */
function screens(store: Store): string[] {
  const told: string[] = [];
  store.watch({
    reset: () => void told.push("reset"),
    draw: (opened: Opened, parts) =>
      void told.push(`draw ${opened.diagram?.id} ${parts.join(",")}`),
  });
  return told;
}

// R-0243
it("opens a diagram by its id: every part read naming it, every screen emptied first and then drawn", async () => {
  const store = new Store();
  const told = screens(store);
  const opening = store.open(7);
  expect(told).toEqual(["reset"]);
  expect(asked.map((a) => a.url).sort()).toEqual([
    "/app/diagrams/7/select",
    "/app/sessions?diagram_id=7",
    "/app/statements?diagram_id=7",
    "/app/timeline?diagram_id=7",
  ]);
  answer(7);
  expect(await opening).toBe(true);
  expect(told).toEqual(["reset", "draw 7 record,thread,sittings"]);
  expect(store.current().diagram?.name).toBe("Family 7");
});

// R-0243
it("draws only the last of two quick opens, and cancels what the first was still reading", async () => {
  const store = new Store();
  const told = screens(store);
  const first = store.open(1);
  const second = store.open(2);
  answer(2);
  expect(await second).toBe(true);
  expect(await first).toBe(false);
  expect(asked.map((a) => a.aborted)).toEqual([true, true, true, true]);
  expect(told).toEqual(["reset", "reset", "draw 2 record,thread,sittings"]);
});

// R-0243
it("drops a part read again for a diagram that is no longer open", async () => {
  const store = new Store();
  const told = screens(store);
  const opening = store.open(1);
  answer(1);
  await opening;
  const older = store.refresh(Part.Thread);
  await flush();
  void store.open(2);
  expect(await older).toBe(false);
  answer(2);
  await flush();
  expect(told.filter((t) => t.startsWith("draw 1"))).toHaveLength(1);
});

// R-0369
it("closes the running turn's stream when another diagram opens", () => {
  const store = new Store();
  const stream = { close: vi.fn() };
  store.hold(stream as unknown as EventSource);
  const still = store.live();
  void store.open(2);
  expect(stream.close).toHaveBeenCalledOnce();
  expect(still()).toBe(false);
});

// R-0243
it("says a diagram an admin only looks at is read-only, from the diagram it opened", async () => {
  const store = new Store();
  const opening = store.open(9);
  answer(9, Access.AdminView);
  await opening;
  expect(store.readOnly()).toBe(true);
  void store.open(3);
  expect(store.readOnly()).toBe(false);
});
