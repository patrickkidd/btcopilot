import { describe, expect, it } from "vitest";
import {
  Level,
  Target,
  dotLayers,
  dotXs,
  inOrder,
  restLayers,
  restWidth,
  spanYears,
  told,
  trail,
  yearAt,
  years,
  type Layer,
} from "../src/picture";
import { zones } from "../src/spotlight";
import type { TimelineEvent } from "../src/types";

const PHONE = 390;
const PAD = 16;

/** Where a date lands on a line of this width, the way the resting picture
 * places it: the first moment at the left pad, the last at the right one. */
const at = (iso: string, dates: string[], width: number): number =>
  PAD +
  ((years(iso) - years(dates[0])) / (years(dates[dates.length - 1]) - years(dates[0]))) *
    (width - 2 * PAD);

const box = (
  cluster: { start: string; end: string },
  dates: string[],
  width: number,
) => ({
  left: at(cluster.start, dates, width) - 10,
  right: at(cluster.end, dates, width) + 10,
});

describe("how wide the resting line is drawn", () => {
  // R-0381
  it("fills the screen and no more when one cluster is all there is", () => {
    const dates = ["1981-05-01", "1994-02-14", "2003-09-10", "2021-11-02"];
    const width = restWidth(
      [{ start: "1981-05-01", end: "2003-09-10" }],
      dates,
      PHONE,
    );
    expect(width).toBe(PHONE);
  });

  // R-0381
  it("is the screen for a record with nothing to separate", () => {
    expect(restWidth([], ["2014-03-02"], PHONE)).toBe(PHONE);
    expect(restWidth([], [], PHONE)).toBe(PHONE);
  });

  // R-0134
  it("pulls two clusters apart until their boxes clear each other", () => {
    const dates = ["2001-01-01", "2001-08-01", "2004-02-01", "2006-06-01"];
    const clusters = [
      { start: "2001-01-01", end: "2001-08-01" },
      { start: "2004-02-01", end: "2006-06-01" },
    ];
    const width = restWidth(clusters, dates, PHONE);
    const [one, two] = clusters.map((c) => box(c, dates, width));
    expect(two.left - one.right).toBeGreaterThanOrEqual(6);
  });

  // R-0134
  it("keeps a box wide enough for the two years written in it", () => {
    const dates = ["2001-01-01", "2002-04-01", "2030-01-01"];
    const cluster = { start: "2001-01-01", end: "2002-04-01" };
    const width = restWidth([cluster], dates, PHONE);
    const only = box(cluster, dates, width);
    // "01-02" at the 10.5px the years are written in, and room around it
    expect(only.right - only.left).toBeGreaterThanOrEqual(39);
  });

  // R-0381
  it("never reaches past two screens, however crowded the record", () => {
    const dates = Array.from({ length: 120 }, (_, i) =>
      new Date(Date.UTC(2019, 0, 5 + i * 15)).toISOString().slice(0, 10),
    );
    const width = restWidth(
      [
        { start: dates[0], end: dates[59] },
        { start: dates[60], end: dates[119] },
      ],
      dates,
      PHONE,
    );
    expect(width).toBe(2 * PHONE);
  });

  // R-0381
  it("parks the present at the right edge, one screen of line behind it", () => {
    const dates = ["2019-01-05", "2020-08-01", "2020-09-01", "2023-12-01"];
    const width = restWidth(
      [
        { start: "2019-01-05", end: "2020-08-01" },
        { start: "2020-09-01", end: "2023-12-01" },
      ],
      dates,
      PHONE,
    );
    expect(width).toBeGreaterThan(PHONE);
    // parked at the far right, the last moment is the last thing on screen
    expect(at(dates[3], dates, width) - (width - PHONE)).toBeLessThanOrEqual(PHONE);
  });
});

describe("the dots inside a cluster box", () => {
  // R-0402
  it("stay where they fall when they already read apart", () => {
    const xs = [40, 60, 90];
    expect(dotXs(xs, 30, 70)).toEqual(xs);
  });

  // R-0402
  it("spreads seven moments held inside a few weeks across the box", () => {
    const xs = Array.from({ length: 7 }, (_, i) => 100 + i * 0.4);
    const drawn = dotXs(xs, 96, 88);
    expect(new Set(drawn.map((x) => x.toFixed(1))).size).toBe(7);
    drawn.forEach((x, i) => {
      if (i) expect(x - drawn[i - 1]).toBeGreaterThanOrEqual(11);
      expect(x).toBeGreaterThanOrEqual(96);
      expect(x).toBeLessThanOrEqual(96 + 88);
    });
  });
});

