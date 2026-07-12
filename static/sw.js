/* 仙途 Service Worker — 缓存静态资源 */

const CACHE_NAME = "xiantu-v2";
const STATIC_ASSETS = [
    "/static/css/style.css",
    "/static/js/socket.io.min.js",
    "/static/js/socket.js",
    "/static/js/ui.js",
    "/static/js/main.js",
    "/static/manifest.json",
    "/static/icon.svg",
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((names) =>
            Promise.all(names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    const url = new URL(event.request.url);
    // 只缓存静态资源，API 和 WebSocket 请求不缓存
    if (url.pathname.startsWith("/static/")) {
        event.respondWith(
            caches.match(event.request).then((cached) => {
                const fetched = fetch(event.request).then((response) => {
                    if (response.ok) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                    }
                    return response;
                });
                return cached || fetched;
            })
        );
    }
});
