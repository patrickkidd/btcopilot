import { expect, it } from "vitest";
import { endpoint, Failed } from "../src/api";
import { Faults, NOISE } from "../src/faults";

const ORIGIN = "https://familydiagram.com";
const BUNDLE = `${ORIGIN}/app/static/web/assets/index-B26jI9NK.js`;

const thrown = (message: string, ...frames: string[]) => {
  const error = new TypeError(message);
  error.stack = [`TypeError: ${message}`, ...frames.map((frame) => `    at ${frame}`)].join("\n");
  return error;
};

// R-0056
it("ignores an error thrown by a browser extension", () => {
  const error = thrown("x is undefined", "inject (chrome-extension://abcdef/content.js:4:11)");
  expect(new Faults(ORIGIN).fault(error, error.message)).toBeNull();
});

// R-0056
it("keeps an error thrown by the app's own bundle with only its own frames, raised by its name, message and first own frame", () => {
  const error = thrown(
    "x is undefined",
    "inject (chrome-extension://abcdef/content.js:4:11)",
    `draw (${BUNDLE}:1:52301)`,
    `place (${BUNDLE}:1:90)`,
  );
  expect(new Faults(ORIGIN).fault(error, `Uncaught ${error}`)).toEqual({
    signature: `TypeError: x is undefined\n${BUNDLE}:1:52301`,
    error: "TypeError: x is undefined",
    frames: [`${BUNDLE}:1:52301`, `${BUNDLE}:1:90`],
  });
});

// R-0056
it("keeps an error naming no script, and drops one whose every frame is another origin's or a package's", () => {
  const faults = new Faults(ORIGIN);
  const refused = new DOMException("The operation either timed out or was not allowed.", "NotAllowedError");
  refused.stack = undefined;
  expect(faults.fault(refused, refused.message)).toEqual({
    signature: "NotAllowedError: The operation either timed out or was not allowed.\n",
    error: "NotAllowedError: The operation either timed out or was not allowed.",
    frames: [],
  });
  expect(faults.fault("not-allowed", "not-allowed")?.error).toBe("not-allowed");
  const elsewhere = thrown("x is undefined", "draw (https://cdn.example.com/app/static/web/a.js:1:2)");
  expect(faults.fault(elsewhere, elsewhere.message)).toBeNull();
  const vendored = thrown(
    "x is undefined",
    `send (${ORIGIN}/app/static/web/node_modules/.vite/deps/faro.js:9:1)`,
  );
  expect(faults.fault(vendored, vendored.message)).toBeNull();
});

// R-0056
it("ignores the noise, any failed request, and anything once the page is going away", () => {
  const faults = new Faults(ORIGIN);
  for (const noise of NOISE) {
    const error = thrown(noise, `draw (${BUNDLE}:1:2)`);
    expect(faults.fault(error, noise)).toBeNull();
  }
  expect(faults.fault(null, "Script error.")).toBeNull();
  const cancelled = new DOMException("signal is aborted without reason", "AbortError");
  expect(faults.fault(cancelled, cancelled.message)).toBeNull();
  for (const status of [0, 404, 500]) {
    const failed = new Failed(status, "GET /app/timeline", "boom");
    expect(faults.fault(failed, failed.message)).toBeNull();
  }

  const error = thrown("x is undefined", `draw (${BUNDLE}:1:2)`);
  faults.leaving = true;
  expect(faults.fault(error, error.message)).toBeNull();
});

// R-0056
it("raises each error once per page and counts the repeats", () => {
  const faults = new Faults(ORIGIN);
  const one = faults.fault(thrown("x is undefined", `draw (${BUNDLE}:1:2)`), "")!.signature;
  const other = faults.fault(thrown("x is undefined", `place (${BUNDLE}:1:9)`), "")!.signature;
  expect(faults.first(one)).toBe(true);
  expect(faults.first(one)).toBe(false);
  expect(faults.first(one)).toBe(false);
  expect(faults.seen.get(one)).toBe(3);
  expect(faults.first(other)).toBe(true);
  expect(endpoint("/app/sessions/12/statements")).toBe("/app/sessions/:id/statements");
  expect(endpoint("/app/items/7")).toBe("/app/items/:id");
});
