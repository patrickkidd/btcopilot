import { describe, expect, it } from "vitest";
import { dotXs, hitSpans, pairSvg, restWidth, yearAt, years } from "../src/picture";
import { DateCertainty, type TimelineEvent } from "../src/types";

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
  // no ruling
  it("fills the screen and no more when one cluster is all there is", () => {
    const dates = ["1981-05-01", "1994-02-14", "2003-09-10", "2021-11-02"];
    const width = restWidth(
      [{ start: "1981-05-01", end: "2003-09-10" }],
      dates,
      PHONE,
    );
    expect(width).toBe(PHONE);
  });

  // no ruling
  it("is the screen for a record with nothing to separate", () => {
    expect(restWidth([], ["2014-03-02"], PHONE)).toBe(PHONE);
    expect(restWidth([], [], PHONE)).toBe(PHONE);
  });

  // no ruling
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

  // no ruling
  it("keeps a box wide enough for the two years written in it", () => {
    const dates = ["2001-01-01", "2002-04-01", "2030-01-01"];
    const cluster = { start: "2001-01-01", end: "2002-04-01" };
    const width = restWidth([cluster], dates, PHONE);
    const only = box(cluster, dates, width);
    // "01-02" at the 10.5px the years are written in, and room around it
    expect(only.right - only.left).toBeGreaterThanOrEqual(39);
  });

  // no ruling
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

  // no ruling
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
  // no ruling
  it("stay where they fall when they already read apart", () => {
    const xs = [40, 60, 90];
    expect(dotXs(xs, 30, 70)).toEqual(xs);
  });

  // no ruling
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

describe("the tap target of a dot on the line", () => {
  // R-0103
  it("is a whole thumb where the dot stands alone", () => {
    const [only] = hitSpans([200], PHONE);
    expect(only.size).toBe(44);
  });

  // no ruling
  it("lets a tap on either of two dots 6px apart pick that dot", () => {
    const xs = [200, 206];
    const spans = hitSpans(xs, PHONE);
    xs.forEach((x, i) => {
      const covering = spans.filter(
        (span) => x >= span.left && x <= span.left + span.size,
      );
      expect(covering).toContain(spans[i]);
      expect(spans[i].left + spans[i].size).toBeLessThanOrEqual(
        i < xs.length - 1 ? (xs[i] + xs[i + 1]) / 2 : PHONE,
      );
    });
  });
});

describe("the two moments face to face", () => {
  const event = (id: number, label: string): TimelineEvent =>
    ({
      id,
      label,
      sentence: label,
      person_name: "Ann",
      person: 1,
      dateTime: "2009-04-02",
      endDateTime: null,
      dateCertainty: DateCertainty.Certain,
      kind: null,
      description: null,
      notes: null,
      location: null,
      symptom: null,
      anxiety: null,
      functioning: null,
      relationship: null,
      relationshipTargets: [],
      relationshipTriangles: [],
      spouse: null,
      child: null,
    }) as TimelineEvent;

  // no ruling
  it("draws both labels and the seam with real numbers", () => {
    const svg = pairSvg(
      event(1, "she moved out of the house that spring"),
      event(2, "he took the job in another town"),
      PHONE,
    );
    expect(svg).not.toContain("NaN");
    expect(svg.match(/class="ss-w"/g)?.length).toBe(4);
  });
});

describe("the year a point on the line falls in", () => {
  // no ruling
  it("is the calendar year, not the count since 1970", () => {
    expect(yearAt(years("2003-09-10"))).toBe(2003);
    expect(yearAt(years("1981-05-01"))).toBe(1981);
  });
});
