import { expect, it, vi } from "vitest";

interface Config {
  url: string;
  instrumentations: unknown[];
}

const init = vi.hoisted(() =>
  vi.fn((_config: Config) => ({ api: { setUser: vi.fn() } })),
);

vi.mock("@grafana/faro-web-sdk", () => ({
  initializeFaro: init,
  getWebInstrumentations: () => [],
}));
vi.mock("@grafana/faro-instrumentation-replay", () => ({
  ReplayInstrumentation: class ReplayInstrumentation {},
}));

/** The telemetry module as a page served from this host starts it. */
async function served(hostname: string) {
  vi.resetModules();
  init.mockClear();
  vi.stubGlobal("location", { hostname });
  return import("../src/telemetry");
}

const { ReplayInstrumentation } = await import("@grafana/faro-instrumentation-replay");
await served("familydiagram.com");
const [config] = init.mock.calls[0];

// R-0370
it("sends browser telemetry to Grafana Cloud", () => {
  expect(new URL(config.url).hostname).toMatch(/\.grafana\.net$/);
});

// R-0406
it("records sessions for replay", () => {
  expect(config.instrumentations.some((i) => i instanceof ReplayInstrumentation)).toBe(true);
});

// R-0370
it("starts only on the production host, never from a sandbox", async () => {
  for (const host of ["127.0.0.1", "localhost", "turin", "turin.local"]) {
    await served(host);
    expect(init).not.toHaveBeenCalled();
  }
  await served("familydiagram.com");
  expect(init).toHaveBeenCalledTimes(1);
});
