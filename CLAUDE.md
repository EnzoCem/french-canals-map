# French Canals Interactive Map — Claude Code Guide

## Project overview

A single-file interactive web map for cruising the French inland waterways, based on David Jefferson's *Through the French Canals* (14th edition). Users can browse towns, locks, haltes fluviales, ports de plaisance, plan routes, write notes, and correct marker positions.

**GitHub:** https://github.com/EnzoCem/french-canals-map
**Live page:** https://enzocem.github.io/french-canals-map/
**Local file:** `french_canals_map.html` (open directly in a browser via `file://`)

---

## Everything is one file

The entire application — HTML, CSS, JavaScript, and all data — lives in **`french_canals_map.html`** (~3 300 lines). There are no build tools, no npm, no bundler. Edit the file and refresh the browser.

**External CDN dependencies** (must have internet access):
- Leaflet 1.9.4 — `https://unpkg.com/leaflet@1.9.4/dist/leaflet.js`
- Leaflet MarkerCluster 1.5.3 — `https://unpkg.com/leaflet.markercluster@1.5.3/...`

---

## File layout (line numbers)

| Lines | Content |
|-------|---------|
| 1–711 | `<head>` + all CSS styles |
| 712–777 | HTML: `#controls` bar, `#main` wrapper, `#map` div, `#sidebar` |
| 778–780 | CDN `<script>` tags (Leaflet + MarkerCluster) |
| 780 | **`<script>` opens** — all application JS starts here |
| 785–833 | `const ROUTES` — 44 canal route definitions |
| 834–1047 | `const WAYPOINTS` — ~77 town/lock waypoints |
| 1048–1143 | `const MOORINGS` — ~23 haltes + ports with full metadata |
| 1144–1175 | localStorage keys, `locationOverrides` init, position patching |
| 1176–1237 | `L.map(...)` init, tile layers, GeoJSON waterway data (~5 400 features) |
| 1238–1296 | Layer group declarations (`clusterGroup`, `townGroup`, `lockGroup`, etc.) |
| 1297–1343 | `buildMooringMarkers()` |
| 1345–1437 | `buildMarkers()` |
| 1438–1553 | Sidebar: `openSidebar()`, note save/delete |
| 1554–1600 | `layerState`, `toggleLayer()` |
| 1601–1818 | Search (`searchPlaces`, `searchKeyNav`) |
| 1819–2326 | Waterway GeoJSON overlay, `waterwayLayer`, waterway dims lookup |
| 2327–2840 | Route planner (`openRoutePlanner`, `nudgeCalculate`, endpoint pins) |
| 2841–3002 | **Edit Locations mode** (see dedicated section below) |
| 3003–3200 | `saveLocationOverride`, `resetAllLocationOverrides`, `exportLocationOverrides`, `importLocationOverrides`, data backup panel |
| 3188 | **`</script>` closes** |
| 3200–3297 | HTML after script: route planner panel, nudge bar, edit-mode banner, `#drag-coord-label`, `#edit-toast`, data panel |

> ⚠️ **Critical rule:** Never write `</script>` (as a literal string) anywhere inside the `<script>` block — not in comments, not in strings. The HTML parser terminates the script block on sight, which causes all subsequent JS to render as raw page text. Use `<\/script>` or rephrase the comment if you need to reference it.

---

## localStorage keys

| Key | Purpose |
|-----|---------|
| `french_canals_notes_v1` | User notes per waypoint (`{ [id]: string }`) |
| `french_canals_location_overrides_v1` | Corrected marker positions (`{ waypoints: { [id]: {lat,lon} }, moorings: { [id]: {lat,lon} } }`) |

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
{ id: 'm_001', name: 'Port de Plaisance Auxerre', type: 'port', // or 'halte'
  lat: 47.798, lon: 3.567, waterway: 'Canal du Nivernais',
  cost: 'paid', pk: '2K3', facilities: 'water/electric/showers',
  max_vessel: '35m', contact: 'Optional contact info' }
```

### ROUTES entry
```js
{ num: 1, canal: 'River Seine', section: 1 }
```

---

## Layer architecture

```
map
├── waterwayLayer   (L.geoJSON — canal polylines, toggled by "Canals" button)
├── clusterGroup    (L.markerClusterGroup — town markers, normal mode)
├── townGroup       (L.layerGroup — same town markers, unclustered in edit mode)
├── lockGroup       (L.layerGroup — lock markers, always unclustered)
├── notesGroup      (L.layerGroup — note-pin markers)
├── halteGroup      (L.layerGroup — halte markers)
└── portGroup       (L.layerGroup — port markers)
```

`allMarkers[]` and `allMooringMarkers[]` hold references to every Leaflet marker for use by edit mode.

---

## Edit Locations mode — full technical context

### What it does
Allows the user to correct the lat/lon of any waypoint or mooring marker. Corrections are saved to localStorage and applied on every page load via `_origPositions`.

### How it works (click-to-place UX)
After **6+ failed attempts** to implement drag-and-drop (see history below), the feature uses a **click-to-place** approach:

1. User clicks **Edit Locations** → `activateEditMode()` runs.
2. Map panning is **disabled** (`map.dragging.disable()`) — scroll-to-zoom still works.
3. User **clicks a marker** → `selectForReposition(marker, data, type)` is called; an orange ring appears on the icon; a label at the top says where to click next.
4. User **clicks the map** → `map.on('click', ...)` places the marker, saves to localStorage.
5. User clicks **✓ Done** → `deactivateEditMode()` runs, re-enables panning, rebuilds markers.

### Why map panning is disabled in edit mode (critical)
Leaflet's `_draggableMoved()` method falls back to checking `map.dragging.moved()` when a marker does not have dragging enabled. `map.dragging._moved` stays `true` permanently after any pan, causing **all marker clicks to be silently suppressed**. Disabling map drag and resetting `_draggable._moved = false` on entry is the only reliable fix.

```js
// In activateEditMode():
map.dragging.disable();
if (map.dragging._draggable) map.dragging._draggable._moved = false;

