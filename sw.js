/* French Canals Map — Service Worker
 *
 * Strategy summary:
 *   • App shell (HTML, manifest, icon, waterways.geojson, Leaflet CDN)
 *     is precached on install → instant offline boot.
 *   • Navigation requests: network-first, fallback to cached shell
 *     (so an updated HTML is picked up immediately when online).
 *   • Map tiles (OSM / IGN / CartoDB / ESRI / OpenTopoMap / OpenSeaMap):
 *     cache-first with LRU cap (~400 tiles ≈ 20–40 MB) — good for
 *     on-boat browsing of areas the user already viewed with 4G/WiFi.
 *   • Dynamic APIs (Overpass, Open-Meteo, Vigicrues, Hub'Eau) are
 *     NEVER cached — always fetched fresh; stale = worse than missing.
 *
 * Bump `VERSION` to force every client to re-install.
 */

const VERSION    = 'fc-v9';
const SHELL      = `fc-shell-${VERSION}`;
const TILES      = `fc-tiles-${VERSION}`;
const TILES_CAP  = 400; // roughly: 400 × 50 KB ≈ 20 MB

/* Files to precache on install. Keep this list tight — misses here
 * only hurt first-offline load, not ongoing use. */
const SHELL_URLS = [
  './',
  './index.html',
  './french_canals_map.html',
  './manifest.json',
  './icon.svg',
  './waterways.geojson',
  './data/bridges.geojson',
  './data/ienc_obstructions.geojson',
  // data/ienc_channel_axis.geojson is 1.2 MB — NOT precached to keep the
  // install payload small. It's fetched on first layer-toggle when
  // online, and staleWhileRevalidate keeps it cached thereafter.
  // Wave 1 — extracted data files (small JSON, safe to precache)
  './data/waypoints.json',
  './data/moorings.json',
  './data/routes.json',
  './data/waterway_constraints.json',
  './data/waterway_colors.json',
  './data/tunnels.json',
  './data/tidal.json',
  // Wave 4 — multi-country closures (FR + NL + DE + BE + AT seeded)
  './data/closures.json',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  'https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js',
  'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css',
  'https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css',
];

/* Hosts that serve map tiles — cache-first with LRU cap. */
const TILE_HOSTS = [
  'tile.openstreetmap.org',
  'a.tile.openstreetmap.org',
  'b.tile.openstreetmap.org',
  'c.tile.openstreetmap.org',
  'data.geopf.fr',
  'wxs.ign.fr',
  'cartocdn.com',       // CartoDB (subdomains handled via endsWith)
  'basemaps.cartocdn.com',
  'tiles.openseamap.org',
  't1.openseamap.org',
  'a.tile.opentopomap.org',
  'b.tile.opentopomap.org',
  'c.tile.opentopomap.org',
  'server.arcgisonline.com',
];

/* Hosts we intentionally never cache (dynamic data). */
const NO_CACHE_HOSTS = [
  'overpass-api.de',
  'api.open-meteo.com',
  'hubeau.eaufrance.fr',
  'www.vigicrues.gouv.fr',
];

/* ── Install: precache shell ────────────────────────────────── */
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL).then((cache) => {
      // addAll is atomic but fails the whole install on any 404.
      // Use individual add() so one bad URL doesn't brick the install.
      return Promise.all(SHELL_URLS.map((url) =>
        cache.add(new Request(url, { cache: 'reload' })).catch((err) => {
          console.warn('[sw] precache miss', url, err);
        })
      ));
    }).then(() => self.skipWaiting())
  );
});

/* ── Activate: clean old version caches ─────────────────────── */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith('fc-') && !k.endsWith(VERSION))
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

/* ── Message: client can ask us to skipWaiting (for updates) ── */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

/* ── Fetch routing ──────────────────────────────────────────── */
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // 1. Dynamic APIs — pass through, no caching.
  if (NO_CACHE_HOSTS.some((h) => url.hostname === h || url.hostname.endsWith('.' + h))) {
    return; // let the browser handle it normally
  }

  // 2. Map tiles — cache-first with LRU cap.
  if (isTileRequest(url)) {
    event.respondWith(tileCacheFirst(req));
    return;
  }

  // 3. Navigation requests (the HTML page) — network-first.
  if (req.mode === 'navigate' || (req.destination === 'document')) {
    event.respondWith(navigateNetworkFirst(req));
    return;
  }

  // 4. Same-origin assets + precached CDN libs — cache-first, revalidate.
  event.respondWith(staleWhileRevalidate(req));
});

/* ── Helpers ────────────────────────────────────────────────── */
function isTileRequest(url) {
  if (TILE_HOSTS.some((h) => url.hostname === h)) return true;
  // Fallback: any *.cartocdn.com / *.arcgisonline.com / *.tile.opentopomap.org / etc.
  if (url.hostname.endsWith('.cartocdn.com')) return true;
  if (url.hostname.endsWith('.arcgisonline.com')) return true;
  if (url.hostname.endsWith('.openseamap.org')) return true;
  if (url.hostname.endsWith('.opentopomap.org')) return true;
  if (url.hostname.endsWith('.openstreetmap.org')) return true;
  return false;
}

async function tileCacheFirst(req) {
  const cache = await caches.open(TILES);
  const hit = await cache.match(req);
  if (hit) return hit;
  try {
    const resp = await fetch(req);
    // Only cache successful or opaque responses.
    if (resp && (resp.ok || resp.type === 'opaque')) {
      cache.put(req, resp.clone());
      trimCache(TILES, TILES_CAP); // fire-and-forget
    }
    return resp;
  } catch (err) {
    // Offline + no cache hit — return a tiny transparent PNG so Leaflet
    // doesn't spam broken-image icons.
    return new Response(TRANSPARENT_TILE_BYTES, {
      headers: { 'Content-Type': 'image/png' },
    });
  }
}

async function navigateNetworkFirst(req) {
  try {
    const resp = await fetch(req);
    // Refresh the shell cache with the latest HTML.
    const cache = await caches.open(SHELL);
    cache.put(req, resp.clone());
    return resp;
  } catch (err) {
    const cache = await caches.open(SHELL);
    const hit = await cache.match(req) || await cache.match('./french_canals_map.html');
    if (hit) return hit;
    throw err;
  }
}

async function staleWhileRevalidate(req) {
  const cache = await caches.open(SHELL);
  const hit = await cache.match(req);
  const fetchPromise = fetch(req).then((resp) => {
    if (resp && (resp.ok || resp.type === 'opaque')) {
      cache.put(req, resp.clone());
    }
    return resp;
  }).catch(() => hit);
  return hit || fetchPromise;
}

/* LRU-ish trim: when the cache exceeds cap, delete oldest keys. */
async function trimCache(name, cap) {
  const cache = await caches.open(name);
  const keys = await cache.keys();
  const over = keys.length - cap;
  if (over <= 0) return;
  for (let i = 0; i < over; i++) {
    await cache.delete(keys[i]);
  }
}

/* 1×1 transparent PNG as a placeholder for missing tiles. */
const TRANSPARENT_TILE_BYTES = Uint8Array.from(atob(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='
), (c) => c.charCodeAt(0));
