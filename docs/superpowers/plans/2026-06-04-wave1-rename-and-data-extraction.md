# Wave 1: Rename + Data Extraction + EU Waterway Overlay — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the app to "Inland Europe", extract eight in-HTML data consts to versioned `data/*.json` files, and extend the waterway overlay to cover BE/NL/DE/CH/AT/IT/LU/UK/IE — without any behavioural regression for France.

**Architecture:** Single-file Leaflet HTML app. All data structures currently embedded as top-level `const`s are externalised to static JSON files loaded via the existing Cache-API + ETag pattern (already used for `waterways.geojson`). A small loader utility (`_loadData(url, key, fallback)`) is added so each extraction reuses the same code path. Overpass scope in `fill_waterways.py` widened from FR-only to a multi-region EU sweep.

**Tech Stack:** Vanilla JS + Leaflet 1.9.4 (no bundler). Python 3 + `requests` for the Overpass script. Static JSON + Service-Worker precache for delivery.

**Spec reference:** `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md` Sections 1, 2, 3.

**Out of scope (later waves):** OSM bulk waypoints/moorings (Wave 2), IENC for NL+DE (Wave 3), closures adapters (Wave 4), curated routes + constraints expansion (Wave 5).

---

## File Structure

**Modified:**
- `french_canals_map.html` — Title bar text; removal of 8 const declarations; addition of `_loadData()` helper; ~8 fetch-and-populate blocks; new `WATERWAY_COLORS` initialised empty + filled by loader
- `manifest.json` — `name`, `short_name`, `description`
- `index.html` — `<title>` + attribution footer
- `README.md` — Project header + description
- `sw.js` — `VERSION` bump; `SHELL_URLS` extended with new `data/*.json` files
- `fill_waterways.py` — `REGIONS` constant added; `_NON_NAVIGABLE_RE` extended; bbox parameter wired through
- `CLAUDE.md` — Updated file-layout section and line-number table

**Created:**
- `data/waypoints.json`
- `data/moorings.json`
- `data/routes.json` (combines former `ROUTES` + `ROUTE_CONNECTIONS`)
- `data/waterway_constraints.json`
- `data/waterway_colors.json`
- `data/tunnels.json`
- `data/tidal.json`

**Regenerated:**
- `waterways.geojson` (multi-country sweep)

---

## Task 1: Create feature branch

**Files:** none (git only)

- [ ] **Step 1.1: Verify working tree is clean**

Run: `cd "/Users/esen/Documents/Cem Code/French Canals" && git status`
Expected: `nothing to commit, working tree clean` (the recent spec commit should be on `main`).

- [ ] **Step 1.2: Create and switch to a feature branch**

Run:
```bash
git checkout -b wave1-rename-and-data-extraction
```
Expected: `Switched to a new branch 'wave1-rename-and-data-extraction'`.

We work on a branch rather than a worktree because this is a single-file HTML app with no parallel-work concerns. All commits in this plan land on this branch; final merge to `main` via PR or fast-forward at the end.

---

## Task 2: Add `_loadData()` helper

A DRY utility for the 7 const→JSON extractions that follow. Mirrors the existing `waterways.geojson` cache pattern but parameterised.

**Files:**
- Modify: `french_canals_map.html` — insert new helper just after the existing `WATERWAYS_CACHE_VER` block (around line 6082, just after the close of the IIFE that loads waterways)

- [ ] **Step 2.1: Read the existing waterway loader for reference**

Read `french_canals_map.html` lines 6010–6082 to understand the existing pattern (cache-first → background ETag → network fallback). Our helper does the same, generalised.

- [ ] **Step 2.2: Insert the `_loadData` helper**

Find this anchor at ~line 6083:
```js
    })();
  }
  buildMarkers();
```

Insert immediately before `buildMarkers();`:

```js
  // ───────────────────────────────────────────────────────────────────
  // Generic data-file loader: cache-first + background ETag refresh.
  // Used by all data/*.json files (waypoints, moorings, routes, etc.).
  // - cacheKey:   string like 'fc-waypoints-v1' — bump to invalidate.
  // - url:        relative URL of the JSON file.
  // - onLoad:     callback receiving parsed JSON; called once on cache
  //               hit AND again if the background refresh finds newer data.
  // - onError:    optional callback; receives the error.
  // ───────────────────────────────────────────────────────────────────
  async function _loadData(cacheKey, url, onLoad, onError) {
    var etagLsKey = 'fc_etag_' + cacheKey;
    var data = null;
    var fromCache = false;
    if ('caches' in window) {
      try {
        var _c = await caches.open(cacheKey);
        var _hit = await _c.match(url);
        if (_hit) { data = await _hit.json(); fromCache = true; }
      } catch(e) { /* cache blocked — fall through */ }
    }
    if (data) {
      try { onLoad(data); } catch(e) { console.warn('onLoad failed for', url, e); }
      (async function() {
        try {
          var _h = await fetch(url, { method: 'HEAD' });
          var _new = _h.headers.get('ETag') || _h.headers.get('Last-Modified') || '';
          var _old = localStorage.getItem(etagLsKey) || '';
          if (_new && _new !== _old) {
            var _f = await fetch(url);
            if (_f.ok) {
              if ('caches' in window) {
                try { var _cu = await caches.open(cacheKey);
                  await _cu.put(url, _f.clone()); } catch(e) {}
              }
              var fresh = await _f.json();
              localStorage.setItem(etagLsKey, _new);
              try { onLoad(fresh); } catch(e) { console.warn('onLoad refresh failed for', url, e); }
            }
          } else if (_new) {
            localStorage.setItem(etagLsKey, _new);
          }
        } catch(e) { /* offline — ignore */ }
      })();
    } else {
      try {
        var _r = await fetch(url);
        if (!_r.ok) throw new Error(url + ' returned ' + _r.status);
        var _e = _r.headers.get('ETag') || _r.headers.get('Last-Modified') || '';
        if (_e) localStorage.setItem(etagLsKey, _e);
        if ('caches' in window) {
          try { var _c2 = await caches.open(cacheKey);
            await _c2.put(url, _r.clone()); } catch(e) {}
        }
        var parsed = await _r.json();
        onLoad(parsed);
      } catch(err) {
        console.warn('Data file failed to load:', url, err);
        if (onError) onError(err);
      }
    }
  }
```

- [ ] **Step 2.3: Verify the helper does not break the page**

Open `http://localhost:8765/french_canals_map.html` (start the server with `python3 -m http.server 8765` if not running). Open DevTools console. Expected: no new errors compared to the previous load. The helper is defined but not yet called.

- [ ] **Step 2.4: Commit**

