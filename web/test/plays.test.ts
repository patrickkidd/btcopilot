import { expect, it } from "vitest";
import { reopen, type Kept } from "../src/plays";
import { apart, timeline } from "./whitlock";

/** A tap on a play-by-play already on the thread. */

const clusters = timeline().clusters;

function tap(kept: Kept): string[] {
  const done: string[] = [];
  reopen(
    kept,
    clusters,
    (told) => done.push(`open ${told.cluster_id}`),
    (id) => done.push(`explain ${id}`),
  );
  return done;
}

// Pending ruling (Patrick, 2026-09-28): one play-by-play per cluster is kept
// until its events change.
// R-0542, R-0563
it("opens a play told from what its cluster holds now, with no call", () => {
  expect(tap({ case: apart(), digest: "apart-now" })).toEqual(["open apart"]);
});

// Pending ruling (Patrick, 2026-09-28), as above.
// R-0542, R-0563
it("explains the cluster again when its events changed since the play was told", () => {
  expect(tap({ case: apart(), digest: "apart-before" })).toEqual(["explain apart"]);
});

// Pending ruling (Patrick, 2026-09-28), as above.
// R-0542, R-0563
it("explains the cluster again for a play kept before digests", () => {
  expect(tap({ case: apart(), digest: null })).toEqual(["explain apart"]);
});
