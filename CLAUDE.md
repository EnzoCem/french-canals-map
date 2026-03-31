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
├── french_canals_map.html   ← entire app (HTML + CSS + JS + data) ~7,660 lines
├── waterways.geojson        ← canal/river geometry fetched from OSM (~8.5 MB, 23,862 features)
├── index.html               ← GitHub Pages redirect to french_canals_map.html
├── Open Map.command         ← macOS launcher script (requires chmod +x once)
├── fill_waterways.py        ← one-shot script that generated waterways.geojson via Overpass
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
| 1–1104 | `<head>` + all CSS styles |
| 1105–1214 | `<body>`: `#controls` bar, `#main`, `#map`, `#sidebar` |
| 1215–1216 | CDN `<script>` tags (Leaflet + MarkerCluster) |
| 1217 | **`<script>` opens** — all application JS starts here |
| 1222–1270 | `const ROUTES` — 44 canal route definitions |
| 1271–1778 | `const WAYPOINTS` — ~120 town/lock waypoints |
| 1779–2016 | `const MOORINGS` — haltes + ports with full metadata |
| 2017–3071 | `const MICHELIN_RESTAURANTS` — 1,007 Michelin-awarded restaurants |
| 3072–3091 | localStorage keys + saved-routes init |
| 3092–3233 | Map init (`L.map`), tile layers, layer switcher, waterways fetch + cache |
| 3234–3293 | Layer group declarations |
| 3294–3369 | `buildMooringMarkers()` |
| 3370–3484 | `buildMarkers()` |
| 3485–3644 | Sidebar: `openSidebar()`, Explore Nearby, Provisions, note save/delete |
| 3645–3696 | `layerState`, `toggleLayer()` |
| 3697–3907 | Vessel profile: `openProfileModal()`, `saveProfile()`, `applyVesselFilter()` |
| 3908–3999 | Chômages data + `buildChomagesMarkers()` |
| 4000–4092 | Michelin markers: `buildMichelinMarkers()` |
| 4093–4351 | Search: `searchPlaces()`, `searchKeyNav()` |
| 4352–4396 | `WATERWAY_COLORS` — per-waterway colour palette (active when no vessel profile set) |
| 4397–4469 | `WATERWAY_CONSTRAINTS` — VNF dimension limits per waterway |
| 4470–4517 | `getWaterwayNavStatus()`, `_updateWaterwayNavLegend()` |
| 4518–4734 | `buildWaterwayOverlay()`, waterway dims lookup, `ROUTE_TO_WATERWAYS` stub |
| 4735–5402 | `ROUTE_CONNECTIONS`, route planner graph, `findRoutePath()`, `calculateRoute()` setup |
| 5403–5535 | `openRoutePlanner()`, `closeRoutePlanner()`, `reverseRoute()`, `exportRouteAsGPX()` |
| 5536–5760 | `renderDayByDay()`, `_getCruiseSettings()`, weather fetch + snippets |
| 5761–5991 | Live locks: `fetchLocksInView()`, `scheduleLockFetch()`, route-lock markers |
| 5992–6085 | `calculateRoute()` — BFS pathfinding + route results rendering |
| 6086–6228 | `ROUTE_TO_WATERWAYS` — maps route numbers → OSM waterway names |
| 6229–6488 | `highlightRouteOnMap()`, `clearRouteHighlight()`, `restoreWaterwayStyles()` |
| 6489–6560 | Saved routes: `saveCurrentRoute()`, `loadSavedRoute()`, `deleteSavedRoute()` |
| 6561–6900 | Route POIs: `renderRoutePOIsSection()`, `showRoutePOIStop()`, Michelin + Explore snippets |
| 6901–7042 | Provisions: `loadRouteProvisions()`, `_buildProvisionsSnippet()` |
| 7043–7131 | Edit mode marker selection: `selectForReposition()`, `deselectForReposition()` |
| 7132–7185 | `activateEditMode()`, `deactivateEditMode()` |
| 7186–7500 | `saveLocationOverride()`, `resetAllLocationOverrides()`, `exportLocationOverrides()`, `importLocationOverrides()` |
| ~7500 | **`</script>` closes** |
| 7500+ | HTML panels: route planner, profile modal, edit-mode banner, data backup panel |

---

## localStorage keys

