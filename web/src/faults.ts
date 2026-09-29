import { Failed } from "./api";

/** Errors that are never the app's to report, matched exactly on the error's
 * message, or on its name where each browser words the message its own way:
 * the browser's warning that a resize observer ran late, a request that was
 * cancelled, and a script from another origin, which the browser names no
 * further. */
export const NOISE = [
  "ResizeObserver loop limit exceeded",
  "ResizeObserver loop completed with undelivered notifications.",
  "AbortError",
  "Script error.",
] as const;

/** Where the app's own scripts are served from: the built bundle, and the dev
 * server's sources. The packages the dev server serves from here are not ours. */
const OURS = "/app/static/web/";
const PACKAGES = "/node_modules/";

/** A script's address in a stack, with its line and column, in any engine's
 * wording of a stack. */
const FRAME = /[a-z][a-z0-9+.-]*:\/\/[^\s()]+?:\d+:\d+/g;

/** An error on the page as it is reported: its name and message, and the
 * first frame of its stack in the app's own scripts, which a stack with no
 * frames at all has none of. */
export interface Fault {
  /** What it is raised once by. */
  signature: string;
  error: string;
  frame: string | null;
}

/** Which errors on the page raise the bug sheet (R-0056): one thrown from the
 * app's own scripts or naming no script at all, a refused passkey or a
 * worker that would not start among them; never noise, a request that failed,
 * which the call helper reports, or the page being torn down. Each is raised
 * once per page, counted after that. */
export class Faults {
  /** The page is going away: what breaks now is the browser tearing it down. */
  leaving = false;
  /** How many times each error has come up on this page. */
  readonly seen = new Map<string, number>();

  constructor(private readonly origin: string) {}

  /** This error as it is reported, or null when it is not the app's to
   * report. `said` is what the browser said of it, for something thrown that
   * is not an error. */
  fault(thrown: unknown, said: string): Fault | null {
    const name = thrown instanceof Error ? thrown.name : "";
    const message = thrown instanceof Error ? thrown.message : said;
    if (this.leaving || NOISE.some((noise) => [name, message, said].includes(noise))) return null;
    if (thrown instanceof Failed) return null;
    const frames = (thrown instanceof Error && thrown.stack?.match(FRAME)) || [];
    const frame = frames.find((one) => this.ours(one)) ?? null;
    if (frames.length && frame === null) return null;
    const error = name ? `${name}: ${message}` : message;
    return { signature: `${error}\n${frame ?? ""}`, error, frame };
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
