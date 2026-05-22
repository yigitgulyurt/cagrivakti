console.log('[SW] Hello from SW!');

self.addEventListener('install', (event) => {
  console.log('[SW] Installed');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Activated');
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  console.log('[SW] Fetch:', event.request.url);
  event.respondWith(fetch(event.request));
});