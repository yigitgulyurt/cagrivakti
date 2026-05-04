// Service Worker - Ezan Vakitleri
/* global VERSION */
const STATIC_CACHE = `cv-static-v${VERSION}`;
const API_CACHE    = `cv-api-v${VERSION}`;
const GAME_CACHE   = `cv-game-v${VERSION}`;
const JS_CACHE     = `cv-js-v${VERSION}`;
const CSS_CACHE    = `cv-css-v${VERSION}`;

// ── Statik dosyalar (İkonlar) ──────────────────────────────────────────────
const STATIC_ASSETS = [
    '/static/icons/favicon.ico',
    '/static/icons/ios/180.png',
    '/static/icons/android/android-launchericon-192-192.png',
    '/static/icons/android/android-launchericon-512-512.png',
    '/static/icons/windows11/Square150x150Logo.scale-100.png',
];

// ── Sayfa URL'leri ───────────────────────────────────────────────────────────
const PAGE_ASSETS = [
    '/',
    '/offline',
    '/sehir',
    '/imsakiye',
    '/ramazan',
    '/neden-biz',
    '/indir',
    '/konum-bul',
    '/iletisim',
    '/ilkelerimiz',
    '/bilgi-kosesi',
    '/asal-sayi',
    '/Mustafa-Kemal-Ataturk',
];

// ── Cross-origin subdomain dosyaları (js. ve css.yigitgulyurt.net.tr) ────────
// Buraya çektiğin JS dosyalarının tam URL'lerini ekle.
// Örnek: 'https://js.yigitgulyurt.net.tr/jquery.min.js'
const JS_ASSETS = [
    'https://js.yigitgulyurt.net.tr/cagrivakti/jquery.cagrivakti.js',
    'https://js.yigitgulyurt.net.tr/cagrivakti/inappredirect.cagrivakti.js',
    'https://js.yigitgulyurt.net.tr/cagrivakti/city-data.cagrivakti.js'
];

// Buraya çektiğin CSS dosyalarının tam URL'lerini ekle.
// Örnek: 'https://css.yigitgulyurt.net.tr/main.css'
const CSS_ASSETS = [
    'https://css.yigitgulyurt.net.tr/cagrivakti/main.cagrivakti.css',
];

// JS_ASSETS ve CSS_ASSETS'i Request objelerine çevir (cross-origin için zorunlu)
const JS_REQUESTS = JS_ASSETS.map(
    (url) => new Request(url, { mode: 'cors', credentials: 'omit' })
);
const CSS_REQUESTS = CSS_ASSETS.map(
    (url) => new Request(url, { mode: 'cors', credentials: 'omit' })
);

// ── Hiç önbelleğe alınmayacak URL'ler (tam eşleşme veya prefix) ─────────────
const NO_CACHE_URLS = [
    '/kaynak/under-the-red-sky/jsons/saveState.json',
    '/stream/viewers',
    '/stream/ping',
];

// Yükleme (Install) - Kritik dosyaları önbelleğe al
self.addEventListener('install', (event) => {
    event.waitUntil(
        Promise.all([
            caches.open(STATIC_CACHE).then((cache) => {
                console.log('[SW] Pre-caching static assets');
                return cache.addAll([...STATIC_ASSETS, ...PAGE_ASSETS]);
            }),
            caches.open(JS_CACHE).then((cache) => {
                console.log('[SW] Pre-caching JS assets');
                return cache.addAll(JS_REQUESTS);
            }),
            caches.open(CSS_CACHE).then((cache) => {
                console.log('[SW] Pre-caching CSS assets');
                return cache.addAll(CSS_REQUESTS);
            })
        ]).then(() => self.skipWaiting())
    );
});

// Aktifleştirme (Activate) - Eski önbellekleri temizle
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            const allowedCaches = [STATIC_CACHE, API_CACHE, GAME_CACHE, JS_CACHE, CSS_CACHE];
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (!allowedCaches.includes(cacheName)) {
                        console.log('[SW] Removing old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// İstekleri Yakalama (Fetch)
self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;

    const url = new URL(event.request.url);

    // Font ve stream bypass (CORS hatalarını önlemek için fontlar yakalanmaz)
    if (
        url.hostname === 'fonts.googleapis.com' ||
        url.hostname === 'fonts.gstatic.com' ||
        url.hostname === 'fonts.yigitgulyurt.net.tr' ||
        url.pathname.startsWith('/canli-kaynak/') ||
        url.pathname === '/stream/status'
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

    // Hiç cache'lenmeyecek URL'ler — her zaman ağdan getir
    if (NO_CACHE_URLS.some(p => url.pathname === p)) {
        event.respondWith(fetch(event.request));
        return;
    }

    // Oyun dosyaları — ayrı GAME_CACHE, Stale-While-Revalidate
    if (url.pathname.startsWith('/kaynak/under-the-red-sky/')) {
        event.respondWith(
            caches.open(GAME_CACHE).then((cache) => {
                return cache.match(event.request).then((cachedResponse) => {
                    const fetchPromise = fetch(event.request).then((networkResponse) => {
                        if (networkResponse && networkResponse.status === 200) {
                            cache.put(event.request, networkResponse.clone());
                        }
                        return networkResponse;
                    }).catch((err) => {
                        if (cachedResponse) {
                            console.warn('[SW] Game fetch failed, using cache:', event.request.url);
                            return;
                        }
                        throw err;
                    });
                    return cachedResponse || fetchPromise;
                });
            })
        );
        return;
    }

    // API istekleri - Network-First, hata durumunda Cache
    if (url.hostname === 'api.cagrivakti.com.tr' && (url.pathname.startsWith('/ezan_vakitleri') || url.pathname.startsWith('/vakitler/'))) {
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

    // ── js. ve css.yigitgulyurt.net.tr — Stale-While-Revalidate ─────────────
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
                            console.warn(`[SW] ${url.hostname} fetch failed, serving from cache:`, event.request.url);
                            return cachedResponse;
                        }
                    });

                return cachedResponse || fetchPromise;
            })
        );
        return;
    }

    // HTML sayfaları - Network-First, hata durumunda Cache, yoksa Offline
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    if (response.ok && response.status === 200 &&
                        !response.url.includes('/offline') &&
                        !response.url.includes('/kaynak/') &&
                        !response.url.includes('/canli-kaynak/')) {
                        const responseClone = response.clone();
                        caches.open(STATIC_CACHE).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                })
                .catch(async () => {
                    const cachedResponse = await caches.match(event.request);
                    if (cachedResponse) return cachedResponse;

                    const url = new URL(event.request.url);
                    const cleanResponse = await caches.match(url.pathname, { ignoreSearch: true });
                    if (cleanResponse) return cleanResponse;

                    if (url.pathname.startsWith('/sehir/')) {
                        const sehirResponse = await caches.match('/sehir');
                        if (sehirResponse) return sehirResponse;
                    }

                    if (url.pathname.startsWith('/imsakiye/')) {
                        const imsakiyeResponse = await caches.match('/imsakiye');
                        if (imsakiyeResponse) return imsakiyeResponse;
                    }

                    return caches.match('/offline');
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
                        console.warn('[SW] Background fetch failed for ' + event.request.url);
                        return;
                    }
                    throw err;
                });

            return cachedResponse || fetchPromise;
        })
    );
});