// In deactivateEditMode():
map.dragging.enable();
```

### Why `_getLbl()` is a function, not a const
The `#drag-coord-label` div is defined **after** `</script>` in the HTML. A module-level `const _dragLabel = document.getElementById(...)` evaluates at script-load time, before that element exists, returning `null`. All access to the element goes through `_getLbl()` which calls `getElementById` at call time.

### Key variables (Edit Locations scope)
| Variable | Purpose |
|----------|---------|
| `editModeActive` | Boolean flag checked by marker click handlers |
| `_selectedEditMarker` | The L.Marker currently selected for repositioning |
| `_selectedEditData` | The raw data object (`w` or `m`) for the selected marker |
| `_selectedEditType` | `'waypoint'` or `'mooring'` |
| `_suppressMapClick` | Set to `true` by marker click to prevent the map click handler from also firing |

### History of drag-and-drop attempts (do not retry these)
All seven drag implementations were attempted and failed due to Leaflet internals:
1. Custom `mousedown` → `map.on('mousemove')` — Leaflet map mousemove doesn't fire when mousedown is on a marker.
2. Custom `mousedown` → `document.addEventListener('mousemove')` — used pointer events pipeline; Leaflet uses mouse events.
3. `pointerdown` + `setPointerCapture` — completely separate event pipeline from Leaflet's mousedown-based system.
4. Native `marker.dragging.enable()/disable()` — with `draggable: false`, `_initInteraction` still creates `marker.dragging` but disabling map drag was needed first.
5. Variants of the above with different ordering — same underlying issues.

**The click-to-place approach is the correct solution for this codebase.**

---

## Git workflow

The project folder already has git initialised and a remote:
```bash
# from inside the French Canals/ folder:
git add french_canals_map.html
git commit -m "Your message"
git push
```

GitHub credentials are set with a PAT. If you need to re-authenticate:
```bash
git remote set-url origin https://EnzoCem:<PAT>@github.com/EnzoCem/french-canals-map.git
```
The user can provide the PAT if needed.

GitHub Pages serves the live site from the `main` branch root. Changes are live within ~2 minutes of pushing. The user also uses the file directly at `file:///Users/esen/Documents/Cem Code/French Canals/french_canals_map.html`.

---

## Key functions quick-reference

| Function | Lines | Purpose |
|----------|-------|---------|
| `buildMooringMarkers()` | ~1297 | Clears + rebuilds halte/port markers |
| `buildMarkers()` | ~1345 | Clears + rebuilds town/lock markers |
| `openSidebar(wid)` | ~1454 | Opens detail panel for a waypoint |
| `toggleLayer(type)` | ~1556 | Show/hide layer groups |
| `searchPlaces(query)` | ~1601 | Live search dropdown |
| `openRoutePlanner()` | ~2327 | Opens the route planner sidebar |
| `nudgeCalculate()` | ~2350 | Computes + highlights route between two pins |
| `activateEditMode()` | ~2950 | Enters Edit Locations mode |
| `deactivateEditMode()` | ~2976 | Exits Edit Locations mode (all steps in try/catch) |
| `selectForReposition()` | ~2861 | Selects a marker for click-to-place |
| `deselectForReposition()` | ~2895 | Clears selection + orange ring |
| `saveLocationOverride()` | ~3004 | Persists a position correction to localStorage |
| `exportLocationOverrides()` | ~3050 | Downloads corrections as JSON |
| `importLocationOverrides()` | ~3139 | Restores corrections from JSON |
| `updateEditBannerCount()` | ~3017 | Updates the "N corrections saved" badge |
| `showEditToast(msg)` | ~3024 | Shows the brief toast notification |

---

## Common tasks

### Add a new mooring
Append to the `MOORINGS` array (around line 1048). Give it a unique `id` starting with `m_`.

### Fix a waterway gap
The waterway GeoJSON is embedded in the HTML around line 1176. Find the relevant section and adjust the coordinates. See the git history for examples of past gap fixes.

### Change map behaviour
The Leaflet map is initialised around line 1176 with options like `zoomControl`, `minZoom`, `maxZoom`. Tile layer attribution is also there.

### Test locally
Open `french_canals_map.html` directly in Chrome/Firefox. No server needed. Use DevTools console to check for JS errors.