| Key | Purpose |
|-----|---------|
| `french_canals_notes_v1` | User notes per waypoint (`{ [id]: string }`) |
| `french_canals_location_overrides_v1` | Corrected marker positions (`{ waypoints: {}, moorings: {} }`) |
| `french_canals_saved_routes_v1` | Saved route plans (array of route objects) |
| `french_canals_vessel_v1` | Vessel profile (`{ vesselName, homePort, air, draught, length, beam, cruiseSpeed, hoursPerDay }`) |

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
└── chomagesGroup    (L.layerGroup — VNF maintenance closures)
```

`allMarkers[]` and `allMooringMarkers[]` hold references to every marker for vessel filter and edit mode.

---

## Waterway overlay (waterways.geojson)

The waterway geometry lives in a **separate file** (`waterways.geojson`) loaded at startup:

```js
// Loaded via Cache API (instant on repeat visits):
fetch('./waterways.geojson')  // → stored in Cache API → ETag checked in background
```

- **23,862 features** covering all French navigable waterways
- Generated by `fill_waterways.py` via 12-region Overpass sweep
- Filtered to navigable canals and named rivers only (no irrigation ditches)
- RDP-simplified at 33m tolerance (2.08M → 348K nodes)
- Cache version: `waterways-v2` — bump this constant to force all browsers to re-fetch

### Vessel-profile waterway colouring

When `_vesselProfile` has dimensions set, `buildWaterwayOverlay()` colours each waterway:
- 🔵 `#4fc3f7` — navigable (all dimensions clear)
- 🔴 `#ef5350` — blocked (dimension exceeded)
- 🟡 `#ffb74d` — marginal (within 10% of a limit)
- ⬜ `#90a4ae` — no VNF data for this waterway

Without a profile, all waterways render in uniform blue.

---

## Vessel profile — two input paths, fully synced

Two UIs both write to `_vesselProfile` and trigger `buildWaterwayOverlay()`:

1. **Profile modal** (`openProfileModal()` / `saveProfile()`) — full vessel details
2. **Controls bar filter** (`#vf-draft` / `#vf-air` + `applyVesselFilter()`) — quick override

`applyVesselFilter()` writes `draught`/`air` back into `_vesselProfile` so both systems stay in sync.
`saveProfile()` syncs values forward into the filter bar inputs.

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
| `buildMooringMarkers()` | ~3294 | Clears + rebuilds halte/port markers |
| `buildMarkers()` | ~3370 | Clears + rebuilds town/lock markers |
| `buildMichelinMarkers()` | ~4000 | Builds Michelin restaurant layer |
| `openSidebar(wid)` | ~3485 | Opens detail panel for a waypoint |
| `toggleLayer(type)` | ~3645 | Show/hide layer groups |
| `searchPlaces(query)` | ~4093 | Live search dropdown |
| `openProfileModal()` | ~3700 | Opens vessel profile modal |
| `saveProfile()` | ~3722 | Saves profile to localStorage + syncs filter bar |
| `applyVesselFilter()` | ~3820 | Applies draft/air filter + syncs `_vesselProfile` |
| `buildChomagesMarkers()` | ~3956 | Builds VNF maintenance closure markers |
| `colorLookup(name)` | ~4541 | Returns per-waterway colour from `WATERWAY_COLORS` (normalised match) |
| `getWaterwayNavStatus(name)` | ~4470 | Returns colour for a waterway: per-palette (no profile) or navigability (with profile) |
| `buildWaterwayOverlay()` | ~4518 | Builds/rebuilds the waterway GeoJSON layer |
| `openRoutePlanner()` | ~5403 | Opens the route planner sidebar |
| `reverseRoute()` | ~5459 | Reverses all route stops (A→B→C becomes C→B→A) |
| `exportRouteAsGPX()` | ~5480 | Downloads planned route as .gpx file |
| `renderDayByDay()` | ~5536 | Builds day-by-day itinerary from route legs |
| `fetchLocksInView()` | ~5761 | Overpass query for locks in current viewport |
| `calculateRoute()` | ~5992 | BFS pathfinding + renders results |
| `highlightRouteOnMap()` | ~6229 | Highlights planned route on map (coral-red + white halo) |
| `activateEditMode()` | ~7132 | Enters Edit Locations mode |
| `deactivateEditMode()` | ~7158 | Exits Edit Locations mode |
| `selectForReposition()` | ~7043 | Selects a marker for click-to-place |
| `saveLocationOverride()` | ~7186 | Persists a position correction to localStorage |
| `exportLocationOverrides()` | ~7232 | Downloads corrections as JSON |
| `importLocationOverrides()` | ~7325 | Restores corrections from JSON |

---

## Common tasks

### Add a new mooring
Append to `MOORINGS` (~line 1779). Give it a unique `id` starting with `m_`.

### Add a new waypoint
Append to `WAYPOINTS` (~line 1271). Give it a unique `id` starting with `w_`.

### Fix a waterway gap
Edit `waterways.geojson` directly, or re-run `fill_waterways.py` for a fresh Overpass sweep. The ETag check will push the update to all browsers automatically.

### Add a waterway constraint
Add an entry to `WATERWAY_CONSTRAINTS` (~line 4397) using the exact OSM name as the key.

### Change map behaviour
Leaflet map initialised at ~line 3092. Tile layers and layer switcher also there.

### Test locally
Run `python3 -m http.server 8765` from the project folder, then open `http://localhost:8765/french_canals_map.html`. Or double-click `Open Map.command` (requires `chmod +x "Open Map.command"` once).

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
