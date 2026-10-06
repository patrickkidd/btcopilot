import { afterEach, expect, it, vi } from "vitest";
import { call, say } from "../src/api";

afterEach(() => vi.unstubAllGlobals());

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
