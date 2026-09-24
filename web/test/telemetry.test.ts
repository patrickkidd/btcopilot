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

const { ReplayInstrumentation } = await import("@grafana/faro-instrumentation-replay");
await import("../src/telemetry");
const [config] = init.mock.calls[0];

// R-0370
it("sends browser telemetry to Grafana Cloud", () => {
  expect(new URL(config.url).hostname).toMatch(/\.grafana\.net$/);
});

// R-0406
it("records sessions for replay", () => {
  expect(config.instrumentations.some((i) => i instanceof ReplayInstrumentation)).toBe(true);
});
