import { describe, expect, it } from "vitest";
import { clockTime, periodLabel, rowDate, shortDate } from "../src/when";

const NOW = new Date(2026, 8, 20, 15, 30); // Sunday 20 September 2026

describe("the heading a session sits under", () => {
  // R-0347
  it("is today, yesterday, the last week, the last month, then the month", () => {
    expect(periodLabel(new Date(2026, 8, 20, 9, 0), NOW)).toBe("Today");
    expect(periodLabel(new Date(2026, 8, 19, 9, 0), NOW)).toBe("Yesterday");
    expect(periodLabel(new Date(2026, 8, 16, 9, 0), NOW)).toBe("Previous 7 days");
    expect(periodLabel(new Date(2026, 8, 2, 9, 0), NOW)).toBe("Previous 30 days");
    expect(periodLabel(new Date(2026, 5, 2, 9, 0), NOW)).toBe("June");
    expect(periodLabel(new Date(2018, 2, 4, 9, 0), NOW)).toBe("March 2018");
  });
});

describe("the date in a row", () => {
  // no ruling
  it("names the day, and the year only when it is another year", () => {
    expect(rowDate(new Date(2026, 8, 12), NOW)).toBe("Sep 12");
    expect(rowDate(new Date(2019, 1, 3), NOW)).toBe("Feb 3, 2019");
  });
});

describe("the clock", () => {
  // no ruling
  it("reads twelve-hour with midnight and noon as 12", () => {
    expect(clockTime(new Date(2026, 8, 7, 0, 7))).toBe("12:07 am");
    expect(clockTime(new Date(2026, 8, 7, 12, 0))).toBe("12:00 pm");
    expect(clockTime(new Date(2026, 8, 7, 23, 59))).toBe("11:59 pm");
  });
});

describe("the short date on the account page", () => {
  // no ruling
  it("drops the clock", () => {
    expect(shortDate(new Date(2026, 8, 20, 9, 5), NOW)).toBe("today");
    expect(shortDate(new Date(2026, 8, 16, 9, 5), NOW)).toBe("Wednesday");
    expect(shortDate(new Date(2019, 1, 3, 9, 5), NOW)).toBe("Feb 2019");
  });
});
