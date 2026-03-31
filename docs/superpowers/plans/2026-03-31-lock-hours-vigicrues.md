# Lock Opening Hours & Vigicrues Water Levels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sparse lock-hours table with full VNF regional data, and replace the static Vigicrues link with a live Hub'Eau water-height fetch.

**Architecture:** Both changes are display-only additions to `openSidebar()` in `french_canals_map.html`. Task 1 replaces the existing `LOCK_HOURS` sparse table with two new lookup tables (`ROUTE_LOCK_GROUP` + `LOCK_HOURS_BY_GROUP`) and updates `getLockHours()`. Task 2 adds `VIGICRUES_STATIONS`, a cache object, and an async `fetchVigicruesHTML()` that updates a placeholder div injected by `openSidebar()`.

**Tech Stack:** Vanilla JS (ES5-compatible, no modules), Leaflet 1.9.4, Hub'Eau Hydrometry API (free, no key, CORS-open).

---

## Task 1: Replace sparse LOCK_HOURS with full regional data

**Files:**
- Modify: `french_canals_map.html:5955-5966` (LOCK_HOURS + getLockHours)
- Modify: `french_canals_map.html:5975` (buildLockHoursHTML null guard)

### Background

The current code (lines 5952–5966) has:
```js
var LOCK_HOURS = {
  'default': { peak: '7:30–19:30', shoulder: '8:00–18:00', offseason: '8:30–17:00', season: 'Apr–Nov' },
  11: { ... }, 12: { ... }, 16: { ... }, 35: { ... }, 49: { ... }
};
function getLockHours(routeNum) {
  return LOCK_HOURS[routeNum] || LOCK_HOURS['default'];
}
```

This will be replaced entirely. The design specifies 6 VNF administrative regions covering all 44 routes.

- [ ] **Step 1: Open the file and locate the replacement target**

Read `french_canals_map.html` lines 5952–5966 to confirm the exact text before editing.

Expected content (confirm before replacing):
```
// ============================================================
//  FEATURE 6: Lock Opening Hours data
// ============================================================
var LOCK_HOURS = {
  'default': { peak: '7:30–19:30', shoulder: '8:00–18:00', offseason: '8:30–17:00', season: 'Apr–Nov' },
  11: ...
  ...
};

function getLockHours(routeNum) {
  return LOCK_HOURS[routeNum] || LOCK_HOURS['default'];
}
```

- [ ] **Step 2: Replace the data section (LOCK_HOURS → ROUTE_LOCK_GROUP + LOCK_HOURS_BY_GROUP + getLockHours)**

In `french_canals_map.html`, replace the entire block from `// FEATURE 6: Lock Opening Hours data` through the closing `}` of `getLockHours()` with:

```js
// ============================================================
//  FEATURE 6: Lock Opening Hours data
// ============================================================
// Route number → VNF administrative region
var ROUTE_LOCK_GROUP = {
  1:'seine', 2:'seine', 3:'seine', 4:'seine', 5:'seine', 6:'seine', 7:'seine', 8:'seine', 9:'seine',
  10:'burgundy', 11:'burgundy', 12:'burgundy', 13:'rhone',
  14:'burgundy', 15:'burgundy', 16:'rhone', 17:'rhone', 18:'rhone',
  19:'north', 20:'north', 21:'north', 22:'north', 23:'north', 24:'north', 25:'north', 26:'north',
  27:'north', 28:'north', 29:'north', 30:'north', 31:'north',
  32:'northeast', 33:'northeast', 34:'northeast', 35:'northeast', 36:'northeast',
  37:'northeast', 38:'northeast', 39:'northeast', 40:'northeast',
  41:'atlantic', 42:'atlantic', 43:'atlantic', 44:'atlantic', 45:'atlantic', 46:'atlantic',
  47:'atlantic', 48:'atlantic', 49:'atlantic', 50:'atlantic', 51:'atlantic', 52:'atlantic'
};

// Hours by region and season
var LOCK_HOURS_BY_GROUP = {
  seine:    { label:'VNF Bassin de la Seine',   peak:'7:30–19:30', shoulder:'8:00–18:30', offseason:'9:00–17:00' },
  burgundy: { label:'VNF Bourgogne',            peak:'7:30–19:30', shoulder:'8:00–18:30', offseason:'9:00–12:30 · 13:30–17:30' },
  rhone:    { label:'VNF Rhône-Saône',          peak:'7:00–19:30', shoulder:'7:30–18:30', offseason:'9:00–17:00' },
  north:    { label:'VNF Nord',                 peak:'7:00–19:00', shoulder:'8:00–18:30', offseason:'9:00–16:30' },
  northeast:{ label:'VNF Nord-Est',             peak:'7:30–19:30', shoulder:'8:00–18:30', offseason:'8:30–17:00' },
  atlantic: { label:'VNF Sud-Ouest / Bretagne', peak:'8:00–19:30', shoulder:'8:30–18:30', offseason:'9:00–17:00' }
};

function getLockHours(routeNum) {
  var group = ROUTE_LOCK_GROUP[routeNum];
  return group ? LOCK_HOURS_BY_GROUP[group] : null;
}
```

