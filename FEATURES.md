# Feature Backlog & To-Do

Planned and proposed enhancements for the French Canals Interactive Map.
*Last updated: 2026-04-19 (PWA shipped)*

---

## ✅ Completed

### Core Map
| Feature | Description |
|---------|-------------|
| Interactive Leaflet map | Dark nautical theme, zoom/pan, mobile-friendly |
| Base layer switcher | IGN France (default), OpenStreetMap, CartoDB Voyager, ESRI Satellite, OpenTopoMap |
| OpenSeaMap overlay | Nautical marks as a toggleable overlay |
| Waterway overlay | 3,474 OSM canal/river segments (deduped + non-navigable filtered, Swiss/Saône upstream trimmed) loaded from `waterways.geojson` |
| Waterway Cache API | Instant load on repeat visits; background ETag check for updates |
| Per-waterway colour coding | Each waterway rendered in its own colour from `WATERWAY_COLORS` when no vessel profile is set |
| Town markers | 120+ waypoints with detail sidebars |
| Lock markers | Curated lock positions + live Overpass locks at zoom ≥ 12 |
| Haltes & Ports | VNF haltes and marinas as separate toggleable layers |
| Michelin restaurants | 1,007 Michelin-awarded restaurants as a toggleable layer |
| Fuel & water stops | Seed data + live Overpass query for marine fuel stations |
| Chômages overlay | VNF maintenance closures (seed data, active + upcoming within 180 days) |
| Tunnel markers | 5 major tunnels (Riqueval, Mauvages, Foug, Pouilly, Saint-Albin) with convoy times + booking info |
| My Notes | User pins with personal notes, persisted in localStorage |
| Edit Locations mode | Click-to-place marker repositioning, saved to localStorage |
| Search | Live search across towns, locks, haltes, and ports |
| VNF integration | Links to VNF route calculator, notices, and regional pages in all sidebars |
| Section filter | Filter map to any of Jefferson's 9 book sections |
| Non-navigable waterway cleanup | `fill_waterways.py --clean-geojson` removes ancien/bras-mort/vieux segments; normalised dedup removes variants |
| Michelin annual update script | `fill_michelin.py` fetches latest data from ngshiheng/michelin-my-maps and regenerates MICHELIN_RESTAURANTS |
| Michelin GitHub Action | `.github/workflows/update-michelin.yml` runs fill_michelin.py on Feb 15 each year; opens PR if data changed |
| Michelin popup on click | Clicking a restaurant in sidebar or route planner opens a Leaflet popup with stars, cuisine, city, Michelin Guide link |
| Explore Nearby POI popups | Clicking 📍 on any Explore Nearby item opens a popup with name, category, opening hours, phone, website |
| Provisions auto-load | Provisions & Services section loads automatically on first expand — no second tap needed |
| Google Maps saved places | Import starred / "Want to go" lists from Google Takeout (KML or GeoJSON); `📍 My Places` toggle layer. Add / Sync / Clear controls in Data Backup panel |
| Explore Nearby error recovery | Overpass calls now use `[timeout:60][maxsize:2000000]` with a 🔄 Try Again button on failure (fixes Vienne-style dense-city timeouts) |
| Per-day weather on itinerary | Each day row in the Day-by-Day panel shows an ETA-date Open-Meteo forecast (icon · high/low · rain) for the day's final stop |
| VHF channel chips in lock popups | Surfaces OSM `vhf_channel` / `communication:vhf` tags on live + route-planner locks |
| Tap-to-call phone numbers | Auto-linkified French phone numbers in mooring, lock, tunnel, and POI popups — tap dials on mobile |
| PWA / offline mode | Installable web app (`manifest.json` + `sw.js` + `icon.svg`). App shell + `waterways.geojson` precached on install; tiles cached LRU (400 entries); update banner prompts reload when a new version is ready |

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
| Nearby attractions | Historic sites, castles, museums, viewpoints, wineries per stop |
| Provisions per stop | Supermarkets, pharmacies, boulangeries per stop |
| Nearest mooring at day-end | Day-by-day itinerary shows nearest halte/port (within 3 km) at the foot of each day row |
| Route navigation warnings | Red banner if any segment blocked by vessel dimensions |

