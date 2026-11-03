/* RoutePou web app service worker.
   Caches this site's own files so the guide opens offline. Cross-origin requests (the IP lookups)
   are never touched, so the connection check always asks the live network. */
"use strict";

var CACHE = "routepou-web-v1";
var FILES = [
  "./", "index.html", "app.css", "app.js", "strings.js", "manifest.webmanifest",
  "icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png"
];

self.addEventListener("install", function (event) {
  event.waitUntil(caches.open(CACHE).then(function (cache) { return cache.addAll(FILES); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  var req = event.request;
  var url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) { return; }

  /* pages: network first, so a new release shows up at once; fall back to the cached copy offline */
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (cache) { cache.put("index.html", copy); });
        return res;
      }).catch(function () { return caches.match("index.html"); })
    );
    return;
  }

  /* static files: cached copy first, refreshed in the background */
  event.respondWith(
    caches.match(req).then(function (hit) {
      var fresh = fetch(req).then(function (res) {
        if (res && res.ok) {
          var copy = res.clone();
          caches.open(CACHE).then(function (cache) { cache.put(req, copy); });
        }
        return res;
      }).catch(function () { return hit; });
      return hit || fresh;
    })
  );
});
