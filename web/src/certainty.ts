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
