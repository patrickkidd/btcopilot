import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/** The review screens are kept apart from the chat app in the import graph,
 * so a change to them cannot reach the chat, the picture, the lists or the
 * settings except through the one file that wires the screens together. */

const SRC = join(dirname(fileURLToPath(import.meta.url)), "../src");

const REVIEW = ["agenda", "ballot", "coding", "cut", "meeting", "result", "rules", "task"];
const CORE = [
  "board", "caption", "chat", "chips", "editor", "menu", "picture", "recording",
  "rows", "search", "sessions", "settings", "speech", "turn",
];

const imports = (name: string): string[] =>
  [...readFileSync(join(SRC, `${name}.ts`), "utf8").matchAll(/(?:from|import)\s+"\.\/(\w+)"/g)].map(
    (m) => m[1],
  );

/** Everything one module pulls in, however far down. */
function reach(name: string, seen = new Set<string>()): Set<string> {
  for (const next of imports(name))
    if (!seen.has(next)) {
      seen.add(next);
      reach(next, seen);
    }
  return seen;
}

describe("the review screens in the import graph", () => {
  // R-0245
  it("no chat-app module pulls in a review screen, however indirectly", () => {
    const leaks = CORE.flatMap((core) =>
      [...reach(core)].filter((one) => REVIEW.includes(one)).map((one) => `${core} -> ${one}`),
    );
    expect(leaks).toEqual([]);
  });

  // R-0245
  it("only the entry point and the review screens themselves import a review screen", () => {
    const modules = readdirSync(SRC)
      .filter((f) => f.endsWith(".ts"))
      .map((f) => f.slice(0, -3));
    const importers = modules
      .filter((one) => imports(one).some((next) => REVIEW.includes(next)))
      .filter((one) => !REVIEW.includes(one));
    expect(importers).toEqual(["main"]);
  });
});
