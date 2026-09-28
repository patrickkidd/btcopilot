import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";

const SOURCE = readFileSync(new URL("../public/sw.js", import.meta.url), "utf8");

/** The worker as the browser starts it for one release, with the caches the
 * phone already holds. */
function worker(release: string, held: string[]) {
  const on: Record<string, (e: unknown) => void> = {};
  const caches = {
    keys: async () => held,
    delete: vi.fn(async () => true),
  };
  runInNewContext(SOURCE, {
    URL,
    caches,
    self: {
      location: { href: `https://familydiagram.com/app/sw.js?release=${release}` },
      addEventListener: (kind: string, run: (e: unknown) => void) => (on[kind] = run),
      clients: { claim: async () => undefined },
    },
  });
  return { on, caches };
}

describe("the offline copy of the app", () => {
  // R-0486
  it("keeps only the release it serves, deleting the last one's files", async () => {
    const { on, caches } = worker("3.2026.9.28.1", [
      "familydiagram-3.2026.9.27.1",
      "familydiagram-3.2026.9.28.1",
    ]);
    let done: Promise<unknown> = Promise.resolve();
    on.activate({ waitUntil: (work: Promise<unknown>) => (done = work) });
    await done;
    expect(caches.delete.mock.calls).toEqual([["familydiagram-3.2026.9.27.1"]]);
  });
});