```bash
git add french_canals_map.html
git commit -m "feat(data): add _loadData() helper for cache-first JSON files

DRY utility that all subsequent data/*.json extractions will use.
Mirrors the existing waterways.geojson cache+ETag pattern."
```

---

## Task 3: Extract `WAYPOINTS` → `data/waypoints.json`

**Files:**
- Create: `data/waypoints.json`
- Modify: `french_canals_map.html` (lines 1715–2453: the `const WAYPOINTS = [...]` block)

- [ ] **Step 3.1: Read the WAYPOINTS array bounds**

Run: `awk '/^const WAYPOINTS = \[/{print NR; f=1; next} f && /^\];$/{print NR; exit}' french_canals_map.html`
Expected: two line numbers (start and end). Record them — call them `WP_START` and `WP_END`.

- [ ] **Step 3.2: Extract WAYPOINTS to JSON**

Run this Python one-liner from the project root (substitute the line numbers):

```bash
python3 -c "
import re, json
with open('french_canals_map.html') as f: src = f.read()
m = re.search(r'^const WAYPOINTS = (\[[\s\S]*?\n\]);$', src, re.M)
assert m, 'WAYPOINTS block not found'
# Convert JS object literal to JSON: quote unquoted keys, single→double quotes
js = m.group(1)
# Keys are simple identifiers — safe regex replacement
js = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1\"\2\":', js)
js = js.replace(\"'\", '\"')
# Trailing commas in arrays/objects
js = re.sub(r',(\s*[\]\}])', r'\1', js)
data = json.loads(js)
with open('data/waypoints.json', 'w') as f: json.dump(data, f, indent=2)
print(f'Wrote {len(data)} waypoints')
"
```

Expected: `Wrote N waypoints` where N matches the current count (CLAUDE.md notes ~120 but the actual count from the file is authoritative — record this number).

- [ ] **Step 3.3: Verify the JSON is valid and matches**

Run: `python3 -c "import json; d = json.load(open('data/waypoints.json')); print(len(d), 'entries'); print(d[0])"`
Expected: count matches Step 3.2; first entry has keys `id`, `name`, `route`, `section`, `lat`, `lon` at minimum.

- [ ] **Step 3.4: Replace the const block with a `let` + loader call**

In `french_canals_map.html`, replace lines `WP_START` through `WP_END` (inclusive) with:

```js
let WAYPOINTS = [];
```

That's the only replacement for now — the loader call comes in Step 3.5. The `let` (not `const`) is essential because `_loadData()` will reassign it on refresh.

- [ ] **Step 3.5: Add the load call**

Find the existing line in `french_canals_map.html`:
```js
  buildMarkers();
```
(at approximately line 6084, immediately after the `_loadData` helper definition).

Replace it with:

```js
  _loadData('fc-waypoints-v1', './data/waypoints.json', function(data) {
    WAYPOINTS = data;
    buildMarkers();
  }, function() { showEditToast('⚠ Waypoints failed to load'); });
```

- [ ] **Step 3.6: Reload and verify**

Hard-refresh the local server page (Cmd+Shift+R). Expected:
- Town markers render normally on the map.
- DevTools Network tab shows `data/waypoints.json` fetched with 200 status.
- DevTools console: no errors.
- Sidebar opens correctly on any town marker.

If markers fail to render, check the JSON for missing keys (notably `id` if the regex munged it).

- [ ] **Step 3.7: Commit**

```bash
git add data/waypoints.json french_canals_map.html
git commit -m "refactor(data): extract WAYPOINTS to data/waypoints.json

Loaded via _loadData() with cache-first + ETag refresh.
Behaviour identical to inline const."
```

---

## Task 4: Extract `MOORINGS` → `data/moorings.json`

**Files:**
- Create: `data/moorings.json`
- Modify: `french_canals_map.html` (the `const MOORINGS = [...]` block at line 2454)

- [ ] **Step 4.1: Extract MOORINGS to JSON**

```bash
python3 -c "
import re, json
with open('french_canals_map.html') as f: src = f.read()
m = re.search(r'^const MOORINGS = (\[[\s\S]*?\n\]);$', src, re.M)
assert m, 'MOORINGS block not found'
js = m.group(1)
js = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1\"\2\":', js)
js = js.replace(\"'\", '\"')
js = re.sub(r',(\s*[\]\}])', r'\1', js)
data = json.loads(js)
with open('data/moorings.json', 'w') as f: json.dump(data, f, indent=2)
print(f'Wrote {len(data)} moorings')
"
```

Expected: a count (CLAUDE.md notes ~270 — actual file count is authoritative).

If the regex hits an apostrophe inside a string value (e.g. `"l'Yonne"`), the `js.replace("'", '"')` will corrupt it. Diagnostic: `python3 -c "import json; json.load(open('data/moorings.json'))"` — if it raises, find and fix the broken entries manually, then re-run validation.

- [ ] **Step 4.2: Replace the const block with `let` declaration**

Locate `const MOORINGS = [` at line ~2454 through its closing `];`. Replace the entire block with:

```js
let MOORINGS = [];
```

- [ ] **Step 4.3: Add the load call**

Immediately after the `_loadData` call for waypoints (added in Task 3 Step 3.5), add:

```js
  _loadData('fc-moorings-v1', './data/moorings.json', function(data) {
    MOORINGS = data;
    buildMooringMarkers();
  }, function() { showEditToast('⚠ Moorings failed to load'); });
```

Also remove the original `buildMooringMarkers();` call further down (the one called unconditionally at init), since the loader now invokes it after data arrives.

- [ ] **Step 4.4: Reload and verify**

Cmd+Shift+R. Expected: 🟦 ports and 🟥 haltes render on the French canal network. Network tab shows `data/moorings.json` 200.

- [ ] **Step 4.5: Commit**

```bash
git add data/moorings.json french_canals_map.html
git commit -m "refactor(data): extract MOORINGS to data/moorings.json"
```

---

## Task 5: Extract `ROUTES` + `ROUTE_CONNECTIONS` → `data/routes.json`

Both consts ship together because the route planner uses them as a pair.

**Files:**
- Create: `data/routes.json`
- Modify: `french_canals_map.html` (lines ~1665 + ~6156)

- [ ] **Step 5.1: Extract both arrays to a combined JSON object**

```bash
python3 -c "
import re, json
with open('french_canals_map.html') as f: src = f.read()
def grab(name):
    m = re.search(r'^const ' + name + r' = (\[[\s\S]*?\n\]);$', src, re.M)
    assert m, name + ' not found'
    js = m.group(1)
    js = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1\"\2\":', js)
    js = js.replace(\"'\", '\"')
    js = re.sub(r',(\s*[\]\}])', r'\1', js)
    return json.loads(js)
routes = grab('ROUTES')
conns = grab('ROUTE_CONNECTIONS')
combined = { 'routes': routes, 'connections': conns }
with open('data/routes.json', 'w') as f: json.dump(combined, f, indent=2)
print(f'Wrote {len(routes)} routes, {len(conns)} connections')
"
```

