import type { Locator, Page } from "@playwright/test";

/** What the chat walks check on every thread: the lines under each coach reply,
 * that every tap changes the page, that nothing is still loading before a
 * reload, and that nothing went wrong on the way. */

/** A tool line names what it touched in words: never a vague stand-in, never
 * only a date, never an id or a field name. */
const MONTH = "(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)";
const RULES: [string, RegExp][] = [
  ["vague", /^Changed (someone|an event)$/],
  ["bare date", new RegExp(`^(\\w+ )?(${MONTH} )?(\\d{1,2} )?\\d{4}$`)],
  ["underscore", /_/],
  [
    "id",
    /(\b(id|person|event|pair ?bond|cluster|item)\s*#?\d+\b)|#\d+|^(Added|Changed|Removed|Showed|Looked at|Tried to \w+) #?\d+$|\bc\d+\b/i,
  ],
];

export function badLines(lines: string[]): string[] {
  return lines.flatMap((l) =>
    RULES.filter(([, re]) => re.test(l)).map(([why]) => `${why}: ${l}`),
  );
}

/** Every tap must change the page: a count of changes to the page, read around
 * each click. */
export const deadTaps: string[] = [];

export async function watchDom(page: Page) {
  deadTaps.length = 0;
  await page.addInitScript(() => {
    (window as any).__mut = 0;
    new MutationObserver((m) => {
      (window as any).__mut += m.length;
    }).observe(document, { subtree: true, childList: true, attributes: true, characterData: true });
  });
}

export async function tap(page: Page, target: Locator) {
  const before = await page.evaluate(() => {
    (window as any).__focus = document.activeElement;
    return (window as any).__mut;
  });
  await target.click();
  const changed = await page
    .waitForFunction(
      (n) => (window as any).__mut > n || document.activeElement !== (window as any).__focus,
      before,
      { timeout: 3000 },
    )
    .then(
      () => true,
      () => false,
    );
  if (!changed) deadTaps.push(String(target));
}

/** Requests still running, so a reload never aborts one. Streams that stay open
 * by design (the turn's live log, telemetry) are not waited on. */
const OPEN = /\/events$|grafana\.net|\/collect\//;
const inflight = new WeakMap<Page, Set<unknown>>();

export function trackRequests(page: Page) {
  const open = new Set<unknown>();
  inflight.set(page, open);
  page.on("request", (r) => {
    if (!OPEN.test(r.url())) open.add(r);
  });
  page.on("requestfinished", (r) => open.delete(r));
  page.on("requestfailed", (r) => open.delete(r));
}

export async function settle(page: Page, quietMs = 500, timeoutMs = 30_000) {
  const open = inflight.get(page)!;
  const start = Date.now();
  let quietSince = open.size ? 0 : Date.now();
  while (Date.now() - start < timeoutMs) {
    if (open.size) quietSince = 0;
    else if (!quietSince) quietSince = Date.now();
    else if (Date.now() - quietSince >= quietMs) return;
    await page.waitForTimeout(100);
  }
  throw new Error(
    `requests still open after ${timeoutMs}ms: ${[...open].map((r: any) => r.url()).join(", ")}`,
  );
}

/** Console errors, page errors, failed requests and refused ones, and every
 * path the page posted to. */
export function watch(page: Page) {
  const bad: string[] = [];
  const posts: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error" && !/faro|grafana|Failed to load resource/.test(m.text()))
      bad.push(`console: ${m.text()}`);
  });
  page.on("pageerror", (e) => bad.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) => {
    if (!OPEN.test(r.url()))
      bad.push(`failed: ${r.method()} ${r.url()} ${r.failure()?.errorText}`);
  });
  page.on("response", async (r) => {
    if (r.status() >= 400)
      bad.push(
        `http ${r.status()}: ${r.request().method()} ${r.url()} ${await r.text().catch(() => "")}`,
      );
  });
  page.on("request", (r) => {
    if (r.method() === "POST") posts.push(new URL(r.url()).pathname);
  });
  return { bad, posts };
}

/** The thread as the page draws it and as the page was handed it: each bubble
 * with its words and lines, the try-again buttons, sideways scroll, and any box
 * that sits outside its parent. */
export async function thread(page: Page) {
  return page.evaluate(() => {
    const chat = document.getElementById("chat")!;
    const bubs = [...chat.querySelectorAll(".bub")].map((b) => ({
      role: b.classList.contains("coach") ? "coach" : "user",
      statement: (b as HTMLElement).dataset.statement ?? null,
      text: (b as HTMLElement).innerText,
      lines: [...b.querySelectorAll(".did")].map((d) => d.textContent ?? ""),
    }));
    const outside: string[] = [];
    for (const el of chat.querySelectorAll("*")) {
      const p = el.parentElement!;
      const a = el.getBoundingClientRect();
      const b = p.getBoundingClientRect();
      if (!a.width || !a.height || getComputedStyle(el).position === "fixed") continue;
      const scrolls = /auto|scroll/.test(getComputedStyle(p).overflowY) && p.scrollHeight > p.clientHeight;
      const sideways = a.left < b.left - 1 || a.right > b.right + 1;
      if (sideways || (!scrolls && (a.top < b.top - 1 || a.bottom > b.bottom + 1)))
        outside.push(
          `${el.tagName}.${el.className} in ${p.tagName}.${p.className} [${Math.round(a.left)},${Math.round(a.right)}]x[${Math.round(a.top)},${Math.round(a.bottom)}] vs [${Math.round(b.left)},${Math.round(b.right)}]x[${Math.round(b.top)},${Math.round(b.bottom)}]`,
        );
    }
    const doc = document.documentElement;
    return {
      bubs,
      retry: chat.querySelectorAll("button.retry").length,
      hscroll: doc.scrollWidth - doc.clientWidth,
      chatHscroll: chat.scrollWidth - chat.clientWidth,
      outside,
      html: chat.innerHTML.length + ":" + chat.innerHTML.slice(-400),
      statements: (window as any).BOOTSTRAP.statements as any[],
      session: (window as any).BOOTSTRAP.session?.id as number,
    };
  });
}

/** The session's statements as the server holds them now, not as the page
 * drew them. */
export async function stored(page: Page, sessionId: number): Promise<any[] | null> {
  return page.evaluate(async (id) => {
    const resp = await fetch(`/app/sessions/${id}`);
    if (!resp.ok) return null;
    const j = await resp.json();
    return j.statements ?? j.session?.statements ?? [];
  }, sessionId);
}
