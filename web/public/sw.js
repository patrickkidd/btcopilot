/* Minimal offline shell: the built bundle is cached so the app opens without a
   network. Every API call goes to the network untouched. */
// The bundle's files carry a hash in their names, so they are cached as the
// page loads them rather than named here. The page registers the worker with
// the release it was served with, so each release has its own cache and the
// worker for a new one deletes the last one's on activation.
const HERE = new URL(self.location.href);
const RELEASE = HERE.searchParams.get("release");
if (!RELEASE) throw new Error("the worker was registered without its release");
const CACHE = `familydiagram-${RELEASE}`;
const SHELL = ["/app/", "/app/manifest.webmanifest"];

// An error in the worker is reported as it happens, with no sheet: the worker
// has no screen to raise one on (R-0056). Only the frames of its stack in the
// worker itself go with it. A report that cannot be sent is only logged, since
// reporting that would report again.
const FRAME = /[a-z][a-z0-9+.-]*:\/\/[^\s()]+?:\d+:\d+/g;

function report(thrown) {
  const error = thrown instanceof Error ? `${thrown.name}: ${thrown.message}` : String(thrown);
  const frames = ((thrown instanceof Error && thrown.stack) || "").match(FRAME) || [];
  return fetch("/app/reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      kind: "bug",
      status: "sent",
      source: "worker",
      release: RELEASE,
      address: HERE.pathname,
      error,
      frames: frames.filter((frame) => frame.startsWith(HERE.origin + HERE.pathname)),
    }),
  }).catch((failed) => console.warn("the worker's report was not sent", failed));
}

self.addEventListener("error", (e) => report(e.error ?? e.message));
self.addEventListener("unhandledrejection", (e) => report(e.reason));

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(CACHE)
      .then((c) => c.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  const shell =
    e.request.mode === "navigate" ||
    url.pathname.startsWith("/app/static/web/");
  if (e.request.method !== "GET" || !shell) return;
  e.respondWith(
    fetch(e.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return response;
      })
      .catch(() =>
        caches.match(e.request).then((hit) => hit || caches.match("/app/")),
      ),
  );
});

// A push is only a pointer: to a coach message already in the thread, to a
// coding task, or to a product notice. Its kind is its tag, so the lock screen holds one of each kind
// and the newest of a kind replaces that kind's unread one.
const TITLE = {
  coach: "Coach",
  task: "Coding task",
  reminder: "Coding task",
  notice: "Family Diagram",
};

self.addEventListener("push", (e) => {
  const { id, kind, body } = e.data.json();
  e.waitUntil(
    self.registration.showNotification(TITLE[kind], {
      body,
      tag: kind,
      renotify: true,
      icon: "/app/static/web/apple-touch-icon.png",
      data: { id },
    }),
  );
});

/** The app already open is told which message to show, so a draft in it
 * survives; otherwise the tap opens the app on that message. */
function arrive(id) {
  return self.clients.matchAll({ type: "window" }).then(([app]) => {
    if (!app) return self.clients.openWindow(`/app/?notification=${id}`);
    app.postMessage({ notification: id });
    return app.focus();
  });
}

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(arrive(e.notification.data.id));
});