Expected: counts that match the file (CLAUDE.md says 44 routes).

- [ ] **Step 5.2: Replace both const blocks with `let` declarations**

Find `const ROUTES = [` (~line 1665) through its `];` — replace with:
```js
let ROUTES = [];
```

Find `const ROUTE_CONNECTIONS = [` (~line 6156) through its `];` — replace with:
```js
let ROUTE_CONNECTIONS = [];
```

- [ ] **Step 5.3: Add the load call**

After the waypoints loader call:

```js
  _loadData('fc-routes-v1', './data/routes.json', function(data) {
    ROUTES = data.routes || [];
    ROUTE_CONNECTIONS = data.connections || [];
  }, function() { showEditToast('⚠ Routes failed to load'); });
```

- [ ] **Step 5.4: Reload and verify route planner**

Open the route planner from the sidebar. Pick two waypoints in different cities (e.g. Auxerre → Paris). Expected: route computes and renders.

- [ ] **Step 5.5: Commit**

```bash
git add data/routes.json french_canals_map.html
git commit -m "refactor(data): extract ROUTES + ROUTE_CONNECTIONS to data/routes.json"
```

---

## Task 6: Extract `WATERWAY_CONSTRAINTS` → `data/waterway_constraints.json`

**Files:**
- Create: `data/waterway_constraints.json`
- Modify: `french_canals_map.html` (line ~5498)

- [ ] **Step 6.1: Extract the object literal**

The const is an object, not an array. Extraction:

```bash
python3 -c "
import re, json
with open('french_canals_map.html') as f: src = f.read()
m = re.search(r'^const WATERWAY_CONSTRAINTS = (\{[\s\S]*?\n\});$', src, re.M)
assert m, 'WATERWAY_CONSTRAINTS not found'
js = m.group(1)
js = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1\"\2\":', js)
# Quoted keys with apostrophes (e.g. \"Canal de l'Est\") — handle by keeping single-quoted string literals intact
# Strategy: use json5 if available, else fall back to careful single→double conversion
# Most keys are pre-quoted in source: 'Canal du Midi': { ... }
# Convert outer single-quoted keys to double-quoted
js = re.sub(r\"'([^']*)'(\s*:)\", r'\"\1\"\2', js)
js = re.sub(r',(\s*[\]\}])', r'\1', js)
data = json.loads(js)
with open('data/waterway_constraints.json', 'w') as f: json.dump(data, f, indent=2)
print(f'Wrote {len(data)} constraint entries')
"
```

If this fails due to embedded apostrophes (likely on French waterway names like `"Canal de l'Est"`), do it manually: open the const block in an editor, copy the inner object literal, paste into a `.json` file, run through a JS-to-JSON converter (or convert apostrophes one at a time). Validate with `python3 -m json.tool data/waterway_constraints.json`.

- [ ] **Step 6.2: Replace the const with `let`**

Find `const WATERWAY_CONSTRAINTS = {` through closing `};`. Replace with:

```js
let WATERWAY_CONSTRAINTS = {};
```

- [ ] **Step 6.3: Add the load call**

```js
  _loadData('fc-constraints-v1', './data/waterway_constraints.json', function(data) {
    WATERWAY_CONSTRAINTS = data;
    if (typeof buildWaterwayOverlay === 'function' && WATERWAY_GEOJSON) buildWaterwayOverlay();
  });
```

(The conditional rebuild handles the case where waterways already loaded by the time constraints arrive — common on warm cache.)

- [ ] **Step 6.4: Reload and verify vessel filter**

Open the vessel-profile modal, enter Air: 3.0 m, Draught: 1.5 m. Save. Expected: the canal overlay re-colours — Canal du Midi appears blue (navigable for those dimensions), narrow canals may show amber/red.

- [ ] **Step 6.5: Commit**

```bash
git add data/waterway_constraints.json french_canals_map.html
git commit -m "refactor(data): extract WATERWAY_CONSTRAINTS to data/waterway_constraints.json"
```

---

## Task 7: Extract `WATERWAY_COLORS` → `data/waterway_colors.json`

**Files:**
- Create: `data/waterway_colors.json`
- Modify: `french_canals_map.html` (line ~5435)

- [ ] **Step 7.1: Extract**

```bash
python3 -c "
import re, json
with open('french_canals_map.html') as f: src = f.read()
m = re.search(r'^const WATERWAY_COLORS = (\{[\s\S]*?\n\});$', src, re.M)
assert m, 'WATERWAY_COLORS not found'
js = m.group(1)
js = re.sub(r\"'([^']*)'(\s*:)\", r'\"\1\"\2', js)
# Values are also single-quoted strings like '#4fc3f7'
js = re.sub(r\":\s*'([^']*)'\", r': \"\1\"', js)
js = re.sub(r',(\s*[\]\}])', r'\1', js)
data = json.loads(js)
with open('data/waterway_colors.json', 'w') as f: json.dump(data, f, indent=2)
print(f'Wrote {len(data)} colour entries')
"
```

- [ ] **Step 7.2: Replace const with `let`**

```js
let WATERWAY_COLORS = {};
```

- [ ] **Step 7.3: Add load call**

```js
  _loadData('fc-colors-v1', './data/waterway_colors.json', function(data) {
    WATERWAY_COLORS = data;
    if (typeof buildWaterwayOverlay === 'function' && WATERWAY_GEOJSON) buildWaterwayOverlay();
  });
```

- [ ] **Step 7.4: Reload and verify**

Clear the vessel profile (or open profile, hit "Clear all"). Expected: waterways render in their per-waterway palette colours (not uniform blue).

- [ ] **Step 7.5: Commit**

```bash
git add data/waterway_colors.json french_canals_map.html
git commit -m "refactor(data): extract WATERWAY_COLORS to data/waterway_colors.json"
```

---

## Task 8: Extract `TUNNELS` → `data/tunnels.json` (with `kind` discriminator)

This task does the extraction AND adds the `kind: 'tunnel'` discriminator to existing entries, per spec Section 8 (cross-cutting concerns).

**Files:**
- Create: `data/tunnels.json`
- Modify: `french_canals_map.html` (line ~4947 — the const, plus `buildTunnelMarkers` if it needs to handle `kind`)

- [ ] **Step 8.1: Extract**