- [ ] **Step 3: Add null guard + region label to buildLockHoursHTML()**

Read `french_canals_map.html` lines 5975–5990 to see the current `buildLockHoursHTML` body.

Current first lines:
```js
function buildLockHoursHTML(routeNum) {
  var h    = getLockHours(routeNum);
  var season = _currentLockSeason();
  var seasonLabels = { peak: 'Peak (Jun–Aug)', shoulder: 'Shoulder (Apr–May, Sep–Oct)', offseason: 'Off-season (Nov–Mar)' };
  var html = '<div class="lock-hours-block">' +
    '<div class="lock-hours-title">🕐 Lock Opening Hours</div>' +
    '<div class="lock-hours-season"><strong>Season:</strong> ' + h.season + '</div>' +
```

Replace the full `buildLockHoursHTML` function with:

```js
function buildLockHoursHTML(routeNum) {
  var h = getLockHours(routeNum);
  if (!h) return '';
  var season = _currentLockSeason();
  var seasonLabels = { peak: 'Peak (Jun–Aug)', shoulder: 'Shoulder (Apr–May, Sep–Oct)', offseason: 'Off-season (Nov–Mar)' };
  var html = '<div class="lock-hours-block">' +
    '<div class="lock-hours-title">🕐 Lock Opening Hours</div>' +
    '<div class="lock-hours-season" style="color:#5a8a9a;font-size:11px;margin-bottom:4px">' + h.label + '</div>' +
    '<div class="lock-hours-season"><strong>Peak hours:</strong> <strong>' + h.peak + '</strong></div>' +
    '<div class="lock-hours-season"><strong>Shoulder hours:</strong> ' + h.shoulder + '</div>' +
    '<div class="lock-hours-season"><strong>Off-season hours:</strong> ' + h.offseason + '</div>' +
    '<div class="lock-hours-season" style="margin-top:4px;color:#f0ad4e">▶ Currently: <strong>' + seasonLabels[season] + '</strong> → <strong>' + h[season] + '</strong></div>' +
    '<div class="lock-hours-vnf"><a href="https://www.vnf.fr/vnf/accueil/les-voies-navigables/informations-pratiques/les-chomages/" target="_blank">📋 VNF Chômages (closures)</a></div>' +
    '<div class="lock-hours-note">Hours subject to change — verify with VNF before travel</div>' +
    '</div>';
  return html;
}
```

Key changes from current:
- Added `if (!h) return '';` guard at top (prevents crash for unmapped routes)
- Removed `h.season` field (replaced with `h.label` showing the VNF region name)
- Added region label line with subdued styling

- [ ] **Step 4: Verify in browser**

Open `http://localhost:8765/french_canals_map.html` (or refresh). Click any lock marker on the map. The sidebar should show:
- "Lock Opening Hours" block with a greyed region label (e.g. "VNF Bassin de la Seine")
- Peak / Shoulder / Off-season hours
- "Currently: Shoulder..." or "Currently: Off-season..." highlight depending on today's month (March = off-season)

Click a lock on a route with no group assignment (should not crash — sidebar just omits the block).

- [ ] **Step 5: Commit**

```bash
git add french_canals_map.html
git commit -m "feat: replace sparse LOCK_HOURS with full VNF regional groups (6 regions, 44 routes)"
```

---

## Task 2: Live Vigicrues water level fetch

**Files:**
- Modify: `french_canals_map.html:1054-1059` (add new CSS rules)
- Modify: `french_canals_map.html:3435-3438` (add VIGICRUES_STATIONS after VIGICRUES_ROUTES)
- Modify: `french_canals_map.html:3562-3566` (replace static card with placeholder div in openSidebar)
- Modify: (add `fetchVigicruesHTML` function near VIGICRUES data — after line 3438)

### Step-by-step

- [ ] **Step 1: Add new CSS for the live data row**

Find the existing CSS block at line ~1054 which contains `.vigicrues-card { ... }`.

Current block ends with:
```css
.rp-vigicrues-strip a { color: #5bc0de; font-size: 12px; display: block; margin: 3px 0; }
```

After that line, add:
```css
.vigicrues-live-row { font-size:14px; font-weight:600; color:#7ad4ef; margin-bottom:4px; display:flex; align-items:center; gap:8px; }
.vigicrues-updated  { font-size:10px; color:#5a7a8a; font-weight:400; }
```

