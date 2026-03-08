# 🚢 French Canals Interactive Map

An interactive, self-contained HTML map for planning canal boat cruises through France, based on **David Jefferson's** *Through the French Canals* (14th edition).

Open `french_canals_map.html` in any modern browser — no server, no installation, no internet required.

---

## Features

### Map & Navigation
- **IGN France base map** (recommended) — shows towpaths, lock buildings, and canal infrastructure in detail. Also switchable to OpenStreetMap, CartoDB Voyager, and ESRI Topo.
- **OpenSeaMap overlay** — nautical marks as a toggleable layer.
- **Real waterway geometry** — 3,416 canal/river segments fetched from OpenStreetMap via Overpass API, covering 23 waterways across France.
- **Section filter** — filter everything on the map to one of the book's 9 geographic sections.

### Points of Interest
All markers are toggleable and clustered for performance:

| Layer | Description |
|-------|-------------|
| 🏘 Towns | Major halting towns with sidebar info (distances, locks, services) |
| 🔒 Locks | Individual lock positions with elevation and PK data |
| ⚓ Haltes | Official VNF mooring haltes |
| ⛵ Ports | Marinas and commercial ports |
| 📌 My Notes | User-created personal notes pinned to the map |

### Route Planner
Click **📍 Plan Route** in the top bar to open the route planner:

- Select any two towns from dropdowns (grouped by the book's 9 sections)
- BFS pathfinding through a graph of 53 waterway junction connections
- Results show total distance (~km), lock count, estimated travel days, and number of route segments
- **Vessel constraints** — automatically finds the bottleneck route and shows the minimum air draught and water draught across the whole journey
- Per-segment breakdown: route name, section, from/to cities, distance, locks, vessel limits
- ⇅ Swap button to reverse the journey
- Direct links to VNF route calculator and avis à la batellerie

### VNF Integration
Every town sidebar and waterway panel includes:
- **Plan route on VNF calculator** — opens the official VNF online tool
- **Check VNF notices** — links to *avis à la batellerie* (navigation notices)
- **Regional VNF territory page** — territory inferred from the book section (Bassin de la Seine, Rhône-Saône, Sud-Ouest, etc.)

### My Notes
- Click anywhere on the map to drop a note pin
- Add a title and body text
- Notes persist in the browser session

---

## Data Sources

| Data | Source |
|------|--------|
| Route information (distances, locks, vessel constraints) | *Through the French Canals*, David Jefferson, 14th ed. |
| Waypoints (towns, locks, haltes, ports) | Manually compiled from the book |
| Waterway geometry (GeoJSON) | OpenStreetMap via [Overpass API](https://overpass-api.de) |
| Base map | [IGN France WMTS](https://data.geopf.fr) (GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2) |
| Nautical marks | [OpenSeaMap](https://www.openseamap.org) |
| VNF links | [Voies Navigables de France](https://www.vnf.fr) |

---

## Waterways Covered

23 waterways with real OSM geometry (3,416 features):

**Rivers:** Rhône · Saône · Seine · Marne · Yonne · Oise · Moselle

**Canals:** Canal du Midi · Canal de Bourgogne · Canal du Nivernais · Canal de Nantes à Brest · Canal latéral à la Loire · Canal latéral à la Marne · Canal de la Marne au Rhin · Canal des Vosges · Canal du Rhône au Rhin · Canal de Saint-Quentin · Canal du Nord · Canal de la Meuse · Canal de la Robine · Canal de Briare · Canal du Centre · Canal du Rhône à Sète · Canal d'Ille-et-Rance

---

## Route Coverage

52 named routes across 9 sections of Jefferson's book:

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

## Technical Architecture

Everything is embedded in a single `french_canals_map.html` file (~1.5 MB):

```
french_canals_map.html
├── <style>          CSS — dark nautical theme
├── <body>
│   ├── #controls    Section filter + layer toggles + Plan Route button
│   ├── #map         Leaflet.js map container
│   ├── #sidebar     Detail panel (towns, waterway dims, VNF links)
│   └── #route-planner-panel  Route planner UI
└── <script>
    ├── const ROUTES[]        52 route records (section, km, locks, constraints)
    ├── const WAYPOINTS[]     78 waypoints (towns + locks with PK values)
    ├── const MOORING[]       Haltes and ports
    ├── const WATERWAY_GEOJSON  3,416 GeoJSON features (1.37 MB embedded)
    ├── const ROUTE_CONNECTIONS[]  53 junction pairs for BFS pathfinding
    ├── buildWaterwayOverlay()
    ├── buildMarkers() / buildMooringMarkers()
    ├── toggleLayer() / sectionFilter()
    ├── openSidebar() / showWaterwayDims()
    ├── vnfLinksHTML()
    ├── findRoutePath() / planRoute()
    ├── calculateRoute() / renderRouteResults()
    └── init()
```

**Libraries used (CDN):**
- [Leaflet.js 1.9.4](https://leafletjs.com) — map rendering
- [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster) — marker clustering

---

## How to Use

1. Download `french_canals_map.html`
2. Open it in Chrome, Firefox, Edge, or Safari
3. No server needed — works completely offline once loaded

### Tips
- Use the **Section** dropdown to focus on one area of France
- Click any town marker to open its detail sidebar
- Click the **🌊 Canals** button to toggle the waterway overlay on/off
- Use the layer control (top-right corner, ☰) to switch base maps or add OpenSeaMap
- Use **📍 Plan Route** to calculate a multi-route journey with vessel constraint checking
- Click anywhere on the map (away from markers) to add a personal note

---

## Known Limitations

- **Brittany network is isolated** — Routes 41–48 have no inland waterway connection to the rest of France's canal network. Cross-network planning from Brittany requires going to sea.
- **Multi-route distances are approximate** — the route planner uses full route distances for connecting segments where only part of the route is traversed.
- **VNF has no public API** — all VNF links open the VNF website in a new tab; live lock status and booking are not available programmatically.
- **Waterway geometry gaps** — a few routes (upper Seine, Canal de Garonne, Somme) had incomplete OSM data at time of generation and use simplified geometry.

---

## Acknowledgements

Based on *Through the French Canals* by David Jefferson, published by Adlard Coles Nautical. All route data, distances, lock counts, and vessel constraints are derived from the 14th edition.

Waterway geometry © OpenStreetMap contributors (ODbL).
