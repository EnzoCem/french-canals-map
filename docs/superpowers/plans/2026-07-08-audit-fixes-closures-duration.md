# Audit Fixes: Closures Layer Repair, Closure-Aware Routing, Trip Duration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the broken 🚧 Closures layer, harden localStorage/script-write reliability, and add two route-planner features: closure warnings on planned routes and vessel-profile-aware trip duration estimates.

**Architecture:** All UI work lives in the single-file app `french_canals_map.html` (vanilla JS + Leaflet, no build step). The closure warning card mirrors the existing 🌊 tidal card pattern (`_getTidalWarnings` / `_buildTidalCardHTML` pair, hooked into both result renderers). Python fixes are small, isolated hardening changes with unit tests where a pure helper can be extracted.

**Tech Stack:** Vanilla JS, Leaflet 1.9.4, Python 3 + pytest (venv at `./venv`).

**Verification note:** There is no JS test infra. Every HTML task ends with `node --check` on the extracted script block (recipe in Task 1) plus a targeted grep. Python tasks use pytest TDD.

---

### Task 0: Create feature branch

**Files:** none

- [ ] **Step 1: Branch off main**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
git checkout main && git pull && git checkout -b audit-fixes-closures-duration
```

---

### Task 1: Fix broken Closures layer (`CHOMAGES_SEED` → `CLOSURES`)

The Wave 4 extraction moved closure data to `data/closures.json` (loaded into the `CLOSURES` array at line ~4870), but `buildClosuresMarkers()` at line 3863 still iterates the deleted `CHOMAGES_SEED` constant. Toggling 🚧 Closures throws `ReferenceError: CHOMAGES_SEED is not defined` and the layer renders nothing.

**Files:**
- Modify: `french_canals_map.html:3863`

- [ ] **Step 1: Apply the fix**

In `buildClosuresMarkers()`, change:

```js
  CHOMAGES_SEED.forEach(function(ch) {
```

to:

```js
  CLOSURES.forEach(function(ch) {
```

- [ ] **Step 2: Verify no other references remain**

```bash
grep -n "CHOMAGES_SEED" french_canals_map.html
```
Expected: no output.

- [ ] **Step 3: Syntax-check the script block**

```bash
python3 - <<'EOF'
import re
html = open('french_canals_map.html', encoding='utf-8').read()
scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
open('/tmp/fc_main.js', 'w', encoding='utf-8').write(max(scripts, key=len))
EOF
node --check /tmp/fc_main.js && echo SYNTAX-OK
```
Expected: `SYNTAX-OK`. (If `node` is unavailable, skip — grep check in Step 2 is the primary gate for this task.)

- [ ] **Step 4: Commit**

```bash
git add french_canals_map.html
git commit -m "fix(closures): render CLOSURES array instead of deleted CHOMAGES_SEED"
```

---

### Task 2: Guard unprotected JSON.parse on localStorage

Two localStorage reads crash the whole app on corrupted values; sibling keys (lines 2735, 2740, 2749) are already guarded.

**Files:**
- Modify: `french_canals_map.html:2743` (saved routes)
- Modify: `french_canals_map.html:3642-3643` (vessel profile)

- [ ] **Step 1: Guard saved routes**

Change:

```js
let savedRoutes = JSON.parse(localStorage.getItem(SAVED_ROUTES_KEY) || '[]');
```

to:

```js
let savedRoutes = [];
try { savedRoutes = JSON.parse(localStorage.getItem(SAVED_ROUTES_KEY) || '[]') || []; } catch(e){}
if (!Array.isArray(savedRoutes)) savedRoutes = [];
```

- [ ] **Step 2: Guard vessel profile**

Change:

```js
var _vesselProfile = Object.assign({}, _PROFILE_DEFAULTS,
  JSON.parse(localStorage.getItem(VESSEL_KEY) || 'null') || {});
```

to:

```js
var _storedProfile = {};
try { _storedProfile = JSON.parse(localStorage.getItem(VESSEL_KEY) || 'null') || {}; } catch(e){}
var _vesselProfile = Object.assign({}, _PROFILE_DEFAULTS, _storedProfile);
```

- [ ] **Step 3: Syntax-check** (same recipe as Task 1 Step 3). Expected: `SYNTAX-OK`.

- [ ] **Step 4: Commit**

```bash
git add french_canals_map.html
git commit -m "fix(storage): guard JSON.parse for saved routes and vessel profile"
```

---

### Task 3: Prune expired closures + bump data cache key

12 of 33 entries in `data/closures.json` ended before 2026-07-08. The UI already filters them (line ~3869), but they bloat the file and the layer count.

**Files:**
- Modify: `data/closures.json`
- Modify: `french_canals_map.html` (`'fc-closures-v1'` → `'fc-closures-v2'`)

- [ ] **Step 1: Prune entries with end < today**

```bash
python3 - <<'EOF'
import json
c = json.load(open('data/closures.json'))
kept = [x for x in c if x['end'] >= '2026-07-08']
print(f'{len(c)} -> {len(kept)} (removed {len(c)-len(kept)})')
with open('data/closures.json.tmp', 'w') as f:
    json.dump(kept, f, indent=2, ensure_ascii=False)
import os; os.replace('data/closures.json.tmp', 'data/closures.json')
EOF
```
Expected: `33 -> 21 (removed 12)`.

- [ ] **Step 2: Bump the cache key in the HTML**

In `french_canals_map.html` change `_loadData('fc-closures-v1', './data/closures.json', ...)` to `_loadData('fc-closures-v2', ...)`.

- [ ] **Step 3: Validate JSON + commit**

```bash
python3 -c "import json; d=json.load(open('data/closures.json')); assert all(x['end']>='2026-07-08' for x in d); print(len(d),'ok')"
git add data/closures.json french_canals_map.html
git commit -m "chore(closures): prune 12 expired entries, bump cache key to fc-closures-v2"
```

---

### Task 4: Add Overpass User-Agent to patch_lyon_waterways.py

Overpass returns HTTP 406 for the default python-requests User-Agent (hit this exact failure in Wave 1). `fill_waterways.py` already sends a proper header; this script doesn't.

**Files:**
- Modify: `patch_lyon_waterways.py:36`

- [ ] **Step 1: Add module-level headers constant and use it**

Near the top (after `OVERPASS_URL`), add:

```python
OVERPASS_HEADERS = {
    'User-Agent': 'french-canals-map/1.0 (https://github.com/EnzoCem/french-canals-map)'
}
```

Change line 36:

```python
resp = requests.post(OVERPASS_URL, data={'data': ql}, timeout=180)
```

to:

```python
resp = requests.post(OVERPASS_URL, data={'data': ql}, headers=OVERPASS_HEADERS, timeout=180)
```

- [ ] **Step 2: Verify it parses**

```bash
python3 -m py_compile patch_lyon_waterways.py && echo OK
```
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add patch_lyon_waterways.py
git commit -m "fix(scripts): send Overpass User-Agent in patch_lyon_waterways"
```

---

### Task 5: Atomic write in fill_auto_routes.py (TDD)

A crash mid-`json.dump` corrupts `data/routes.json` (which contains hand-curated routes). Extract an `atomic_write_json()` helper and test it.

**Files:**
- Modify: `fill_auto_routes.py:156`
- Test: `tests/test_fill_auto_routes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_fill_auto_routes.py`:

```python
def test_atomic_write_json(tmp_path):
    from fill_auto_routes import atomic_write_json
    target = tmp_path / 'out.json'
    atomic_write_json(str(target), {'a': [1, 2], 'name': 'Rhône'})
    import json
    assert json.loads(target.read_text()) == {'a': [1, 2], 'name': 'Rhône'}
    # no temp file left behind
    assert list(tmp_path.iterdir()) == [target]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source venv/bin/activate && python3 -m pytest tests/test_fill_auto_routes.py::test_atomic_write_json -v
```
Expected: FAIL with `ImportError: cannot import name 'atomic_write_json'`.

- [ ] **Step 3: Implement**

In `fill_auto_routes.py`, add near the other helpers:

```python
def atomic_write_json(path, obj):
    """Write JSON to path via a .tmp sibling + os.replace (crash-safe)."""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
```

Ensure `import os` exists at the top. Then replace in `main()`:

```python
    with open(ROUTES_PATH, 'w') as f:
        json.dump(rj, f, indent=2, ensure_ascii=False)
```

with:

```python
    atomic_write_json(ROUTES_PATH, rj)
```

(`ROUTES_PATH` may be a `Path`; if so pass `str(ROUTES_PATH)` or build `tmp` with `str(path) + '.tmp'` — check its type at the top of the file and match.)

- [ ] **Step 4: Run the full test file**

```bash
python3 -m pytest tests/test_fill_auto_routes.py -v
```
Expected: all PASS (4 existing + 1 new).

- [ ] **Step 5: Commit**

```bash
git add fill_auto_routes.py tests/test_fill_auto_routes.py
git commit -m "fix(scripts): atomic write for routes.json in fill_auto_routes"
```

---

### Task 6: Atomic write in fill_michelin.py

Same crash-safety issue, but the target is the 8,300-line `french_canals_map.html` itself — corruption here is catastrophic. This script has no test file; add one for the new helper only (full-script tests are out of scope for this batch).

**Files:**
- Modify: `fill_michelin.py:209`
- Create: `tests/test_fill_michelin.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fill_michelin.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_atomic_write_text(tmp_path):
    from fill_michelin import atomic_write_text
    target = tmp_path / 'page.html'
    atomic_write_text(target, '<html>é</html>')
    assert target.read_text(encoding='utf-8') == '<html>é</html>'
    assert list(tmp_path.iterdir()) == [target]
```

(Match the import-path convention used at the top of `tests/test_fill_auto_routes.py` — if it uses a different sys.path idiom, copy that instead.)

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_fill_michelin.py -v
```
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

In `fill_michelin.py` add:

```python
def atomic_write_text(path, text):
    """Write text to path via a .tmp sibling + os.replace (crash-safe)."""
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)
```

Ensure `import os` and `from pathlib import Path` exist (the script already uses `Path` for `HTML_FILE`). Replace:

```python
    HTML_FILE.write_text(new_html, encoding='utf-8')
```

with:

```python
    atomic_write_text(HTML_FILE, new_html)
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_fill_michelin.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add fill_michelin.py tests/test_fill_michelin.py
git commit -m "fix(scripts): atomic write for HTML in fill_michelin"
```

---

### Task 7: Closure-aware route planning (feature)

When a planned route crosses a waterway with an active or upcoming closure, show a 🚧 warning card in the results — same integration pattern as the 🌊 tidal card. Matching is by normalized waterway name: closure `waterway` (e.g. `"Canal du Midi"`) vs segment `routeName` (e.g. `"Canal du Midi"`, `"River Seine (Le Havre–Paris)"`), substring match in either direction.

**Files:**
- Modify: `french_canals_map.html` — add two helpers next to `_getTidalWarnings` (~line 4379), hook into `renderMultiStopResults` (~line 5493, right after the tidal card) and `renderRouteResults` (~line 5090s, after its tidal card hook if present — grep `_buildTidalCardHTML` for both call sites).

- [ ] **Step 1: Add the matching helper**

Insert after `_getTidalWarnings` (keep the same style):

```js
/* ── Closure warnings for the route planner ──────────────────────────
 * _getClosureWarnings(segments) — walks route segments, returns closures
 * (active, or upcoming within 90 days) whose waterway name matches a
 * segment's routeName. Matching is normalised-substring in either
 * direction so "Canal du Midi" matches "Canal du Midi (Toulouse–Sète)".
 */
function _normWaterwayName(s) {
  return (s || '').toLowerCase()
    .normalize('NFD').replace(/[̀-ͯ]/g, '')   // strip accents
    .replace(/\(.*?\)/g, ' ')                            // drop parentheticals
    .replace(/[^a-z0-9]+/g, ' ').trim();
}

function _getClosureWarnings(segments) {
  if (!segments || !segments.length || !CLOSURES || !CLOSURES.length) return [];
  var now = new Date();
  var segNames = [];
  var seen = {};
  segments.forEach(function(seg) {
    var n = _normWaterwayName(seg.routeName || seg.waterway || '');
    if (n && !seen[n]) { seen[n] = true; segNames.push(n); }
  });
  var out = [];
  CLOSURES.forEach(function(ch) {
    var endDate = new Date(ch.end);
    var startDate = new Date(ch.start);
    if (endDate < now) return;                                   // expired
    if ((startDate - now) / 86400000 > 90) return;               // too far out
    var cw = _normWaterwayName(ch.waterway);
    if (!cw) return;
    var hit = segNames.some(function(sn) {
      return sn.indexOf(cw) !== -1 || cw.indexOf(sn) !== -1;
    });
    if (hit) out.push(Object.assign({ _active: startDate <= now }, ch));
  });
  return out;
}
```

- [ ] **Step 2: Add the card builder**

Insert directly after `_getClosureWarnings`:

```js
function _buildClosureCardHTML(closures) {
  if (!closures || !closures.length) return '';
  var FLAG = { FR:'🇫🇷', NL:'🇳🇱', DE:'🇩🇪', BE:'🇧🇪', AT:'🇦🇹' };
  var rows = closures.map(function(ch) {
    var flag = FLAG[ch.country] || '🏳';
    var status = ch._active
      ? '<strong style="color:#ffcdd2">ACTIVE now</strong>'
      : 'upcoming ' + ch.start;
    var link = ch.source_url
      ? ' <a href="' + ch.source_url + '" target="_blank" style="color:#ffe082">verify →</a>'
      : '';
    return flag + ' <strong>' + ch.waterway + '</strong>' +
      (ch.section ? ' (' + ch.section + ')' : '') +
      ' — ' + status + ' · ' + ch.start + ' → ' + ch.end +
      '<br><small>' + (ch.desc || '') + link + '</small>';
  });
  return '<div class="rp-nav-warning" style="background:#8d4a12">🚧 <strong>Closure' +
    (closures.length > 1 ? 's' : '') + ' on this route:</strong><br>' +
    rows.join('<br>') + '</div>';
}
```

- [ ] **Step 3: Hook into both result renderers**

Find every call site of `_buildTidalCardHTML(` (there should be one in `renderMultiStopResults` ~line 5492 and possibly one in `renderRouteResults`). Immediately after each:

```js
  // ── Closure warnings (Wave 4 data meets the route planner) ──
  if (typeof _getClosureWarnings === 'function') {
    html += _buildClosureCardHTML(_getClosureWarnings(allSegs));
  }
```

In `renderRouteResults` the segments variable is `segs`, not `allSegs` — use the local name. If `renderRouteResults` has no tidal hook, add the closure hook after its vessel-warning block instead.

- [ ] **Step 4: Syntax-check** (Task 1 Step 3 recipe). Expected: `SYNTAX-OK`.

- [ ] **Step 5: Manual verification via local server**

```bash
python3 -m http.server 8765 &
```
Open `http://localhost:8765/french_canals_map.html`, plan a route over a waterway with a seeded upcoming closure (check `data/closures.json` for a waterway that has a curated route — e.g. Canal du Midi if entry survives the Task 3 prune, else pick any FR entry with `end >= today` and plan across that canal). Expected: 🚧 card appears above the legs. Also toggle 🚧 Closures layer — markers must render (Task 1 regression check). Kill the server after.

- [ ] **Step 6: Commit**

```bash
git add french_canals_map.html
git commit -m "feat(planner): warn when planned route crosses an active/upcoming closure"
```

---

### Task 8: Vessel-profile trip duration estimates (feature)

Replace the crude `Math.ceil(dist / 35)` day estimate (3 sites: lines ~5113, ~5415, ~5508) with a calculation using the vessel profile's `cruiseSpeed` (default 7 km/h) and `hoursPerDay` (default 8), plus 15 min per lock — the standard canal rule of thumb.

**Files:**
- Modify: `french_canals_map.html` — new helper + 3 call sites

- [ ] **Step 1: Add the helper**

Insert near `_vesselCheckSegment` / other profile helpers (grep `function _vesselCheckSegment` and put it adjacent):

```js
/* Trip duration from distance + lock count using the vessel profile.
 * Rule of thumb: cruising time = km / cruiseSpeed, plus 15 min per lock.
 * Returns { days, hours, speed, hoursPerDay }. */
function _estimateTripDays(distKm, locks) {
  var p = _vesselProfile || {};
  var speed = (p.cruiseSpeed > 0) ? p.cruiseSpeed : 7;
  var hpd   = (p.hoursPerDay > 0) ? p.hoursPerDay : 8;
  var hours = distKm / speed + (locks || 0) * 0.25;
  return { days: Math.max(1, Math.ceil(hours / hpd)), hours: hours, speed: speed, hoursPerDay: hpd };
}
```

- [ ] **Step 2: Replace the three estimate sites**

Site A — `renderRouteResults` (~5113):
```js
  const estDays = Math.ceil(totalDist / 35);
```
→
```js
  const _est = _estimateTripDays(totalDist, totalLocks);
  const estDays = _est.days;
```

Site B — `renderMultiStopResults` (~5415): identical replacement (`totalDist`, `totalLocks` are in scope there too).

Site C — per-leg subtotal (~5508):
```js
        <span>⏱ ~${Math.ceil(legDist/35)} days</span>
```
→
```js
        <span>⏱ ~${_estimateTripDays(legDist, legLocks).days} days</span>
```

- [ ] **Step 3: Show the assumptions under the Est. Days stat**

In both summary grids, the stat cell reads:
```js
      <div class="rp-stat"><span class="val">${estDays}</span><div class="lbl">Est. Days</div></div>
```
→
```js
      <div class="rp-stat"><span class="val">${estDays}</span><div class="lbl">Est. Days</div><div class="lbl" style="opacity:.7">${_est.speed} km/h · ${_est.hoursPerDay} h/day</div></div>
```

- [ ] **Step 4: Syntax-check** (Task 1 Step 3 recipe). Expected: `SYNTAX-OK`. Then grep:

```bash
grep -n "/ 35\|/35" french_canals_map.html | grep -v http
```
Expected: no remaining estimate sites.

- [ ] **Step 5: Manual verification**

Local server: plan any route; Est. Days must reflect profile (change cruiseSpeed in ⚓ profile modal from 7 → 14, recalc, days should drop roughly in half).

- [ ] **Step 6: Commit**

```bash
git add french_canals_map.html
git commit -m "feat(planner): trip duration from vessel cruiseSpeed/hoursPerDay + lock time"
```

---

### Task 9: SW version bump + docs touch-up

**Files:**
- Modify: `sw.js:17` (`fc-v10` → `fc-v11`)
- Modify: `CLAUDE.md` (closures section + key-functions table)

- [ ] **Step 1: Bump SW VERSION**

```js
const VERSION    = 'fc-v11';
```

- [ ] **Step 2: CLAUDE.md updates**

In the closures section note: closures now also surface as a 🚧 warning card in route-planner results via `_getClosureWarnings(segments)` / `_buildClosureCardHTML(list)` (matching mirrors the tidal card). In the sw.js file-structure line, update `VERSION = fc-v6` mention to `fc-v11`. Add `_estimateTripDays(distKm, locks)` to the key-functions table.

- [ ] **Step 3: Commit**

```bash
git add sw.js CLAUDE.md
git commit -m "chore: bump SW to fc-v11, document closure card + duration helper"
```

---

### Task 10: Full test suite + push + PR

- [ ] **Step 1: Run the whole Python suite**

```bash
source venv/bin/activate && python3 -m pytest tests/ -v
```
Expected: all pass (~30 tests incl. 2 new).

- [ ] **Step 2: Final smoke greps**

```bash
grep -n "CHOMAGES_SEED" french_canals_map.html          # expect: nothing
grep -c "fc-closures-v2" french_canals_map.html          # expect: 1
python3 -c "import json; json.load(open('data/closures.json')); print('json ok')"
```

- [ ] **Step 3: Push + open PR**

```bash
git push -u origin audit-fixes-closures-duration
gh pr create --title "Audit fixes: repair closures layer, closure-aware routing, trip duration estimates" --body "$(cat <<'EOF'
## Summary
- **Fix**: 🚧 Closures layer was broken since Wave 4 (`CHOMAGES_SEED` ReferenceError) — now renders from `CLOSURES`
- **Fix**: guard `JSON.parse` on saved-routes + vessel-profile localStorage keys
- **Fix**: Overpass User-Agent in patch_lyon_waterways.py; atomic writes in fill_michelin.py + fill_auto_routes.py
- **Chore**: pruned 12 expired closures, cache key → fc-closures-v2, SW → fc-v11
- **Feat**: route planner warns when a planned route crosses an active/upcoming (≤90 days) closure
- **Feat**: Est. Days now uses vessel cruiseSpeed + hoursPerDay + 15 min/lock instead of km/35

## Test plan
- [x] pytest suite passes (incl. 2 new atomic-write tests)
- [x] node --check on extracted script block
- [ ] Manual: toggle 🚧 Closures layer, plan route across a closed waterway, verify card + Est. Days changes with profile speed

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review notes

- Spec coverage: all 6 quick fixes + 2 features from the approved batch have tasks. The "closure expiry filtering" item from the audit turned out to already exist in the UI (line 3869) — scope reduced to data-prune (Task 3), documented above.
- Type consistency: `_getClosureWarnings` returns closure objects with `_active` flag; `_buildClosureCardHTML` consumes exactly those fields (`country`, `waterway`, `section`, `start`, `end`, `desc`, `source_url`, `_active`) — all present in the closures.json schema.
- `renderRouteResults` (single-stop) vs `renderMultiStopResults`: both get the closure hook and the duration replacement; local segment variable names differ (`segs` vs `allSegs`) and Task 7/8 call this out.