- [ ] **Step 2: Add VIGICRUES_STATIONS and cache object after VIGICRUES_ROUTES**

Current code at line ~3438:
```js
const VIGICRUES_ROUTES = new Set([1, 6, 13, 16, 20, 24, 25, 26, 30, 36, 37]);
```

After that line (before the `// SIDEBAR` comment), insert:

```js
// Hub'Eau station codes for live water height fetch
// Note: station codes are representative — verify against
// https://hubeau.eaufrance.fr/api/v1/hydrometrie/referentiel/stations if data is missing
var VIGICRUES_STATIONS = {
  1:  { hubeau:'H--0615050', label:'Seine at Alfortville',      url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=H--0615050' },
  6:  { hubeau:'H--0674010', label:'Yonne at Sens',             url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=H--0674010' },
  13: { hubeau:'V-----00',   label:'Rhône at Lyon (Perrache)',  url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=V-----00' },
  16: { hubeau:'V217401001', label:'Saône at Mâcon',            url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=V217401001' },
  20: { hubeau:'A034001001', label:'Oise at Verberie',          url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=A034001001' },
  24: { hubeau:'A072001001', label:'Somme at Abbeville',        url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=A072001001' },
  25: { hubeau:'A034001002', label:'Sambre at Maubeuge',        url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=A034001002' },
  26: { hubeau:'A046001001', label:'Escaut at Cambrai',         url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=A046001001' },
  30: { hubeau:'A072001002', label:'Scarpe at Douai',           url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=A072001002' },
  36: { hubeau:'M100001001', label:'Moselle at Metz',           url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=M100001001' },
  37: { hubeau:'M100002001', label:'Meuse at Verdun',           url:'https://www.vigicrues.gouv.fr/niv_station.php?CdStationHydro=M100002001' }
};

// Cache: routeNum → { html: string, ts: Date.now() }
var _vigicruesCache = {};
```

- [ ] **Step 3: Add fetchVigicruesHTML() function**

The function goes immediately after `_vigicruesCache = {};` (still in the Vigicrues data section, before the `// SIDEBAR` comment).

Insert:

```js
async function fetchVigicruesHTML(wid, routeNum) {
  var station = VIGICRUES_STATIONS[routeNum];
  if (!station) return; // no station for this route — static link already rendered
  var el = document.getElementById('vigicrues-live-' + wid);
  if (!el) return;

  // Cache hit (10-minute TTL)
  var cached = _vigicruesCache[routeNum];
  if (cached && (Date.now() - cached.ts) < 600000) {
    el.innerHTML = cached.html;
    return;
  }

  var url = 'https://hubeau.eaufrance.fr/api/v1/hydrometrie/observations_tr' +
    '?code_entite=' + encodeURIComponent(station.hubeau) +
    '&grandeur_hydro=H&size=1&sort=desc&fields=resultat_obs,date_obs';

  var html;
  try {
    var resp = await fetch(url);
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    var data = await resp.json();
    var obs  = data.data && data.data[0];
    if (!obs) throw new Error('no data');
    var cm   = Math.round(obs.resultat_obs / 10);
    var dt   = new Date(obs.date_obs);
    var time = dt.getHours() + ':' + String(dt.getMinutes()).padStart(2, '0');
    html = '<div class="vigicrues-card">' +
      '<div class="vigicrues-live-row">🌊 <strong>' + cm + ' cm</strong>' +
      '<span class="vigicrues-updated">updated ' + time + '</span></div>' +
      '<div style="font-size:11px;color:#c0d0e0;margin-bottom:4px">' + station.label + '</div>' +
      '<a href="' + station.url + '" target="_blank">📋 View station on Vigicrues →</a>' +
      '<div class="vigicrues-note">Real-time data: Hub\'Eau / VNF — always verify before navigating</div>' +
      '</div>';
  } catch (e) {
    html = '<div class="vigicrues-card">' +
      '<div class="vigicrues-live-row" style="color:#e57373">⚠ Level unavailable</div>' +
      '<div style="font-size:11px;color:#c0d0e0;margin-bottom:4px">' + station.label + '</div>' +
      '<a href="' + station.url + '" target="_blank">📋 View station on Vigicrues →</a>' +
      '<div class="vigicrues-note">Real-time data: Hub\'Eau / VNF — always verify before navigating</div>' +
      '</div>';
  }

  _vigicruesCache[routeNum] = { html: html, ts: Date.now() };
  if (el) el.innerHTML = html;
}
```

- [ ] **Step 4: Replace static card in openSidebar() with placeholder + async call**