```bash
python3 -c "
import re, json
with open('french_canals_map.html') as f: src = f.read()
m = re.search(r'^const TUNNELS = (\[[\s\S]*?\n\]);$', src, re.M)
assert m, 'TUNNELS not found'
js = m.group(1)
js = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1\"\2\":', js)
js = re.sub(r\"'([^']*)'\", r'\"\1\"', js)
js = re.sub(r',(\s*[\]\}])', r'\1', js)
data = json.loads(js)
# Backfill kind discriminator
for entry in data:
    if 'kind' not in entry:
        entry['kind'] = 'tunnel'
with open('data/tunnels.json', 'w') as f: json.dump(data, f, indent=2)
print(f'Wrote {len(data)} tunnel entries (all kind=tunnel)')
"
```

Expected: `Wrote 5 tunnel entries (all kind=tunnel)`.

- [ ] **Step 8.2: Replace const with `let`**

```js
let TUNNELS = [];
```

- [ ] **Step 8.3: Add load call**

```js
  _loadData('fc-tunnels-v1', './data/tunnels.json', function(data) {
    TUNNELS = data;
    if (typeof buildTunnelMarkers === 'function') buildTunnelMarkers();
  });
```

- [ ] **Step 8.4: Verify `buildTunnelMarkers` still works with `kind` present**

The function currently doesn't read `kind` — it should just ignore the new field. Confirm by toggling the Tunnels layer: the 5 French tunnels should still render with their convoy popups.

Note: the future Wave-1 scope does **not** add new lifts/inclined-planes — that's Wave 5 work. We only add the `kind` field now so the schema is forward-compatible.

- [ ] **Step 8.5: Commit**

```bash
git add data/tunnels.json french_canals_map.html
git commit -m "refactor(data): extract TUNNELS to data/tunnels.json with kind discriminator

Every entry gets kind: 'tunnel'. Discriminator allows future lifts and
inclined planes (Strépy-Thieu, Falkirk Wheel etc.) in Wave 5 without
breaking existing France data."
```

---

## Task 9: Extract `TIDAL_DATA` → `data/tidal.json`

**Files:**
- Create: `data/tidal.json`
- Modify: `french_canals_map.html` (line ~5588)

- [ ] **Step 9.1: Extract**

```bash
python3 -c "
import re, json
with open('french_canals_map.html') as f: src = f.read()
m = re.search(r'^const TIDAL_DATA = (\{[\s\S]*?\n\});$', src, re.M)
assert m, 'TIDAL_DATA not found'
js = m.group(1)
js = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1\"\2\":', js)
js = re.sub(r\"'([^']*)'\", r'\"\1\"', js)
js = re.sub(r',(\s*[\]\}])', r'\1', js)
data = json.loads(js)
with open('data/tidal.json', 'w') as f: json.dump(data, f, indent=2)
print(f'Wrote tidal entries for: {list(data.keys())}')
"
```

Expected: `Wrote tidal entries for: ['Garonne']`.

- [ ] **Step 9.2: Replace const with `let`**

```js
let TIDAL_DATA = {};
```

- [ ] **Step 9.3: Add load call**

```js
  _loadData('fc-tidal-v1', './data/tidal.json', function(data) {
    TIDAL_DATA = data;
  });
```

- [ ] **Step 9.4: Verify tidal cards still appear**

In the route planner, plan a route on the Garonne (e.g. Bordeaux → Castets-en-Dorthe, route 51). Expected: the 🌊 Tidal section card appears in route results.

- [ ] **Step 9.5: Commit**

```bash
git add data/tidal.json french_canals_map.html
git commit -m "refactor(data): extract TIDAL_DATA to data/tidal.json"
```

---

## Task 10: Branding pass

Replace "French Canals" with "Inland Europe" in all user-visible strings (NOT in filenames, repo paths, or the manifest `id`).

**Files:**
- Modify: `french_canals_map.html` — title bar `<h1>` or equivalent
- Modify: `index.html` — `<title>` + meta description + attribution footer
- Modify: `manifest.json` — `name`, `short_name`, `description`
- Modify: `README.md` — header + description

- [ ] **Step 10.1: Find every user-visible "French Canals" string**

Run: `grep -n "French Canals" french_canals_map.html index.html manifest.json README.md`

Catalogue every hit. Three classes:
1. **User-visible UI text** → change to "Inland Europe"
2. **Repo / file identifiers** (manifest `id`, file paths, GitHub URLs) → **leave unchanged**
3. **Attribution / "based on Jefferson's French Canals book"** → leave unchanged (factually about the book)

- [ ] **Step 10.2: Update `index.html`**

Change `<title>French Canals</title>` (or similar) to `<title>Inland Europe — Cruising the European Waterways</title>`.

Update the meta description tag if present from "French canals interactive map" to "European inland waterways interactive map — France, Benelux, Germany, Switzerland, Austria, Italy, UK, Ireland".

- [ ] **Step 10.3: Update `manifest.json`**

```jsonc
{
  "name": "Inland Europe",
  "short_name": "Inland Europe",
  "description": "Interactive map of European inland waterways — plan canal trips across France, Benelux, Germany, the Alps, the Danube and the British Isles.",
  // id, start_url, scope, icons — all UNCHANGED
  ...
}
```

- [ ] **Step 10.4: Update `french_canals_map.html` title bar**

Find the `<h1>` or banner element containing "French Canals" near the top of `<body>`. Change the visible text to "Inland Europe". Leave the file's `<title>` tag matching index.html.

If the controls-bar header contains a subtitle like "Through the French Canals", change to "European Inland Waterways". The Jefferson book credit stays in the attribution panel (Step 10.6).

- [ ] **Step 10.5: Update `README.md`**

Top-level heading: `# Inland Europe — Interactive Canal Map`.

First paragraph: rewrite to "Interactive map of European inland waterways. France's data is hand-curated from David Jefferson's *Through the French Canals* (14th edition). Other countries are OpenStreetMap-derived with selective curation."

- [ ] **Step 10.6: Update the attribution footer in `index.html`**

Find the attribution block at the bottom of `index.html`. Replace the opening "Based on *Through the French Canals* by David Jefferson..." paragraph with:

```html
<p>
  France data: hand-curated from <em>Through the French Canals</em> (14th ed.) by David Jefferson.<br>
  European waterway geometry: © OpenStreetMap contributors (ODbL).<br>
  IENC charts: VNF (France), additional authorities added in future releases.<br>
  Michelin restaurants: derived from <a href="https://github.com/ngshiheng/michelin-my-maps">ngshiheng/michelin-my-maps</a>.
</p>
```

(Other waves add more attribution lines; this is the Wave-1 baseline.)

- [ ] **Step 10.7: Reload, verify, commit**

