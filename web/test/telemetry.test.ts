import { beforeEach, expect, it, vi } from "vitest";

const sent = vi.fn((_url: string, _init: RequestInit) => Promise.resolve(new Response(null, { status: 204 })));
vi.stubGlobal("fetch", sent);
vi.stubGlobal("location", { pathname: "/app/" });
vi.stubGlobal("window", { BOOTSTRAP: { version: "3.2026.10.6.1" } });
const page = new EventTarget();
vi.stubGlobal("addEventListener", page.addEventListener.bind(page));

const { ERRORS_URL, RESIZE_NOTICE, Source } = await import("../src/telemetry");

beforeEach(() => sent.mockClear());

function fire(type: string, fields: object): void {
  page.dispatchEvent(Object.assign(new Event(type), fields));
}

function body(): Record<string, unknown> {
  const [url, init] = sent.mock.calls[0];
  expect(url).toBe(ERRORS_URL);
  return JSON.parse(init.body as string);
}

// R-0370
it("posts an uncaught error to the page's own server, never to an outside collector", () => {
  fire("error", { error: new TypeError("x is undefined"), message: "x is undefined" });
  expect(ERRORS_URL.startsWith("/")).toBe(true);
  expect(body()).toMatchObject({
    source: Source.Error,
    message: "TypeError: x is undefined",
    address: "/app/",
    release: "3.2026.10.6.1",
  });
});

// R-0370
it("posts a rejected promise with what it was rejected with", () => {
  fire("unhandledrejection", { reason: "timed out" });
  expect(body()).toMatchObject({ source: Source.Rejection, message: "timed out" });
});

// R-0370
it("posts a real error but not the browser's notice of a resize put off a frame", () => {
  fire("error", { error: null, message: RESIZE_NOTICE });
  expect(sent).not.toHaveBeenCalled();
  fire("error", { error: new Error("broke"), message: "broke" });
  expect(body()).toMatchObject({ source: Source.Error, message: "Error: broke" });
});