Find the static card block in `openSidebar()` at line ~3562:

```js
    ${VIGICRUES_ROUTES.has(w.route) ? `
    <div class="vigicrues-card">
      <a href="https://www.vigicrues.gouv.fr/" target="_blank">🌊 Check Water Level (Vigicrues)</a>
      <div class="vigicrues-note">Real-time river height monitoring — check before navigating</div>
    </div>` : ''}
```

Replace with:

```js
    ${VIGICRUES_ROUTES.has(w.route) ? `
    <div id="vigicrues-live-${w.id}">⏳ Loading water level…</div>` : ''}
```

Then find the line immediately after `place-info.innerHTML = ...;` is set in `openSidebar()`. It looks like:

```js
  document.getElementById('place-info').innerHTML = html;
```

After that line, add:

```js
  if (VIGICRUES_ROUTES.has(w.route)) fetchVigicruesHTML(w.id, w.route);
```

- [ ] **Step 5: Verify in browser**

Open `http://localhost:8765/french_canals_map.html`. Click a town on a river route (e.g. any Seine town on Route 1, or a Rhône/Saône town on Route 13/16).

Expected:
1. Sidebar opens immediately with "⏳ Loading water level…"
2. Within ~1–2 seconds, div updates to show water height in cm + observation time + station label + link to Vigicrues station page
3. Close and reopen same sidebar within 10 minutes → loads instantly from cache (no spinner)
4. Open a canal-only town (e.g. Route 10 Burgundy canal) → no Vigicrues block at all

If Hub'Eau returns no data or HTTP error for a station code, the div should show "⚠ Level unavailable" with a link.

- [ ] **Step 6: Commit**

```bash
git add french_canals_map.html
git commit -m "feat: live Vigicrues water height fetch via Hub'Eau API with 10-min cache"
```

---

## Task 3: Update FEATURES.md

**Files:**
- Modify: `FEATURES.md` (move both features from In-Progress to Completed)

- [ ] **Step 1: Mark Lock Opening Hours complete in FEATURES.md**

In the `## 🟡 In Progress / Partially Implemented` table, find:
```
| Lock opening hours | CSS stub only | No data structure or display logic implemented |
```
Delete that row entirely.

In the `## ✅ Completed` → Vessel Profile table (or add a new Route Planning row), add:
```
| Lock opening hours | VNF regional schedule (6 groups, 44 routes) shown in lock sidebars |
```

- [ ] **Step 2: Mark Vigicrues complete in FEATURES.md**

In the `## 🟡 In Progress / Partially Implemented` table, find:
```
| Vigicrues water levels | Link only | Sidebar shows link to vigicrues.gouv.fr but no live data fetched |
```
Delete that row entirely.

In the `## ✅ Completed` section (Navigation & Planning group), add:
```
| Live Vigicrues water levels | Real-time Hub'Eau water height fetch for 11 river routes, 10-min cache |
```

- [ ] **Step 3: Commit**

```bash
git add FEATURES.md
git commit -m "docs: mark lock hours and vigicrues as completed in FEATURES.md"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ `_currentLockSeason()` — exists and correct, not changed
- ✅ `ROUTE_LOCK_GROUP` — Task 1 Step 2
- ✅ `LOCK_HOURS_BY_GROUP` — Task 1 Step 2
- ✅ `getLockHours()` returns null for unmapped routes — Task 1 Step 2
- ✅ `buildLockHoursHTML()` null guard — Task 1 Step 3
- ✅ Region label shown in HTML output — Task 1 Step 3 (uses `h.label`)
- ✅ `VIGICRUES_STATIONS` — Task 2 Step 2
- ✅ `_vigicruesCache` with 10-min TTL — Task 2 Step 2 + Step 3
- ✅ `fetchVigicruesHTML(wid, routeNum)` — Task 2 Step 3
- ✅ Placeholder div injected by `openSidebar()` — Task 2 Step 4
- ✅ `fetchVigicruesHTML` called after `innerHTML` set — Task 2 Step 4
- ✅ New CSS `.vigicrues-live-row` + `.vigicrues-updated` — Task 2 Step 1
- ✅ Error state renders correctly — Task 2 Step 3 (catch block)
- ✅ No new localStorage keys, no new map layers

**Placeholder scan:** No TBDs or TODOs.

**Type consistency:** `getLockHours()` returns `{ label, peak, shoulder, offseason }` — `buildLockHoursHTML` accesses `h.label`, `h.peak`, `h.shoulder`, `h.offseason`, `h[season]` — all keys present in `LOCK_HOURS_BY_GROUP`. `fetchVigicruesHTML` accesses `station.hubeau`, `station.label`, `station.url` — all keys present in `VIGICRUES_STATIONS`.
