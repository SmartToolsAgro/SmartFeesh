/* global self, caches, fetch, Response, URL */
// Service worker of the driver app (P3-T07a, D-096). No library: it keeps what the app already showed so the
// screens still open without signal.
//  - The app itself (pages, scripts, styles, icons): answered from the cache when it is there, refreshed in
//    the background; a page that was never cached falls back to the home page.
//  - Reads of the API (stock, customers, prices, the day): the network first, the last answer when offline.
//  - Writes are never touched here (the queue of P3-T07b handles them).
const APP = "frutti-truck-app-v1";
const DATA = "frutti-truck-data-v1";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(names.filter((name) => name !== APP && name !== DATA).map((name) => caches.delete(name)));
      await self.clients.claim();
    })(),
  );
});

async function networkFirst(request) {
  const cache = await caches.open(DATA);
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    return response;
  } catch (error) {
    const saved = await cache.match(request);
    if (saved) return saved;
    throw error;
  }
}

async function cacheThenRefresh(request, fallbackUrl) {
  const cache = await caches.open(APP);
  const saved = await cache.match(request);
  const refresh = fetch(request)
    .then(async (response) => {
      if (response.ok) await cache.put(request, response.clone());
      return response;
    })
    .catch(() => undefined);
  if (saved) return saved;
  const fresh = await refresh;
  if (fresh) return fresh;
  const home = fallbackUrl ? await cache.match(fallbackUrl) : undefined;
  return home ?? Response.error();
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) {
    // The session and the CSRF token must always be live.
    if (url.pathname.startsWith("/api/v1/auth/")) return;
    event.respondWith(networkFirst(request));
    return;
  }
  if (request.mode === "navigate") {
    // Every screen is the same page: keep one copy of it under "/".
    event.respondWith(
      (async () => {
        const cache = await caches.open(APP);
        try {
          const response = await fetch(request);
          if (response.ok) await cache.put("/", response.clone());
          return response;
        } catch {
          return (await cache.match("/")) ?? Response.error();
        }
      })(),
    );
    return;
  }
  event.respondWith(cacheThenRefresh(request));
});
