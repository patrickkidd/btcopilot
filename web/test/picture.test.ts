import { describe, expect, it } from "vitest";
import {
  Level,
  Target,
  dotLayers,
  pills,
  reach,
  restLayers,
  restWidth,
  ruler,
  spanYears,
  strongest,
  told,
  trail,
  yearAt,
  years,
  type Layer,
} from "../src/picture";
import { zones } from "../src/spotlight";
import { Touch, type Cluster, type TimelineEvent } from "../src/types";

const PHONE = 390;
const PAD = 16;

/** Where a date lands on a line of this width, the way the resting picture
 * places it: the first moment at the left pad, the last at the right one. */
const at = (iso: string, dates: string[], width: number): number =>
  PAD +
  ((years(iso) - years(dates[0])) / (years(dates[dates.length - 1]) - years(dates[0]))) *
    (width - 2 * PAD);

const event = (id: number, iso: string): TimelineEvent =>
  ({ id, dateTime: iso, label: `event ${id}` }) as TimelineEvent;

const cluster = (id: number, events: TimelineEvent[]): Cluster =>
  ({
    id: String(id),
    event_ids: events.map((e) => e.id),
    start: events[0].dateTime as string,
    end: events[events.length - 1].dateTime as string,
  }) as Cluster;

/** Lay these events and clusters on a phone's line. */
const lay = (clusters: Cluster[], dated: TimelineEvent[]) => {
  const dates = dated.map((e) => e.dateTime as string).sort();
  return pills(clusters, dated, (iso) => at(iso, dates, PHONE));
};

describe("the marks on the line", () => {
  // R-0543
  it("draws one pill per cluster and a dot only for an event no cluster claims", () => {
    const early = [event(1, "1981-05-01"), event(2, "1983-02-01"), event(3, "1984-07-01")];
    const late = [event(4, "2003-09-10"), event(5, "2005-01-01")];
    const alone = [event(6, "1973-03-01"), event(7, "2026-01-01")];
    const laid = lay([cluster(10, early), cluster(11, late)], [...alone, ...early, ...late]);
    expect(laid.map((m) => m.cluster?.id ?? `dot ${m.event?.id}`)).toEqual([
      "dot 6",
      "10",
      "11",
      "dot 7",
    ]);
  });

  // R-0402, R-0543
  it("draws seven events held inside a few weeks as one pill, not seven dots", () => {
    const held = Array.from({ length: 7 }, (_, i) =>
      event(i + 1, new Date(Date.UTC(2009, 2, 1 + i * 3)).toISOString().slice(0, 10)),
    );
    const laid = lay([cluster(10, held)], [event(20, "1990-01-01"), ...held]);
    expect(laid.filter((m) => m.cluster)).toHaveLength(1);
    expect(laid.filter((m) => m.event).map((m) => m.event?.id)).toEqual([20]);
  });

  // R-0134, R-0543
  it("gives way between two clusters a month apart and leaves a gap", () => {
    const one = [event(1, "2001-01-01"), event(2, "2001-08-01")];
    const two = [event(3, "2001-09-01"), event(4, "2006-06-01")];
    const [a, b] = lay([cluster(10, one), cluster(11, two)], [...one, ...two]);
    expect(b.left - a.right).toBeGreaterThanOrEqual(6);
  });

  // R-0543
  it("gives way to a loose event dated just before or after it, keeping its own years", () => {
    const held = [event(1, "1980-09-15"), event(2, "1982-11-15")];
    const laid = (before: string, after: string) => {
      const dated = [event(5, "1924-06-01"), event(3, before), ...held, event(4, after)];
      const dates = dated.map((e) => e.dateTime as string).sort();
      const where = (iso: string) => at(iso, dates, PHONE);
      const marks = pills([cluster(10, held)], dated, where);
      const pill = marks.find((m) => m.cluster)!;
      const [one, two] = [3, 4].map((id) => marks.find((m) => m.event?.id === id)!);
      // the pill keeps the years it holds
      expect(pill.left).toBeLessThanOrEqual(where("1980-09-15"));
      expect(pill.right).toBeGreaterThanOrEqual(where("1982-11-15"));
      return { before: pill.left - one.right, after: two.left - pill.right };
    };
    // with room, a gap
    const roomy = laid("1978-01-01", "1985-06-01");
    expect(roomy.before).toBeGreaterThanOrEqual(6);
    expect(roomy.after).toBeGreaterThanOrEqual(6);
    // without room for a gap, the pill still never reaches over the dot
    const tight = laid("1979-06-01", "1983-09-01");
    expect(tight.before).toBeGreaterThan(0);
    expect(tight.after).toBeGreaterThan(0);
  });

  // R-0134, R-0543
  it("keeps a cluster held inside one day wider than a dot", () => {
    const same = [event(1, "2001-01-01"), event(2, "2001-01-01")];
    const [only] = lay([cluster(10, same)], [event(3, "1990-01-01"), ...same]).filter(
      (m) => m.cluster,
    );
    expect(only.right - only.left).toBeGreaterThanOrEqual(20);
  });

  // R-0381, R-0543
  it("lays sixty events over fifty years across at most two screens, the pills apart", () => {
    const dated = Array.from({ length: 60 }, (_, i) =>
      event(i + 1, new Date(Date.UTC(1974, 0, 1 + i * 300)).toISOString().slice(0, 10)),
    );
    const clusters = Array.from({ length: 10 }, (_, i) =>
      cluster(100 + i, dated.slice(i * 6, i * 6 + 6)),
    );
    const width = restWidth(clusters, dated, PHONE);
    expect(width).toBeLessThanOrEqual(2 * PHONE);
    const dates = dated.map((e) => e.dateTime as string);
    const laid = pills(clusters, dated, (iso) => at(iso, dates, width));
    expect(laid).toHaveLength(10);
    for (const mark of laid) {
      expect(mark.left).toBeGreaterThanOrEqual(0);
      expect(mark.right).toBeLessThanOrEqual(width);
    }
    laid.forEach((mark, i) => {
      if (i) expect(mark.left).toBeGreaterThan(laid[i - 1].right);
    });
  });
});

