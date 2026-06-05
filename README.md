# Inland Europe — Interactive Canal Map

Interactive map of European inland waterways. France's data is hand-curated from David Jefferson's *Through the French Canals* (14th edition). Other countries are OpenStreetMap-derived with selective curation.

**Live:** https://enzocem.github.io/french-canals-map/french_canals_map.html

---

## Quick Start

**Online:** Open the live link above in any modern browser — works on desktop and iPhone.

**Local:**
1. Clone or download the repo
2. Double-click `Open Map.command` (Mac) — starts a local server and opens the map
   - First time only: `chmod +x "Open Map.command"` in Terminal
3. Or run manually: `python3 -m http.server 8765` then open `http://localhost:8765/french_canals_map.html`

> ⚠️ Opening `french_canals_map.html` directly via `file://` works for most features but the waterway overlay will not load (browser security blocks local file fetches).

---

## Features

### 🗺 Map & Base Layers
- **IGN France** (default) — France's official 1:25,000 topo map showing towpaths, lock buildings, canal infrastructure
- **OpenStreetMap, CartoDB Voyager, ESRI Satellite, OpenTopoMap** — switchable via layer control
- **OpenSeaMap** — nautical marks overlay (lock symbols, buoys, hazards)
- **Waterway overlay** — 3,500 canal and river segments from OpenStreetMap (deduplicated and non-navigable segments removed), color-coded by navigability when a vessel profile is set

### 📍 Marker Layers (all independently toggleable)
| Button | Layer | Description |
|--------|-------|-------------|
| 🏘 Towns | Town markers | 120+ halting towns with sidebars (distances, locks, services) |
| 🔒 Locks | Lock markers | Curated locks + live Overpass locks (zoom ≥ 12) |
| ⚓ Haltes | Halte markers | Official VNF mooring haltes |
| ⛵ Ports | Port markers | Marinas and commercial ports |
| 📌 Notes | My Notes | Personal notes pinned to the map |
| ⭐ Michelin | Restaurants | 1,007 Michelin-awarded restaurants across France |
| ⛽ Fuel | Fuel stops | Marine fuel and water stations |
| 🚧 Chômages | Closures | VNF maintenance closures (active + upcoming) |
| 🚇 Tunnels | Tunnels | 5 major tunnels with convoy times and booking requirements |
| 🌊 Canals | Waterways | Canal and river geometry overlay |

### 📍 Route Planner
Open **📍 Plan Route** to access the route planner:

- Select any two (or more) towns — full multi-stop planning (A → B → C → … → Z)
- BFS pathfinding across 44 connected waterway routes
- Results: total distance, lock count, estimated travel days, vessel constraint warnings
- **Day-by-day itinerary** — split by your cruise speed and daily hours
- **Lock count per day** — see where the lock-heavy days fall
- **Weather forecast** — 5-day Open-Meteo forecast per stop
- **Michelin restaurants** and **nearby attractions** (castles, museums, wineries, viewpoints) per stop
- **Explore Nearby** — 12 categories of local POIs per town: bike hire, swimming spots, restaurants, local food shops, weekly markets, wineries & distilleries, castles, churches, historic sites, museums, attractions, viewpoints
- **Provisions** (supermarkets, pharmacies, boulangeries) per stop
- **Reverse route** — flip A → B into B → A instantly
- **Save routes** — store named route plans for later
- **GPX export** — download for Navionics, Garmin, or any chartplotter

### ⛵ Vessel Profile
Click **⛵ Profile** to enter your boat's details:

| Field | Used for |
|-------|----------|
| Vessel name | Shown on profile button |
| Air draught | Waterway colour coding + route warnings |
| Water draught | Waterway colour coding + route warnings |
| Length | Waterway colour coding |
| Beam | Waterway colour coding |
| Cruise speed | Day-by-day itinerary calculation |
| Daily hours | Day-by-day itinerary calculation |

