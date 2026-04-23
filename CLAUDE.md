# French Canals Interactive Map — Claude Code Guide

## Project overview

A single-file interactive web map for cruising the French inland waterways, based on David Jefferson's *Through the French Canals* (14th edition). Users can browse towns, locks, haltes fluviales, ports de plaisance, plan routes, write notes, and correct marker positions.

**GitHub:** https://github.com/EnzoCem/french-canals-map
**Live page:** https://enzocem.github.io/french-canals-map/french_canals_map.html
**Local file:** Open `french_canals_map.html` via `file://` (waterway overlay will not load — needs a server or GitHub Pages)
**Local launcher:** Double-click `Open Map.command` to start a Python HTTP server and open the map at `http://localhost:8765`

---

## File structure

```
French Canals/
├── french_canals_map.html          ← entire app (HTML + CSS + JS + data) ~8,200 lines
├── waterways.geojson               ← canal/river geometry fetched from OSM (~8.5 MB, 3,474 features after cleanup)
├── index.html                      ← GitHub Pages redirect to french_canals_map.html
├── Open Map.command                ← macOS launcher script (requires chmod +x once)
├── fill_waterways.py               ← one-shot script that generated waterways.geojson via Overpass
├── fill_michelin.py                ← annual script to update MICHELIN_RESTAURANTS from ngshiheng/michelin-my-maps
├── patch_lyon_waterways.py         ← one-shot patch: fetched Miribel/Jonage/Rhône through Lyon
├── manifest.json                   ← PWA manifest (installable)
├── sw.js                           ← Service worker: app shell precache + tile LRU cache
├── icon.svg                        ← PWA icon (vessel on canal)
├── extract_ienc.py                 ← GDAL-based extractor: VNF IENC S-57 zips → data/bridges.geojson
├── tests/test_extract_ienc.py      ← Pytest suite for extract_ienc (pure + one GDAL integration test)
├── data/
│   └── bridges.geojson             ← 990 bridge air-clearance points (VNF IENC, Licence Ouverte 2.0)
├── .github/workflows/
│   └── update-michelin.yml         ← GitHub Action: runs fill_michelin.py on Feb 15 each year
└── CLAUDE.md / README.md / FEATURES.md
```

**No build tools, no npm, no bundler.** Edit `french_canals_map.html` and refresh the browser.

**External CDN dependencies** (requires internet):
- Leaflet 1.9.4 — `https://unpkg.com/leaflet@1.9.4/dist/leaflet.js`
- Leaflet MarkerCluster 1.5.3 — `https://unpkg.com/leaflet.markercluster@1.5.3/...`

---

## Critical rule: never write `</script>` inside the script block

The HTML parser terminates the `<script>` block the moment it sees `</script>` as a literal string — even inside comments or strings. Use `<\/script>` or rephrase. Violation causes all JS after that point to render as raw page text.

---

## File layout (current line numbers)