/** A record three generations long: births decades apart, then the years a
 * couple came apart as one cluster, the way the Whitlock fixture has it. */
const generations = () => {
  const born = ["1924-06-01", "1926-06-01", "1948-06-01", "1951-10-01", "1953-06-01", "1970-06-01", "1975-06-01", "1979-06-01"].map(
    (iso, i) => event(i + 1, iso),
  );
  const apart = ["1980-09-15", "1981-06-15", "1982-11-15"].map((iso, i) => event(20 + i, iso));
  return { clusters: [cluster(30, apart)], dated: [...born, ...apart] };
};

describe("how wide the line is drawn", () => {
  // R-0381
  it("draws a long record wider than the phone, so every mark has a thumb's width, and never past two screens", () => {
    const { clusters, dated } = generations();
    const width = restWidth(clusters, dated, PHONE);
    expect(width).toBeGreaterThan(PHONE);
    expect(width).toBeLessThanOrEqual(2 * PHONE);
  });

  // R-0381
  it("keeps a record that reads across one screen at one screen", () => {
    const dated = Array.from({ length: 60 }, (_, i) =>
      event(i + 1, new Date(Date.UTC(2019, 0, 5 + 30 * i)).toISOString().slice(0, 10)),
    );
    const clusters = [cluster(1, dated.slice(0, 20)), cluster(2, dated.slice(20))];
    expect(restWidth(clusters, dated, PHONE)).toBe(PHONE);
  });

  // R-0381
  it("coarsens the scale rather than reach past two screens", () => {
    const dated = Array.from({ length: 200 }, (_, i) =>
      event(i + 1, `${1900 + Math.floor(i / 2)}-0${1 + (i % 2) * 5}-01`),
    );
    expect(restWidth([], dated, PHONE)).toBe(2 * PHONE);
  });
});

describe("the colour a pill takes while the coach replies", () => {
  // R-0544, R-0539
  it("is the strongest thing the coach did to any event inside it", () => {
    const touched = new Map([
      [1, Touch.Read],
      [2, Touch.Change],
      [9, Touch.Remove],
    ]);
    expect(strongest([1, 2, 3], touched)).toBe(Touch.Change);
    expect(strongest([1, 3], touched)).toBe(Touch.Read);
    expect(strongest([3, 4], touched)).toBeNull();
  });
});

