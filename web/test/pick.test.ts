import { expect, it } from "vitest";
import { Level, Via, picked, resting, wireOf, type Look } from "../src/picture";
import { baseOpacity } from "../src/spotlight";
import { Spotlight, type Cluster } from "../src/types";

const CLUSTER: Cluster = {
  id: "cT",
  label: "Leaving and losing",
  title: "Leaving and losing",
  summary: null,
  reason: null,
  cluster_ids: ["cT"],
  start: "1981-05-01",
  end: "2003-09-10",
  event_ids: [10, 11, 12],
  count: 3,
};
const CLUSTERS = [CLUSTER];
const EVENTS = 4;
const LOOSE = 13;

const REST: Look = { level: Level.Rest, focus: null, named: [], selected: null };
/** Where a thumb reaches a clustered event's dot: its cluster open. */
const OPEN: Look = {
  level: Level.Wire,
  focus: CLUSTER,
  named: CLUSTER.event_ids,
  selected: null,
};

const pick = (look: Look, id: number, via: Via, spot = Spotlight.Unified) =>
  picked(look, id, [id], CLUSTERS, spot, via);

// R-0168
it("a chip and a dot pick an event inside a cluster the same way, the rest faded", () => {
  const chip = pick(REST, 11, Via.Chip);
  const dot = pick(OPEN, 11, Via.Dot);
  expect(dot).toEqual(chip);
  expect(chip.named.filter((id) => id !== 11)).toEqual([]);
  expect(baseOpacity(EVENTS, chip.named.length)).toBeLessThan(1);
});

// R-0168, R-0235
it("a chip and a dot pick an event outside every cluster the same way, clusters kept as brackets", () => {
  const chip = pick(REST, LOOSE, Via.Chip);
  const dot = pick(REST, LOOSE, Via.Dot);
  expect(dot).toEqual(chip);
  expect(resting(chip)).toBe(true);
  expect(chip.named).toEqual([LOOSE]);
});

// R-0377, R-0460
it("picking an event either way leaves the line where a picked event's line runs", () => {
  const inside = pick(REST, 11, Via.Chip);
  for (const look of [pick(REST, LOOSE, Via.Chip), pick(REST, LOOSE, Via.Dot)])
    expect(wireOf(look)).toBe(wireOf(inside));
});

// R-0168
it("with the old chip spotlight set, a chip puts a loose event on the wire and a dot only picks it", () => {
  const chip = pick(REST, LOOSE, Via.Chip, Spotlight.Chip);
  expect(chip).toEqual({ level: Level.Wire, focus: null, named: [LOOSE], selected: LOOSE });
  expect(resting(chip)).toBe(false);

  const dot = pick(OPEN, 11, Via.Dot, Spotlight.Chip);
  expect(dot).toEqual({ ...OPEN, selected: 11 });
});
