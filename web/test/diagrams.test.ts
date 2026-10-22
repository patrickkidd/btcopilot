import { afterEach, expect, it, vi } from "vitest";
import { newDiagram, renameDiagram } from "../src/api";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

function sent(): { method: string; url: string; body: unknown }[] {
  const calls: { method: string; url: string; body: unknown }[] = [];
  vi.stubGlobal("document", { querySelector: () => ({ content: "served" }) });
  vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
    calls.push({ method: init.method ?? "GET", url, body: JSON.parse(init.body as string) });
    return new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } });
  });
  return calls;
}

// R-PENDING-387-7
it("a new diagram is made with its name and the answer to whether it is the maker's own family", async () => {
  const calls = sent();
  await newDiagram("The Hales", true);
  await newDiagram("A client's family", false);
  expect(calls.map((c) => [c.method, c.body])).toEqual([
    ["POST", { name: "The Hales", own_family: true }],
    ["POST", { name: "A client's family", own_family: false }],
  ]);
  expect(calls.every((c) => c.url.endsWith("/diagrams"))).toBe(true);
});

// R-PENDING-387-7
it("a diagram is renamed through the diagram's own address", async () => {
  const calls = sent();
  await renameDiagram(42, "The Hale family");
  expect(calls).toHaveLength(1);
  expect(calls[0].method).toBe("PATCH");
  expect(calls[0].url.endsWith("/diagrams/42")).toBe(true);
  expect(calls[0].body).toEqual({ name: "The Hale family" });
});

// R-PENDING-387-7
it("the list of diagrams and the question are the same words for everyone, licence or none", async () => {
  for (const pro of [true, false]) {
    vi.resetModules();
    vi.stubGlobal("window", { BOOTSTRAP: { user: { pro } } });
    const words = await import("../src/pro");
    expect([words.DIAGRAMS, words.OWN_FAMILY]).toEqual(["Diagrams", "Is this your own family?"]);
  }
});
