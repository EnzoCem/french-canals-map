# Feature Backlog & To-Do

Planned and proposed enhancements for the French Canals Interactive Map.
*Last updated: 2026-03-31*

---

## ✅ Completed

### Core Map
| Feature | Description |
|---------|-------------|
| Interactive Leaflet map | Dark nautical theme, zoom/pan, mobile-friendly |
| Base layer switcher | IGN France (default), OpenStreetMap, CartoDB Voyager, ESRI Satellite, OpenTopoMap |
| OpenSeaMap overlay | Nautical marks as a toggleable overlay |
| Waterway overlay | 23,862 OSM canal/river segments loaded from `waterways.geojson` |
| Waterway Cache API | Instant load on repeat visits; background ETag check for updates |
| Town markers | 120+ waypoints with detail sidebars |
| Lock markers | Curated lock positions + live Overpass locks at zoom ≥ 12 |
| Haltes & Ports | VNF haltes and marinas as separate toggleable layers |
| Michelin restaurants | 1,007 Michelin-awarded restaurants as a toggleable layer |
| Fuel & water stops | Seed data + live Overpass query for marine fuel stations |
| Chômages overlay | VNF maintenance closures (seed data, active + upcoming within 60 days) |
| My Notes | User pins with personal notes, persisted in localStorage |
| Edit Locations mode | Click-to-place marker repositioning, saved to localStorage |
| Search | Live search across towns, locks, haltes, and ports |
| VNF integration | Links to VNF route calculator, notices, and regional pages in all sidebars |
| Section filter | Filter map to any of Jefferson's 9 book sections |

### Route Planner
| Feature | Description |
|---------|-------------|
| BFS pathfinding | Find route between any two towns across 44 connected waterways |
| Multi-stop planning | Add via stops (A → B → C → … → Z) |
| Route highlight on map | Planned route in coral-red + white halo; non-route waterways fade |
| Reverse route | Flip entire stop order with one click |
| Save / load / delete routes | Persist named route plans in localStorage |
| GPX export | Download planned route as .gpx for chartplotters |
| Day-by-day itinerary | Split journey into daily stages based on speed + hours |
| Lock opening hours | VNF regional schedule (6 groups, 44 routes) shown in lock sidebars |
| Live Vigicrues water levels | Real-time Hub'Eau water height for 11 river routes, 10-min cache |
| Lock count per day | Shows locks per day in the itinerary |
| Cruise speed calculator | Set km/h, hours/day, lock time → realistic day count |
| Weather along route | 5-day Open-Meteo forecast per stop (async, cached) |
| Michelin stops | Top 5 Michelin restaurants near each stop in route panel |
| Nearby attractions | OSM historic sites, castles, museums, viewpoints per stop |
| Provisions per stop | Supermarkets, pharmacies, boulangeries per stop |
| Route navigation warnings | Red banner if any segment blocked by vessel dimensions |

### Vessel Profile
| Feature | Description |
|---------|-------------|
| Profile modal | Vessel name, home port, air draught, water draught, length, beam, speed, hours/day |
| Persisted in localStorage | Profile survives browser restart |
| Controls-bar quick filter | Draft + air draught inputs that sync two-way with full profile |
| Vessel filter on markers | Dims waypoint + mooring markers on blocked waterways |
| Waterway navigability colouring | Blue/red/amber/grey waterways based on vessel vs VNF limits |
| Navigability legend | Appears in controls bar when profile has dimensions |
| Route planner speed pre-fill | Route planner inherits speed + hours from profile |

---

## 🔴 Bugs / Known Issues

