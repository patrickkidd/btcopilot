import { ReplayInstrumentation } from "@grafana/faro-instrumentation-replay";
import { getWebInstrumentations, initializeFaro } from "@grafana/faro-web-sdk";

const FARO_URL =
  "https://faro-collector-prod-us-west-0.grafana.net/collect/5f770e33802f802976174ef8f5ff793b";

/** Only the page production serves reports to the production collector; a
 * sandbox or a dev server reports nothing (R-0370). */
const PRODUCTION = "familydiagram.com";

const faro =
  location.hostname === PRODUCTION
    ? initializeFaro({
        url: FARO_URL,
        app: { name: "fd-app", environment: import.meta.env.MODE },
        instrumentations: [...getWebInstrumentations(), new ReplayInstrumentation()],
      })
    : undefined;

export function identify(email: string): void {
  faro?.api.setUser({ email });
}
