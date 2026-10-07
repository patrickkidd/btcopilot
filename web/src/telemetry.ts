/** Uncaught errors and rejected promises go to the page's own server, which
 * writes each as one log line (doc/MONITORING.md). */

export enum Source {
  Error = "error",
  Rejection = "rejection",
}

export const ERRORS_URL = "/app/browser-errors";

function send(source: Source, reason: unknown): void {
  const error = reason instanceof Error ? reason : undefined;
  void fetch(ERRORS_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    keepalive: true,
    body: JSON.stringify({
      source,
      message: error ? `${error.name}: ${error.message}` : String(reason),
      stack: error?.stack,
      address: location.pathname,
      release: window.BOOTSTRAP?.version,
    }),
  }).catch((failed: unknown) => console.warn("The page's error was not sent", failed));
}

addEventListener("error", (e) => send(Source.Error, e.error ?? e.message));
addEventListener("unhandledrejection", (e) => send(Source.Rejection, e.reason));