describe("the years under the line", () => {
  const span = (y0: number, y1: number) => {
    const dates = [`${y0}-01-01`, `${y1}-01-01`];
    return ruler(y0, y1, (iso) => at(iso, dates, PHONE), PAD, PHONE - PAD).map((t) => t.year);
  };

  // R-0543
  it("writes the first and last years at the ends and each decade that has room", () => {
    expect(span(1973, 2026)).toEqual([1973, 1980, 1990, 2000, 2010, 2026]);
  });

  // R-0543
  it("writes every second decade where ten years is too narrow for a year", () => {
    expect(span(1880, 2026)).toEqual([1880, 1900, 1920, 1940, 1960, 1980, 2000, 2026]);
  });

  // R-0543
  it("writes a record held inside one year once", () => {
    expect(span(2014, 2014)).toEqual([2014]);
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

  /** A line with one cluster, a loose event dated inside its years and one
   * after it, laid the way the picture lays its targets. */
  const line = () => {
    const held = [event(1, "1994-01-01"), event(3, "2021-01-01")];
    const inside = event(2, "2015-01-01");
    const outside = event(4, "2024-01-01");
    const dates = ["1994-01-01", "2015-01-01", "2021-01-01", "2024-01-01"];
    const where = (iso: string) => at(iso, dates, PHONE);
    const laid = pills([cluster(10, held)], [...held, inside, outside], where);
    const hits = reach(laid, PHONE);
    const i = laid.findIndex((m) => m.cluster);
    const box: Layer = {
      target: Target.Cluster,
      index: 0,
      left: hits[i].left,
      width: hits[i].right - hits[i].left,
      label: "1994\u20132021",
    };
    const marks = laid
      .filter((m) => m.event)
      .map((m) => ({ x: (m.left + m.right) / 2, event: m.event as TimelineEvent }));
    return { laid, hits, layers: restLayers([box], dotLayers(zones(marks, PHONE))), where };
  };

  // R-0537
  it("opens the cluster from anywhere on its pill, a loose dot inside it too", () => {
    const { layers, where } = line();
    expect(reached(layers, where("2015-01-01"))).toBe(Target.Cluster);
    expect(reached(layers, where("1994-01-01") - 8)).toBe(Target.Cluster);
    expect(reached(layers, where("2024-01-01"))).toBe(Target.Zone);
  });

  // R-0544
  it("gives each mark a target that covers it and stops halfway to the next", () => {
    const { laid, hits } = line();
    hits.forEach((hit, i) => {
      expect(hit.left).toBeLessThanOrEqual(laid[i].left);
      expect(hit.right).toBeGreaterThanOrEqual(laid[i].right);
      expect(hit.left).toBeGreaterThanOrEqual(0);
      expect(hit.right).toBeLessThanOrEqual(PHONE);
    });
    // the pill and the dot after it meet halfway between their middles
    const mid = (m: { left: number; right: number }) => (m.left + m.right) / 2;
    const n = laid.length;
    const seam = (mid(laid[n - 2]) + mid(laid[n - 1])) / 2;
    expect(hits[n - 2].right).toBeCloseTo(seam);
    expect(hits[n - 1].left).toBeCloseTo(seam);
  });
});

describe("the path row over the line", () => {
  const cluster = { start: "2009-03-01", end: "2010-11-20" };

  // R-0540
  it("names each level from the whole line down, the cluster by its years", () => {
    expect(trail(Level.Rest, null, null)).toEqual(["Timeline"]);
    expect(trail(Level.Rest, null, "Delphine died")).toEqual(["Timeline", "Delphine died"]);
    expect(trail(Level.Wire, null, null)).toEqual(["Timeline"]);
    expect(trail(Level.Wire, cluster, null)).toEqual(["Timeline", "2009–10"]);
    expect(trail(Level.Wire, cluster, "Delphine died")).toEqual([
      "Timeline",
      "2009–10",
      "Delphine died",
    ]);
  });

  // R-0540, R-0570
  it("names the about page and a comparison as modes of the cluster", () => {
    expect(trail(Level.About, cluster, null)).toEqual(["Timeline", "2009–10", "about"]);
    expect(trail(Level.Compare, null, null)).toEqual(["Timeline", "compare"]);
  });

  // R-0540
  it("names a moment picked by the first name and what happened, the rest left over", () => {
    expect(told("Delphine Reyes", "died")).toEqual(["Delphine died", ""]);
    expect(told("Ben", "Ben stopped calling")).toEqual(["Ben stopped calling", ""]);
    expect(told("", "Moved to Denver")).toEqual(["Moved to Denver", ""]);
    // a long one keeps its first words, never ending on a small word
    expect(told("Delphine Reyes", "died of breast cancer")).toEqual([
      "Delphine died",
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
