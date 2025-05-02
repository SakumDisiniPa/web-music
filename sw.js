const CACHE_NAME = 'tunexa-v1';
const urlsToCache = [
  '/',
  'public/index.html',
  'public/css/style.css',
  'public/js/index.js',
  '/icon1',
  '/icon2',
  '/sc1',
  '/sc2'
];

// Install Service Worker
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(urlsToCache))
  );
});

// Fetch cached resources
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => response || fetch(event.request))
  );
});