| Lines | Content |
|-------|---------|
| 1–1189 | `<head>` + all CSS styles |
| 1190–1238 | Head-embedded script: PWA service-worker registration + update banner |
| 1239 | **`</head>`** |
| 1240–1359 | `<body>`: `#controls` bar, `#main`, `#map`, `#sidebar` |
| 1358 | First HTML `<script>` tag for CDN libs + SW wiring already closed above |
| 1360 | **Main `<script>` opens** — application JS starts here |
| 1365–1413 | `const ROUTES` — 44 canal route definitions |
| 1414–1921 | `const WAYPOINTS` — ~120 town/lock waypoints |
| 1922–2159 | `const MOORINGS` — haltes + ports with full metadata |
| 2160–3216 | `const MICHELIN_RESTAURANTS` — 1,007 Michelin-awarded restaurants |
| 3217–3228 | localStorage keys (incl. `GOOGLE_PLACES_KEY`) + saved-routes / google-places init |
| 3229–3345 | Map init (`L.map`), tile layers, layer switcher, waterways fetch + cache |
| 3346–3452 | Layer group declarations (incl. `tunnelGroup`, `bridgesGroup`, `googlePlacesGroup`) |
| 3453–3500 | `buildMooringMarkers()` |
| 3501–3577 | `buildMichelinMarkers()` |
| 3578–3759 | `buildMarkers()` |
| 3760–3917 | Sidebar: `openSidebar()`, Explore Nearby, Provisions, note save/delete |
| 3918–3993 | `layerState`, `toggleLayer()` (incl. `bridges`, `googleplaces` cases) |
| 3994–4115 | Vessel profile: `openProfileModal()`, `saveProfile()` |
| 4116–4255 | `applyVesselFilter()`, vessel-filter wiring |
| 4256–4310 | Chômages data + `buildChomagesMarkers()` |
| 4311–4412 | `const TUNNELS` — 5 tunnel entries with convoy schedules |
| 4413–4798 | `buildTunnelMarkers()` + tunnel popups + related helpers |
| 4799–4846 | `WATERWAY_COLORS` — per-waterway colour palette (active when no vessel profile set) |
| 4847–4933 | `WATERWAY_CONSTRAINTS` — VNF dimension limits per waterway |
| 4934–4979 | **`TIDAL_DATA`** — Garonne tidal propagation table (Task 6) |
| 4980 | `const _normName` — shared name normaliser |
| 4981–5005 | Shared contact helpers: `_telLink`, `_autoLinkPhones`, `_vhfChip` |
| 5027–5039 | `colorLookup(name)` — normalised WATERWAY_COLORS lookup |
| 5040–5090 | `getWaterwayNavStatus()`, `_updateWaterwayNavLegend()` |
| 5091–5313 | `buildWaterwayOverlay()`, waterway dims lookup, cache loader (`WATERWAYS_CACHE_VER`) |
| 5314–6070 | `ROUTE_CONNECTIONS`, route planner graph, `findRoutePath()`, `calculateRoute()` setup |
| 6071–6112 | `openRoutePlanner()`, `closeRoutePlanner()` |
| 6113–6189 | `reverseRoute()`, `exportRouteAsGPX()` |
| 6190–6450 | `renderDayByDay()`, `_getCruiseSettings()`, weather fetch + per-day weather hydration |
| 6451–6701 | Live locks: `fetchLocksInView()`, `scheduleLockFetch()`, route-lock markers |
| 6702–6795 | `calculateRoute()` — BFS pathfinding + route results rendering |
| 6796–6938 | `ROUTE_TO_WATERWAYS` — maps route numbers → OSM waterway names |
| 6939–7175 | `highlightRouteOnMap()`, `clearRouteHighlight()`, `restoreWaterwayStyles()` |
| 7176–7294 | Saved routes: `saveCurrentRoute()`, `loadSavedRoute()`, `deleteSavedRoute()` |
| 7295–7378 | `_buildExploreSnippet()` — route planner attractions snippet |
| 7379–7451 | `renderRoutePOIsSection()`, `showRoutePOIStop()`, `loadRoutePOIExplore()` |
| 7452–7494 | `_fetchPOIsNearby()` — 15 km Overpass query |
| 7495–7634 | Provisions: `_fetchProvisionsNearby()`, `_buildProvisionsSnippet()` |
| 7635–7794 | `_renderPOIList()` — Explore Nearby category chips + item rows |
| 7795–7883 | Edit mode marker selection |
| 7884–7937 | `activateEditMode()`, `deactivateEditMode()` |
| 7938–8199 | `saveLocationOverride()`, export/import overrides |
| 8200–8276 | **IENC Bridges**: `buildBridgeMarkers()`, `_renderBridgeMarkers()`, `_bridgeStatus()` |
| 8278–8403 | Google Places: `buildGooglePlacesMarkers()`, parse/import/clear |
| 8404 | **`</script>` closes** |
| 8405+ | HTML panels: route planner, profile modal, edit-mode banner, data backup panel (incl. VNF/OSM/Michelin attribution block) |

---

## localStorage keys

| Key | Purpose |
|-----|---------|
| `french_canals_notes_v1` | User notes per waypoint (`{ [id]: string }`) |
| `french_canals_location_overrides_v1` | Corrected marker positions (`{ waypoints: {}, moorings: {} }`) |
| `french_canals_saved_routes_v1` | Saved route plans (array of route objects) |
| `french_canals_vessel_v1` | Vessel profile (`{ vesselName, homePort, air, draught, length, beam, cruiseSpeed, hoursPerDay }`) |
| `french_canals_google_places_v1` | Imported Google Maps saved places (array of `{ id, name, lat, lon, note, url, importedAt }`) |

---

## Data structures

