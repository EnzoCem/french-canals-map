# Feature Backlog & To-Do

Planned and proposed enhancements for the French Canals Interactive Map.
*Last updated: 2026-04-23 (IENC: bridges, locks, moorings, channel axis, obstructions, Garonne tidal UI, attribution)*

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
| ~~Bridge height markers~~ | Done | 🌉 Bridges layer renders 990 bridges across 13 waterways (Rhine, Moselle, Seine, Saône, Oise, Garonne tidal, Dunkerque-Escaut, etc.). Per-bridge air clearance from VNF IENC; vessel-profile-aware colouring (green/amber/red). Extraction pipeline: `extract_ienc.py` → `data/bridges.geojson` (226 KB). |

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
| ~~IENC bridge air clearances~~ | Done | 🌉 Bridges layer — see row above. 990 bridges with VERCLR; vessel-profile-aware colouring. |
| ~~IENC locks reconciliation data~~ | Done | `data/ienc_locks.geojson` (192 locks with length/width/rise) + `bridges_locks_reconciliation.csv` for manual review. Source for cherry-picking lock waypoints missing from the app. |
| ~~IENC moorings reconciliation data~~ | Done | `data/ienc_moorings.geojson` (625 quays + pontoons) + `bridges_moorings_reconciliation.csv`. Surfaces candidate matches (e.g. Chalon port position verified; Seurre, Toul positions worth reviewing). |
| ~~IENC channel axis (🧭 Channel)~~ | Done | 2,508 dredged-channel centerline segments from `wtwaxs` layer. Toggleable polyline overlay (dashed, per-waterway colour) — shows the official navigation axis vs. OSM's river bank. Significant on meandering sections (Moselle, lower Seine). |
| ~~IENC obstructions (⚠ Hazards)~~ | Done | 157 navigation hazards from `OBSTRN` — rocks, snags, foul areas, islets. Colour-coded markers by water-level category (submerged/awash/visible). Popup shows CATOBS type + WATLEV context + bilingual description. |
| ~~Garonne tidal data constant~~ | Done | `TIDAL_DATA` JS constant in `french_canals_map.html` (~line 4934): Bordeaux → Castets tidal propagation table per coefficient (45/70/100), marnage per sector, mascaret warning. Data half of Tidal-section-warnings (UI still pending). |
| VNF / OSM / Michelin attribution | Done | Data Backup panel now carries a permanent attribution block (Licence Ouverte 2.0, ODbL, etc.). |
| 📱 Complementary apps link-outs | Done | Data Backup panel lists four external tools that extend this map: C-MAP Embark (coastal charts), Navily (mooring reviews), VNF Itinéraires (official route calculator), Waterway Routes (PDF cruising guides). Outbound links only; no tracking, no embedding. |
| Controls-bar reorganisation | Done | Top toolbar collapsed from ~20 buttons into 3 dropdowns (🗺 Map, 📍 Layers, ⋮ Tools) + a 4-chip Quick row (Canals / Ports / Locks / Michelin). Layers popover groups toggles by category (Markers / POIs / Charts & Hazards). Layers button shows a badge count when non-default layers are on. Mobile: popovers reposition via `position:fixed` + JS so they don't clip off the edge. Click-outside / Esc closes any open popover. |
| Header absorbs info-only controls | Done | Canals-navigability legend + global stats (routes · places · locks · haltes · ports · notes) moved from a third controls row into the right side of `#header`. Controls bar reduced from 3 rows to 2 (main + secondary). Vessel-dims filter + Waterway-dimensions dropdown merged into the Quick row. On phones (≤720 px) the header info is hidden to save vertical space. |
| Mobile / touch optimisation | Medium | Larger touch targets, swipe sidebar |
| ~~Tidal-section warnings (UI)~~ | Done | 🌊 Tidal section card in route-planner results when a leg crosses the tidal Garonne. Mascaret warning + marnage-per-sector chips + collapsible propagation table (Bordeaux / Portets / Cadillac / Langon / Castets × coefficients 45/70/100). Compact sidebar badge when user taps any tidal-Garonne waypoint. New route 51 "Garonne (tidal)" with 5 waypoints (Bordeaux → Castets-en-Dorthe) makes the tidal leg planable end-to-end. Extensible to future tidal waterways via `TIDAL_DATA` key + matching route entry. |
| ~~SHOM live-tide links~~ | Done | 📅 Live tide-prediction link-outs to `maree.shom.fr` for Le Verdon (entrance) / Pauillac (mid-estuary) / Bordeaux (reference) embedded in the tidal card. Sidebar badge also carries a single tap-through to Bordeaux. Official SHOM pages, always current, Licence Ouverte. User combines the live HW/LW from SHOM with the propagation table already in the card to derive station times. |
| ~~Lock waypoints from IENC~~ | Done | 208 locks imported from `data/ienc_locks.geojson` into `WAYPOINTS` as `lk100..lk307` (2026-04-24, refreshed 2026-04-25). Each carries chamber length × width in the description so the vessel-profile filter can flag locks that won't fit. 2026-04-25 refresh fixed the Saar mislabel (previously mapped as "Saône upper") and added Rhône Lyon→Med locks via CNR cells. Coverage: Seine 41, Moselle 33, Dunkerque-Escaut 31, Seine-Amont 26, Saône 19, Rhine 18, Saar 16, Oise 13, Leie 7, Rhône (full) 5, Nieuwpoort-Dunkerque 6, Rhône-Rhin 2. |
| ~~IENC bundle expansion (Tier 1)~~ | Done | 2026-04-25: ingested the user-supplied IENC France 2021 + Inland ENC Europe 05.2022 bundles. Net additions: full Rhône Lyon→Mediterranean (CNR cells `3T5RHO*`, 33 cells, ~88 new bridges + 4 locks), German Saar (10 cells, 16 locks), Belgium (8 zips, 380 bridges in Belgium-waterway category + 82 Albert Canal). Bridges geojson: 990 → 1,700. Locks: 192 → 325 in source data, 208 imported into WAYPOINTS. |
| IENC notice marks + restricted areas | Medium | `notmrk` (speed limits, no-overtaking, no-anchoring signboards) + `RESARE` (regulated zones). High signal for on-board decision-making. ~1.5 h effort, extraction pattern already established. |
| IENC depth areas (DEPARE) | Low | Real river-depth polygons. Mostly irrelevant on big rivers for pleasure craft <1.5 m draft, so low priority. |
| IENC soundings (SOUNDG) | Low | Dense individual depth points. Noisy without expert interpretation. Skip unless someone specifically asks. |
| IENC anchorage areas (ACHARE) | Low | Legal anchoring zones. Niche — most pleasure cruisers moor rather than anchor. |
| IENC distance marks (dismar) | Skip | Official PK positions. PKs are already shown in waypoint popups; physical markers on the map would clutter. |
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