describe("the year a point on the line falls in", () => {
  // R-0111
  it("is the calendar year, not the count since 1970", () => {
    expect(yearAt(years("2003-09-10"))).toBe(2003);
    expect(yearAt(years("1981-05-01"))).toBe(1981);
  });
});

describe("a tap on the resting line", () => {
  /** The target a tap at x reaches: the last laid that covers it. */
  const reached = (layers: Layer[], x: number) =>
    [...layers].reverse().find((l) => x >= l.left && x <= l.left + l.width)?.target;

  // R-0537
  it("opens the cluster from anywhere in its box, a loose dot inside it too", () => {
    const dates = ["1994-01-01", "2015-01-01", "2021-01-01", "2024-01-01"];
    const edges = box({ start: dates[0], end: dates[2] }, dates, PHONE);
    const cluster: Layer = {
      target: Target.Cluster,
      index: 0,
      left: edges.left,
      width: edges.right - edges.left,
      label: "1994\u20132021",
    };
    const inside = at(dates[1], dates, PHONE);
    const outside = at(dates[3], dates, PHONE);
    const marks = [inside, outside].map((x) => ({ x, event: { label: "Died" } as TimelineEvent }));
    const layers = restLayers([cluster], dotLayers(zones(marks, PHONE)));
    expect(reached(layers, inside)).toBe(Target.Cluster);
    expect(reached(layers, outside)).toBe(Target.Zone);
  });
});

describe("the play-by-play of a cluster", () => {
  /** The record's own order: dated by date, then the undated. */
  const events = [
    [10, "1990-01-01"],
    [11, "1991-01-01"],
    [13, "1992-01-01"],
    [12, null],
    [14, null],
    [15, null],
  ].map(([id, dateTime]) => ({ id, dateTime, dateCertainty: null }) as TimelineEvent);

  // R-0532
  it("steps the dated events in date order whatever order the coach stored", () => {
    expect(inOrder(events, [13, 10, 11]).map((e) => e.id)).toEqual([10, 11, 13]);
  });

  // R-0527, R-0532
  it("steps an undated event right after the one stored before it, or first", () => {
    expect(inOrder(events, [15, 13, 12, 10, 11, 14]).map((e) => e.id)).toEqual([
      15, 10, 11, 14, 13, 12,
    ]);
  });
});

describe("the path row over the line", () => {
  const cluster = { start: "2009-03-01", end: "2010-11-20" };

  // R-0540
  it("names each level from the whole line down, the cluster by its years", () => {
    expect(trail(Level.Rest, null, null)).toEqual(["Timeline"]);
    expect(trail(Level.Rest, null, "Catherine died")).toEqual(["Timeline", "Catherine died"]);
    expect(trail(Level.Wire, null, null)).toEqual(["Timeline"]);
    expect(trail(Level.Wire, cluster, null)).toEqual(["Timeline", "2009–10"]);
    expect(trail(Level.Wire, cluster, "Catherine died")).toEqual([
      "Timeline",
      "2009–10",
      "Catherine died",
    ]);
  });

  // R-0540
  it("names the board, the about page and a comparison as modes of the cluster", () => {
    expect(trail(Level.Board, cluster, null)).toEqual(["Timeline", "2009–10", "explain"]);
    expect(trail(Level.About, cluster, null)).toEqual(["Timeline", "2009–10", "about"]);
    expect(trail(Level.Compare, null, null)).toEqual(["Timeline", "compare"]);
  });

  // R-0540
  it("names a moment picked by the first name and what happened, the rest left over", () => {
    expect(told("Catherine Hale", "died")).toEqual(["Catherine died", ""]);
    expect(told("Ben", "Ben stopped calling")).toEqual(["Ben stopped calling", ""]);
    expect(told("", "Moved to Denver")).toEqual(["Moved to Denver", ""]);
    // a long one keeps its first words, never ending on a small word
    expect(told("Catherine Hale", "died of breast cancer")).toEqual([
      "Catherine died",
      "of breast cancer",
    ]);
  });

  // R-0540
  it("writes a cluster's years short, and in full across a century", () => {
    expect(spanYears("2009-03-01", "2009-11-20")).toBe("2009");
    expect(spanYears("1998-03-01", "2003-11-20")).toBe("1998–2003");
    expect(spanYears("1981-05-01", "1989-11-20")).toBe("1981–89");
  });
});
