import { DateCertainty } from "../certainty";
import { when } from "../snapshots";
import { known, type CDate } from "./casefile";

/** A date as the case files hold it: a year ("1971"), a month ("1971-04") or a
 * day ("1971-04-09"). The app's record keeps a full date with a certainty; a
 * year-only date is the first of that year, approximate, as the app stores
 * one. A thing the record holds with no date at all ("unknown") has no Dated. */
export type Grain = "year" | "month" | "day";

export interface Dated {
  iso: string;
  certainty: DateCertainty;
  grain: Grain;
}

export function dated(d: CDate | undefined): Dated | null {
  if (!known(d)) return null;
  if (/^\d{4}$/.test(d)) return { iso: `${d}-01-01`, certainty: DateCertainty.Approximate, grain: "year" };
  if (/^\d{4}-\d{2}$/.test(d)) return { iso: `${d}-01`, certainty: DateCertainty.Certain, grain: "month" };
  return { iso: d.slice(0, 10), certainty: DateCertainty.Certain, grain: "day" };
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** The date written as far as the record holds it: "1971", "Apr 1971", "9 Apr 1971". */
export function fullDate(d: Dated): string {
  const [y, m, day] = d.iso.split("-").map(Number);
  if (d.grain === "year") return String(y);
  if (d.grain === "month") return `${MONTHS[m - 1]} ${y}`;
  return `${day} ${MONTHS[m - 1]} ${y}`;
}

/** The last instant of the period a date names, as a year with its fraction. */
export function endOf(d: Dated): number {
  const start = when(d.iso);
  if (d.grain === "year") return start + 1 - 1e-6;
  if (d.grain === "month") return start + 1 / 12 - 1e-6;
  return start + 1 / 365;
}

/** The last day of the period a date names, as an iso date: "1971" is
 * 1971-12-31, "1971-04" is 1971-04-30, a full date is itself. */
export function lastIso(d: Dated): string {
  const [y, m] = d.iso.split("-").map(Number);
  if (d.grain === "day") return d.iso;
  const month = d.grain === "year" ? 12 : m;
  const days = new Date(Date.UTC(y, month, 0)).getUTCDate();
  return `${y}-${String(month).padStart(2, "0")}-${String(days).padStart(2, "0")}`;
}

export const at = (d: CDate | undefined): number | null => {
  const x = dated(d);
  return x ? when(x.iso) : null;
};
