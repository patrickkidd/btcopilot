import { readFileSync } from "node:fs";
import { beforeEach, expect, it, vi } from "vitest";

const source = (name: string) => readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");

/** An element of the coding screen, as much of one as the fold reads. */
class Box extends EventTarget {
  private names = new Set<string>();
  classList = {
    add: (name: string) => this.names.add(name),
    remove: (name: string) => this.names.delete(name),
    contains: (name: string) => this.names.has(name),
    toggle: (name: string, on: boolean) => (on ? this.names.add(name) : this.names.delete(name)),
  };
  offsetHeight = 144;
  constructor(private kids: Record<string, Box> = {}) {
    super();
  }
  querySelector(selector: string): Box {
    return this.kids[selector];
  }
  closest(): null {
    return null;
  }
  getAnimations(): [] {
    return [];
  }
  blur(): void {
    page.activeElement = null;
    this.dispatchEvent(new Event("blur"));
  }
}

const page: { activeElement: Box | null } = { activeElement: null };
const seen = Object.assign(new EventTarget(), { width: 393, height: 852, scale: 1, pageTop: 0 });
let hardware = false;

vi.stubGlobal("document", page);
vi.stubGlobal("getComputedStyle", () => ({ marginTop: "0px", opacity: "1" }));
vi.stubGlobal("window", {
  visualViewport: seen,
  matchMedia: (query: string) => ({ matches: query.includes("reduce") || hardware }),
});

const { fold } = await import("../src/viewport");

let composer: Box;
let pic: Box;
let screen: Box;
let toEnd: () => void;

beforeEach(() => {
  hardware = false;
  seen.height = 852;
  page.activeElement = null;
  composer = new Box();
  pic = new Box({ ":scope > .pin-label": new Box(), ":scope > .view": new Box() });
  screen = new Box({ ":scope > .pic": pic, ".chat": new Box() });
  toEnd = vi.fn();
  fold(composer as unknown as HTMLElement, screen as unknown as HTMLElement, toEnd, () => Promise.resolve());
});

/** The phone's keyboard comes up over the message box. */
const keyboard = async () => {
  page.activeElement = composer;
  composer.dispatchEvent(new Event("focus"));
  seen.height = 460;
  seen.dispatchEvent(new Event("resize"));
  await Promise.resolve();
};

// R-0949
it("shrinks the coding screen's timeline to the strip while the phone's keyboard is up", async () => {
  await keyboard();
  expect(screen.classList.contains("folded")).toBe(true);
  expect(screen.classList.contains("typing")).toBe(true);
  expect(toEnd).toHaveBeenCalledOnce();
});

// R-0949
it("brings the full timeline back when the keyboard closes", async () => {
  await keyboard();
  composer.blur();
  seen.height = 852;
  seen.dispatchEvent(new Event("resize"));
  expect(screen.classList.contains("folded")).toBe(false);
  expect(screen.classList.contains("typing")).toBe(false);
});

// R-0949
it("puts the keyboard away and opens the full timeline on a tap on the strip", async () => {
  await keyboard();
  pic.dispatchEvent(new Event("click"));
  expect(page.activeElement).toBeNull();
  expect(screen.classList.contains("folded")).toBe(false);
});

// R-0949
it("leaves the timeline whole on a desktop, where the box has focus with no keyboard over it", async () => {
  hardware = true;
  await keyboard();
  expect(screen.classList.contains("folded")).toBe(false);
});

// R-0949
it("drops the home bar's room under the coding screen's message box only while the keyboard is up", () => {
  const css = source("theme.css");
  expect(css).toMatch(/\.inbar \{[^}]*padding: 8px 10px calc\(8px \+ env\(safe-area-inset-bottom\)\);/);
  expect(css).toContain("#coding-screen .typing > .inbar { padding-bottom: 8px; }");
  expect(source("coding.ts")).toMatch(/fold\(\s*composer,\s*view\.closest<HTMLElement>\("\.screen"\)!,/);
  const markup = readFileSync(new URL("../index.html", import.meta.url), "utf8");
  expect(markup).toMatch(/<div class="split" id="coding-screen" hidden>\s*<div class="screen">\s*<div class="pic">/);
});
