import { Link } from "./types";

/** Every view and object in the app has an address under /app/, so the address
 * bar says where the app is, the back button steps back through it, and the
 * coach, a notice or a link can put the app anywhere (R-0055). Each value is
 * the address after /app/: a word stands for itself, `:n` for a number, `:key`
 * for an id of any shape, and `:day` for a meeting's day, or `undated` for the
 * meeting that has none. btcopilot/place.py mirrors this table and a test
 * keeps the two equal. Where two could read one address, the first written
 * wins.
 *
 * Every address sits under the diagram the app is on, named by its public id:
 * `/app/diagram/<public id>/account/coach`. The same place written without
 * that segment, `/app/account/coach`, is that place on the diagram the app is
 * on, which is how the coach, a notice and the home-screen icon still say
 * where to go. */
export enum Place {
  Chat = "",
  Message = "chat/:n",
  Sessions = "sessions",
  Session = "sessions/:n",
  Account = "account",
  Profile = "account/profile",
  Notices = "account/notices",
  Notice = "account/notices/:n",
  Coach = "account/coach",
  Appearance = "account/appearance",
  Diagrams = "account/diagrams",
  Theirs = "account/diagrams/:n",
  Plan = "account/plan",
  Task = "account/coding-task",
  Agenda = "account/meeting",
  MeetingDay = "account/meeting/:day",
  MeetingCut = "account/meeting/:day/:n",
  Literature = "account/literature-review",
  Cluster = "cluster/:key",
  NewEvent = "event/new",
  Event = "event/:n",
  EventEditor = "event/:n/edit",
  NewPerson = "person/new",
  Person = "person/:n",
  Events = "events",
  People = "people",
  Questions = "questions",
  CaseReport = "case-report",
  Play = "play/:n",
  PlayStep = "play/:n/:n",
  Family = "family",
  FamilyStep = "family/:n",
  Coding = "coding/:n",
  Vote = "vote/:n",
  Meeting = "meeting/:n",
  Result = "result/:n",
  Guidelines = "guidelines",
}

export const APP = "/app/";

/** The meeting that has no day yet, in its address. */
export const UNDATED = "undated";

/** The word before a diagram's public id in an address; no place starts with it. */
export const DIAGRAM = "diagram";

const SLOT: Record<string, RegExp> = {
  ":n": /^\d+$/,
  ":key": /^[\w.-]+$/,
  ":day": new RegExp(`^(\\d{4}-\\d{2}-\\d{2}|${UNDATED})$`),
};

const UNDER = new RegExp(`^${APP}${DIAGRAM}/([a-z0-9]+)(?=/|$)`);

/** One place and what fills its slots, in order, on the diagram the address
 * names, or on the one the app is on when it names none. */
export interface Spot {
  place: Place;
  args: string[];
  diagram: string | null;
}

const parts = (place: Place) => (place ? place.split("/") : []);

/** The address of one place with its slots filled, on the diagram the app is
 * on; `on` puts it under one diagram by name. */
export function address(place: Place, ...args: (string | number)[]): string {
  const slots = parts(place).filter((part) => part in SLOT);
  if (slots.length !== args.length)
    throw new Error(`${place || "the chat"} takes ${slots.length} values, not ${args.length}`);
  let at = 0;
  return APP + parts(place).map((part) => (part in SLOT ? String(args[at++]) : part)).join("/");
}

/** The public id of the diagram an address names, and the address under it:
 * `/app/diagram/k7m2x9pq4w/account` is `k7m2x9pq4w` and `/app/account`. An
 * address without the segment names no diagram and is its own rest. */
