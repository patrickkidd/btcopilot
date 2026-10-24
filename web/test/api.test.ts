import { afterEach, expect, it, vi } from "vitest";
import { call, cut, Failed, say, scribe } from "../src/api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

/** An answer that comes back after `ms`, or not at all once the page gives up. */
const answerAfter = (ms: number, json: unknown) =>
  vi.stubGlobal(
    "fetch",
    (_url: string, init: RequestInit) =>
      new Promise((done, fail) => {
        const at = setTimeout(
          () => done(new Response(JSON.stringify(json), { status: 200, headers: { "Content-Type": "application/json" } })),
          ms,
        );
        init.signal!.addEventListener("abort", () => {
          clearTimeout(at);
          fail(new DOMException("The operation timed out.", "TimeoutError"));
        });
      }),
  );

// R-0869, R-0883
it("waits for a slow scribe past the page's minute, so what it wrote lands as written, not as not saved", async () => {
  vi.useFakeTimers();
  // the page's own limit, on the clock the test moves
  vi.spyOn(AbortSignal, "timeout").mockImplementation((ms: number) => {
    const gate = new AbortController();
    setTimeout(() => gate.abort(), ms);
    return gate.signal;
  });
  vi.stubGlobal("document", { querySelector: () => ({ content: "served" }) });
  const written = { lines: [{ verb: "add", text: "Client" }], refused: [], made: [], choices: [] };

  answerAfter(84_000, written);
  const slow = scribe(4, 3, "Client has been sleeping badly since 2019");
  await vi.advanceTimersByTimeAsync(84_000);
  await expect(slow).resolves.toEqual(written);

  answerAfter(84_000, {});
  const other = cut(1).catch((error: unknown) => error);
  await vi.advanceTimersByTimeAsync(60_000);
  expect(await other).toBeInstanceOf(Failed);
});

// R-0760
it("sends the browser's time zone with each message, so the coach's today is the person's", async () => {
  vi.stubGlobal("document", { querySelector: () => ({ content: "served" }) });
  const bodies: Record<string, unknown>[] = [];
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    bodies.push(JSON.parse(init.body as string));
    return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
  });
  await say(null, "My dad turns 70 tomorrow.");
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  expect(zone).toBeTruthy();
  expect(bodies).toEqual([{ statement: "My dad turns 70 tomorrow.", time_zone: zone }]);
});

// R-0738
it("writes with the CSRF token of the newest answer, not the one the page was served with", async () => {
  vi.stubGlobal("document", { querySelector: () => ({ content: "served" }) });
  const sent: (string | null)[] = [];
  vi.stubGlobal("fetch", async (_url: string, init: RequestInit) => {
    sent.push(new Headers(init.headers).get("X-CSRFToken"));
    return new Response("{}", { status: 200, headers: { "Content-Type": "application/json", "X-CSRFToken": `fresh-${sent.length}` } });
  });
  await call("GET", "/timeline");
  await call("POST", "/diagrams", { name: "x" });
  await call("POST", "/diagrams", { name: "y" });
  expect(sent).toEqual(["served", "fresh-1", "fresh-2"]);
});
