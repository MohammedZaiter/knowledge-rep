/* LU Teaching Slides, offline cache.
   Strategy:
     · HTML  → network first, cache fallback. An edited lecture is never stale;
               a lecture you have opened before still works with no network.
     · Same-origin assets → stale-while-revalidate. The cached copy is served
               immediately AND refreshed in the background, so an edit to
               lu.css lands on the next load without anyone bumping a version.
     · Webfonts → cache first. They never change.
   CACHE only needs bumping if you want to evict everything at once. */
const CACHE = 'foodscope-ui-v4';
const SHELL = [
  './',
  './index.html',
  './assets/lu.css?v=1.1.0',
  './assets/foodscope.css?v=1.2.1',
  './assets/foodscope.js?v=1.2.2',
  './manifest.webmanifest'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  if (new URL(req.url).pathname.includes('/build/') || new URL(req.url).pathname === '/api/ask' || new URL(req.url).searchParams.has('question')) return;

  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;
  const isDoc = req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html');

  if (isDoc) {
    // Network first: an updated lecture wins, a cached one covers offline.
    // cache:'no-store' matters. GitHub Pages serves HTML with max-age=600, so
    // a plain fetch() here is answered by the browser's HTTP cache and
    // "network first" quietly becomes "ten minutes stale first". Students then
    // sit on an old lecture through a reload.
    e.respondWith(
      fetch(req, { cache: 'no-store' })
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req).then((hit) => hit || caches.match('./index.html')))
    );
    return;
  }

  if (!sameOrigin) {
    if (!/fonts\.(googleapis|gstatic)\.com/.test(url.host)) return;
    // Webfonts: cache first, they are immutable.
    e.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
        return res;
      }))
    );
    return;
  }

  // Query UI changes must take effect on the first refresh.
  if (/\/assets\/foodscope\.(js|css)$/.test(url.pathname)) {
    e.respondWith(fetch(req, {cache: 'no-store'}));
    return;
  }

  // Same-origin assets: stale-while-revalidate.
  e.respondWith(
    caches.open(CACHE).then((c) => c.match(req).then((hit) => {
      const fresh = fetch(req)
        .then((res) => { if (res.ok) c.put(req, res.clone()); return res; })
        .catch(() => hit);
      return hit || fresh;
    }))
  );
});

