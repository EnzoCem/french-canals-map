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
All marker layers are independently toggleable and clustered for performance:

| Layer | Description |
|-------|-------------|
| 🏘 Towns | Major halting towns with sidebar info (distances, locks, services) |
| 🔒 Locks | Individual lock positions with elevation and PK data |
| ⚓ Haltes | Official VNF mooring haltes |
| ⛵ Ports | Marinas and commercial ports |
| 📌 My Notes | User-created personal notes pinned to the map |

### Route Planner
Click **📍 Plan Route** in the top bar to open the route planner panel, which docks to the left side of the map so the route is always visible:

- Select any two towns from dropdowns grouped by the book's 9 sections
- BFS pathfinding through a graph of 53 waterway junction connections
- Results show total distance (~km), lock count, estimated travel days, and number of route segments
- **Vessel constraints** — automatically finds the bottleneck route and shows the minimum air draught and water draught across the whole journey
- Per-segment breakdown: route name, section, from/to cities, distance, locks, vessel limits
- ⇅ Swap button to reverse the journey direction
- Direct links to VNF route calculator and avis à la batellerie

### Route Highlight on Map
After calculating a route, the matching canals and rivers are highlighted directly on the map:

- All other waterways fade to near-invisible so the route stands out clearly
- The planned waterways glow with a **pulsing gold halo** and bright coloured line
- Each waterway keeps its own colour (Rhône in orange, Canal de Bourgogne in purple, etc.) so you can still tell them apart
- The map **auto-zooms and pans** to fit the entire highlighted route
- The route planner panel **auto-collapses** to a thin title bar after calculating, so the full map is visible
- Click the title bar (▼/▲) to expand or collapse the panel at any time
- **🗺 Highlight** and **✕ Clear** buttons toggle the highlight without recalculating
- Closing the panel clears the highlight and restores all waterways to full colour

### VNF Integration
Every town sidebar and waterway panel includes:
- **Plan route on VNF calculator** — opens the official VNF online tool
- **Check VNF notices** — links to *avis à la batellerie* (navigation notices)
- **Regional VNF territory page** — territory inferred from the book section (Bassin de la Seine, Rhône-Saône, Sud-Ouest, etc.)

### My Notes
- Click anywhere on the map (away from existing markers) to drop a note pin
- Add a title and body text
- Notes persist for the browser session

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

37 waterways with real OSM geometry (4,622 features):

**Rivers:** Rhône · Saône · Seine · Marne · Yonne · Oise · Moselle · Rhine · Loire · Lys · Mayenne · Sarthe · Charente · Aa

**Canals:** Canal du Midi · Canal de Garonne · Canal de Bourgogne · Canal du Nivernais · Canal de Nantes à Brest · Canal latéral à la Loire · Canal latéral à la Marne · Canal latéral à l'Aisne · Canal de la Marne au Rhin · Canal des Vosges · Canal du Rhône au Rhin · Canal de Saint-Quentin · Canal du Nord · Canal de la Meuse · Canal de la Robine · Canal de Briare · Canal du Centre · Canal du Rhône à Sète · Canal d'Ille-et-Rance · Canal entre Champagne et Bourgogne · Canal de l'Oise à l'Aisne · Canal des Ardennes · Canal de Calais · Canals of Paris · Liaison Dunkerque–Escaut

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

Everything is embedded in a single `french_canals_map.html` file (~2.1 MB):

```
french_canals_map.html
├── <style>          CSS — dark nautical theme + route highlight animations
├── <body>
│   ├── #controls    Section filter + layer toggles + Plan Route button
│   ├── #map         Leaflet.js map container
│   ├── #sidebar     Detail panel (towns, waterway dims, VNF links)
│   └── #route-planner-panel  Route planner (docked left, collapsible)
└── <script>
    ├── const ROUTES[]              52 route records (section, km, locks, constraints)
    ├── const WAYPOINTS[]           78 waypoints (towns + locks with PK values)
    ├── const MOORING[]             Haltes and ports
    ├── const WATERWAY_GEOJSON      4,622 GeoJSON features (embedded)
    ├── const WATERWAY_COLORS       Colour map: waterway name → hex colour
    ├── const ROUTE_CONNECTIONS[]   53 junction pairs for BFS pathfinding
    ├── const ROUTE_TO_WATERWAYS    Maps route numbers → GeoJSON waterway names
    ├── buildWaterwayOverlay()
    ├── buildMarkers() / buildMooringMarkers()
    ├── toggleLayer() / sectionFilter()
    ├── openSidebar() / showWaterwayDims()
    ├── vnfLinksHTML()
    ├── findRoutePath() / planRoute()
    ├── calculateRoute() / renderRouteResults()
    ├── highlightRouteOnMap() / clearRouteHighlight() / restoreWaterwayStyles()
    ├── toggleCollapseRoutePlanner() / expandRoutePlanner()
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
- Click **🌊 Canals** to toggle the waterway overlay on/off
- Use the layer control (top-right corner, ☰) to switch base maps or add OpenSeaMap
- Open **📍 Plan Route**, select two towns, and hit **⚓ Calculate Route** — the route highlights on the map and the panel collapses so you can see it
- Click the panel title bar to expand the full results; click again to collapse
- Click anywhere on the map (away from markers) to add a personal note

---

## Changelog

### March 2026
- **Extended waterway coverage** — 14 previously-missing waterways added (Canal latéral à l'Aisne, Canal de l'Oise à l'Aisne, Canals of Paris, Liaison Dunkerque–Escaut, Canal de Calais, River Aa, River Lys, Canal des Ardennes, River Moselle, Rhine, Loire, Mayenne, Sarthe, Charente); total features 3,416 → 4,622 across 37 waterways
- **Map-click endpoint selection** — click any waterway or town to set From/To route endpoints directly on the map; floating nudge bar shows selected endpoints and triggers route calculation
- **Route highlight zoom fix** — highlight corridor now clips to the journey's geographic extent (not the full waterway); map fits to the From/To pins rather than the entire GeoJSON
- **Route highlight on map** — calculated routes glow on the map with a pulsing gold halo; non-route waterways fade
- **Route planner panel repositioned** — docked to left side of screen (was centered overlay); auto-collapses after calculating so the map is fully visible; collapsible title bar
- **Route planner** — BFS pathfinding with vessel constraint checking, per-segment breakdown, VNF links
- **VNF integration** — route calculator, notices, and regional territory links in all sidebars
- **Real waterway geometry** — OSM segments via Overpass API, replacing straight-line route polylines
- **IGN France base map** + tile layer switcher + OpenSeaMap overlay
- Initial release: map, markers, section filter, My Notes

---

## Known Limitations

- **Brittany network is isolated** — Routes 41–48 have no inland waterway connection to the rest of France's canal network. Cross-network planning from Brittany requires going to sea.
- **Multi-route distances are approximate** — the route planner uses full route distances for connecting segments where only part of the route is traversed.
- **VNF has no public API** — all VNF links open the VNF website in a new tab; live lock status and booking are not available programmatically.
- **Waterway geometry gaps** — a few routes (upper Seine, Canal de Garonne, Canal de la Somme) had incomplete OSM data at time of generation and use simplified or absent geometry.
- **River Moselle sparse** — only 9 OSM way segments found for the Moselle; the route highlight will show partial coverage.

---

## Acknowledgements

Based on *Through the French Canals* by David Jefferson, published by Adlard Coles Nautical. All route data, distances, lock counts, and vessel constraints are derived from the 14th edition.

Waterway geometry © OpenStreetMap contributors (ODbL).