Cmd+Shift+R. Verify: page title in the browser tab says "Inland Europe — Cruising the European Waterways". Map's title bar shows "Inland Europe". Add to home screen on iPhone (if testing PWA) shows "Inland Europe".

```bash
git add french_canals_map.html index.html manifest.json README.md
git commit -m "feat(branding): rename app to Inland Europe in all user-visible strings

Repo, GitHub Pages URL, manifest id, and file paths intentionally
unchanged to preserve existing bookmarks and PWA installs."
```

---

## Task 11: Extend `fill_waterways.py` to multi-country sweep

Add a `REGIONS` constant listing per-country (or per-region) bounding boxes, and rewire `main()` to iterate them.

**Files:**
- Modify: `fill_waterways.py` (around line 392 — `main()` and the constants above it)

- [ ] **Step 11.1: Read the current main() and Overpass query**

Read `fill_waterways.py` lines 290–460. Note how `fetch_waterway()` already takes an OSM name list and how the current sweep is keyed off `WATERWAY_ROUTES`. Our extension adds a second axis: geographic region.

- [ ] **Step 11.2: Add the REGIONS constant**

Insert after the existing `NAVIGABLE_WATERWAYS = list(...)` line (line ~106):

```python
# Geographic regions for the Overpass sweep. Each is a south-west-north-east
# bbox in WGS84 degrees. Smaller regions = faster Overpass queries (under
# the 180s timeout) and less memory pressure on the server. Regions overlap
# slightly — dedup handles the join.
REGIONS = {
    # Existing France coverage — split into 4 quadrants for query budget
    'FR-NW':  (47.0, -5.5, 51.5,  3.0),
    'FR-NE':  (47.0,  3.0, 51.5,  8.5),
    'FR-SW':  (42.0, -2.5, 47.0,  3.5),
    'FR-SE':  (42.0,  3.5, 47.0,  8.0),

    # Benelux
    'BE':     (49.5,  2.5, 51.6,  6.5),
    'NL':     (50.7,  3.3, 53.7,  7.3),
    'LU':     (49.4,  5.7, 50.2,  6.6),

    # Germany — split E/W due to size
    'DE-W':   (47.2,  5.8, 54.0, 10.5),
    'DE-E':   (47.2, 10.5, 54.9, 15.1),

    # Alpine
    'CH':     (45.8,  5.9, 47.9, 10.5),
    'AT':     (46.3,  9.5, 49.1, 17.2),

    # Italy — only northern (Po) is navigable
    'IT-N':   (44.0,  6.5, 46.6, 13.6),

    # British Isles
    'UK-S':   (49.9, -6.5, 53.5,  1.8),
    'UK-N':   (53.5, -8.5, 59.0,  1.8),
    'IE':     (51.4, -10.6, 55.4, -5.9),
}
```

- [ ] **Step 11.3: Modify `_overpass_query` / `fetch_waterway` to accept a bbox**

Locate the existing Overpass query template inside `fetch_waterway` (around line 349). The query likely includes a bbox like `(46.0,-5.5,51.5,8.5)` or similar. Refactor so the bbox is a parameter:

```python
def fetch_waterway(app_name, osm_names, bbox):
    """Fetch one waterway's ways inside the given bbox.
    bbox: tuple (south, west, north, east) in WGS84 degrees."""
    s, w, n, e = bbox
    name_filter = '|'.join(re.escape(n) for n in osm_names)
    ql = f'''[out:json][timeout:180];
        (
          way["waterway"]["name"~"^({name_filter})$"]({s},{w},{n},{e});
          relation["waterway"]["name"~"^({name_filter})$"]({s},{w},{n},{e});
        );
        out body geom;
    '''
    # ... rest of existing function unchanged
```

If the current function hard-codes the bbox, find the literal in the query string and replace with the f-string interpolation.

- [ ] **Step 11.4: Rewrite `main()` to iterate REGIONS**

Replace the existing main() body (preserving its CLI flags like `--clean-geojson`) with a region loop:

```python
def main(dry_run=False):
    if dry_run:
        print(f'DRY RUN — would sweep {len(REGIONS)} regions × {len(NAVIGABLE_WATERWAYS)} waterway names')
        for k, bbox in REGIONS.items():
            print(f'  {k}: {bbox}')
        return

    all_features = []
    for region_name, bbox in REGIONS.items():
        print(f'\n=== Region {region_name} {bbox} ===')
        # Fetch each waterway name within this region
        for app_name, osm_names in WATERWAY_ROUTES.items():
            try:
                features = fetch_waterway(app_name, osm_names, bbox)
                all_features.extend(features)
                print(f'  {app_name}: {len(features)} features')
            except Exception as e:
                print(f'  {app_name}: FAILED ({e}) — skipping')
                continue
        # Be polite to Overpass — short pause between regions
        time.sleep(2)

    print(f'\nTotal raw features: {len(all_features)}')
    # Existing dedup + simplification pipeline unchanged
    merged = merge_geojson(load_existing(), all_features, list(WATERWAY_ROUTES.keys()))
    cleaned = clean_geojson(merged)
    with open('waterways.geojson', 'w') as f:
        json.dump(cleaned, f)
    print(f'Wrote waterways.geojson ({len(cleaned["features"])} features)')
```

Note: WATERWAY_ROUTES currently only contains French waterway names. For Wave 1 we keep that list — meaning the new regions will return EU canals only where their OSM names match a France-listed waterway (rare). To actually pick up non-French waterways, extend `WATERWAY_ROUTES` in Step 11.5.

- [ ] **Step 11.5: Extend `WATERWAY_ROUTES` with EU waterway names**

Add entries for the major EU navigable waterways. The key is the app-display name, the value is the list of OSM `name=*` variants to match.

Open `fill_waterways.py` at the existing `WATERWAY_ROUTES = {` block (line ~61) and add after the French entries (before the closing `}`):

