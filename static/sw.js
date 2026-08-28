var CACHE_NAME = "budgetlab-v5";
var urlsToCache = ["/static/style.css", "/static/script.js", "/static/theme.js", "/static/manifest.json", "/static/icon-192x192.png", "/static/icon-512x512.png"];
self.addEventListener("install", function (e) { e.waitUntil(caches.open(CACHE_NAME).then(function (c) { return c.addAll(urlsToCache) })) });
self.addEventListener("activate", function (e) { e.waitUntil(caches.keys().then(function (n) { return Promise.all(n.map(function (k) { if (k !== CACHE_NAME) return caches.delete(k) })) })) });
self.addEventListener("fetch", function (e) { e.respondWith(fetch(e.request).then(function (r) { var rc = r.clone(); caches.open(CACHE_NAME).then(function (c) { c.put(e.request, rc) }); return r }).catch(function () { return caches.match(e.request) })) });