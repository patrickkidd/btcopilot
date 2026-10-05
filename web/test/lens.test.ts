import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

const source = (name: string) => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");

// R-0711
it("leaves the chat screen with no picture controller of its own", () => {
  const main = source("main.ts");
  expect(main).not.toContain("new Picture(");
  expect(main).toContain("new Lens(");
});

// R-0711
it("keeps one width at which the app widens", () => {
  const all = ["main.ts", "pro.ts", "viewport.ts", "pairs.ts", "lens.ts", "casereport.ts"].map(source).join("\n");
  expect(all.match(/min-width: 840px/g)).toHaveLength(1);
});