### Explore Nearby (town sidebars)
| Category | Icon | Notes |
|----------|------|-------|
| Bike Hire | 🚲 | `amenity=bicycle_rental` — explore from the mooring |
| Swimming Spots | 🏊 | `leisure=swimming_area` + public `natural=beach` |
| Restaurants | 🍽 | `amenity=restaurant`, nearest 8, excluded from All view |
| Local Food Shops | 🧀 | `shop=cheese/farm/deli` — fromageries, farm shops, delis |
| Weekly Markets | 🏪 | `amenity=marketplace/market` with `opening_hours` shown in amber |
| Wineries & Distilleries | 🍷 | `craft=winery/distillery`, `shop=wine`, `tourism=wine_cellar` |
| Castles & Châteaux | 🏰 | `historic=castle/manor/palace/fort/fortress` |
| Abbeys & Churches | ⛪ | `historic=church/cathedral/abbey/monastery/chapel` |
| Historic Sites | 🏛 | Other `historic=*` tags |
| Museums & Galleries | 🖼 | `tourism=museum/gallery` |
| Attractions | 🎭 | `tourism=attraction` |
| Viewpoints | 🏔 | `tourism=viewpoint` |

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
| 1 | ~~`reverseRoute()` duplicates `swapRoutePlannerEndpoints()`~~ | Fixed |
| 2 | ~~Unnamed waterway segments show grey with profile active~~ | Fixed |
| 3 | ~~Waterway overlay still uses `WATERWAY_COLORS` fallback~~ | Fixed: `colorLookup()` now active for no-profile rendering |
| 4 | `Open Map.command` needs `chmod +x` once | Execute permission not set after clone/copy |
| 5 | ~~Chômages data is hardcoded seed, not live~~ | Fixed: updated to spring/summer 2026; lookahead extended to 180 days |
| 6 | ~~Fuel stops refetch on every map move~~ | Fixed: bbox cache + 700ms debounce |
| 7 | ~~Phase 3 `rp-poi-section` may not populate~~ | Fixed: variable rename |

---

## 🟡 In Progress / Partially Implemented

| Feature | Status | Notes |
|---------|--------|-------|
| Live chômages from VNF | Not started | VNF has no public API; would need scraping `data.gouv.fr` JSON |

---

## 🔵 Planned — Navigation & Planning

| Feature | Priority | Notes |
|---------|----------|-------|
| Live VNF chômages | Low | Parse published JSON from data.gouv.fr or Overpass `hazard` tags |
| ~~Share route via URL hash~~ | Done | `#r=fromId:toId` written on calculate; `_initFromHash()` restores on load; 🔗 Copy Link button in results |
| Printable route card | Medium | `@media print` CSS showing segment table, locks, VNF links — for the helm |
| Bridge height markers | **High** | Plan ready: `docs/superpowers/plans/2026-04-23-ienc-bridge-heights.md` — extract exact per-bridge air clearances from official VNF IENC S-57 cells (Rhône, Saône, Seine, Moselle). Unlocks vessel-profile-aware bridge colouring on the big rivers. |

---

## 🟢 Planned — Stats & UX

| Feature | Priority | Notes |
|---------|----------|-------|
| Trip log / journal | Low | Log actual days cruised, distances, locks passed |
| Photo pins | Low | Attach image URL to any waypoint note |
| Elevation profile | Low | SVG cross-section of summit level and lock climbs/descents |
| ~~Offline tile caching~~ | Done | Service worker now runtime-caches tiles LRU (400 entries ≈ 20–40 MB) |
| ~~PWA / offline mode~~ | Done | `manifest.json` + `sw.js` + `icon.svg`; app shell + geojson precached; update banner wired |
| ~~Route-day weather~~ | Done | Open-Meteo per-stop ETA forecast rendered on each day row |
| ~~VHF channel per lock~~ | Done | `_vhfChip()` renders on live + route-planner locks |
| ~~Capitainerie tel: links~~ | Done | `_autoLinkPhones()` + `_telLink()` across mooring/lock/tunnel/POI popups |
| Mobile / touch optimisation | Medium | Larger touch targets, swipe sidebar |
| Tidal-section warnings | Medium | Data half covered by IENC plan Task 6 (Garonne tidal table transcribed from VNF README). UI half still TBD: show tide-window banner + mascaret warning when route crosses tidal PK zones on Garonne / Seine-Aval. |
| Voies vertes (towpath cycling) | Medium | OSM `route=bicycle` relations alongside canals — pair bike with the boat |
| Download-area-for-offline button | Medium | Explicit "download this area" that warms the tile cache over the current viewport + zoom range |
| Fuel price overlay | Low | Crowdsource via export/import pattern (mirrors Google Places) |
| Mooring pricing (€/night) | Low | `MOORINGS.cost` has `paid`/`free` but no ranges — help budgeting |
| Border-crossing markers | Low | FR/BE/DE/CH border points with paperwork notes |

---

## 🛠 Technical Debt

| Item | Description |
|------|-------------|
| Single-file architecture | At ~8,200 lines the HTML is large; no immediate plans to split, but worth tracking |
| CLAUDE.md line numbers drift | Line numbers will drift as the file grows — use `grep -n "^function foo"` to find current positions |
| Overpass error handling inconsistency | `_fetchPOIsNearby` has Try Again UX; `_fetchProvisionsNearby`, `fetchLocksInView`, chômages do not. Extract shared `_overpassFetch(ql, opts)` helper |
| `_NON_NAVIGABLE_RE` over-matches | Anchors weakly on `écluse` — any waterway name containing that token is filtered. Revisit to anchor on primary descriptor only |
| Inline `onclick=` handlers | Data Backup panel & POI buttons use inline handlers; blocks future CSP tightening — migrate to `addEventListener` |
| No localStorage schema migration | All keys use `_v1` suffix but there's no `_migrate()` runner — add now before needed |
