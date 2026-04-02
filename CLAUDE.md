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
├── french_canals_map.html          ← entire app (HTML + CSS + JS + data) ~7,700 lines
├── waterways.geojson               ← canal/river geometry fetched from OSM (~8.5 MB, 3,500 features after cleanup)
├── index.html                      ← GitHub Pages redirect to french_canals_map.html
├── Open Map.command                ← macOS launcher script (requires chmod +x once)
├── fill_waterways.py               ← one-shot script that generated waterways.geojson via Overpass
├── fill_michelin.py                ← annual script to update MICHELIN_RESTAURANTS from ngshiheng/michelin-my-maps
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
| 1–1104 | `<head>` + all CSS styles |
| 1105–1214 | `<body>`: `#controls` bar, `#main`, `#map`, `#sidebar` |
| 1215–1216 | CDN `<script>` tags (Leaflet + MarkerCluster) |
| 1217 | **`<script>` opens** — all application JS starts here |
| 1227–1275 | `const ROUTES` — 44 canal route definitions |
| 1276–1783 | `const WAYPOINTS` — ~120 town/lock waypoints |
| 1784–2021 | `const MOORINGS` — haltes + ports with full metadata |
| 2022–3076 | `const MICHELIN_RESTAURANTS` — 1,007 Michelin-awarded restaurants |
| 3077–3096 | localStorage keys + saved-routes init |
| 3097–3241 | Map init (`L.map`), tile layers, layer switcher, waterways fetch + cache |
| 3242–3299 | Layer group declarations (incl. `tunnelGroup`) |
| 3300–3375 | `buildMooringMarkers()` |
| 3348–3375 | `buildMichelinMarkers()` |
| 3376–3557 | `buildMarkers()` |
| 3558–3713 | Sidebar: `openSidebar()`, Explore Nearby, Provisions, note save/delete |
| 3714–3777 | `layerState`, `toggleLayer()` |
| 3778–3897 | Vessel profile: `openProfileModal()`, `saveProfile()`, `applyVesselFilter()` |
| 4036–4090 | Chômages data + `buildChomagesMarkers()` |
| 4091–4192 | `const TUNNELS` — 5 tunnel entries with convoy schedules |
| 4193–4260 | `buildTunnelMarkers()` |
| 4579–4623 | `WATERWAY_COLORS` — per-waterway colour palette (active when no vessel profile set) |
| 4624–4698 | `WATERWAY_CONSTRAINTS` — VNF dimension limits per waterway |
| 4699 | `const _normName` — shared name normaliser |
| 4710–4722 | `colorLookup(name)` — normalised WATERWAY_COLORS lookup |
| 4723–4773 | `getWaterwayNavStatus()`, `_updateWaterwayNavLegend()` |
| 4774–4989 | `buildWaterwayOverlay()`, waterway dims lookup |
| 4990–5657 | `ROUTE_CONNECTIONS`, route planner graph, `findRoutePath()`, `calculateRoute()` setup |
| 5658–5699 | `openRoutePlanner()`, `closeRoutePlanner()` |
| 5700–5776 | `reverseRoute()`, `exportRouteAsGPX()` |
| 5777–6007 | `renderDayByDay()`, `_getCruiseSettings()`, weather fetch + snippets |
| 6008–6259 | Live locks: `fetchLocksInView()`, `scheduleLockFetch()`, route-lock markers |
| 6260–6353 | `calculateRoute()` — BFS pathfinding + route results rendering |
| 6354–6496 | `ROUTE_TO_WATERWAYS` — maps route numbers → OSM waterway names |
| 6497–6733 | `highlightRouteOnMap()`, `clearRouteHighlight()`, `restoreWaterwayStyles()` |
| 6734–6853 | Saved routes: `saveCurrentRoute()`, `loadSavedRoute()`, `deleteSavedRoute()` |
| 6854–6937 | `_buildExploreSnippet()` — route planner attractions snippet |
| 6938–7010 | `renderRoutePOIsSection()`, `showRoutePOIStop()`, `loadRoutePOIExplore()` |
| 7011–7049 | `_fetchPOIsNearby()` — 15 km Overpass query (markets, bike hire, restaurants, food, swimming, tourism, wineries+distilleries) |
| 7050–7182 | Provisions: `_fetchProvisionsNearby()`, `_buildProvisionsSnippet()`, `loadRouteProvisions()` |
| 7183–7332 | `_renderPOIList()` — Explore Nearby category chips + item rows |
| 7334–7422 | Edit mode marker selection: `selectForReposition()`, `deselectForReposition()` |
| 7423–7448 | `activateEditMode()`, `deactivateEditMode()` |
| 7477–7684 | `saveLocationOverride()`, `resetAllLocationOverrides()`, `exportLocationOverrides()`, `importLocationOverrides()` |
| 7685 | **`</script>` closes** |
| 7686+ | HTML panels: route planner, profile modal, edit-mode banner, data backup panel |

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
└── tunnelGroup      (L.layerGroup — canal tunnel markers with convoy schedules)
```

`allMarkers[]` and `allMooringMarkers[]` hold references to every marker for vessel filter and edit mode.

---

## Waterway overlay (waterways.geojson)

The waterway geometry lives in a **separate file** (`waterways.geojson`) loaded at startup:

```js
// Loaded via Cache API (instant on repeat visits):
fetch('./waterways.geojson')  // → stored in Cache API → ETag checked in background
```

- **3,500 features** covering all French navigable waterways (down from 23,862 after deduplication and non-navigable removal)
- Generated by `fill_waterways.py` via 12-region Overpass sweep
- Non-navigable segments filtered by name pattern (`_NON_NAVIGABLE_RE`: ancien, bras-mort, vieux/vieille, écluse, pont-canal, aqueduc, prise d'eau, souterrain)
- Normalised deduplication removes regional/spelling variants; canonical OSM name kept
- RDP-simplified at 33m tolerance
- Cache version: `waterways-v7` — bump this constant to force all browsers to re-fetch

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

Five major tunnels in `const TUNNELS` (~line 4091), rendered by `buildTunnelMarkers()` into `tunnelGroup`:

| ID | Name | Canal | Length | Tug |
|----|------|-------|--------|-----|
| t001 | Riqueval | Canal de Saint-Quentin | 5,670 m | Yes |
| t002 | Mauvages | Canal de la Marne au Rhin | 4,877 m | Yes |
| t003 | Foug | Canal de la Marne au Rhin | 866 m | No |
| t004 | Pouilly-en-Auxois | Canal de Bourgogne | 3,333 m | No |
| t005 | Saint-Albin / Balesmes | Canal entre Champagne et Bourgogne | 2,306 m | Yes |

Each tunnel popup shows: length, tug requirement, northbound/southbound convoy times, booking info, and VNF link.

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
| `buildMooringMarkers()` | ~3300 | Clears + rebuilds halte/port markers |
| `buildMichelinMarkers()` | ~3348 | Builds Michelin restaurant layer |
| `buildMarkers()` | ~3376 | Clears + rebuilds town/lock markers |
| `buildTunnelMarkers()` | ~4193 | Builds tunnel layer with convoy popups |
| `openSidebar(wid)` | ~3558 | Opens detail panel for a waypoint |
| `toggleLayer(type)` | ~3716 | Show/hide layer groups |
| `searchPlaces(query)` | ~4093 | Live search dropdown |
| `openProfileModal()` | ~3778 | Opens vessel profile modal |
| `saveProfile()` | ~3800 | Saves profile to localStorage + syncs filter bar |
| `applyVesselFilter()` | ~3898 | Applies draft/air filter + syncs `_vesselProfile` |
| `buildChomagesMarkers()` | ~4036 | Builds VNF maintenance closure markers |
| `colorLookup(name)` | ~4710 | Returns per-waterway colour from `WATERWAY_COLORS` (normalised match) |
| `getWaterwayNavStatus(name)` | ~4723 | Returns colour for a waterway: per-palette (no profile) or navigability (with profile) |
| `buildWaterwayOverlay()` | ~4774 | Builds/rebuilds the waterway GeoJSON layer |
| `openRoutePlanner()` | ~5658 | Opens the route planner sidebar |
| `reverseRoute()` | ~5700 | Reverses all route stops (A→B→C becomes C→B→A) |
| `exportRouteAsGPX()` | ~5721 | Downloads planned route as .gpx file |
| `renderDayByDay()` | ~5777 | Builds day-by-day itinerary from route legs |
| `fetchLocksInView()` | ~6013 | Overpass query for locks in current viewport |
| `calculateRoute()` | ~6260 | BFS pathfinding + renders results |
| `highlightRouteOnMap()` | ~6497 | Highlights planned route on map (coral-red + white halo) |
| `_buildExploreSnippet()` | ~6854 | Route planner attractions snippet (top 5 nearest) |
| `renderRoutePOIsSection()` | ~6938 | Renders per-stop POI panel in route planner |
| `_fetchPOIsNearby()` | ~7011 | 15 km Overpass query for all Explore Nearby categories |
| `_renderPOIList()` | ~7183 | Explore Nearby category chips + item rows |
| `activateEditMode()` | ~7423 | Enters Edit Locations mode |
| `deactivateEditMode()` | ~7449 | Exits Edit Locations mode |
| `selectForReposition()` | ~7334 | Selects a marker for click-to-place |
| `saveLocationOverride()` | ~7477 | Persists a position correction to localStorage |
| `exportLocationOverrides()` | ~7523 | Downloads corrections as JSON |
| `importLocationOverrides()` | ~7616 | Restores corrections from JSON |

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
Append to `MOORINGS` (~line 1784). Give it a unique `id` starting with `m_`.

### Add a new waypoint
Append to `WAYPOINTS` (~line 1276). Give it a unique `id` starting with `w_`.

### Add a tunnel
Append to `TUNNELS` (~line 4091). Give it a unique `id` starting with `t0`.

### Fix a waterway gap
Edit `waterways.geojson` directly, or re-run `fill_waterways.py` for a fresh Overpass sweep. The ETag check will push the update to all browsers automatically.

### Clean non-navigable segments from waterways.geojson
```bash
python3 fill_waterways.py --clean-geojson
```

### Add a waterway constraint
Add an entry to `WATERWAY_CONSTRAINTS` (~line 4624) using the exact OSM name as the key.

### Change map behaviour
Leaflet map initialised at ~line 3097. Tile layers and layer switcher also there.

### Test locally
Run `python3 -m http.server 8765` from the project folder, then open `http://localhost:8765/french_canals_map.html`. Or double-click `Open Map.command` (requires `chmod +x "Open Map.command"` once).

### Force browsers to re-fetch waterways.geojson
Change `WATERWAYS_CACHE_VER` constant (currently `'waterways-v7'`) to the next version.

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
