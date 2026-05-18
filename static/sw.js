var CACHE_NAME = "budgetlab-v1";
var urlsToCache = [
    "/static/style.css",
    "/static/script.js",
    "/static/manifest.json",
    "/static/icon-192x192.png",
    "/static/icon-512x512.png"
];

self.addEventListener("install", function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME).then(function (cache) {
            return cache.addAll(urlsToCache);
        })
    );
});

self.addEventListener("activate", function (event) {
    event.waitUntil(
        caches.keys().then(function (cacheNames) {
            return Promise.all(
                cacheNames.map(function (cacheName) {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

self.addEventListener("fetch", function (event) {
    event.respondWith(
        fetch(event.request).then(function (response) {
            var responseClone = response.clone();
            caches.open(CACHE_NAME).then(function (cache) {
                cache.put(event.request, responseClone);
            });
            return response;
        }).catch(function () {
            return caches.match(event.request);
        })
    );
});
