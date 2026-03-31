# Lock Opening Hours & Vigicrues Water Levels — Design Spec
*Date: 2026-03-31*

---

## Overview

Two partially-implemented features are being completed:

1. **Lock Opening Hours** — populate the existing CSS/HTML stub with real VNF schedule data, grouped by VNF administrative region (6 groups covering 44 routes).
2. **Vigicrues Water Levels** — replace the static link with a live water-height fetch from the Hub'Eau Hydrometry API, shown inline in the sidebar for the 11 river routes already flagged in `VIGICRUES_ROUTES`.

Both features are display-only additions to `openSidebar()`. No new layers, no new localStorage keys, no structural changes.

---

## Feature 1 — Lock Opening Hours

### Season detection

```js
function _currentLockSeason()
// Returns: 'peak' | 'shoulder' | 'offseason'
// peak:      June–August      (months 5–7)
// shoulder:  April–May, Sep–Oct (months 3–4, 8–9)
// offseason: November–March   (months 10–2)
```

### Regional groups

VNF publishes lock schedules by administrative region. Routes are assigned to one of five groups:

| Group | Route numbers | VNF region |
|-------|--------------|------------|
| `seine` | 1–9 | DI Bassin de la Seine |
| `burgundy` | 10–12, 14–15 | DI Bourgogne-Franche-Comté |
| `rhone` | 13, 16–18 | DI Rhône-Saône |
| `north` | 19–31 | DI Nord-Pas-de-Calais |
| `northeast` | 32–40 | DI Nord-Est (Lorraine / Alsace) |
| `atlantic` | 41–52 | DI Sud-Ouest + Bretagne |

### Hours per group

| Group | Peak (Jun–Aug) | Shoulder (Apr–May, Sep–Oct) | Off-season (Nov–Mar) |
|-------|---------------|----------------------------|----------------------|
| seine | 7:30–19:30 | 8:00–18:30 | 9:00–17:00 |
| burgundy | 7:30–19:30 | 8:00–18:30 | 9:00–12:30 + 13:30–17:30 |
| rhone | 7:00–19:30 | 7:30–18:30 | 9:00–17:00 |
| north | 7:00–19:00 | 8:00–18:30 | 9:00–16:30 |
| northeast | 7:30–19:30 | 8:00–18:30 | 8:30–17:00 |
| atlantic | 8:00–19:30 | 8:30–18:30 | 9:00–17:00 |

### Data structures

```js
// Lookup: route number → group name
const ROUTE_LOCK_GROUP = {
  1:'seine', 2:'seine', ..., 9:'seine',
  10:'burgundy', 11:'burgundy', 12:'burgundy', 13:'rhone',
  14:'burgundy', 15:'burgundy', 16:'rhone', 17:'rhone', 18:'rhone',
  19:'north', ..., 31:'north',
  32:'northeast', ..., 40:'northeast',
  41:'atlantic', ..., 52:'atlantic',
};

// Hours per group — season sub-object matches the h.{season} access pattern
// already used in the existing buildLockHoursHTML()
const LOCK_HOURS_BY_GROUP = {
  seine:    { season:'VNF Bassin de la Seine',   peak:'7:30–19:30', shoulder:'8:00–18:30', offseason:'9:00–17:00' },
  burgundy: { season:'VNF Bourgogne',            peak:'7:30–19:30', shoulder:'8:00–18:30', offseason:'9:00–12:30 · 13:30–17:30' },
  rhone:    { season:'VNF Rhône-Saône',          peak:'7:00–19:30', shoulder:'7:30–18:30', offseason:'9:00–17:00' },
  north:    { season:'VNF Nord',                 peak:'7:00–19:00', shoulder:'8:00–18:30', offseason:'9:00–16:30' },
  northeast:{ season:'VNF Nord-Est',             peak:'7:30–19:30', shoulder:'8:00–18:30', offseason:'8:30–17:00' },
  atlantic: { season:'VNF Sud-Ouest / Bretagne', peak:'8:00–19:30', shoulder:'8:30–18:30', offseason:'9:00–17:00' },
};
```

### `getLockHours(routeNum)`

```js
function getLockHours(routeNum) {
  const group = ROUTE_LOCK_GROUP[routeNum];
  return group ? LOCK_HOURS_BY_GROUP[group] : null;
}
```

Returns `null` for unmapped routes. `buildLockHoursHTML()` must guard: `if (!h) return '';` at the top of the function — render nothing rather than crash.

### Integration point

