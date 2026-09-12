/** What a professional licence turns on. One app on the phone and the desktop,
 * with features turned on by licence, role and view — never a second app
 * (R-0237). A reader without the licence never sees the word case (R-0285). */

export const PRO = window.BOOTSTRAP.user?.pro === true;

/** What a record is called on screen: a professional keeps cases, everyone else
 * keeps their own family. */
export const RECORD = PRO ? "case" : "family";
export const RECORDS = PRO ? "cases" : "families";

const upper = (word: string) => word[0].toUpperCase() + word.slice(1);

export const Record = upper(RECORD);
export const Records = upper(RECORDS);

/** The drawer stands beside the thread rather than sliding over it once the
 * window is this wide, which is the width the desktop drawings are drawn at. */
export const WIDE = "(min-width: 840px)";
