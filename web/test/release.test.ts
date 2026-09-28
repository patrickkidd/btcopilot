import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { IDLE_POLL_MS, Release } from "../src/release";

let busy: boolean;
let reload: ReturnType<typeof vi.fn>;
const release = (live: string) =>
  new Release("3.2026.9.27.1", async () => live, () => busy, reload);

beforeEach(() => {
  vi.useFakeTimers();
  busy = false;
  reload = vi.fn();
});
afterEach(() => vi.useRealTimers());

describe("coming back to the front after a deploy", () => {
  // R-0486
  it("stays on the page when the server runs the release it was served with", async () => {
    await release("3.2026.9.27.1").check();
    expect(reload).not.toHaveBeenCalled();
  });

  // R-0486
  it("loads the release the server runs now when it changed", async () => {
    await release("3.2026.9.28.1").check();
    expect(reload).toHaveBeenCalledOnce();
  });

  // R-0486, R-0369
  it("waits while unsent words or a running turn would be lost, then loads", async () => {
    busy = true;
    await release("3.2026.9.28.1").check();
    vi.advanceTimersByTime(IDLE_POLL_MS * 5);
    expect(reload).not.toHaveBeenCalled();
    busy = false;
    vi.advanceTimersByTime(IDLE_POLL_MS);
    expect(reload).toHaveBeenCalledOnce();
  });

  // R-0486
  it("loads once however often the app comes back while it waits", async () => {
    busy = true;
    const page = release("3.2026.9.28.1");
    await page.check();
    await page.check();
    busy = false;
    vi.advanceTimersByTime(IDLE_POLL_MS);
    expect(reload).toHaveBeenCalledOnce();
  });
});
