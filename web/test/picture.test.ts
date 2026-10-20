import { describe, expect, it, vi } from "vitest";
import {
  CLUSTER_BOOK,
  CLUSTER_BOOK_TITLE,
  ClusterView,
  Key,
  Via,
  chosen,
  clusterPage,
  stand,
  VIEW_KEY,
  drawing,
  place,
  storeView,
  storedView,
  Level,
  Target,
  aboutMarkup,
  centredOn,
  clusterName,
  clusterStep,
  dotLayers,
  inSight,
  into,
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
import { periodName } from "../src/caseview";
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
    const dates = dated.map((e) => e.dateTime as string);
    const width = restWidth(clusters, dates, PHONE);
    expect(width).toBeLessThanOrEqual(2 * PHONE);
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

  // R-0381, R-0577
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

  // R-0381, R-0577
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
  const cluster = { title: "", start: "2009-03-01", end: "2010-11-20" };

  // R-0767
  it("names an open cluster in the path by its name and years", () => {
    const named = { title: "Every mark", label: "1972–1999", start: "1972-06-10", end: "1999-02-01" };
    expect(trail(Level.Wire, named, null)).toEqual(["Timeline", "Every mark · 1972–1999"]);
    expect(trail(Level.About, named, null)).toEqual(["Timeline", "Every mark · 1972–1999", "about"]);
  });

  // R-0583, R-0767
  it("names the open cluster under the line by its name, the count beside it", () => {
    const open = { title: "Every mark", label: "1972–1999", start: "1972-06-10", end: "1999-02-01", count: 12 };
    expect(clusterName(open)).toBe("Every mark");
    expect(clusterName({ ...open, title: "" })).toBe("1972–1999");
  });

  // R-0540
  it("names each level from the whole line down, a cluster with no name by its years", () => {
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

  // R-0540, R-0681
  it("names a moment picked by the first name and what happened, the rest left over", () => {
    expect(told("Delphine Reyes", "died")).toEqual(["Delphine died", ""]);
    expect(told("Ben", "Ben stopped calling")).toEqual(["Ben stopped calling", ""]);
    expect(told("Ben", "Stopped calling")).toEqual(["Ben stopped calling", ""]);
    expect(told("", "Moved to Denver")).toEqual(["Moved to Denver", ""]);
    // a long one keeps its first words, never ending on a small word
    expect(told("Delphine Reyes", "died of breast cancer")).toEqual([
      "Delphine died",
      "of breast cancer",
    ]);
  });

  // R-0540
  it("drops the words' own separator where they are cut, so the date's separator before the rest is never doubled", () => {
    expect(told("Harold Bell", "died · of lung cancer")).toEqual(["Harold died", "of lung cancer"]);
  });

  // R-0540
  it("writes a cluster's years short, and in full across a century", () => {
    expect(spanYears("2009-03-01", "2009-11-20")).toBe("2009");
    expect(spanYears("1998-03-01", "2003-11-20")).toBe("1998–2003");
    expect(spanYears("1981-05-01", "1989-11-20")).toBe("1981–89");
  });
});

// R-0730
it("names an event whose title starts with someone else in the family with a colon, and leaves the rest as today", () => {
  const family = ["Ben", "Marcus", "James"];
  expect(told("Ben Holt", "Marcus left", family)[0]).toBe("Ben: Marcus left");
  expect(told("Ben Holt", "Ben stopped calling", family)[0]).toBe("Ben stopped calling");
  expect(told("Ben Holt", "Stopped calling", family)[0]).toBe("Ben stopped calling");
  expect(told("Ben Holt", "Christmas at home", family)[0]).toBe("Ben christmas");
  // the 20-letter cut still applies
  expect(told("Ben Holt", "Marcus moved out of the flat in Oslo", family)).toEqual(["Ben: Marcus moved", "out of the flat in Oslo"]);
});

// Patrick, 2026-10-08, with R-0836 to R-0838: a cluster's info page carries the book button.
// R-0213, R-0691
describe("the page behind a cluster's i", () => {
  const moments = [
    { year: "1981", label: "Grandmother died" },
    { year: "2003", label: "Moved away" },
  ];
  const page = aboutMarkup("Ada lost her grandmother, then moved away.", "1981–2003", moments);

  // R-0213
  it("says the reason, the years and the count, then each moment with its year", () => {
    expect(page).toContain('<p class="ab-why">Ada lost her grandmother, then moved away.</p>');
    expect(page).toContain('<p class="ab-span">1981–2003 · 2 events</p>');
    expect(page).toContain('<span class="ab-yr">1981</span><span class="ab-what">Grandmother died</span>');
    expect(aboutMarkup("", "1981", moments.slice(0, 1))).toContain("1981 · 1 event</p>");
    expect(aboutMarkup("", "1981", [])).not.toContain("ab-why");
  });

  // R-0691, R-0688
  it("carries the app's book button, keyed to the passages behind what a cluster is", () => {
    expect(page).toContain(`class="book" data-book="${CLUSTER_BOOK}" data-title="${CLUSTER_BOOK_TITLE}"`);
    expect(CLUSTER_BOOK).toBe("cluster");
    expect(CLUSTER_BOOK_TITLE).toBe("What a cluster is");
    // the book sits inside the page, before its close button
    expect(page.indexOf('class="book"')).toBeLessThan(page.indexOf('class="cardx"'));
    expect(page).toContain(`data-target="${Target.Close}"`);
  });

  // R-0213
  it("escapes the record's words", () => {
    expect(aboutMarkup("<b>why</b>", "1981", [{ year: "1981", label: "a & b" }])).not.toContain("<b>");
    expect(aboutMarkup("", "1981", [{ year: "1981", label: "a & b" }])).toContain("a &amp; b");
  });
});

// "the timeline needs to scroll to the right in the full family diagram view." (Patrick, 2026-10-07)
// R-0796
it("slides the line to put the step's dot in the middle, as near as its ends allow, and knows when a dot is out of sight", () => {
  expect(centredOn(2000, 2880, 1440)).toBe(1280);
  expect(centredOn(100, 2880, 1440)).toBe(0);
  expect(centredOn(2850, 2880, 1440)).toBe(1440);
  expect(centredOn(200, 300, 393)).toBe(0);
  expect(inSight(2000, 0, 1440)).toBe(false);
  expect(inSight(2000, 1280, 1440)).toBe(true);
  expect(inSight(10, 0, 1440)).toBe(false);
});

// "The timeline needs to scroll an event or cluster into view when it is off screen. It should not scroll when the cluster or event is already in view." (Patrick, 2026-10-15)
// R-0767
it("slides the line to an event or a cluster only when it is out of sight, and a cluster wider than the screen to its start", () => {
  const dot = (x: number) => ({ left: x, right: x });
  expect(into(dot(500), 300, 2880, 393)).toBe(300);
  expect(into(dot(2000), 300, 2880, 393)).toBe(centredOn(2000, 2880, 393));
  expect(into(dot(500), null, 2880, 393)).toBe(centredOn(500, 2880, 393));
  expect(into({ left: 400, right: 600 }, 300, 2880, 393)).toBe(300);
  expect(into({ left: 400, right: 600 }, 450, 2880, 393)).toBe(centredOn(500, 2880, 393));
  expect(into({ left: 1000, right: 1600 }, 1100, 2880, 393)).toBe(1100);
  expect(into({ left: 1000, right: 1600 }, 0, 2880, 393)).toBe(984);
});

describe("the drawing on a cluster's page", () => {
  const ev = (id: number, iso: string | null, over: Partial<TimelineEvent> = {}): TimelineEvent =>
    ({ id, dateTime: iso, label: `event ${id}`, kind: "shift", person: 1, person_name: "Ada", dateCertainty: "certain", ...over }) as TimelineEvent;
  const events = [
    ev(1, "1998-01-01", { symptom: "up" }),
    ev(2, "1998-07-01", { kind: "death", label: "Grandmother died", person: 2, person_name: "Rose" }),
    ev(3, "1999-01-01", { anxiety: "up", dateCertainty: "approximate", person_name: "Ada → Rose" }),
    ev(4, "1998-04-01", { kind: "bonded", dateCertainty: "unknown" }),
  ];
  const people = new Map([[1, "Ada"], [2, "Rose"]]);

  // R-0213, R-0850
  it("puts one row of dots by date, hollow when the date is unsure or unknown", () => {
    const p = place(events, ClusterView.Row, 300, null);
    const x = (iso: string) => 8 + ((years(iso) - years("1998-01-01")) / (years("1999-01-01") - years("1998-01-01"))) * 284;
    expect(p.dots.map((d) => [d.id, Math.round(d.x), d.hollow])).toEqual([
      [1, 8, false],
      [4, Math.round(x("1998-04-01")), true],
      [2, Math.round(x("1998-07-01")), false],
      [3, 292, true],
    ]);
    expect(p.dots.map((d) => d.colour)).toEqual(["var(--remove)", "var(--ink)", "var(--ink)", "var(--ask)"]);
    expect(p.years).toEqual(["1998", "1999"]);
    expect(p.lanes).toEqual([]);
  });

  // R-0862, R-0867
  it("draws a solid line at every death, a dashed one at each illness found in someone other than the diagram's own person, and one at the stored opening when it is neither", () => {
    const keys = (opening: number | null, you: number | null) =>
      place(events, ClusterView.Row, 300, opening, people, you).keys.map((k) => [k.id, k.key, k.label]);
    expect(keys(null, 1)).toEqual([[2, Key.Death, "Rose's death"]]);
    expect(keys(null, 2)).toEqual([[1, Key.Illness, "Ada: event 1"], [2, Key.Death, "Rose's death"]]);
    expect(keys(2, 1)).toEqual([[2, Key.Death, "Rose's death"]]);
    expect(keys(3, 1)).toEqual([[2, Key.Death, "Rose's death"], [3, Key.Opening, "event 3"]]);
    const p = place(events, ClusterView.Row, 300, 3, people, 2);
    expect(p.keys.find((k) => k.id === 2)!.x).toBe(p.dots.find((d) => d.id === 2)!.x);
    const svg = drawing(events, ClusterView.Row, 300, 3, people, 2);
    expect(svg).toContain('<line class="ab-key ab-death"');
    expect(svg).toContain('<line class="ab-key ab-illness"');
    expect(svg).toContain('<line class="ab-key ab-opening"');
    expect(svg).toContain(">Rose&#39;s death</text>");
    expect(svg).toContain('ab-line ab-death"></span>death');
    expect(svg).toContain('ab-line ab-illness"></span>illness found');
    // the lanes draw the same lines through every lane
    expect(place(events, ClusterView.Lanes, 300, 3, people, 2).keys.map((k) => k.key)).toEqual([Key.Illness, Key.Death, Key.Opening]);
    expect(drawing(events, ClusterView.Lanes, 300, 3, people, 2)).toContain('<line class="ab-key ab-death"');
  });

  // R-0862
  it("names a death with one possessive whether the name ends in s, is already possessive or is a stand-in", () => {
    const label = (name: string) => {
      const died = [{ ...events[1], person: 9, person_name: name }];
      return place(died, ClusterView.Row, 300, null, new Map(), 1).keys[0].label;
    };
    expect(label("Jess Hale")).toBe("Jess's death");
    expect(label("User's")).toBe("User's death");
    expect(label("User's partner")).toBe("User's partner's death");
  });

  // R-0862
  it("stands the lines' labels on rows so no two overlap and no line crosses a label, cutting one only when no row is clear", () => {
    const lines = [100, 104, 110, 118, 290].map((x, i) => ({ id: i, key: Key.Death, x, label: `Grandmother number ${i}'s death` }));
    const laid = stand(lines, 300);
    expect(laid).toHaveLength(5);
    for (const a of laid)
      for (const b of laid) {
        if (a === b) continue;
        if (a.row === b.row) expect(a.to < b.from || b.to < a.from).toBe(true);
        if (a.row < b.row) expect(a.x < b.from || a.x > b.to).toBe(true);
      }
    expect(new Set(laid.map((k) => k.row)).size).toBeGreaterThan(1);
    const last = laid.find((k) => k.id === 4)!;
    expect(last.to).toBeLessThan(last.x);
    expect(laid.every((k) => k.label.length <= 22)).toBe(true);
    // the dots move down under as many rows of labels as there are
    const many = [ev(1, "1998-01-01", { kind: "death" }), ev(2, "1998-01-02", { kind: "death", person: 2 }), ev(3, "1999-01-01")];
    const p = place(many, ClusterView.Row, 300, null, people, 1);
    expect(p.keys.map((k) => k.row)).toEqual([0, 1]);
    expect(p.top).toBeGreaterThan(place(events, ClusterView.Row, 300, null, people, 1).top);
  });

  // R-0861
  it("makes a lane as tall as its largest stack of same-date dots, so no dot rises into the labels or the lane above", () => {
    const seven = [1, 2, 3, 4, 5, 6, 7].map((id) => ev(id, "2001-05-01"));
    const row = place([...seven, ev(8, "2003-01-01")], ClusterView.Row, 300, null);
    expect(Math.min(...row.dots.map((d) => d.y - 5))).toBeGreaterThanOrEqual(row.top);
    const plain = place(events, ClusterView.Row, 300, null);
    expect(row.height - row.lines[0]).toBe(plain.height - plain.lines[0]);
    const rose = [9, 10, 11, 12, 13].map((id) => ev(id, "2001-05-01", { person: 2, person_name: "Rose" }));
    const lanes = place([ev(14, "2000-01-01"), ...rose], ClusterView.Lanes, 300, null, people, 1);
    const top = Math.min(...lanes.dots.filter((d) => d.id !== 14).map((d) => d.y - 5));
    expect(top).toBeGreaterThan(lanes.lines[0]);
  });

  // R-0850
  it("gives each person one lane by who they are, a two-person event in its first person's", () => {
    const p = place(events, ClusterView.Lanes, 300, 2, people, 1);
    expect(p.lanes.map((l) => l.name)).toEqual(["Ada", "Rose"]);
    expect(p.dots.find((d) => d.id === 3)!.y).toBe(p.lanes[0].y);
    expect(p.dots.find((d) => d.id === 2)!.y).toBe(p.lanes[1].y);
    expect(p.dots[0].x).toBe(72);
    expect(drawing(events, ClusterView.Lanes, 300, 2, people)).toContain('class="ab-view" data-view="row">One row</button>');
  });

  // R-0850
  it("lists every event of the cluster, the undated ones too", () => {
    const cluster = { reason: "", summary: null, label: "1998–1999", start: "1998-01-01", end: "1999-01-01", event_ids: [1, 2, 3], play_ids: [1, 2, 3, 4, 5], openingEventId: null } as unknown as Cluster;
    const page = clusterPage(cluster, [...events, ev(5, null, { label: "Moved away" })], [], ClusterView.Row, 300);
    expect(page).toContain("1998–1999 · 5 events");
    expect(page).toContain('<span class="ab-yr"></span><span class="ab-what">Moved away</span>');
  });

  /** A period as the person stored it, Sep 2009 to Jan 2011: on the line to
   * Nov 2010, four events after it whose dates the diagram does not know. */
  const period = () => {
    const dates: [number, string, string][] = [
      [16, "2009-09-01", "approximate"], [17, "2009-09-01", "approximate"], [18, "2010-01-01", "approximate"],
      [19, "2010-06-01", "approximate"], [20, "2010-10-01", "approximate"], [21, "2010-10-01", "approximate"],
      [23, "2010-11-01", "approximate"], [104, "2010-11-01", "approximate"], [105, "2010-11-01", "approximate"],
      [106, "2010-12-01", "unknown"], [107, "2011-01-01", "unknown"], [108, "2011-01-01", "unknown"], [24, "2011-01-01", "unknown"],
    ];
    const all = dates.map(([id, iso, sure]) => ev(id, iso, { dateCertainty: sure as TimelineEvent["dateCertainty"] }));
    const ids = all.map((e) => e.id);
    const cluster = { id: "p", title: "2009\u20132011", label: "2009\u20132011", reason: "", summary: null, start: "2009-09-01", end: "2010-11-01", count: 13, event_ids: ids.slice(0, 9), play_ids: ids, openingEventId: null } as unknown as Cluster;
    return { all, cluster };
  };

  // R-0853, R-0850
  it("writes a period's years one way, the years the server stored for it, on its page, in the path and on a detail chip", () => {
    const { all, cluster } = period();
    expect(clusterPage(cluster, all, [], ClusterView.Row, 360)).toContain("2009\u20132011 · 13 events");
    expect(place(all, ClusterView.Row, 360, null).years).toEqual(["2009", "2011"]);
    expect(clusterStep(cluster)).toBe("2009\u20132011");
    expect(periodName(cluster)).toBe("2009\u20132011");
    expect(periodName({ ...cluster, title: "When Lily came" })).toBe("When Lily came \u00b7 2009\u20132011");
  });

  // R-0853, R-0767
  it("writes an app period's years once beside its name, though its stored name ends in them", () => {
    const { cluster } = period();
    const app = { ...cluster, title: "When Lily came, 2009\u20132011" };
    expect(periodName(app)).toBe("When Lily came \u00b7 2009\u20132011");
    expect(clusterStep(app)).toBe("When Lily came · 2009\u20132011");
    expect(trail(Level.About, app, null)).toEqual(["Timeline", "When Lily came · 2009\u20132011", "about"]);
    expect(periodName({ ...cluster, title: "When Lily came, 2007" })).toBe("When Lily came, 2007 \u00b7 2009\u20132011");
  });

  // R-0168, R-0850
  it("stacks events on one date a few pixels apart in the one row, each dot answering its own tap", () => {
    const { all } = period();
    const p = place(all, ClusterView.Row, 360, null);
    const at = (id: number) => p.dots.find((d) => d.id === id)!;
    expect(p.lanes).toEqual([]);
    expect([at(23).x, at(104).x]).toEqual([at(105).x, at(105).x]);
    expect([at(23).y - at(104).y, at(104).y - at(105).y]).toEqual([8, 8]);
    const inside = (b: { x: number; y: number; w: number; h: number }, d: { x: number; y: number }) =>
      d.x >= b.x && d.x <= b.x + b.w && d.y >= b.y && d.y <= b.y + b.h;
    for (const d of p.dots) expect(p.dots.filter((o) => inside(o.hit, d)).map((o) => o.id)).toEqual([d.id]);
    const svg = drawing(all, ClusterView.Row, 360, null);
    expect(svg.match(/<rect class="ab-hit"/g)).toHaveLength(13);
  });

  // R-0861
  it("selects a tapped row alone, a tapped dot with every event on its date, and nothing on a second tap", () => {
    const { all } = period();
    expect(chosen([], 104, Via.Row, all)).toEqual([104]);
    expect(chosen([104], 104, Via.Row, all)).toEqual([]);
    expect(chosen([], 104, Via.Dot, all)).toEqual([23, 104, 105]);
    expect(chosen([23, 104, 105], 105, Via.Dot, all)).toEqual([]);
    expect(chosen([23, 104, 105], 104, Via.Row, all)).toEqual([104]);
    expect(chosen([104], 19, Via.Dot, all)).toEqual([19]);
    expect(chosen([19], 19, Via.Row, all)).toEqual([]);
  });

  // R-0861
  it("marks each row and each dot with its event, so a selection lights both", () => {
    const { all, cluster } = period();
    const page = clusterPage(cluster, all, [], ClusterView.Row, 360);
    expect(page).toContain('<li data-event="104"><span class="ab-yr">2010</span>');
    expect(page).toContain('<circle class="ab-dot" data-event="104"');
    expect(page.match(/<li data-event=/g)).toHaveLength(13);
  });

  // R-0168
  it("gives every dot a target the picture's tap language answers", () => {
    const svg = drawing(events, ClusterView.Row, 300, null);
    expect(svg.match(new RegExp(`data-target="${Target.Dot}"`, "g"))).toHaveLength(4);
    expect(svg).toContain('data-index="4"');
  });

  // R-0850
  it("names under the drawing only the colours in it, and the hollow dot", () => {
    const legend = drawing(events, ClusterView.Row, 300, null).split('class="ab-span ab-legend">')[1];
    expect(legend).toContain("symptom");
    expect(legend).toContain("anxiety");
    expect(legend).toContain("other events");
    expect(legend).toContain("hollow: approximate date");
    expect(legend).not.toContain("functioning");
    expect(legend).not.toContain("relationship");
  });

  // R-0213
  it("keeps the reader's choice in the browser, one row by default", () => {
    expect(storedView()).toBe(ClusterView.Row);
    const kept = new Map<string, string>();
    vi.stubGlobal("localStorage", { getItem: (k: string) => kept.get(k) ?? null, setItem: (k: string, v: string) => kept.set(k, v) });
    expect(drawing(events, storedView(), 300, null)).toContain('data-view="lanes">By person</button>');
    storeView(ClusterView.Lanes);
    expect(storedView()).toBe(ClusterView.Lanes);
    expect(kept.get(VIEW_KEY)).toBe("lanes");
    storeView(ClusterView.Row);
    expect(storedView()).toBe(ClusterView.Row);
    vi.unstubAllGlobals();
  });
});