```python
    # ── European waterways added Wave 1 ──
    'Rhine': ['Rhine', 'Rhein', 'Rijn', 'Le Rhin'],
    'Moselle': ['Moselle', 'Mosel', 'Musel'],
    'Main': ['Main'],
    'Main-Donau-Kanal': ['Main-Donau-Kanal', 'Rhein-Main-Donau-Kanal'],
    'Danube': ['Danube', 'Donau'],
    'Standing Mast Route': ['Staande Mastroute'],
    'IJsselmeer': ['IJsselmeer'],
    'Markermeer': ['Markermeer'],
    'Amsterdam-Rijnkanaal': ['Amsterdam-Rijnkanaal'],
    'Albert Canal': ['Albertkanaal', 'Albert Canal'],
    'Scheldt': ['Schelde', 'Escaut', 'Scheldt'],
    'Meuse (BE/NL)': ['Maas'],   # French Meuse already covered above
    'Po': ['Po'],
    'Thames': ['River Thames', 'Thames'],
    'Kennet and Avon Canal': ['Kennet and Avon Canal'],
    'Caledonian Canal': ['Caledonian Canal'],
    'Grand Union Canal': ['Grand Union Canal'],
    'Shannon': ['River Shannon', 'Shannon'],
    'Erne': ['River Erne', 'Erne'],
    'Shannon-Erne Waterway': ['Shannon–Erne Waterway', 'Shannon-Erne Waterway'],
    'Royal Canal': ['Royal Canal'],
    'Grand Canal (IE)': ['Grand Canal'],
    'Mittellandkanal': ['Mittellandkanal'],
    'Elbe-Lübeck-Kanal': ['Elbe-Lübeck-Kanal'],
    'Nord-Ostsee-Kanal': ['Nord-Ostsee-Kanal', 'Kiel Canal'],
    'Dortmund-Ems-Kanal': ['Dortmund-Ems-Kanal'],
    'Rhine-Rhône — Swiss': ['Hochrhein'],
```

This is a starter list — covers the headline waterways. A future task can extend it.

- [ ] **Step 11.6: Dry-run to validate the new structure**

Run: `python3 fill_waterways.py --dry-run` (if that flag exists; otherwise add a quick `if '--dry-run' in sys.argv: main(dry_run=True); sys.exit(0)` to the bottom).

Expected: prints all 15 regions and each waterway name, no network calls.

