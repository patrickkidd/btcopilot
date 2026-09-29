/* Minimal offline shell: the built bundle is cached so the app opens without a
   network. Every API call goes to the network untouched. */
// The bundle's files carry a hash in their names, so they are cached as the
// page loads them rather than named here. The page registers the worker with
// the release it was served with, so each release has its own cache and the
// worker for a new one deletes the last one's on activation.
const RELEASE = new URL(self.location.href).searchParams.get("release");
if (!RELEASE) throw new Error("the worker was registered without its release");
const CACHE = `familydiagram-${RELEASE}`;
const SHELL = ["/app/", "/app/manifest.webmanifest"];

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

// A push is only a pointer: to a coach message already in the thread, or to a
// coding task. Its kind is its tag, so the lock screen holds one of each kind
// and the newest of a kind replaces that kind's unread one.
const TITLE = { coach: "Coach", task: "Coding task", reminder: "Coding task" };

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
