import { expect, it } from "vitest";
import { Failed } from "../src/api";
import { endpoint, Faults, NOISE } from "../src/faults";

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
  expect(new Faults(ORIGIN).key(error, error.message)).toBeNull();
});

// R-0056
it("keeps an error thrown by the app's own bundle, keyed by its message and top frame", () => {
  const error = thrown(
    "x is undefined",
    `draw (${BUNDLE}:1:52301)`,
    "inject (chrome-extension://abcdef/content.js:4:11)",
  );
  expect(new Faults(ORIGIN).key(error, error.message)).toBe(`x is undefined\n${BUNDLE}:1:52301`);
});

// R-0056
it("ignores an error with no stack, one from another origin, and the dev server's packages", () => {
  const faults = new Faults(ORIGIN);
  expect(faults.key(null, "Script error.")).toBeNull();
  const bare = new TypeError("x is undefined");
  bare.stack = undefined;
  expect(faults.key(bare, bare.message)).toBeNull();
  const elsewhere = thrown("x is undefined", "draw (https://cdn.example.com/app/static/web/a.js:1:2)");
  expect(faults.key(elsewhere, elsewhere.message)).toBeNull();
  const vendored = thrown(
    "x is undefined",
    `send (${ORIGIN}/app/static/web/node_modules/.vite/deps/faro.js:9:1)`,
  );
  expect(faults.key(vendored, vendored.message)).toBeNull();
});

// R-0056
it("ignores the noise, the server breaking, and anything once the page is going away", () => {
  const faults = new Faults(ORIGIN);
  for (const noise of NOISE) {
    const error = thrown(noise, `draw (${BUNDLE}:1:2)`);
    expect(faults.key(error, noise)).toBeNull();
  }
  const cancelled = new DOMException("signal is aborted without reason", "AbortError");
  expect(faults.key(cancelled, cancelled.message)).toBeNull();
  expect(faults.key(new Failed(500, "GET /app/timeline", "boom"), "boom")).toBeNull();

  const error = thrown("x is undefined", `draw (${BUNDLE}:1:2)`);
  faults.leaving = true;
  expect(faults.key(error, error.message)).toBeNull();
});

// R-0056
it("raises each error once per page and counts the repeats", () => {
  const faults = new Faults(ORIGIN);
  const one = faults.key(thrown("x is undefined", `draw (${BUNDLE}:1:2)`), "x is undefined")!;
  const other = faults.key(thrown("x is undefined", `place (${BUNDLE}:1:9)`), "x is undefined")!;
  expect(faults.first(one)).toBe(true);
  expect(faults.first(one)).toBe(false);
  expect(faults.first(one)).toBe(false);
  expect(faults.seen.get(one)).toBe(3);
  expect(faults.first(other)).toBe(true);
  expect(faults.first(endpoint("GET /app/sessions/12"))).toBe(true);
  expect(faults.first(endpoint("GET /app/sessions/13"))).toBe(false);
});
