// Cache public assets only; never conversations, pages, tokens or API responses.
const CACHE_NAME = "hsaai-public-v4";
const isPublicAsset = (url) => url.origin === self.location.origin &&
  (url.pathname.startsWith("/brand/") || url.pathname.startsWith("/fonts/") || url.pathname.startsWith("/_next/static/"));
self.addEventListener("install", (event) => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((key) => key.startsWith("hsaai-") && key !== CACHE_NAME).map((key) => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET" || !isPublicAsset(new URL(event.request.url))) return;
  event.respondWith(caches.open(CACHE_NAME).then(async (cache) => {
    const cached = await cache.match(event.request);
    if (cached) return cached;
    const response = await fetch(event.request);
    if (response.ok && !response.redirected && !/no-store|private/.test(response.headers.get("Cache-Control") || "")) await cache.put(event.request, response.clone());
    return response;
  }));
});
