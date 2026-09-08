import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

/** Install the fixture records, take a one-time sign-in link for each, and save
 * the session it opens. Every spec then starts already signed in as the fixture
 * it needs, so a golden depends only on the page.
 *
 * The repo and the sandbox database are named by the environment, so this never
 * guesses at anyone's real record:
 *   COMPANION_URL   the sandbox (default http://127.0.0.1:8889)
 *   FIXTURE_CMD     how to run the fixture installer, default
 *                   "uv run flask companion fixtures"
 *   FIXTURE_CWD     where to run it (default ~/theapp)
 */

const HERE = dirname(fileURLToPath(import.meta.url));
export const AUTH = join(HERE, ".auth");
export const KEYS = [
  "empty",
  "one",
  "three40",
  "dense60",
  "hostile",
  "moves",
] as const;
export type Key = (typeof KEYS)[number];

export const stateFor = (key: Key) => join(AUTH, `${key}.json`);

export default async function setup() {
  const base = process.env.COMPANION_URL ?? "http://127.0.0.1:8889";
  const command = (
    process.env.FIXTURE_CMD ?? "uv run flask companion fixtures"
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
    const state = await context.storageState();
    writeFileSync(stateFor(key), JSON.stringify(state));
    await context.close();
  }
  await browser.close();
}
