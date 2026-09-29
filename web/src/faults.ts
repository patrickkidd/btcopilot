import { Failed } from "./api";

/** Errors that are never the app's to report, matched exactly on the error's
 * message, or on its name where each browser words the message its own way:
 * the browser's warning that a resize observer ran late, and a request that
 * was cancelled. */
export const NOISE = [
  "ResizeObserver loop limit exceeded",
  "ResizeObserver loop completed with undelivered notifications.",
  "AbortError",
] as const;

/** Where the app's own scripts are served from: the built bundle, and the dev
 * server's sources. The packages the dev server serves from here are not ours. */
const OURS = "/app/static/web/";
const PACKAGES = "/node_modules/";

/** A script's address in a stack, with its line and column, in any engine's
 * wording of a stack. */
const FRAME = /[a-z][a-z0-9+.-]*:\/\/[^\s()]+?:\d+:\d+/g;

/** A request as the endpoint it is, whichever row it names:
 * `GET /app/sessions/12` is `GET /app/sessions/:id`. */
export const endpoint = (request: string) => request.replace(/\/\d+(?=\/|$)/g, "/:id");

/** Which errors on the page raise the bug sheet (R-0056): only one the app's
 * own scripts threw, never noise or the page being torn down, and each once
 * per page, counted after that. */
export class Faults {
  /** The page is going away: what breaks now is the browser tearing it down. */
  leaving = false;
  /** How many times each error has come up on this page. */
  readonly seen = new Map<string, number>();

  constructor(private readonly origin: string) {}

  /** The key this error is raised once by, its message and the top frame of
   * its stack, or null when it is not the app's to report. The server breaking
   * is not one: the call helper raises that itself. */
  key(thrown: unknown, message: string): string | null {
    const name = thrown instanceof Error ? thrown.name : "";
    if (this.leaving || NOISE.some((noise) => noise === message || noise === name)) return null;
    if (!(thrown instanceof Error) || (thrown instanceof Failed && thrown.status >= 500)) return null;
    const frames = thrown.stack?.match(FRAME) ?? [];
    if (!frames.some((frame) => this.ours(frame))) return null;
    return `${message}\n${frames[0]}`;
  }

  /** True the first time this key comes up on the page; every time is counted. */
  first(key: string): boolean {
    const times = (this.seen.get(key) ?? 0) + 1;
    this.seen.set(key, times);
    return times === 1;
  }

  private ours(frame: string): boolean {
    const url = new URL(frame.replace(/:\d+:\d+$/, ""));
    return (
      url.origin === this.origin && url.pathname.startsWith(OURS) && !url.pathname.includes(PACKAGES)
    );
  }
}
