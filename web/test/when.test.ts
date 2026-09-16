import { describe, expect, it } from "vitest";
import { clockTime, dayLabel, shortDate } from "../src/when";

const NOW = new Date(2026, 8, 20, 15, 30); // Sunday 20 September 2026

describe("the heading over a day's sessions", () => {
  it("names today and yesterday, then the weekday and date", () => {
    expect(dayLabel(new Date(2026, 8, 20, 9, 0), NOW)).toBe("Today");
    expect(dayLabel(new Date(2026, 8, 19, 9, 0), NOW)).toBe("Yesterday");
    expect(dayLabel(new Date(2026, 8, 16, 9, 0), NOW)).toBe("Wed, Sep 16");
    expect(dayLabel(new Date(2018, 2, 4, 9, 0), NOW)).toBe("Sun, Mar 4, 2018");
  });
});

describe("the clock", () => {
  it("reads twelve-hour with midnight and noon as 12", () => {
    expect(clockTime(new Date(2026, 8, 7, 0, 7))).toBe("12:07 am");
    expect(clockTime(new Date(2026, 8, 7, 12, 0))).toBe("12:00 pm");
    expect(clockTime(new Date(2026, 8, 7, 23, 59))).toBe("11:59 pm");
  });
});

describe("the short date on the account page", () => {
  it("drops the clock", () => {
    expect(shortDate(new Date(2026, 8, 20, 9, 5), NOW)).toBe("today");
    expect(shortDate(new Date(2026, 8, 16, 9, 5), NOW)).toBe("Wednesday");
    expect(shortDate(new Date(2019, 1, 3, 9, 5), NOW)).toBe("Feb 2019");
  });
});
