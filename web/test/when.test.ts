import { describe, expect, it } from "vitest";
import { clockTime, groupLabel, shortDate, whenText } from "../src/when";

const NOW = new Date(2026, 8, 20, 15, 30); // Sunday 20 September 2026

describe("the group a session falls under", () => {
  it("names today, yesterday, this week, this month, then the month", () => {
    expect(groupLabel(new Date(2026, 8, 20, 9, 0), NOW)).toBe("Today");
    expect(groupLabel(new Date(2026, 8, 19, 9, 0), NOW)).toBe("Yesterday");
    expect(groupLabel(new Date(2026, 8, 16, 9, 0), NOW)).toBe("This week");
    expect(groupLabel(new Date(2026, 8, 2, 9, 0), NOW)).toBe("This month");
    expect(groupLabel(new Date(2018, 2, 4, 9, 0), NOW)).toBe("March 2018");
  });

  it("has no Earlier bucket", () => {
    expect(groupLabel(new Date(1999, 0, 1), NOW)).toBe("January 1999");
  });
});

describe("the date beside a session", () => {
  it("shows the clock when the day holds more than one session", () => {
    expect(whenText(new Date(2026, 8, 20, 9, 5), NOW, 2)).toBe("9:05 am");
    expect(whenText(new Date(2026, 8, 2, 13, 5), NOW, 3)).toBe("Sep 2 · 1:05 pm");
  });

  it("says how long ago when the day holds only one", () => {
    expect(whenText(new Date(2026, 8, 20, 9, 5), NOW, 1)).toBe("today 9:05 am");
    expect(whenText(new Date(2026, 8, 19, 9, 5), NOW, 1)).toBe("yesterday");
    expect(whenText(new Date(2026, 8, 16, 9, 5), NOW, 1)).toBe("Wednesday");
    expect(whenText(new Date(2026, 1, 3, 9, 5), NOW, 1)).toBe("Feb 3");
    expect(whenText(new Date(2019, 1, 3, 9, 5), NOW, 1)).toBe("Feb 2019");
  });
});

describe("the clock", () => {
  it("reads twelve-hour with midnight and noon as 12", () => {
    expect(clockTime(new Date(2026, 8, 7, 0, 7))).toBe("12:07 am");
    expect(clockTime(new Date(2026, 8, 7, 12, 0))).toBe("12:00 pm");
    expect(clockTime(new Date(2026, 8, 7, 23, 59))).toBe("11:59 pm");
  });
});

describe("the short date on a family header", () => {
  it("drops the clock", () => {
    expect(shortDate(new Date(2026, 8, 20, 9, 5), NOW)).toBe("today");
    expect(shortDate(new Date(2026, 8, 19, 9, 5), NOW)).toBe("yesterday");
  });
});
