# Feature Backlog

Planned and proposed enhancements for the French Canals Interactive Map.

---

## ✅ Completed

| Feature | Description |
|---------|-------------|
| Interactive map | Leaflet.js map with dark nautical theme |
| IGN France base map | Best-quality French topo map as default layer |
| Tile layer switcher | IGN France, OpenStreetMap, CartoDB, ESRI Topo |
| OpenSeaMap overlay | Nautical marks as a toggleable overlay |
| Real waterway geometry | 3,416 OSM canal/river segments covering 23 waterways |
| Town markers | 78 waypoints with detail sidebars |
| Lock markers | Individual lock positions with PK data |
| Haltes & Ports | VNF haltes and marinas as separate toggleable layers |
| Section filter | Filter map to any of Jefferson's 9 book sections |
| My Notes | User pins with title/body text |
| VNF integration | Links to VNF route calculator, notices, and regional pages |
| Route planner | BFS pathfinding with distance, locks, vessel constraints, estimated days |

---

## 🔵 High Priority — Most Impact for Trip Planning

### 1. Day-by-Day Itinerary Builder
**What:** Extend the route planner to split a journey into daily stages.
**How:** Divide total distance by 35 km/day target, find the nearest halte or port at each overnight stop, display a "Day 1 → Day 2 → …" breakdown with overnight locations.
**Value:** The most practically useful feature once actually preparing to cast off.
**Complexity:** Medium — builds on existing route planner data.

### 2. Vessel Profile & Route Filter
**What:** Let the user enter their boat's air draught, water draught, and beam once, then automatically highlight or dim routes based on whether the boat fits.
**How:** Two number inputs stored in `localStorage`. When set, colour-code route buttons green/amber/red and show a warning badge on inaccessible segments in the route planner.
**Value:** Immediately answers "can my boat do this route?" without manual checking.
**Complexity:** Low — the constraint data is already in the `ROUTES` array.

### 3. GPX Export
**What:** Export the planned route as a `.gpx` file.
**How:** Build a GPX XML string from the waypoints on the planned route, create a `Blob`, trigger a browser download. Works entirely in JavaScript.
**Value:** Loads directly into Navionics, iNavX, Garmin, or Raymarine chartplotters.
**Complexity:** Low.

### 4. Save & Restore Trips
**What:** Persist planned routes, vessel profile, and notes between browser sessions.
**How:** Serialize to `localStorage` on change; restore on page load.
**Value:** Don't lose work when closing the tab.
**Complexity:** Low.

---

## 🟡 Medium Priority — Nice to Have

### 5. Trip Cost Estimator
**What:** Estimate VNF lock tolls based on boat length.
**How:** One number input (boat length in metres). Lock fee ≈ €0.85–1.20/metre/lock. Show estimated toll cost in the route planner results alongside distance and locks.
**Value:** Useful for trip budgeting.
**Complexity:** Low.

### 6. Share Route Link
**What:** Encode From/To waypoint IDs and vessel settings into the URL hash so a specific planned route can be bookmarked or shared.
**How:** `window.location.hash = '#from=w001&to=w121&height=3.5&draught=1.4'`. Read on page load, auto-populate and calculate.
**Value:** Share a planned route with crew or other boaters.
**Complexity:** Low.

### 7. Printable Route Card
**What:** A clean print view of a planned route — segment table, lock count, vessel constraints, estimated days, VNF links — formatted for A4.
**How:** `@media print` CSS hides the map and shows a formatted summary. `window.print()` opens the print dialog.
**Value:** Physical reference to take on the boat.
**Complexity:** Low–Medium.

### 8. Tunnel Details
**What:** Add specific info for major canal tunnels — length, procedure, convoy times, advance booking requirements.
**Key tunnels:**
  - Riqueval (Canal de Saint-Quentin) — 5,670 m, convoy required, advance booking
  - Mauvages (Canal de la Marne au Rhin) — 4,877 m, convoy, tow service
  - Foug (Canal de la Marne au Rhin) — 866 m
  - Souterrain de Pouilly (Canal de Bourgogne) — 3,333 m, electric tow
  - Souterrain de Saint-Albin (Canal du Nivernais) — 758 m
**How:** New `TUNNELS` array → map markers with a distinct icon → sidebar with procedure details.
**Value:** Tunnels are one of the most practically important pieces of information for route planning.
**Complexity:** Medium — needs data research and a new marker layer.

### 9. Seasonal Closures (Chômage)
**What:** Show typical annual maintenance closure periods for each canal.
**How:** Static data object mapping route numbers to closure months (most canals close for 2–6 weeks in winter). Display as a badge on route cards and a warning in the route planner if the planned travel overlaps.
**Value:** Prevents planning a route that is closed.
**Complexity:** Low — static data only.

### 10. Bridge Height Markers
**What:** Mark the lowest bridge or fixed obstacle on each route — the real limiting factor for air draught, often a single structure mid-route rather than the route average.
**How:** New data in `ROUTES` or a `BRIDGES` array with position and measured clearance. Map markers and route planner warning if vessel exceeds the bridge clearance.
**Value:** More accurate than using the route average air draught.
**Complexity:** Medium — requires data research.

---

## 🟠 Lower Priority — Future Ideas

### 11. Weather Along Route
**What:** Show current and 5-day forecast weather at key points along a planned route.
**How:** Requires a call to a weather API (OpenWeatherMap free tier, or Météo-France). Only feature on this list that needs an external API key.
**Complexity:** Medium — needs API key and async fetch.

### 12. Water Level / Lock Status
**What:** Live lock closures and water levels from VNF.
**Note:** VNF has no public API. This would require scraping the VNF avis à la batellerie page, which is fragile and may not be permissible.
**Complexity:** High / uncertain.

### 13. Elevation Profile
**What:** Show a cross-section elevation chart along a planned route — useful for understanding the summit level and how many locks climb vs. descend.
**How:** Use stored lock elevation data (partially in `WAYPOINTS`) to build an SVG chart.
**Complexity:** Medium.

### 14. Offline Tile Caching
**What:** Cache map tiles locally using a Service Worker so the map works fully offline on the boat.
**Complexity:** High — Service Workers add significant complexity and browser compatibility concerns.

### 15. Mobile / Touch Optimisation
**What:** Improve the UI for phone and tablet use — larger touch targets, collapsible controls, swipe-friendly sidebar.
**Complexity:** Medium.

---

## 🛠 Technical Debt

| Item | Description |
|------|-------------|
| PK data gaps | Several routes (e.g. Route 3, 6, 7, 9, 17, 20, 21) have few or no intermediate waypoints — limits route planner precision for those segments |
| Waterway geometry gaps | Upper Seine, Canal de Garonne, Somme have incomplete OSM geometry — Overpass API returned errors at time of generation |
| Lock count estimates | Multi-route planner uses proportional estimates for partial segments — would be more accurate with per-waypoint lock counts |
| File size | At ~1.5 MB the HTML is large; the GeoJSON could be lazy-loaded to improve initial load time |

---

*Last updated: March 2026*
