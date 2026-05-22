// Basic Test Service Worker
const CACHE_VERSION = '6.09';
const CACHE_NAME = `cv-test-v${CACHE_VERSION}`;

console.log('[SW] Loading basic SW, version:', CACHE_VERSION);

self.addEventListener('install', (event) => {
    console.log('[SW] Installing...');
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[SW] Cache opened');
            return self.skipWaiting();
        })
    );
});

self.addEventListener('activate', (event) => {
    console.log('[SW] Activating...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            console.log('[SW] Found caches:', cacheNames);
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[SW] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    console.log('[SW] Fetch:', event.request.url);
    event.respondWith(fetch(event.request));
});