| # | Issue | Details |
|---|-------|---------|
| 1 | ~~`reverseRoute()` duplicates `swapRoutePlannerEndpoints()`~~ | Fixed: removed dead with-via branch from `swapRoutePlannerEndpoints()`; ⇅ now always swaps only endpoints (via stays put), 🔄 reverses everything; swap button no longer hidden when via stops exist |
| 2 | ~~Unnamed waterway segments show grey with profile active~~ | Fixed: added `!name` guard in `getWaterwayNavStatus` returning blue; fixed `onEachFeature` to pass raw feature name (not `'Waterway'` display fallback) to nav check |
| 3 | ~~Waterway overlay still uses `WATERWAY_COLORS` fallback~~ | Fixed: `buildWaterwayOverlay` now uses `nav.color` directly (uniform blue when no profile); `restoreWaterwayStyles` now uses `getWaterwayNavStatus` so profile colours survive route highlight clear |
| 4 | `Open Map.command` needs `chmod +x` once | Execute permission not set after clone/copy |
| 5 | ~~Chômages data is hardcoded seed, not live~~ | Fixed: removed 11 expired winter entries; added 13 spring/summer 2026 closures (Apr–Sep); lookahead extended 60 → 180 days |
| 6 | ~~Fuel stops refetch on every map move~~ | Fixed: bbox cache check skips Overpass when viewport is within last queried area; 700ms debounce added to `moveend` handler |
| 7 | ~~Phase 3 `rp-poi-section` may not populate~~ | Fixed: local variable renamed from `_poiRouteStops` to `poiStops` to avoid confusion with module-level `_routePOIStops` (which `clearEndpointPins()` resets to `[]`) |

---

## 🟡 In Progress / Partially Implemented

| Feature | Status | Notes |
|---------|--------|-------|
| Live chômages from VNF | Not started | VNF has no public API; would need scraping `data.gouv.fr` JSON |

---

## 🔵 Planned — Navigation & Planning

| Feature | Priority | Notes |
|---------|----------|-------|
| Lock opening hours per lock | High | Show VNF seasonal schedules in lock popups; Overpass has `opening_hours` tags on many locks |
| Chômage lookahead 180 days | Medium | Extend from 60 days to cover full summer season |
| Live VNF chômages | Low | Parse published JSON from data.gouv.fr or Overpass `hazard` tags |
| Share route via URL hash | Medium | Encode from/to/via IDs in `#` fragment for bookmarking + sharing |
| Printable route card | Medium | `@media print` CSS showing segment table, locks, VNF links — for the helm |

---

## 🟠 Planned — Points of Interest

| Feature | Priority | Notes |
|---------|----------|-------|
| Weekly markets | Medium | OSM has good `amenity=marketplace` + `opening_hours` data; add to Explore Nearby |
| Wineries near route | Medium | Already partially supported via Overpass `craft=winery` — surface in route panel |
| Tunnel details | Medium | Riqueval, Mauvages, Foug, Pouilly, Saint-Albin — convoy times, booking requirements |
| Bridge height markers | Low | Single lowest bridge is often the real air-draught bottleneck, not the route average |

---

## 🟢 Planned — Stats & UX

| Feature | Priority | Notes |
|---------|----------|-------|
| Trip log / journal | Low | Log actual days cruised, distances, locks passed |
| Photo pins | Low | Attach image URL to any waypoint note |
| Elevation profile | Low | SVG cross-section of summit level and lock climbs/descents |
| Offline tile caching | Low | Service Worker — significant complexity |
| Mobile / touch optimisation | Medium | Larger touch targets, swipe sidebar |

---

## 🛠 Technical Debt

| Item | Description |
|------|-------------|
| `WATERWAY_COLORS` dead weight | ~50-entry legacy colour map still in code, used in two places, should be removed once uniform colour is confirmed |
| `reverseRoute()` duplicate | Consolidate with `swapRoutePlannerEndpoints()` |
| CLAUDE.md line numbers drift | Line numbers will drift as the file grows — use `grep -n "^function foo"` to find current positions |
| `waterways.geojson` still includes non-navigable segments | Some small Alpine rivers and Camargue channels still slip through the whitelist filter |
| Single-file architecture | At 7,600 lines the HTML is large; no immediate plans to split, but worth tracking |