### WAYPOINTS entry
```js
{ id: 'w_001', name: 'Montereau', route: 1, section: 1,
  lat: 48.387, lon: 2.950, pk: '86K', is_lock: false,
  desc: 'Optional description text.' }
```

### MOORINGS entry
```js
{ id: 'm_001', name: 'Port de Plaisance Auxerre', type: 'port',
  lat: 47.798, lon: 3.567, waterway: 'Canal du Nivernais',
  cost: 'paid', pk: '2K3', facilities: 'water/electric/showers',
  max_vessel: '35m', contact: 'Optional contact info' }
```

### ROUTES entry
```js
{ num: 1, canal: 'River Seine', section: 1,
  dist_km: 86, locks: 6, max_height: 5.9, max_draught: 3.5 }
```

### WATERWAY_CONSTRAINTS entry
```js
'Canal du Midi': { air: 3.50, draft: 1.60, beam: 5.45, length: 30 }
```

### TUNNELS entry
```js
{ id:'t001', name:'Riqueval', fullName:'Souterrain de Riqueval',
  canal:'Canal de Saint-Quentin', route:29, lat:49.9714, lon:3.2500,
  length_m:5670, pk:'97', tug_required:true,
  convoys:[{label:'S-bound',times:['07:30','13:30']},{label:'N-bound',times:['10:00','16:00']}],
  booking:'48 h advance booking required', contact:'VNF HAF: 03 23 09 17 70',
  vnf_url:'https://www.vnf.fr/vnf/naviguer-sur-le-reseau/naviguer/les-souterrains/' }
```

---

## Layer architecture

```
map
├── waterwayLayer    (L.geoJSON — loaded from waterways.geojson, toggled by "Canals")
├── clusterGroup     (L.markerClusterGroup — town markers, normal mode)
├── townGroup        (L.layerGroup — same towns, unclustered in edit mode)
├── lockGroup        (L.layerGroup — curated lock markers)
├── liveLocksGroup   (L.layerGroup — live OSM locks from Overpass, zoom ≥ 12)
├── notesGroup       (L.layerGroup — user note pins)
├── halteGroup       (L.layerGroup — halte markers)
├── portGroup        (L.layerGroup — port markers)
├── michelinGroup    (L.layerGroup — Michelin restaurant markers)
├── fuelGroup        (L.layerGroup — fuel/water stops)
├── chomagesGroup    (L.layerGroup — VNF maintenance closures)
├── tunnelGroup      (L.layerGroup — canal tunnel markers with convoy schedules)
├── bridgesGroup     (L.markerClusterGroup — IENC bridges with air-clearance colouring)
└── googlePlacesGroup (L.layerGroup — user's imported Google Maps saved places)
```

`allMarkers[]` and `allMooringMarkers[]` hold references to every marker for vessel filter and edit mode.

---

## Waterway overlay (waterways.geojson)

The waterway geometry lives in a **separate file** (`waterways.geojson`) loaded at startup:

```js
// Loaded via Cache API (instant on repeat visits):
fetch('./waterways.geojson')  // → stored in Cache API → ETag checked in background
```

