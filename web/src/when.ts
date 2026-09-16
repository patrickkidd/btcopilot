/** How a session's date reads in a row and in a group header, from the ratified
 * session-menu scaffold. Pure, so it can be checked without a browser. */

const DAY = 24 * 3600 * 1000;
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

/** The heading over a day's sessions: Today, Yesterday, then the weekday and
 * date, with the year once it is not this one. */
export function dayLabel(d: Date, now: Date): string {
  if (sameDay(d, now)) return "Today";
  if (sameDay(d, yesterday(now))) return "Yesterday";
  const date = `${WD[d.getDay()].slice(0, 3)}, ${MON[d.getMonth()]} ${d.getDate()}`;
  return d.getFullYear() === now.getFullYear() ? date : `${date}, ${d.getFullYear()}`;
}

/** The next meeting, named the same way wherever it is named: the agenda
 * screen's own title, and the sessions sheet's way in to it. */
export function meetingTitle(date: string | null): string {
  if (!date) return "Next meeting";
  const d = new Date(`${date}T00:00:00`);
  return `Next meeting · ${WD[d.getDay()].slice(0, 3)}, ${MON[d.getMonth()]} ${d.getDate()}`;
}

/** A stored timestamp said as a bare day, the way a row names one: "Sep 15". */
export function dayText(value: string): string {
  const d = new Date(value);
  return `${MON[d.getMonth()]} ${d.getDate()}`;
}

export function shortDate(d: Date, now: Date): string {
  if (sameDay(d, now)) return "today";
  if (sameDay(d, yesterday(now))) return "yesterday";
  if (now.getTime() - d.getTime() < 7 * DAY) return WD[d.getDay()];
  if (d.getFullYear() === now.getFullYear())
    return `${MON[d.getMonth()]} ${d.getDate()}`;
  return `${MON[d.getMonth()]} ${d.getFullYear()}`;
}
