/** How a session's date reads in a row and in a group header, from the ratified
 * session-menu scaffold. Pure, so it can be checked without a browser. */

const DAY = 24 * 3600 * 1000;
const MONTH = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const MON = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];
const WD = [
  "Sunday", "Monday", "Tuesday", "Wednesday",
  "Thursday", "Friday", "Saturday",
];

const sameDay = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() &&
  a.getMonth() === b.getMonth() &&
  a.getDate() === b.getDate();

const yesterday = (now: Date) => {
  const d = new Date(now);
  d.setDate(d.getDate() - 1);
  return d;
};

export const dayKey = (d: Date) =>
  d.getFullYear() * 10000 + d.getMonth() * 100 + d.getDate();

export function clockTime(d: Date): string {
  const minutes = String(d.getMinutes()).padStart(2, "0");
  const suffix = d.getHours() >= 12 ? "pm" : "am";
  return `${d.getHours() % 12 || 12}:${minutes} ${suffix}`;
}

/** Today / Yesterday / This week / This month / "March 2018". No Earlier. */
export function groupLabel(d: Date, now: Date): string {
  if (sameDay(d, now)) return "Today";
  if (sameDay(d, yesterday(now))) return "Yesterday";
  if (now.getTime() - d.getTime() < 7 * DAY) return "This week";
  if (d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth())
    return "This month";
  return `${MONTH[d.getMonth()]} ${d.getFullYear()}`;
}

/** The row's right-hand side. A day holding two or more sessions shows the
 * clock, so the rows can be told apart; otherwise it says how long ago. */
export function whenText(d: Date, now: Date, sameDayCount: number): string {
  if (sameDayCount >= 2)
    return sameDay(d, now)
      ? clockTime(d)
      : `${MON[d.getMonth()]} ${d.getDate()} · ${clockTime(d)}`;
  if (sameDay(d, now)) return `today ${clockTime(d)}`;
  return shortDate(d, now);
}

export function shortDate(d: Date, now: Date): string {
  if (sameDay(d, now)) return "today";
  if (sameDay(d, yesterday(now))) return "yesterday";
  if (now.getTime() - d.getTime() < 7 * DAY) return WD[d.getDay()];
  if (d.getFullYear() === now.getFullYear())
    return `${MON[d.getMonth()]} ${d.getDate()}`;
  return `${MON[d.getMonth()]} ${d.getFullYear()}`;
}