**Waterway colour coding** (when profile is set):
- 🔵 Blue — vessel fits, all dimensions clear
- 🔴 Red — cannot navigate (e.g. air draught limit exceeded)
- 🟡 Amber — marginal, within 10% of a limit
- ⬜ Grey — no VNF data available for this waterway

You can also set draft and air draught directly in the controls bar — both inputs stay in sync with your profile.

### ✏️ Edit Locations
Click **✏️ Edit** to enter Edit Locations mode:
- Click any marker to select it (orange ring appears)
- Click the map to move it to the correct position
- Corrections are saved to your browser and applied on every reload
- Export corrections as JSON to share with others

### 🔍 Search
Search bar finds towns, locks, haltes, and ports instantly.

---

## Data Sources

| Data | Source |
|------|--------|
| Route information (distances, locks, vessel constraints) | *Through the French Canals*, David Jefferson, 14th ed. |
| Waypoints (towns, locks, haltes, ports) | Manually compiled from the book |
| Waterway geometry | OpenStreetMap via Overpass API (3,500 features after dedup + cleanup) |
| VNF dimension limits | Voies Navigables de France official publications |
| Base map (IGN) | [IGN Géoportail](https://data.geopf.fr) |
| Nautical marks | [OpenSeaMap](https://www.openseamap.org) |
| Weather | [Open-Meteo](https://open-meteo.com) (free, no API key) |
| Michelin restaurants | [ngshiheng/michelin-my-maps](https://github.com/ngshiheng/michelin-my-maps) — updated annually via `fill_michelin.py` |

---

## Technical Architecture

Two-file architecture: the app HTML + a separate GeoJSON for waterway geometry.

```
french_canals_map.html   (~7,700 lines — HTML + CSS + JS + all data)
waterways.geojson        (~8.5 MB — 3,500 OSM waterway features, deduplicated and cleaned)
```

**No build tools, no npm.** Edit and refresh.

**Maintenance scripts:**
- `fill_waterways.py` — re-fetch canal geometry from OpenStreetMap
- `fill_michelin.py` — update Michelin restaurant data (runs automatically via GitHub Action every February)

**Libraries (CDN):**
- [Leaflet.js 1.9.4](https://leafletjs.com) — map rendering
- [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) — marker clustering

**Persistence:** All user data (notes, vessel profile, saved routes, location corrections) stored in `localStorage` — survives browser restarts, never leaves your device.

---

## Route Coverage

44 named routes across 9 sections of Jefferson's book:

| Section | Area | Routes |
|---------|------|--------|
| 1 | Seine (Le Havre–Paris) | 1 |
| 2 | Bassin de la Seine | 2–9 |
| 3 | Centre-Est (Bourbonnais) | 10–12 |
| 4 | Rhône–Saône | 13–18 |
| 5 | Northern France | 19–31 |
| 6 | Nord-Est (Ardennes, Meuse, Lorraine) | 32–37 |
| 7 | Rhine / Alsace | 38–40 |
| 8 | Brittany & Atlantic | 41–48 |
| 9 | Entre Deux Mers (South-West) | 49–52 |

---

## Known Limitations

- **Brittany network is isolated** — Routes 41–48 have no inland waterway connection to the rest of France. Cross-network planning requires going to sea.
- **Chômages are seed data** — VNF has no public API; closures are hand-curated and may be incomplete or outdated. Always verify at [vnf.fr](https://www.vnf.fr).
- **Multi-route distances are approximate** — the planner uses full route distances for connecting segments where only part is traversed.
- **Waterway overlay uses OSM names** — vessel navigability colouring only works for waterways whose OSM `name` tag matches an entry in the `WATERWAY_CONSTRAINTS` table.

---

## Acknowledgements

Based on *Through the French Canals* by David Jefferson, published by Adlard Coles Nautical. All route data, distances, lock counts, and vessel constraints are derived from the 14th edition.

Waterway geometry © OpenStreetMap contributors (ODbL).