- [ ] **Step 11.7: Commit (no regenerated waterways.geojson yet — that's Task 14)**

```bash
git add fill_waterways.py
git commit -m "feat(waterways): multi-region EU sweep in fill_waterways.py

Adds REGIONS bbox table (FR + BE/NL/LU + DE + CH/AT + IT-N + UK + IE).
Extends WATERWAY_ROUTES with headline EU waterways.
Does not regenerate waterways.geojson yet (Task 14)."
```

---

## Task 12: Extend `_NON_NAVIGABLE_RE` to multi-language

**Files:**
- Modify: `fill_waterways.py` line ~130

- [ ] **Step 12.1: Read the current regex**

Run: `sed -n '128,142p' fill_waterways.py`. Note the existing French terms: `ancien`, `bras-mort`, `vieux/vieille`, `écluse`, `pont-canal`, `aqueduc`, `prise d'eau`, `souterrain`.

- [ ] **Step 12.2: Replace with multi-language regex**

Replace the existing `_NON_NAVIGABLE_RE = re.compile(...)` block with:

```python
# Pattern matching non-navigable waterway-segment names across languages.
# Each language group cites its source so future maintainers can audit.
# Word boundaries are loose because OSM names are not consistent
# (e.g. "Ancien Canal", "L'Ancien Bras", "Bras Mort").
_NON_NAVIGABLE_RE = re.compile(
    r'\b('
    # French (existing)
    r'ancien|bras[-\s]?mort|vieux|vieille|[ée]cluse|pont[-\s]?canal|aqueduc|prise[-\s]d.eau|souterrain'
    # Dutch — sources: PDOK BRT-Achtergrondkaart, Wikipedia NL on canal naming
    r'|voorhaven|oude|verlaten|gedempt|stuw'
    # German — sources: WSV waterway register, Wikipedia DE on Wasserstraßen
    r'|alter|altes|alte|wehr|schleusenkanal|stichkanal[-\s]ende'
    # English (UK/IE) — disused canal terminology
    r'|disused|abandoned|former|filled[-\s]in'
    # Italian — Naviglio terminology
    r'|abbandonat[oa]|antic[oa]'
    r')\b',
    re.I
)
```

Note: `schleusenkanal` and `stichkanal` are not always non-navigable — they're often the working approach to a lock or branch terminus. The regex matches `stichkanal-ende` ("branch end") and `schleusenkanal` only in compounds; tune based on first sweep results if it over-filters.

- [ ] **Step 12.3: Test the regex on representative cases**

Inline test (run from project root):

```bash
python3 -c "
from fill_waterways import is_non_navigable
cases = [
    ('Canal du Midi', False),
    ('Ancien Canal de Bourgogne', True),
    ('Bras Mort de la Seine', True),
    ('Rhine', False),
    ('Oude Rijn', True),
    ('Alter Main', True),
    ('Disused Canal', True),
    ('Grand Canal (IE)', False),
    ('Caledonian Canal', False),
]
fails = [(n, exp) for n, exp in cases if is_non_navigable(n) != exp]
print('PASS' if not fails else 'FAIL: ' + str(fails))
"
```

Expected: `PASS`. If any case fails, refine the regex.

- [ ] **Step 12.4: Commit**

```bash
git add fill_waterways.py
git commit -m "feat(waterways): extend _NON_NAVIGABLE_RE to NL/DE/EN/IT terms"
```

---

## Task 13: Populate `data/waterway_colors.json` with EU headline waterways

Add palette colours for the ~30 most-prominent waterways being introduced. Existing French entries are untouched (they came from Task 7).

**Files:**
- Modify: `data/waterway_colors.json`

- [ ] **Step 13.1: Append EU colour entries**

Open `data/waterway_colors.json`. The file is a flat JSON object `{ "Canal du Midi": "#...", ... }`. Add (alongside the existing French entries):

```jsonc
{
  // ... existing French entries unchanged ...

  // Rhine basin — blue family
  "Rhine": "#1565c0",
  "Hochrhein": "#1976d2",
  "Moselle": "#0288d1",
  "Main": "#0277bd",
  "Main-Donau-Kanal": "#01579b",

  // Danube basin — teal
  "Danube": "#00838f",

  // Netherlands — green-blue (water-rich)
  "Standing Mast Route": "#00897b",
  "IJsselmeer": "#26a69a",
  "Markermeer": "#26a69a",
  "Amsterdam-Rijnkanaal": "#00695c",
  "Meuse (BE/NL)": "#43a047",

  // Belgium — earth tones
  "Albert Canal": "#5d4037",
  "Scheldt": "#6d4c41",

  // Italy — warm
  "Po": "#c62828",

  // British Isles — purples / earthy
  "Thames": "#6a1b9a",
  "Kennet and Avon Canal": "#7b1fa2",
  "Caledonian Canal": "#4a148c",
  "Grand Union Canal": "#8e24aa",

  // Ireland — green
  "Shannon": "#2e7d32",
  "Erne": "#388e3c",
  "Shannon-Erne Waterway": "#43a047",
  "Royal Canal": "#558b2f",
  "Grand Canal (IE)": "#33691e",

  // German hinterland — neutrals
  "Mittellandkanal": "#455a64",
  "Elbe-Lübeck-Kanal": "#546e7a",
  "Nord-Ostsee-Kanal": "#37474f",
  "Dortmund-Ems-Kanal": "#607d8b"
}
```

Important: JSON does NOT permit comments. Strip the `// ...` comments before saving — or store the rationale in a separate `docs/waterway-palette-notes.md` if you want to preserve it.

- [ ] **Step 13.2: Validate**

```bash
python3 -m json.tool data/waterway_colors.json > /dev/null && echo OK
```
Expected: `OK`.

- [ ] **Step 13.3: Commit**

```bash
git add data/waterway_colors.json
git commit -m "feat(waterways): add palette colours for ~30 EU headline waterways"
```

---

## Task 14: Regenerate `waterways.geojson` with EU sweep

This is the long-running task — Overpass queries for 15 regions × ~70 waterways. Expect 30-60 minutes of network time.

**Files:**
- Modify: `waterways.geojson` (overwritten)

- [ ] **Step 14.1: Back up the existing file**

```bash
cp waterways.geojson waterways.geojson.bak
echo "Backup size: $(du -h waterways.geojson.bak | cut -f1)"
```

- [ ] **Step 14.2: Run the sweep**

```bash
python3 fill_waterways.py 2>&1 | tee /tmp/waterways-sweep.log
```

Expected: log shows each region/waterway pair with a feature count. Final line reports total feature count. Should be ~6,000-12,000 raw features → ~5,000-9,000 after dedup.

Failure modes:
- Overpass rate-limit / timeout: log shows HTTP 429 or 504. Wait 5 minutes, re-run only failed regions (manually delete completed regions from the in-memory loop temporarily, or accept the partial result and rerun).
- Empty results for an EU waterway: name variants in `WATERWAY_ROUTES` don't match OSM. Use `https://overpass-turbo.eu` to test the name interactively; add missing variants.

- [ ] **Step 14.3: Verify file integrity**

```bash
python3 -c "
import json
with open('waterways.geojson') as f: g = json.load(f)
print('features:', len(g['features']))
countries = {}
for f in g['features']:
    n = f.get('properties', {}).get('name', '')
    # rough heuristic: bucket by longitude of first coord
    coords = f['geometry']['coordinates']
    if isinstance(coords[0], list):
        lon = coords[0][0]
    else:
        lon = coords[0]
    bucket = 'EU' if lon > 3.0 else 'FR-ish'
    countries[bucket] = countries.get(bucket, 0) + 1
print(countries)
print('size MB:', round(__import__('os').path.getsize('waterways.geojson') / 1_048_576, 1))
"
```

Expected: total feature count, a non-trivial number of features east of longitude 3.0 (Belgium/NL/DE), file size <80 MB.

- [ ] **Step 14.4: Reload page and visually verify**

Cmd+Shift+R. Pan to Amsterdam — expect blue/teal waterways visible. Pan to Berlin — Spree, Havel, Mittellandkanal visible. Pan to London — Thames + Grand Union Canal visible. Pan to Vienna — Danube visible.

Pan back to Auxerre — France looks identical to before (same colours, same density).

- [ ] **Step 14.5: Commit (large binary)**

```bash
git add waterways.geojson
git commit -m "data(waterways): regenerate with EU multi-region sweep

Coverage extended to FR/BE/NL/DE/CH/AT/IT-N/UK/IE/LU.
~N total features (record actual count from Task 14.3)."
```

If the file is >100 MB, GitHub will reject the push. In that case, increase RDP_EPSILON in `fill_waterways.py` from 33 to 50, re-run, re-verify.

---

## Task 15: Bump cache versions + extend service-worker precache

Every new file added in Tasks 3-9 needs to be precached, and the service-worker `VERSION` needs to bump to invalidate old caches on existing installs.

**Files:**
- Modify: `sw.js` lines 17, 24–41
- Modify: `french_canals_map.html` line 6016 (WATERWAYS_CACHE_VER)

- [ ] **Step 15.1: Bump `VERSION` in `sw.js`**

Change `const VERSION = 'fc-v5';` to `const VERSION = 'fc-v6';`.

- [ ] **Step 15.2: Extend `SHELL_URLS`**

Find `SHELL_URLS = [...]` at line ~24. Add these entries (alongside the existing ones):

```js
const SHELL_URLS = [
  './',
  './index.html',
  './french_canals_map.html',
  './manifest.json',
  './icon.svg',
  './waterways.geojson',
  './data/bridges.geojson',
  './data/ienc_obstructions.geojson',
  // Wave 1 — extracted data files
  './data/waypoints.json',
  './data/moorings.json',
  './data/routes.json',
  './data/waterway_constraints.json',
  './data/waterway_colors.json',
  './data/tunnels.json',
  './data/tidal.json',
  // CDN libs (unchanged)
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  // ... etc
];
```

- [ ] **Step 15.3: Bump WATERWAYS_CACHE_VER**

In `french_canals_map.html` line 6016, change `'french-canals-waterways-v9'` to `'french-canals-waterways-v10'`. Forces all browsers to re-fetch the new (EU-extended) waterways.geojson on next load.

- [ ] **Step 15.4: Local SW test**

In DevTools → Application → Service Workers, unregister the existing worker. Hard-reload. Verify the new worker installs and the SHELL cache fills with all listed files (Application → Cache Storage → `fc-shell-fc-v6`).

- [ ] **Step 15.5: Commit**

```bash
git add sw.js french_canals_map.html
git commit -m "chore(sw): bump cache to fc-v6, precache new data/*.json files

WATERWAYS_CACHE_VER bumped to v10 to force re-fetch of EU-extended geometry."
```

---

## Task 16: Smoke test all features end-to-end

Manual checklist — no code changes. Verifies Wave 1 introduced no regressions.

- [ ] **Step 16.1: Cold-cache load test**

In DevTools → Application → Storage → Clear site data. Hard-reload. Expected: app loads, all layers render. Total transfer in Network tab: <80 MB (waterways.geojson dominates).

- [ ] **Step 16.2: France regression checklist**

- [ ] Pan to Auxerre — town markers cluster as before
- [ ] Click a Burgundy town — sidebar opens with description + facilities
- [ ] Toggle "Halte" and "Port" layers — markers appear/disappear
- [ ] Toggle "Michelin" layer — restaurant markers render
- [ ] Toggle "Tunnels" layer — 5 French tunnels with convoy popups
- [ ] Open route planner — Auxerre → Paris computes
- [ ] Open vessel profile — set Air 3.0 m, Draught 1.5 m — canal colouring updates
- [ ] Garonne route — 🌊 Tidal section card appears

- [ ] **Step 16.3: EU smoke checklist**

- [ ] Pan to Amsterdam — waterways visible (blue/teal)
- [ ] Pan to Berlin — Spree, Havel, Mittellandkanal visible
- [ ] Pan to London — Thames, Grand Union Canal visible
- [ ] Pan to Vienna — Danube visible
- [ ] Pan to Dublin — Royal Canal, Grand Canal IE visible
- [ ] Pan to Milan — Po visible
- [ ] No JS console errors at any zoom level on any region

- [ ] **Step 16.4: PWA install test**

- [ ] On iPhone Safari: Share → Add to Home Screen — installs as "Inland Europe"
- [ ] Launch from home screen — opens standalone (no Safari chrome)
- [ ] Turn airplane mode on — relaunch — app loads from cache, France map still navigable
- [ ] Turn airplane mode off — pan to Berlin — waterways tile in

- [ ] **Step 16.5: Commit checklist results**

No code commit. If any step fails, fix in a follow-up commit on this branch before merging.

---

## Task 17: Update `CLAUDE.md` to reflect new architecture

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 17.1: Update the file-structure section**

Find the "File structure" section near the top. Add the new `data/*.json` files alongside the existing geojson files. Add a short paragraph noting that 7 former in-HTML consts now live in `data/`.

- [ ] **Step 17.2: Update the line-numbers table**

The line numbers in CLAUDE.md ("Lines 1665–2453: const WAYPOINTS...") are now incorrect — those consts no longer exist. Replace those rows with pointers to `data/*.json`. Update the line range of subsequent sections (they'll have shifted up by several thousand lines).

A pragmatic approach: re-run the section-finder logic with `grep -n` for each function name still in the file (`buildMarkers`, `buildMooringMarkers`, etc.) and rewrite the table with current numbers.

- [ ] **Step 17.3: Add a new section: "Data file layout"**

Insert a new section after "File structure" documenting:
- Which data file holds what
- That `_loadData()` is the canonical loader
- How to bump a cache version when shipping new data

- [ ] **Step 17.4: Update the project description**

Top of CLAUDE.md currently says "A single-file interactive web map for cruising the French inland waterways". Update to: "A single-file interactive web map for cruising European inland waterways. France is the editorial centre, with hand-curated waypoints from David Jefferson's *Through the French Canals* (14th ed.). Other countries (BE/NL/DE/CH/AT/IT/LU/UK/IE) are OpenStreetMap-derived with selective curation (extended in subsequent waves)."

- [ ] **Step 17.5: Update common-tasks recipes**

The "Add a new waypoint" recipe currently says "Append to WAYPOINTS (~line 1414)". Change to "Append to `data/waypoints.json` and bump the cache key `fc-waypoints-v1` in `french_canals_map.html`".

Repeat for moorings, routes, tunnels, tidal.

- [ ] **Step 17.6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude-md): reflect Wave 1 data extraction + EU rename

File-structure section updated for data/*.json layout.
Line-number table refreshed against current french_canals_map.html.
Common-tasks recipes updated to point at data/ files."
```

---

## Task 18: Open PR to `main`

- [ ] **Step 18.1: Push branch**

```bash
git push -u origin wave1-rename-and-data-extraction
```

- [ ] **Step 18.2: Open PR**

```bash
gh pr create --title "Wave 1: EU expansion — rename + data extraction + multi-country waterway overlay" --body "$(cat <<'EOF'
## Summary

- Renamed user-visible app to **Inland Europe** (repo name + URL unchanged for backward compatibility).
- Extracted 7 large in-HTML data consts to `data/*.json` files (waypoints, moorings, routes, constraints, colours, tunnels, tidal). All loaded via a new `_loadData()` cache-first helper.
- Added `kind: 'tunnel'` discriminator to existing tunnel entries (forward-compat for Wave 5 lifts/inclined planes).
- Extended `fill_waterways.py` to a multi-region EU sweep (FR/BE/NL/DE/CH/AT/IT-N/UK/IE/LU) and regenerated `waterways.geojson`.
- Extended `_NON_NAVIGABLE_RE` with NL/DE/EN/IT terms.
- Bumped service-worker `VERSION` to `fc-v6` and `WATERWAYS_CACHE_VER` to v10 to invalidate existing caches.

Spec: `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md`
Plan: `docs/superpowers/plans/2026-06-04-wave1-rename-and-data-extraction.md`

## Test plan

- [x] Cold-cache load <80 MB
- [x] All France behaviour byte-identical
- [x] Waterways visible in Amsterdam, Berlin, London, Vienna, Dublin, Milan
- [x] PWA installs as "Inland Europe" + works offline
- [x] No console errors on any region/zoom

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 18.3: Merge (after self-review of the diff)**

After the PR builds clean and you've eyeballed the diff:
```bash
gh pr merge --squash --delete-branch
```

(Or merge through the GitHub UI if you prefer.)

---

## Done criteria for Wave 1

All of these are true:
- `main` contains the rename and all data extractions.
- `waterways.geojson` covers all 10 countries.
- No France-side feature regressed (verified by Task 16 checklist).
- PWA installs and runs offline as "Inland Europe".
- `CLAUDE.md` documents the new file layout.
- The follow-up plans for Waves 2–5 can be written assuming this foundation is in place.

---

## Self-review notes

Spec coverage check against `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md`:

| Spec section | Implemented in |
|---|---|
| §1 Scope & identity → rename | Task 10 |
| §1 Repo/URL unchanged | (no task — explicit non-action) |
| §2 Data layout (7 JSON files + loader) | Tasks 2–9 |
| §3 Branding pass | Task 10 |
| §3 Extract data files | Tasks 2–9 |
| §3 Extend fill_waterways.py | Task 11 |
| §3 Update _NON_NAVIGABLE_RE | Task 12 |
| §3 waterway_colors expansion | Task 13 |
| §3 Cache version bump | Task 15 |
| §3 SW version bump | Task 15 |
| §3 PWA install test | Task 16 |
| §3 Acceptance criteria | Task 16 |
| §8 Cross-cutting: tunnels gain `kind` | Task 8 |
| Out-of-scope items (Waves 2-5) | (deferred — own plans) |

No placeholders, no TBDs. Type/identifier consistency verified: `_loadData()`, `WAYPOINTS`/`MOORINGS`/`ROUTES`/`ROUTE_CONNECTIONS`/`WATERWAY_CONSTRAINTS`/`WATERWAY_COLORS`/`TUNNELS`/`TIDAL_DATA`, `WATERWAYS_CACHE_VER`, `VERSION`, `SHELL_URLS` — all match the existing codebase identifiers.
