import { afterEach, expect, it, vi } from "vitest";
import { call } from "../src/api";

afterEach(() => vi.unstubAllGlobals());

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
