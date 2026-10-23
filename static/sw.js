/**
 * SIAM - Sistema Inteligente de Aprovechamiento de Material
 * Service Worker para soporte PWA y funcionamiento Offline
 * Empresa: Aluminios Cristales Villegas
 */

const CACHE_NAME = 'siam-pwa-v1.0.0';

// Recursos esenciales del App Shell que se almacenan en cache durante la instalacion
const STATIC_ASSETS = [
    '/',
    '/static/manifest.json',
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
    '/static/icons/icon.svg',
    '/offline',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css'
];

// Evento Install: Descargar y almacenar en cache los recursos estaticos criticos
self.addEventListener('install', (event) => {
    console.log('[Service Worker] Instalando SIAM PWA...');
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Almacenando App Shell en cache');
            return cache.addAll(STATIC_ASSETS).catch((err) => {
                console.warn('[Service Worker] Advertencia al cachear algunos recursos:', err);
            });
        }).then(() => self.skipWaiting())
    );
});

// Evento Activate: Limpiar caches obsoletas al actualizar la version
self.addEventListener('activate', (event) => {
    console.log('[Service Worker] Activando nueva version...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cache) => {
                    if (cache !== CACHE_NAME) {
                        console.log('[Service Worker] Eliminando cache antigua:', cache);
                        return caches.delete(cache);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Evento Fetch: Estrategia de enrutamiento y cache inteligente
self.addEventListener('fetch', (event) => {
    const request = event.request;
    const url = new URL(request.url);

    // 1. Ignorar solicitudes que no sean GET (como uploads POST de fotos /api/scan)
    if (request.method !== 'GET') {
        return;
    }

    // 2. Solicitudes de navegacion (paginas HTML): Network-First con fallback a offline.html
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request)
                .then((networkResponse) => {
                    // Actualizar cache con la ultima version obtenida
                    return caches.open(CACHE_NAME).then((cache) => {
                        cache.put(request, networkResponse.clone());
                        return networkResponse;
                    });
                })
                .catch(() => {
                    // Si no hay red, intentar servir desde cache o pagina offline
                    return caches.match(request).then((cachedResponse) => {
                        return cachedResponse || caches.match('/offline');
                    });
                })
        );
        return;
    }

    // 3. Recursos estaticos locales (CSS, JS, Imagenes, Iconos): Cache-First con actualizacion en segundo plano (Stale-While-Revalidate)
    if (url.origin === location.origin && (url.pathname.startsWith('/static/') || url.pathname === '/manifest.json')) {
        event.respondWith(
            caches.match(request).then((cachedResponse) => {
                const fetchPromise = fetch(request).then((networkResponse) => {
                    if (networkResponse && networkResponse.status === 200) {
                        const responseClone = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(request, responseClone);
                        });
                    }
                    return networkResponse;
                }).catch(() => {/* Offline silente */});

                return cachedResponse || fetchPromise;
            })
        );
        return;
    }

    // 4. Recursos externos (CDNs de Bootstrap, iconos, fuentes): Cache-First
    event.respondWith(
        caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
                return cachedResponse;
            }
            return fetch(request).then((networkResponse) => {
                if (networkResponse && networkResponse.status === 200) {
                    const responseClone = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(request, responseClone);
                    });
                }
                return networkResponse;
            });
        })
    );
});