`buildLockHoursHTML(routeNum)` already exists and is already called in `openSidebar()`. It calls `getLockHours()` and `_currentLockSeason()` — both of which are currently missing (causing a ReferenceError for any lock sidebar). Adding the two new functions and the two data tables is the complete fix.

---

## Feature 2 — Vigicrues Water Levels

### API

**Hub'Eau Hydrometry API** (free, no key, CORS-open):
```
GET https://hubeau.eaufrance.fr/api/v1/hydrometrie/observations_tr
    ?code_entite={stationCode}
    &grandeur_hydro=H
    &size=1
    &sort=desc
    &fields=resultat_obs,date_obs
```
- `resultat_obs`: water height in **mm** → divide by 10 for cm
- `date_obs`: ISO datetime of observation
- No API key required. Free tier allows ~10 req/s.

### Station mapping

Station codes must be verified against the Hub'Eau station catalogue
(`https://hubeau.eaufrance.fr/api/v1/hydrometrie/referentiel/stations`) during implementation — the codes below are representative examples based on known VNF stations and should be confirmed before going live.

```js
// Maps route number → { hubeau: stationCode, label: 'River at Location',
//                        url: station page on vigicrues.gouv.fr }
const VIGICRUES_STATIONS = {
  1:  { hubeau:'H--0615050', label:'Seine at Alfortville',      url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=H--0615050' },
  6:  { hubeau:'H--0674010', label:'Yonne at Sens',             url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=H--0674010' },
  13: { hubeau:'V-----00',   label:'Rhône at Lyon (Perrache)', url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=V-----00' },
  16: { hubeau:'V217401001', label:'Saône at Mâcon',            url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=V217401001' },
  20: { hubeau:'A034001001', label:'Oise at Verberie',          url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=A034001001' },
  24: { hubeau:'A072001001', label:'Somme at Abbeville',        url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=A072001001' },
  25: { hubeau:'A034001002', label:'Sambre at Maubeuge',        url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=A034001002' },
  26: { hubeau:'A046001001', label:'Escaut at Cambrai',         url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=A046001001' },
  30: { hubeau:'A072001002', label:'Scarpe at Douai',           url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=A072001002' },
  36: { hubeau:'M100001001', label:'Moselle at Metz',           url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=M100001001' },
  37: { hubeau:'M100002001', label:'Meuse at Verdun',           url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=M100002001' },
};
```

### `fetchVigicruesHTML(wid, routeNum)`

Async function. Called from `openSidebar()` after the sidebar is already rendered.

1. Look up station in `VIGICRUES_STATIONS[routeNum]`. If none → return (static link already rendered, no change).
2. Target element: `document.getElementById('vigicrues-live-' + wid)` — a placeholder div injected by `openSidebar()`.
3. Fetch Hub'Eau. On success: update div with height (cm) + observation time + link.
4. On fetch error or empty data: update div with "⚠ Level unavailable" + link.
5. Response is cached in `_vigicruesCache[routeNum]` (plain object, keyed by route). Cache TTL: 10 minutes (compare `Date.now()` on hit).

### Rendered output (success state)

```html
<div class="vigicrues-card">
  <div class="vigicrues-live-row">
    🌊 <strong>153 cm</strong>
    <span class="vigicrues-updated">updated 10:00</span>
  </div>
  <div style="font-size:11px;color:#c0d0e0;margin-bottom:4px">Seine at Alfortville</div>
  <a href="https://www.vigicrues.gouv.fr/..." target="_blank">📋 View station on Vigicrues →</a>
  <div class="vigicrues-note">Real-time data: Hub'Eau / VNF — always verify before navigating</div>
</div>
```

### Integration point

In `openSidebar()`, replace the existing static Vigicrues card template literal with:
1. A placeholder div `<div id="vigicrues-live-{w.id}">⏳ Loading water level…</div>` (still wrapped in the `VIGICRUES_ROUTES.has(w.route)` guard).
2. A call to `fetchVigicruesHTML(w.id, w.route)` immediately after `place-info.innerHTML` is set.

### New CSS needed

One additional rule for the live data row:
```css
.vigicrues-live-row { font-size:14px; font-weight:600; color:#7ad4ef; margin-bottom:4px; display:flex; align-items:center; gap:8px; }
.vigicrues-updated  { font-size:10px; color:#5a7a8a; font-weight:400; }
```

---

## What is NOT changing

- No new localStorage keys
- No new map layers
- No changes to mooring sidebar, route planner, or any other panel
- `VIGICRUES_ROUTES` set remains as-is (used as the display guard)
- All existing CSS classes for `.lock-hours-*` and `.vigicrues-card` remain unchanged

---

## Files changed

- `french_canals_map.html` only — all additions inline
