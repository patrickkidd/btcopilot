import { execFileSync } from "node:child_process";
import {
  closeSync,
  mkdirSync,
  openSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

/** Install the fixture records, take a one-time sign-in link for each, and save
 * the session it opens. Every spec then starts already signed in as the fixture
 * it needs, so a golden depends only on the page.
 *
 * The repo and the sandbox database are named by the environment, so this never
 * guesses at anyone's real record:
 *   SANDBOX_URL   the sandbox (default http://127.0.0.1:8889)
 *   FIXTURE_CMD     how to run the fixture installer, default
 *                   "uv run flask personal fixtures"
 *   FIXTURE_CWD     where to run it (default ~/theapp)
 *
 * The installer inherits this environment, so FLASK_SQLALCHEMY_DATABASE_URI must
 * name the same database SANDBOX_URL is serving. Point it anywhere else and the
 * installer writes tokens the sandbox has never heard of: every invite answers 400
 * and it reads as an auth failure. Run the installer without swallowing stderr when
 * that happens — it crashes on a schema it cannot read and prints nothing at all.
 *
 * Installing the fixtures deletes and recreates each fixture user's diagram and
 * discussions, which signs out any run already using them. Several people share
 * one checkout and one sandbox database here, so a whole run holds an exclusive
 * lock: a second run waits rather than pulling the record out from under the
 * first. Without it a suite fails with no bubbles on the page at all.
 */

const LOCK = join(dirname(fileURLToPath(import.meta.url)), ".lock");
const LOCK_WAIT_MS = 10 * 60 * 1000;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function releaseLock(): void {
  rmSync(LOCK, { force: true });
}

/** A run killed outright cannot clean up after itself, so the lock carries the
 * pid that took it and a lock whose process is gone is not a lock. */
function heldByLiveRun(): boolean {
  let pid: number;
  try {
    pid = Number(readFileSync(LOCK, "utf8").trim());
  } catch {
    return false;
  }
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

async function takeLock(): Promise<void> {
  const until = Date.now() + LOCK_WAIT_MS;
  for (;;) {
    try {
      const handle = openSync(LOCK, "wx");
      writeFileSync(handle, String(process.pid));
      closeSync(handle);
      process.on("exit", releaseLock);
      for (const signal of ["SIGINT", "SIGTERM"] as const)
        process.once(signal, () => {
          releaseLock();
          process.exit(1);
        });
      return;
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "EEXIST") throw e;
      if (!heldByLiveRun()) {
        rmSync(LOCK, { force: true });
        continue;
      }
      if (Date.now() > until)
        throw new Error(`another visual run has held ${LOCK} for ten minutes`);
      await sleep(2000);
    }
  }
}

const HERE = dirname(fileURLToPath(import.meta.url));
export const AUTH = join(HERE, ".auth");
export const KEYS = [
  "empty",
  "one",
  "three40",
  "dense60",
  "hostile",
  "moves",
  "play",
  "longname",
] as const;
export type Key = (typeof KEYS)[number];

export const stateFor = (key: Key) => join(AUTH, `${key}.json`);

/** For the goldens of a drawing rather than a page. The suite's one percent
 * ratio is worth hundreds of pixels on a small cell, enough to hide a whole
 * stroke width: five move drawings once passed while carrying the wrong one.
 * An absolute count instead, loose enough for antialiasing and nothing more.
 * The ratio is set wide so it cannot be the binding limit, because the
 * stricter of the two applies. */
export const EXACT = { maxDiffPixels: 8, maxDiffPixelRatio: 1 };

export default async function setup() {
  await takeLock();
  const base = process.env.SANDBOX_URL ?? "http://127.0.0.1:8889";
  const command = (
    process.env.FIXTURE_CMD ?? "uv run flask personal fixtures"
  ).split(" ");
  const cwd = process.env.FIXTURE_CWD ?? join(process.env.HOME ?? "", "theapp");

  const printed = execFileSync(command[0], [...command.slice(1), ...KEYS], {
    cwd,
    encoding: "utf8",
    env: process.env,
  });
  const tokens = new Map<string, string>();
  for (const line of printed.split("\n")) {
    const [key, token] = line.trim().split(/\s+/);
    if (KEYS.includes(key as Key) && token) tokens.set(key, token);
  }
  if (tokens.size !== KEYS.length)
    throw new Error(
      `the fixture installer returned ${tokens.size} of ${KEYS.length} sign-in links`,
    );

  mkdirSync(AUTH, { recursive: true });
  const browser = await chromium.launch();
  for (const key of KEYS) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(`${base}/invite/${tokens.get(key)}`, {
      waitUntil: "domcontentloaded",
    });
    // A sign-in link works once. If it has already been opened, or if the
    // installer wrote to a different database than the sandbox reads, the
    // invite answers with the sign-in page and the state below would be
    // anonymous — every golden then shows a logged-out shell. Fail here
    // instead, where the cause is still visible.
    const me = await page.request.get(`${base}/me`);
    if (!me.ok() || !(await me.json()).user)
      throw new Error(
        `the sign-in link for "${key}" did not open a session (GET /me returned ${me.status()}). ` +
          `The link is single-use, and the installer and ${base} must share one database.`,
      );
    const state = await context.storageState();
    writeFileSync(stateFor(key), JSON.stringify(state));
    await context.close();
  }
  await browser.close();
}