- **3,474 features** covering all French navigable waterways (down from 23,862 after deduplication, non-navigable removal, and Swiss/Saône upstream trimming)
- Generated by `fill_waterways.py` via 12-region Overpass sweep
- Non-navigable segments filtered by name pattern (`_NON_NAVIGABLE_RE`: ancien, bras-mort, vieux/vieille, écluse, pont-canal, aqueduc, prise d'eau, souterrain)
- Normalised deduplication removes regional/spelling variants; canonical OSM name kept
- RDP-simplified at 33m tolerance
- Cache version: `french-canals-waterways-v7` — bump this constant (in `buildWaterwayOverlay()`) to force all browsers to re-fetch

### Vessel-profile waterway colouring

When `_vesselProfile` has dimensions set, `buildWaterwayOverlay()` colours each waterway:
- 🔵 `#4fc3f7` — navigable (all dimensions clear)
- 🔴 `#ef5350` — blocked (dimension exceeded)
- 🟡 `#ffb74d` — marginal (within 10% of a limit)
- ⬜ `#90a4ae` — no VNF data for this waterway

Without a profile, each waterway renders in its per-waterway colour from `WATERWAY_COLORS` (via `colorLookup()`), falling back to uniform blue if not found.

---

## Vessel profile — two input paths, fully synced

Two UIs both write to `_vesselProfile` and trigger `buildWaterwayOverlay()`:

1. **Profile modal** (`openProfileModal()` / `saveProfile()`) — full vessel details
2. **Controls bar filter** (`#vf-draft` / `#vf-air` + `applyVesselFilter()`) — quick override

`applyVesselFilter()` writes `draught`/`air` back into `_vesselProfile` so both systems stay in sync.
`saveProfile()` syncs values forward into the filter bar inputs.

---

## Explore Nearby panel

Triggered by tapping any town marker → **🔍 Explore Nearby** accordion.

Fetches POIs within **15 km** via Overpass. Categories (shown as filter chips):

| Chip | Icon | OSM tags |
|------|------|----------|
| Bike Hire | 🚲 | `amenity=bicycle_rental` |
| Swimming | 🏊 | `leisure=swimming_area`, `natural=beach` (public only) |
| Restaurants | 🍽 | `amenity=restaurant` — capped at 8 nearest; **excluded from All view** |
| Local Food | 🧀 | `shop=cheese/farm/deli` |
| Weekly Markets | 🏪 | `amenity=marketplace/market` — shows `opening_hours` in amber |
| Wineries & Distilleries | 🍷 | `craft=winery/distillery`, `shop=wine`, `tourism=wine_cellar` |
| Castles & Châteaux | 🏰 | `historic=castle/manor/palace/fort/fortress` |
| Abbeys & Churches | ⛪ | `historic=church/cathedral/abbey/monastery/chapel` |
| Historic Sites | 🏛 | other `historic=*` |
| Museums | 🖼 | `tourism=museum/gallery` |
| Attractions | 🎭 | `tourism=attraction` |
| Viewpoints | 🏔 | `tourism=viewpoint` |

---

## Tunnel markers

Five major tunnels in `const TUNNELS` (~line 4164), rendered by `buildTunnelMarkers()` into `tunnelGroup`:

| ID | Name | Canal | Length | Tug |
|----|------|-------|--------|-----|
| t001 | Riqueval | Canal de Saint-Quentin | 5,670 m | Yes |
| t002 | Mauvages | Canal de la Marne au Rhin | 4,877 m | Yes |
| t003 | Foug | Canal de la Marne au Rhin | 866 m | No |
| t004 | Pouilly-en-Auxois | Canal de Bourgogne | 3,333 m | No |
| t005 | Saint-Albin / Balesmes | Canal entre Champagne et Bourgogne | 2,306 m | Yes |

Each tunnel popup shows: length, tug requirement, northbound/southbound convoy times, booking info, and VNF link.

---

## IENC Bridges layer (VNF air clearances)

The 🌉 Bridges layer shows 990 bridge air-clearance points extracted from official VNF IENC (Inland ENC, S-57) cells.

### Pipeline
```
ienc/FR.zip  +  VNF Charts/*.zip  →  extract_ienc.py  →  data/bridges.geojson
```

- `extract_ienc.py` runs via `source venv/bin/activate && python3 extract_ienc.py --zip <path> ... --out data/bridges.geojson`
- Requires system GDAL (`brew install gdal`) plus matching Python binding (`pip install GDAL==$(gdal-config --version)` inside venv)
- Aggregates per-named-bridge (MIN `VERCLR` across spans = worst-case for a vessel), cross-zip dedup keeps the more conservative record
- Filters sentinels: `VERCLR=9999` (aggregate parent) and `VERCLR=0` (missing data) both dropped
- Licence Ouverte 2.0 — attribution line in every popup

### Coverage
Rhine 281 · Dunkerque–Escaut 185 · Seine 176 · Moselle 100 · Saône 115 · Seine Amont 38 · Oise 32 · Garonne tidal 23 · Canal du Rhône au Rhin 12 · Rhône 11 · Nieuwpoort–Dunkerque 10 · Leie 7. **Gap**: full Rhône Lyon→Med is not in the current bundles.

### Vessel-profile colouring (in popup + marker border)
- 🟢 ok: `verclr ≥ air + 0.5 m`
- 🟡 tight: `verclr ≥ air` but `< air + 0.5`
- 🔴 blocked: `verclr < air`
- ⚪ neutral: no profile set
- Rebuild hooks: `saveProfile()` and `applyVesselFilter()` call `_refreshBridgesOnProfileChange()`

### Caveat shown in every popup
Clearances are at the IENC *reference water level*. Actual clearance drops in high water — the popup includes this note.

---

## Google Places import

Users can bring their Google Maps "Saved Places" (Starred, Want to Go, lists) into the map as a 📍 My Places layer. Managed from the **Data Backup** panel under the *Google Maps places* heading.

### Supported input formats
- **KML** (`.kml`) — from Google Takeout → Maps → Your places
- **GeoJSON / JSON** (`.json`, `.geojson`) — Takeout's newer format

Parsed client-side via `DOMParser` (KML) or `JSON.parse` (GeoJSON). No server, no library.

### Place entry shape
```js
{ id: 'gp_…', name: 'Le Petit Bateau', lat: 47.45, lon: 3.12,
  note: 'Optional comment', url: 'https://maps.google.com/…',
  importedAt: 1713000000000 }
```

### UI actions (all in Data Backup panel)
| Button | Action |
|--------|--------|
| **📥 Add places** | Merge imported file into existing list (dedup by name+lat/lon round to 4dp) |
| **🔄 Sync places** | Replace-all (re-import after editing Google lists) |
| **🗑 Clear places** | Wipe all with confirm |

### Layer toggle
`📍 My Places` button in the controls bar toggles `googlePlacesGroup`. Auto-enabled at init if `googlePlaces[]` is non-empty.

---

## PWA / offline mode

The app is installable and works offline. Files that make this work:

| File | Role |
|------|------|
| `manifest.json` | Installable web app metadata (name, icons, theme, start_url) |
| `sw.js` | Service worker — precache app shell + LRU tile cache |
| `icon.svg` | 512×512 vessel-on-canal icon referenced by manifest + Apple touch-icon |

### Caching strategies (all in `sw.js`)

| Resource | Strategy | Cache |
|----------|----------|-------|
| App shell (HTML, manifest, icon, `waterways.geojson`, `data/bridges.geojson`, Leaflet CDN) | Precache at install | `fc-shell-<VERSION>` |
| Navigation / HTML | Network-first, fallback shell | `fc-shell-<VERSION>` |
| Map tiles (OSM, IGN, CartoDB, ESRI, OpenTopo, OpenSeaMap) | Cache-first, LRU cap 400 entries | `fc-tiles-<VERSION>` |
| Overpass, Open-Meteo, Vigicrues, Hub'Eau | **Never cached** (pass-through) | — |
| Other same-origin / CDN | Stale-while-revalidate | `fc-shell-<VERSION>` |

### Versioning
Bump `VERSION` at the top of `sw.js` to invalidate ALL caches. New workers `skipWaiting()` on user request via the update banner.

### Update banner (`#sw-update-banner`)
Shows when a new SW is waiting. User taps **Reload** → SW posts `SKIP_WAITING` → `controllerchange` fires → page auto-reloads with the new version.

### Limitations
- Service workers require HTTP(S). `file://` skips registration silently.
- Offline tile viewing only works for areas the user viewed while online (cache-first but no pre-downloading yet).
- Overpass-dependent features (Explore Nearby, live locks, provisions) degrade gracefully — the cached geojson still renders the canal network.

---

## Edit Locations mode

### How it works (click-to-place)
1. User clicks **Edit Locations** → `activateEditMode()` runs
2. Map panning is **disabled** — scroll-to-zoom still works
3. User **clicks a marker** → orange ring appears; banner prompts where to click
4. User **clicks the map** → marker repositioned, saved to localStorage
5. User clicks **✓ Done** → `deactivateEditMode()` re-enables panning, rebuilds markers

### Why map panning is disabled (critical)
Leaflet's `_draggableMoved()` checks `map.dragging._moved`, which stays `true` after any pan, silently suppressing all marker clicks. Fix:
```js
map.dragging.disable();
if (map.dragging._draggable) map.dragging._draggable._moved = false;
```

### Why `_getLbl()` is a function
`#drag-coord-label` is in the HTML after `</script>`. A module-level `const` would evaluate to `null` at script load time. `_getLbl()` calls `getElementById` at call time.

### Do not retry drag-and-drop
Seven drag implementations were attempted and all failed due to Leaflet internals (mousedown/mousemove pipeline conflicts). Click-to-place is the correct solution.

---

## Key functions quick-reference

| Function | Line | Purpose |
|----------|------|---------|
| `buildMooringMarkers()` | ~3453 | Clears + rebuilds halte/port markers |
| `buildMichelinMarkers()` | ~3501 | Builds Michelin restaurant layer |
| `buildMarkers()` | ~3578 | Clears + rebuilds town/lock markers |
| `buildTunnelMarkers()` | ~4413 | Builds tunnel layer with convoy popups |
| `buildBridgeMarkers()` | ~8248 | Fetches `data/bridges.geojson` (first-time), renders clustered bridge markers with vessel-profile-aware colouring |
| `openSidebar(wid)` | ~3760 | Opens detail panel for a waypoint |
| `toggleLayer(type)` | ~3918 | Show/hide layer groups (incl. `bridges`, `googleplaces`) |
| `openProfileModal()` | ~3994 | Opens vessel profile modal |
| `saveProfile()` | ~4016 | Saves profile; also triggers `_refreshBridgesOnProfileChange()` |
| `applyVesselFilter()` | ~4116 | Applies draft/air filter; also triggers bridge re-colouring |
| `buildChomagesMarkers()` | ~4256 | Builds VNF maintenance closure markers |
| `colorLookup(name)` | ~5027 | Returns per-waterway colour from `WATERWAY_COLORS` (normalised match) |
| `getWaterwayNavStatus(name)` | ~5040 | Returns colour for a waterway: per-palette (no profile) or navigability (with profile) |
| `buildWaterwayOverlay()` | ~5091 | Builds/rebuilds the waterway GeoJSON layer |
| `openRoutePlanner()` | ~6071 | Opens the route planner sidebar |
| `reverseRoute()` | ~6113 | Reverses all route stops |
| `exportRouteAsGPX()` | ~6134 | Downloads planned route as .gpx file |
| `renderDayByDay()` | ~6190 | Builds day-by-day itinerary + async per-day weather hydration |
| `fetchLocksInView()` | ~6451 | Overpass query for locks in current viewport |
| `calculateRoute()` | ~6702 | BFS pathfinding + renders results |
| `highlightRouteOnMap()` | ~6939 | Highlights planned route on map |
| `_buildExploreSnippet()` | ~7295 | Route planner attractions snippet (top 5 nearest) |
| `renderRoutePOIsSection()` | ~7379 | Renders per-stop POI panel |
| `_fetchPOIsNearby()` | ~7452 | 15 km Overpass query for Explore Nearby categories |
| `_fetchProvisionsNearby()` | ~7495 | Overpass query for shops & services |
| `_renderPOIList()` | ~7635 | Explore Nearby category chips + item rows |
| `selectForReposition()` | ~7795 | Selects a marker for click-to-place |
| `activateEditMode()` | ~7884 | Enters Edit Locations mode |
| `deactivateEditMode()` | ~7910 | Exits Edit Locations mode |
| `saveLocationOverride()` | ~7938 | Persists a position correction to localStorage |
| `exportLocationOverrides()` | ~7984 | Downloads corrections as JSON |
| `importLocationOverrides()` | ~8078 | Restores corrections from JSON |
| `buildGooglePlacesMarkers()` | ~8278 | Renders 📍 pins for imported Google Maps places |
| `_parseKMLPlaces()` | ~8303 | DOMParser KML → places array |
| `_parseGoogleTakeoutPlaces()` | ~8336 | Parses Google Takeout GeoJSON export |
| `importGooglePlaces()` | ~8357 | Import KML/JSON/GeoJSON (append or replace) |
| `clearGooglePlaces()` | ~8395 | Clears all imported places (with confirm) |

---

## fill_waterways.py — key functions

| Function / constant | Purpose |
|---------------------|---------|
| `_PREFIX_RE` | Strips `river/la/le/l'/les/the` from waterway names for normalisation (intentionally excludes `canal de`) |
| `_norm_name(name)` | Lowercases + strips prefix — used for deduplication matching |
| `_NON_NAVIGABLE_RE` | Pattern: `ancien, bras-mort, vieux/vieille, écluse, pont-canal, aqueduc, prise d'eau, souterrain` |
| `is_non_navigable(name)` | Returns `True` if name matches `_NON_NAVIGABLE_RE` |
| `clean_geojson(geojson)` | Removes non-navigable features + non-canonical variants from existing GeoJSON |
| `merge_geojson()` | Merges Overpass fetch with existing file using normalised dedup |
| `--clean-geojson` | CLI mode: run cleanup pass on `waterways.geojson` without re-fetching |

---

## fill_michelin.py — Michelin update script

Downloads the latest Michelin Guide France data from [ngshiheng/michelin-my-maps](https://github.com/ngshiheng/michelin-my-maps) and regenerates the `MICHELIN_RESTAURANTS` constant in `french_canals_map.html`.

**Run manually:**
```bash
python3 fill_michelin.py --preview   # dry run — shows counts, no file changes
python3 fill_michelin.py             # update in-place
git add french_canals_map.html
git commit -m "Update Michelin restaurants YYYY"
git push
```

**Automated:** `.github/workflows/update-michelin.yml` runs this automatically on **15 February each year** and opens a Pull Request if the data has changed. Can also be triggered manually from GitHub → Actions → Update Michelin Restaurants → Run workflow.

**Filter logic:**
- Country: `', France'` in the `Location` column
- Included awards: `1 Star`, `2 Stars`, `3 Stars`, `Bib Gourmand`
- Excluded: `Selected Restaurants` (~2,000 entries — unstarred, non-Bib)
- Sort order: 3★ → 2★ → 1★ → Bib, then city + name alphabetically

**Data source columns used:** `Name`, `Latitude`, `Longitude`, `Award`, `Cuisine`, `Location` (city), `Url`

---

## Common tasks

### Add a new mooring
Append to `MOORINGS` (~line 1922). Give it a unique `id` starting with `m_`.

### Add a new waypoint
Append to `WAYPOINTS` (~line 1414). Give it a unique `id` starting with `w_`.

### Add a tunnel
Append to `TUNNELS` (~line 4311). Give it a unique `id` starting with `t0`.

### Refresh IENC bridge data (after new VNF release)
```bash
source venv/bin/activate   # system GDAL + Python binding must be installed
python3 extract_ienc.py \
  --zip ienc/FR.zip \
  --zip "VNF Charts/ENC_ROOT_SEINE_AVAL_ED2.zip" \
  --zip "VNF Charts/ENC_ROOT_SEINE_AMONT_ED1.zip" \
  --zip "VNF Charts/ENC_ROOT_SAONE_ED_2.zip" \
  --zip "VNF Charts/Garonne_edition3.zip" \
  --zip "VNF Charts/ENC_ROOT_GARONNE_MAJ1.zip" \
  --zip "VNF Charts/ENC_ROOT_OISE.zip" \
  --zip "VNF Charts/ENC_ROOT_OISE_MAJ1.zip" \
  --out data/bridges.geojson \
  --out-locks data/ienc_locks.geojson \
  --out-moorings data/ienc_moorings.geojson \
  --reconcile french_canals_map.html
```

### Fix a waterway gap
Edit `waterways.geojson` directly, or re-run `fill_waterways.py` for a fresh Overpass sweep. The ETag check will push the update to all browsers automatically.

### Clean non-navigable segments from waterways.geojson
```bash
python3 fill_waterways.py --clean-geojson
```

### Add a waterway constraint
Add an entry to `WATERWAY_CONSTRAINTS` (~line 4847) using the exact OSM name as the key.

### Add tidal data for another waterway
Add an entry to `TIDAL_DATA` (~line 4934). Schema matches the Garonne entry: `stations[]` with per-coefficient offsets in minutes, `marnage_min_m`, and a `warnings[]` list.

### Change map behaviour
Leaflet map initialised at ~line 3229. Tile layers and layer switcher also there.

### Test locally
Run `python3 -m http.server 8765` from the project folder, then open `http://localhost:8765/french_canals_map.html`. Or double-click `Open Map.command` (requires `chmod +x "Open Map.command"` once).

### Force browsers to re-fetch waterways.geojson
Change `WATERWAYS_CACHE_VER` constant (currently `'french-canals-waterways-v7'`) to the next version.

### Deploy
```bash
git add french_canals_map.html waterways.geojson
git commit -m "Your message"
git push
```
GitHub Pages serves from `main` branch root. Live within ~2 minutes.

---

## Git workflow

```bash
# from inside the French Canals/ folder:
git add french_canals_map.html
git commit -m "Your message"
git push
```

If you need to re-authenticate:
```bash
git remote set-url origin https://EnzoCem:<PAT>@github.com/EnzoCem/french-canals-map.git
```
