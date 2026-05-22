// Service Worker - Ezan Vakti
const CACHE_VERSION = '6.08';
const STATIC_CACHE = `cv-static-v${CACHE_VERSION}`;
const API_CACHE    = `cv-api-v${CACHE_VERSION}`;
const GAME_CACHE   = `cv-game-v${CACHE_VERSION}`;
const JS_CACHE     = `cv-js-v${CACHE_VERSION}`;
const CSS_CACHE    = `cv-css-v${CACHE_VERSION}`;

console.log('[SW] Loading, CACHE_VERSION:', CACHE_VERSION);

// ── Hiç önbelleğe alınmayacak URL'ler ─────────────
const NO_CACHE_URLS = [
    '/kaynak/under-the-red-sky/jsons/saveState.json',
    '/stream/viewers',
    '/stream/ping',
    '/paylas/vakit',
];

// Yükleme (Install) - Basit versiyon, sadece gerekli dosyalar
self.addEventListener('install', (event) => {
    console.log('[SW] Installing...');
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(() => {
                console.log('[SW] Cache opened successfully');
                return self.skipWaiting();
            })
            .catch(err => {
                console.error('[SW] Install error:', err);
                return self.skipWaiting();
            })
    );
});

// Aktifleştirme (Activate) - Eski önbellekleri temizle
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            const allowedCaches = [STATIC_CACHE, API_CACHE, GAME_CACHE, JS_CACHE, CSS_CACHE];
            console.log('[SW] Allowed caches:', allowedCaches);
            console.log('[SW] Found caches:', cacheNames);
            
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (!allowedCaches.includes(cacheName)) {
                        console.log('[SW] Removing old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('[SW] Activate completed, claiming clients');
            return self.clients.claim();
        })
    );
});

// İstekleri Yakalama (Fetch)
self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    const url = new URL(event.request.url);

    // Font ve stream bypass
    if (
        url.hostname === 'fonts.googleapis.com' ||
        url.hostname === 'fonts.gstatic.com' ||
        url.hostname === 'font.yigitgulyurt.net.tr' ||
        url.hostname === 'image.yigitgulyurt.net.tr' ||
        url.pathname.startsWith('/canli-kaynak/') ||
        url.pathname === '/stream/status' ||
        url.pathname.startsWith('/paylas/')
    ) {
        return;
    }

    // Oyun worker dosyaları bypass
    if (
        url.pathname === '/workermain.js' ||
        url.pathname.startsWith('/scripts/jobworker') ||
        url.pathname.startsWith('/scripts/dispatchworker')
    ) {
        return;
    }

    // Hiç cache'lenmeyecek URL'ler
    if (NO_CACHE_URLS.some(p => url.pathname === p)) {
        event.respondWith(fetch(event.request));
        return;
    }

    // API istekleri - Network-First
    if (url.hostname === 'api.cagrivakti.com.tr' && (url.pathname.startsWith('/cagri_vakitleri') || url.pathname.startsWith('/vakitler/'))) {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    if (response.ok) {
                        const responseClone = response.clone();
                        caches.open(API_CACHE).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                })
                .catch(async () => {
                    const cachedResponse = await caches.match(event.request);
                    if (cachedResponse) return cachedResponse;
                    return new Response(JSON.stringify({
                        durum: "hata",
                        mesaj: "İnternet bağlantısı yok ve veri henüz önbelleğe alınmamış."
                    }), {
                        status: 503,
                        headers: { 'Content-Type': 'application/json' }
                    });
                })
        );
        return;
    }

    // js. ve css.yigitgulyurt.net.tr - Stale-While-Revalidate
    if (
        url.hostname === 'js.yigitgulyurt.net.tr' ||
        url.hostname === 'css.yigitgulyurt.net.tr'
    ) {
        const targetCacheName = url.hostname === 'js.yigitgulyurt.net.tr' ? JS_CACHE : CSS_CACHE;

        event.respondWith(
            caches.match(event.request, { ignoreSearch: true }).then((cachedResponse) => {
                const fetchPromise = fetch(event.request, { mode: 'cors', credentials: 'omit' })
                    .then((networkResponse) => {
                        if (networkResponse && networkResponse.status === 200) {
                            caches.open(targetCacheName).then((cache) => {
                                cache.put(event.request, networkResponse.clone());
                            });
                        }
                        return networkResponse;
                    })
                    .catch(() => {
                        if (cachedResponse) {
                            return cachedResponse;
                        }
                    });

                return cachedResponse || fetchPromise;
            })
        );
        return;
    }

    // Statik dosyalar - Stale-While-Revalidate
    event.respondWith(
        caches.match(event.request, { ignoreSearch: true }).then((cachedResponse) => {
            const fetchPromise = fetch(event.request)
                .then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseToCache = networkResponse.clone();
                        caches.open(STATIC_CACHE).then((cache) => {
                            cache.put(event.request, responseToCache);
                        });
                    }
                    return networkResponse;
                })
                .catch((err) => {
                    if (cachedResponse) {
                        return;
                    }
                });

            return cachedResponse || fetchPromise;
        })
    );
});