export function split(path: string): { diagram: string | null; under: string } {
  const bare = path.split(/[?#]/)[0];
  const found = UNDER.exec(bare);
  if (!found) return { diagram: null, under: bare };
  return { diagram: found[1], under: APP.slice(0, -1) + bare.slice(found[0].length) };
}

/** The same place under one diagram, by its public id: `/app/account` on
 * `k7m2x9pq4w` is `/app/diagram/k7m2x9pq4w/account`. An address already under
 * a diagram is moved; with no diagram to be on, it is left bare. */
export function on(diagram: string | null, path: string): string {
  const { under } = split(path);
  if (diagram === null) return under;
  return `${APP}${DIAGRAM}/${diagram}${under.slice(APP.length - 1)}`;
}

/** Which place an address names, or null for one the app does not have. A
 * trailing slash and anything after `?` or `#` are not part of it. */
export function parse(path: string): Spot | null {
  const { diagram, under } = split(path);
  const bare = under.replace(/\/+$/, "");
  const root = APP.slice(0, -1);
  if (bare !== root && !bare.startsWith(APP)) return null;
  const words = bare === root ? [] : bare.slice(APP.length).split("/");
  for (const place of Object.values(Place)) {
    const want = parts(place);
    if (want.length !== words.length) continue;
    if (want.every((part, i) => (part in SLOT ? SLOT[part].test(words[i]) : part === words[i])))
      return { place, args: words.filter((_, i) => want[i] in SLOT), diagram };
  }
  return null;
}

/** An address that lights something inside a view names that view once the
 * light has faded, which is how the app compares where it is with the bar. */
const SETTLES: Partial<Record<Place, (args: string[]) => { place: Place; args: string[] }>> = {
  [Place.Message]: () => ({ place: Place.Chat, args: [] }),
  [Place.Session]: () => ({ place: Place.Sessions, args: [] }),
  [Place.Notice]: () => ({ place: Place.Notices, args: [] }),
  [Place.MeetingCut]: ([day]) => ({ place: Place.MeetingDay, args: [day] }),
  [Place.PlayStep]: ([statement]) => ({ place: Place.Play, args: [statement] }),
  [Place.FamilyStep]: () => ({ place: Place.Family, args: [] }),
};

/** Still on the diagram the address was on. */
export function settled(path: string): string | null {
  const spot = parse(path);
  if (!spot) return null;
  const view = SETTLES[spot.place]?.(spot.args) ?? spot;
  return on(spot.diagram, address(view.place, ...view.args));
}

/** The places that are the chat and its picture: moving between them changes
 * the address in place rather than adding a step to go back through, so a
 * reply naming five things is not five presses of back. */
export const PICTURE = new Set([Place.Chat, Place.Message, Place.Cluster, Place.Event]);

/** The fixed screens a notice names, by the place each one is (R-0613). */
const LINKED: Record<Link, Place> = {
  [Link.Account]: Place.Account,
  [Link.Coach]: Place.Coach,
  [Link.Task]: Place.Task,
  [Link.Agenda]: Place.Agenda,
};

/** Where a notification's link goes: one of the fixed screens, or any address
 * in the app. */
export const linked = (link: string): string =>
  link.startsWith(APP) ? link : address(LINKED[link as Link]);

/** Each place by the name a button that opens it gives it. */
export const NAMES: Record<Place, string> = {
  [Place.Chat]: "Chat",
  [Place.Message]: "Message",
  [Place.Sessions]: "Sessions",
  [Place.Session]: "Session",
  [Place.Account]: "Account",
  [Place.Profile]: "Profile",
  [Place.Notices]: "Notices",
  [Place.Notice]: "Notices",
  [Place.Coach]: "Coach settings",
  [Place.Appearance]: "Appearance",
  [Place.Diagrams]: "Diagrams",
  [Place.Theirs]: "Their diagrams",
  [Place.Plan]: "Your Plan",
  [Place.Task]: "Your coding task",
  [Place.Agenda]: "Next meeting",
  [Place.MeetingDay]: "Meeting",
  [Place.MeetingCut]: "Meeting",
  [Place.Literature]: "Auditor's Coding Guide",
  [Place.Cluster]: "Cluster",
  [Place.NewEvent]: "New event",
  [Place.Event]: "Event",
  [Place.EventEditor]: "Event",
  [Place.NewPerson]: "New person",
  [Place.Person]: "Person",
  [Place.Events]: "Events",
  [Place.People]: "People",
  [Place.Questions]: "Questions",
  [Place.CaseReport]: "Case report",
  [Place.Play]: "Play-by-play",
  [Place.PlayStep]: "Play-by-play",
  [Place.Family]: "Family",
  [Place.FamilyStep]: "Family",
  [Place.Coding]: "Coding",
  [Place.Vote]: "Vote",
  [Place.Meeting]: "Meeting",
  [Place.Result]: "Result",
  [Place.Guidelines]: "Guidelines",
};

/** The account view and its Notices hold the notice already, so a link to
 * them shows nothing more than the notice's own words. */
const HOLDS = new Set([Place.Account, Place.Notices, Place.Notice]);

/** The name of where a notice's link takes the reader, or null when there is
 * nothing more to see there (Patrick, 2026-09-29). */
export function beyond(link: string | null): string | null {
  if (link === null) return null;
  const spot = parse(linked(link));
  if (!spot) throw new Error(`${link} is no address in the app`);
  return HOLDS.has(spot.place) ? null : NAMES[spot.place];
}
