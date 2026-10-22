/** What a professional licence turns on. One app on the phone and the desktop,
 * with features turned on by licence, role and view — never a second app
 * (R-0237). A reader without the licence never sees the word case (R-0894). */

export const PRO = window.BOOTSTRAP.user?.pro === true;

/** What a record is called on screen: a professional keeps cases, everyone else
 * keeps their own family. */
export const RECORD = PRO ? "case" : "family";
export const RECORDS = PRO ? "cases" : "families";

const upper = (word: string) => word[0].toUpperCase() + word.slice(1);

export const Record = upper(RECORD);
export const Records = upper(RECORDS);

/** The settings list of diagrams, the same words for everyone (FD-387). */
export const DIAGRAMS = "Diagrams";
export const OWN_FAMILY = "Is this your own family?";

export { WIDE } from "./viewport";
