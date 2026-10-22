/** How sure the record is of a date. Unknown means the date matches anything,
 * so the event has no place on the line and belongs on the undated shelf.
 *
 * A const object rather than an enum, in a file of its own: the Playwright
 * walks import modules that use it, and Node 24 loads those with their types
 * stripped, which cannot carry an enum. */
export const DateCertainty = {
  Unknown: "unknown",
  Approximate: "approximate",
  Certain: "certain",
} as const;
export type DateCertainty = (typeof DateCertainty)[keyof typeof DateCertainty];

/** How much of an event's date the person said; the date is always a whole
 * day, the first of what was said. Null on an event from before it was kept,
 * which reads as the day. */
export const DatePrecision = {
  Year: "year",
  Month: "month",
  Day: "day",
} as const;
export type DatePrecision = (typeof DatePrecision)[keyof typeof DatePrecision];
