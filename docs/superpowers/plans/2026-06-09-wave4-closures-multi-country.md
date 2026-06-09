# Wave 4: Multi-Country Closures (FR + NL + DE + BE + AT) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing France-only chômages layer to cover navigation closures in 5 countries (FR, NL, DE, BE, AT) using the same hand-curated seed pattern that already works for France, plus add deep-link fallbacks for the 5 countries where we don't curate closures (UK/IE/IT/CH/LU).

**Architecture:** No live API integration. Wave 4 keeps the existing France-tested pattern — a static `CLOSURES` array loaded from `data/closures.json` and rendered by `buildClosuresMarkers()` — and extends it with country-tagged entries for NL/DE/BE/AT. Each entry retains a deep-link to its authority's official portal for verification. Layer / variable names rename from "chomages" (French) to "closures" (neutral). The seed is refreshed manually each season (no API, no proxy, no CORS).

**Tech Stack:** Vanilla JS (Leaflet markers + Cache-API `_loadData` pattern from Wave 1). Static JSON. No new runtime dependencies.

**Spec reference:** `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md` §6 (Wave 4) — note: the spec implied live adapters, but the existing FR chômages are already seeded, and the user has chosen to extend that proven pattern rather than introduce CORS-prone live adapters.

**Prerequisites:** Wave 3's PR #6 merged to `main` (✅ done as of 2026-06-09).

**Out of scope (later):**
- Live API adapters for any country (CORS risk; can revisit if a working proxy emerges).
- Wave 5 (curated routes, constraints, auto-derived routes).
- A periodic refresh GitHub Action — the closure data changes weekly during the season and a stale cron PR is worse than no automation.

---

## File Structure

**Created:**
- `data/closures.json` — array of closure entries, multi-country, country-tagged. Replaces the in-HTML `CHOMAGES_SEED` const.

**Modified:**
- `french_canals_map.html` — extract `CHOMAGES_SEED` const → `_loadData` call; rename `chomagesGroup` → `closuresGroup`, `buildChomagesMarkers` → `buildClosuresMarkers`, `layerState.chomages` → `layerState.closures`; update the layer-toggle button label "🚧 Chômages" → "🚧 Closures"; popup template adds country flag emoji + country-specific authority link.
- `sw.js` — `SHELL_URLS` += `data/closures.json`; `VERSION` bump `fc-v8 → fc-v9`.
- `CLAUDE.md` — document the new file layout, per-country authority links, refresh workflow.

**Deferred to a future wave:**
- Live API integration. The seed is the canonical source for now.

---

## Task 1: Branch off main

**Files:** none (git only)

- [ ] **Step 1.1: Sync main + create branch**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
git fetch origin
git checkout main
git pull origin main
git checkout -b wave4-closures-multi-country
```

Expected: `Switched to a new branch 'wave4-closures-multi-country'`.

- [ ] **Step 1.2: Verify the existing chômages layer still works**

```bash
grep -n "CHOMAGES_SEED\|buildChomagesMarkers\|chomagesGroup\|layerState.chomages" french_canals_map.html | wc -l
```

Expected: ≥ 6 hits. These are the references we'll be renaming.

---

## Task 2: Extract `CHOMAGES_SEED` → `data/closures.json`

This task mirrors what Wave 1 did for `WAYPOINTS`, `MOORINGS`, etc. — move the in-HTML const to a versioned JSON file loaded via `_loadData`.

**Files:**
- Create: `data/closures.json`
- Modify: `french_canals_map.html` — replace the const block with `let CLOSURES = []`; add `_loadData` call

- [ ] **Step 2.1: Find the const block**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
awk '/^const CHOMAGES_SEED = \[/{print NR; f=1; next} f && /^\];$/{print NR; exit}' french_canals_map.html
```

Record start and end line numbers. Both will be passed to the Python extractor.

- [ ] **Step 2.2: Extract to JSON with country tagging**

```bash
python3 - <<'PYEOF'
import re, json
with open('french_canals_map.html') as f: src = f.read()
m = re.search(r'^const CHOMAGES_SEED = (\[[\s\S]*?\n\]);$', src, re.M)
assert m, 'CHOMAGES_SEED block not found'
js = m.group(1)
# Convert JS object literal to JSON
js = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', js)
js = js.replace("'", '"')
js = re.sub(r',(\s*[\]\}])', r'\1', js)
# Strip JS line comments — appear inside the array
js = re.sub(r'^\s*//.*$', '', js, flags=re.M)
data = json.loads(js)
# Add country: 'FR' to every existing entry + a default source_url
for entry in data:
    entry.setdefault('country', 'FR')
    entry.setdefault('source_url', 'https://www.vnf.fr/vnf/vnf-gere-le-reseau/les-chomages/')
with open('data/closures.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Wrote {len(data)} closure entries, all tagged country=FR')
PYEOF
```

Expected: `Wrote 15 closure entries, all tagged country=FR` (count from the existing CHOMAGES_SEED). Verify:

```bash
python3 -c "import json; d=json.load(open('data/closures.json')); print(len(d), 'entries'); print(d[0])"
```

The first entry should have `id`, `waterway`, `section`, `start`, `end`, `lat`, `lon`, `type`, `desc`, `country='FR'`, `source_url=...`.

- [ ] **Step 2.3: Replace the const block with a `let` declaration**

In `french_canals_map.html`, replace the entire `const CHOMAGES_SEED = [...];` block with:

```js
let CLOSURES = [];
```

(Note the rename: `CHOMAGES_SEED` → `CLOSURES`. The lowercase + plural form matches the new generic name.)

- [ ] **Step 2.4: Add the `_loadData` call**

The existing data-file loaders are clustered together in `buildMarkers()`'s preamble (find by `grep -n "_loadData('fc-waypoints" french_canals_map.html`). Add a new loader right after that group:

```js
  _loadData('fc-closures-v1', './data/closures.json', function(data) {
    CLOSURES = data;
    if (layerState.closures && typeof buildClosuresMarkers === 'function') {
      buildClosuresMarkers();
    }
  }, function() { showEditToast('⚠ Closures failed to load'); });
```

Note: the loader's `onLoad` callback rebuilds the layer IF it's currently visible — handles the case where the user toggles the layer ON before the JSON has finished fetching.

- [ ] **Step 2.5: Reload + verify**

Start the local server in another shell (`python3 -m http.server 8765` from project root). Open `http://localhost:8765/french_canals_map.html` and click "🚧 Chômages" in the controls. Markers should still appear on the map. Console should show no errors.

- [ ] **Step 2.6: Commit**

```bash
git add data/closures.json french_canals_map.html
git commit -m "refactor(closures): extract CHOMAGES_SEED to data/closures.json + country field

Every existing entry tagged country='FR'. Loader pattern matches Wave 1's
data-file extractions (cache-first + ETag refresh). No behavioural change."
```

---

## Task 3: Rename `chomagesGroup` → `closuresGroup` (Leaflet layer)

**Files:**
- Modify: `french_canals_map.html` (multiple references)

- [ ] **Step 3.1: Find every reference**

```bash
grep -n "chomagesGroup" french_canals_map.html
```

Expected: 4-6 hits (declaration + addLayer/removeLayer in `toggleLayer` + `chomagesGroup.addLayer(marker)` inside builder + possibly an init call).

- [ ] **Step 3.2: Rename**

```bash
# macOS sed: -i with backup, then remove backup
sed -i.bak 's/chomagesGroup/closuresGroup/g' french_canals_map.html
rm french_canals_map.html.bak
grep -c "chomagesGroup" french_canals_map.html   # expect 0
grep -c "closuresGroup" french_canals_map.html   # expect same count as before
```

- [ ] **Step 3.3: Reload + smoke-test**

Hard-refresh the page. Click the closures toggle — markers should still render. Toggling off should remove them. Console clear.

- [ ] **Step 3.4: Commit**

```bash
git add french_canals_map.html
git commit -m "refactor(closures): rename chomagesGroup → closuresGroup (Leaflet layer)"
```

---

## Task 4: Rename `buildChomagesMarkers` → `buildClosuresMarkers` + `layerState.chomages` → `layerState.closures`

**Files:**
- Modify: `french_canals_map.html`

- [ ] **Step 4.1: Survey references**

```bash
grep -n "buildChomagesMarkers\|layerState\.chomages\|layerState\['chomages'\]\|'chomages'" french_canals_map.html
```

Expected ~6-8 hits across function definition, the layer-toggle dispatch in `toggleLayer()`, the layerState default object, and the loader call added in Task 2.

- [ ] **Step 4.2: Rename**

```bash
sed -i.bak \
  -e 's/buildChomagesMarkers/buildClosuresMarkers/g' \
  -e "s/layerState\\.chomages/layerState.closures/g" \
  french_canals_map.html
rm french_canals_map.html.bak
```

Now find any remaining string-key references (`'chomages'` used as an object property key or a string compare in `toggleLayer(type)`):

```bash
grep -n "'chomages'" french_canals_map.html
```

For each hit, change `'chomages'` → `'closures'`. Critical hits will be in:
- The `layerState` default-state object literal (`{ ... chomages: false ... }` — this is a property name, not a string, so sed already handled it via the `layerState.chomages` substitution; verify)
- The `toggleLayer('chomages')` switch case (`else if (type === 'chomages')` → `else if (type === 'closures')`)
- The HTML `onclick="toggleLayer('chomages')"` attribute on the toggle button (Task 5 deals with the button label separately; the onclick string also needs updating)

Use Edit / sed carefully for each occurrence — they're string literals, not identifiers.

- [ ] **Step 4.3: Verify zero stragglers**

```bash
grep -cE "chomages|Chomages|CHOMAGES" french_canals_map.html
```

Expected: 0 (case-insensitive). If non-zero, inspect each remaining hit:

```bash
grep -nE "chomages|Chomages|CHOMAGES" french_canals_map.html
```

The Wave 1 deep-link `🚧 Chômages` in the sidebar at line ~6297 (`grep "VNF Chômages"`) contains the French word with the accent (`ô`). That's user-facing translated text, not an identifier — leave it as-is. Only ASCII `chomages` should be 0.

- [ ] **Step 4.4: Reload + smoke-test**

Hard-refresh, click "🚧 Chômages" toggle, verify markers appear. Toggle off — markers vanish. Console clear.

- [ ] **Step 4.5: Commit**

```bash
git add french_canals_map.html
git commit -m "refactor(closures): rename CHOMAGES_SEED/buildChomagesMarkers/layerState.chomages → CLOSURES/buildClosuresMarkers/layerState.closures

Identifier-only rename; user-visible 'Chômages' button text unchanged
(that gets refreshed in Task 5 alongside the popup country-tag work)."
```

---

## Task 5: Update `buildClosuresMarkers` popup to include country flag + per-country authority link

The renamed `buildClosuresMarkers` currently hardcodes "🚧 Chômage" in the popup title and the VNF deep-link. After this task it reads `country` and `source_url` from each entry and renders country-appropriate decoration.

**Files:**
- Modify: `french_canals_map.html` — `buildClosuresMarkers` function body

- [ ] **Step 5.1: Read the current function**

```bash
grep -n "function buildClosuresMarkers" french_canals_map.html
```

Read the function (it's ~45 lines).

- [ ] **Step 5.2: Add a flag-emoji lookup + replace popup template**

Inside `buildClosuresMarkers`, immediately after `chomagesGroup.clearLayers()` (now `closuresGroup.clearLayers()`), add:

```js
  var FLAG = { FR:'🇫🇷', NL:'🇳🇱', DE:'🇩🇪', BE:'🇧🇪', AT:'🇦🇹' };
```

Then find the `var popupHtml = '...'` template (~5 lines of HTML construction). Replace the entire `var popupHtml = '<div...` through `'</div>';` block with:

```js
    var flag = FLAG[ch.country] || '🏳';
    var authorityLabel = ch.country === 'FR' ? 'VNF'
                       : ch.country === 'NL' ? 'Rijkswaterstaat'
                       : ch.country === 'DE' ? 'WSV / ELWIS'
                       : ch.country === 'BE' ? 'DVW / SPW'
                       : ch.country === 'AT' ? 'viadonau / DoRIS'
                       : 'authority';
    var sourceUrl = ch.source_url || '#';
    var popupHtml = '<div style="min-width:210px">' +
      '<div style="font-size:10px;color:#e87a7a;margin-bottom:4px;font-weight:600">⚠ Curated — always verify with the ' + authorityLabel + '</div>' +
      '<div style="font-weight:700;font-size:13px;margin-bottom:4px">' + flag + ' 🚧 Closure · ' + statusLabel + '</div>' +
      '<div style="font-size:12px;color:#f0ad4e;margin-bottom:4px;font-weight:600">' + ch.waterway + '</div>' +
      sectionHtml +
      '<div style="font-size:11px;color:#8ab4c2;margin-bottom:2px">' + typeLabel + '</div>' +
      '<div style="font-size:11px;color:#aaa;margin-bottom:6px">' + dateStr + '</div>' +
      '<div style="font-size:12px;margin-bottom:8px">' + ch.desc + '</div>' +
      '<a href="' + sourceUrl + '" target="_blank" style="font-size:11px;color:#5bc0de">📋 View on ' + authorityLabel + ' →</a>' +
      '</div>';
```

Key changes:
- "Chômage" → "Closure" in the popup title (now neutral)
- Country flag prefixed to the title
- "Verify on VNF" → "Verify with the <authority>"
- Source-URL link uses per-entry `ch.source_url` (was hardcoded VNF)

- [ ] **Step 5.3: Reload + spot-check**

Click any France closure marker. Expected: popup title now shows "🇫🇷 🚧 Closure · 🟡 Upcoming" (or 🔴 ACTIVE), the "Verify on VNF" link works, the rest of the layout is unchanged.

- [ ] **Step 5.4: Commit**

```bash
git add french_canals_map.html
git commit -m "feat(closures): country flag + per-country authority link in popup

Reads ch.country and ch.source_url. Authority label mapped per country.
Existing FR closures display correctly with 🇫🇷 + VNF link."
```

---

## Task 6: Update the controls-bar toggle label (`🚧 Chômages` → `🚧 Closures`)

**Files:**
- Modify: `french_canals_map.html` (the button at ~line 1609)

- [ ] **Step 6.1: Find the button**

```bash
grep -n "toggle-chomages\|>🚧 Chômages\|Chômages\|🚧 Chômages" french_canals_map.html
```

There should be one toggle button (~line 1609) plus possibly an ID `id="toggle-chomages"`.

- [ ] **Step 6.2: Rewrite the button**

Find:
```html
<button class="toggle-btn" id="toggle-chomages" onclick="toggleLayer('chomages')" title="VNF maintenance closures">🚧 Chômages</button>
```

Replace with:
```html
<button class="toggle-btn" id="toggle-closures" onclick="toggleLayer('closures')" title="Navigation closures (FR/NL/DE/BE/AT)">🚧 Closures</button>
```

Then verify any other `toggle-chomages` references are also updated (e.g. `document.getElementById('toggle-chomages')` for visual-state toggling):

```bash
grep -n "toggle-chomages\|toggle-closures" french_canals_map.html
```

If any `toggle-chomages` remain, edit each one to `toggle-closures`.

- [ ] **Step 6.3: Reload + click**

Verify the button now reads "🚧 Closures" and toggling still shows/hides the markers.

- [ ] **Step 6.4: Commit**

```bash
git add french_canals_map.html
git commit -m "feat(ui): rename layer toggle to '🚧 Closures' (was 'Chômages')

Multi-country layer needs a neutral label. Updated tooltip lists the
covered countries."
```

---

## Task 7: Curate NL closures (Rijkswaterstaat Stremmingen)

This task uses a WebFetch to read the current Rijkswaterstaat stremmingen portal and produces 4-8 curated entries. The data refreshes weekly during the season; we capture a current snapshot in `data/closures.json`.

**Files:**
- Modify: `data/closures.json`

- [ ] **Step 7.1: Fetch the current Rijkswaterstaat stremmingen list**

Use a browser or the WebFetch tool to load:
- https://www.vaarweginformatie.nl/frp/main/#/page/sluis/stremmingen — the public Stremmingen / Notice-to-Skippers index
- Alternative: https://www.rijkswaterstaat.nl/water/wetten-regels-en-vergunningen/scheepvaartverkeer (links to the active notices)

Identify 4-8 representative active or imminent closures (within next 90 days). For each, capture:
- Waterway (canonical Dutch name; e.g. "Amsterdam-Rijnkanaal", "Maas", "Waal")
- Section (between two locks or towns; e.g. "Sluis Maasbracht")
- Start/end ISO dates
- Lat/lon (approximate the section midpoint; the RWS portal often shows a map)
- Type ('travaux' for maintenance / 'hivernage' if winter / 'incident' for unplanned)
- Short description (1 sentence; "Sluis renovation", "Brug schoonmaak", etc.)
- The direct portal URL where this closure was found — becomes `source_url`

If no current closures are visible (rare — there's almost always one), seed with two placeholder entries marked `desc: "No active NL closures at this time — refresh from RWS Stremmingen portal next season"` and disable them with an `end` date in the past (so `buildClosuresMarkers` filters them out at render time).

- [ ] **Step 7.2: Append to `data/closures.json`**

Edit `data/closures.json` and add the NL entries to the array. Each entry must have:

```jsonc
{
  "id": "cl_nl_001",
  "country": "NL",
  "waterway": "Amsterdam-Rijnkanaal",
  "section": "Sluis Princess Beatrix",
  "lat": 51.987,
  "lon": 5.122,
  "start": "2026-06-15",
  "end": "2026-06-22",
  "type": "travaux",
  "desc": "Sluis maintenance — single chamber operation",
  "source_url": "https://www.vaarweginformatie.nl/frp/main/#/page/sluis/stremmingen"
}
```

Use sequential IDs `cl_nl_001`, `cl_nl_002`, … per country. Coordinates need to be at the section midpoint, not the waterway centerline — so the marker lands on the actual closure location.

- [ ] **Step 7.3: Validate JSON**

```bash
python3 -c "import json; d=json.load(open('data/closures.json')); print(len(d), 'total,', len([x for x in d if x['country']=='NL']), 'NL')"
```

- [ ] **Step 7.4: Reload + visual check**

Reload `http://localhost:8765/french_canals_map.html`, enable the closures layer, pan to the Netherlands. Markers should render in the right spots with 🇳🇱 flag + Rijkswaterstaat attribution in the popup.

- [ ] **Step 7.5: Commit**

```bash
git add data/closures.json
git commit -m "data(closures): seed NL closures from Rijkswaterstaat Stremmingen portal

Snapshot as of 2026-06-09. Refresh manually each season per the recipe
in CLAUDE.md → 'Refresh closures'."
```

---

## Task 8: Curate DE closures (ELWIS / WSV)

**Files:**
- Modify: `data/closures.json`

- [ ] **Step 8.1: Fetch the current ELWIS Schifffahrtspolizeiliche Bekanntmachungen (notices)**

Browse / WebFetch:
- https://www.elwis.de/DE/Service/Schifffahrtspolizeiliche-Bekanntmachungen-und-Anordnungen/Schifffahrtspolizeiliche-Bekanntmachungen-und-Anordnungen-node.html
- Or per-waterway: https://www.elwis.de/DE/Schifffahrtsinformationen/Sperrungen-und-Einschraenkungen/Sperrungen-und-Einschraenkungen-node.html

Pick 4-8 entries on the Rhein, Mosel, Main, or Main-Donau-Kanal. Same fields as Task 7.

- [ ] **Step 8.2: Append entries to `data/closures.json`**

Use IDs `cl_de_001`, etc. Example:

```jsonc
{
  "id": "cl_de_001",
  "country": "DE",
  "waterway": "Mosel",
  "section": "Schleuse Koblenz",
  "lat": 50.353,
  "lon": 7.605,
  "start": "2026-06-20",
  "end": "2026-06-21",
  "type": "travaux",
  "desc": "Single-chamber operation overnight",
  "source_url": "https://www.elwis.de/DE/Service/Schifffahrtspolizeiliche-Bekanntmachungen-und-Anordnungen/Schifffahrtspolizeiliche-Bekanntmachungen-und-Anordnungen-node.html"
}
```

- [ ] **Step 8.3: Validate + visual check + commit**

```bash
python3 -c "import json; d=json.load(open('data/closures.json')); print(len(d), 'total,', len([x for x in d if x['country']=='DE']), 'DE')"
git add data/closures.json
git commit -m "data(closures): seed DE closures from WSV / ELWIS notices"
```

---

## Task 9: Curate BE closures (DVW Flanders + SPW Wallonia)

Belgium splits navigation responsibility between regions. We grab a couple of entries from each region's portal.

**Files:**
- Modify: `data/closures.json`

- [ ] **Step 9.1: Fetch DVW (Flanders) notices**

- https://www.visuris.be/Berichten — "Berichten aan de schipperij" / NtS
- Alt: https://www.vlaamsewaterweg.be/scheepvaartberichten

- [ ] **Step 9.2: Fetch SPW (Wallonia) notices**

- https://voies-hydrauliques.wallonie.be/opencms/opencms/fr/avis-aux-navigants/ — Avis aux navigants

Pick 2-3 Flanders entries (Albertkanaal, Schelde, Leie) and 1-2 Wallonia entries (Sambre, Meuse-Wallonie, Canal du Centre BE).

- [ ] **Step 9.3: Append to `data/closures.json`**

Use IDs `cl_be_001`+. Tag all as `country: 'BE'`. Use the source_url for the specific region (DVW vs SPW) so popups deep-link correctly.

Example DVW:
```jsonc
{
  "id": "cl_be_001",
  "country": "BE",
  "waterway": "Albertkanaal",
  "section": "Sluis Wijnegem",
  "lat": 51.230, "lon": 4.522,
  "start": "2026-07-01", "end": "2026-07-05",
  "type": "travaux",
  "desc": "Lock maintenance — restricted hours",
  "source_url": "https://www.visuris.be/Berichten"
}
```

Example SPW:
```jsonc
{
  "id": "cl_be_004",
  "country": "BE",
  "waterway": "Meuse",
  "section": "Écluse de Lanaye",
  "lat": 50.795, "lon": 5.682,
  "start": "2026-08-10", "end": "2026-08-18",
  "type": "travaux",
  "desc": "Lock chamber maintenance",
  "source_url": "https://voies-hydrauliques.wallonie.be/opencms/opencms/fr/avis-aux-navigants/"
}
```

- [ ] **Step 9.4: Validate + commit**

```bash
python3 -c "import json; d=json.load(open('data/closures.json')); print(len(d), 'total,', len([x for x in d if x['country']=='BE']), 'BE')"
git add data/closures.json
git commit -m "data(closures): seed BE closures from DVW (Flanders) + SPW (Wallonia)"
```

---

## Task 10: Curate AT closures (viadonau / DoRIS)

**Files:**
- Modify: `data/closures.json`

- [ ] **Step 10.1: Fetch viadonau Notice-to-Skippers**

- https://www.doris.bmk.gv.at/ — DoRIS public portal (German + English)
- Or the NtS feed: https://www.doris.bmk.gv.at/NtS

Austria is essentially the Danube. Pick 2-4 entries on the Austrian Danube stretch (Passau → Vienna → Bratislava border).

- [ ] **Step 10.2: Append to `data/closures.json`**

```jsonc
{
  "id": "cl_at_001",
  "country": "AT",
  "waterway": "Donau",
  "section": "Schleuse Ottensheim-Wilhering",
  "lat": 48.328, "lon": 14.155,
  "start": "2026-07-15", "end": "2026-07-17",
  "type": "travaux",
  "desc": "Lock inspection — alternating chambers",
  "source_url": "https://www.doris.bmk.gv.at/"
}
```

- [ ] **Step 10.3: Commit**

```bash
git add data/closures.json
git commit -m "data(closures): seed AT closures from viadonau / DoRIS NtS"
```

---

## Task 11: Add deep-link fallback section for UK/IE/IT/CH/LU (no curated closures)

For the 5 countries where we don't curate closures, the sidebar (or controls bar legend) should expose a "Check official portal" link so users aren't left without information.

**Files:**
- Modify: `french_canals_map.html` — likely in the closures toggle's tooltip, OR a new info popup, OR a footer note.

- [ ] **Step 11.1: Decide the surface**

The simplest, least-invasive surface is to extend the closures toggle's `title` attribute to mention "FR/NL/DE/BE/AT only" (already done in Task 6) AND add a sidebar/footer note. Choose the approach that fits the existing UI — search for where other multi-country deep-links live (Wave 2's OSM "suggest edit" pattern is the model). The data-sources panel (`<div class="dp-attribution">`) at ~line 8239 is a good home.

- [ ] **Step 11.2: Add a new `<div class="dp-companion">`-style block or extend the closures section**

Find the existing data-sources `<ul>` and add a follow-up block after it:

```html
<div class="dp-attribution" style="margin-top:10px">
  <h5>Closures (not curated)</h5>
  <ul>
    <li>🇬🇧 UK &mdash; <a href="https://canalrivertrust.org.uk/notices" target="_blank" rel="noopener">CRT navigation notices</a></li>
    <li>🇮🇪 IE &mdash; <a href="https://www.waterwaysireland.org/marine-notices" target="_blank" rel="noopener">Waterways Ireland marine notices</a></li>
    <li>🇮🇹 IT &mdash; <a href="https://www.aipo.it/" target="_blank" rel="noopener">AIPo Po navigation notices</a></li>
    <li>🇨🇭 CH &mdash; <a href="https://www.portofswitzerland.ch/en/news-and-publications/" target="_blank" rel="noopener">Port of Switzerland (Rhine notices)</a></li>
    <li>🇱🇺 LU &mdash; Moselle covered under <strong>🇩🇪 WSV / ELWIS</strong> above</li>
  </ul>
</div>
```

- [ ] **Step 11.3: Reload + visual check**

Open the data-sources panel and verify the new "Closures (not curated)" section appears with 5 working links.

- [ ] **Step 11.4: Commit**

```bash
git add french_canals_map.html
git commit -m "feat(closures): deep-link section for UK/IE/IT/CH/LU (no curated coverage)

CRT, Waterways Ireland, AIPo, Port of Switzerland — each links direct to
that authority's notices page. LU defers to DE WSV (Moselle)."
```

---

## Task 12: Update service-worker cache + bump VERSION

**Files:**
- Modify: `sw.js`

- [ ] **Step 12.1: Add `closures.json` to precache list**

Find `SHELL_URLS` in `sw.js` and add `'./data/closures.json'` to the list (alongside the other `data/*.json` entries from Wave 1).

```js
const SHELL_URLS = [
  './',
  // ... existing entries ...
  './data/closures.json',   // NEW (Wave 4)
  // ... rest unchanged ...
];
```

The exact insertion order doesn't matter functionally — keep it grouped with the other `data/*.json` entries for readability.

- [ ] **Step 12.2: Bump `VERSION`**

```bash
grep "^const VERSION" sw.js   # expect: const VERSION    = 'fc-v8';
```

Edit line 17 to `const VERSION    = 'fc-v9';`.

- [ ] **Step 12.3: Verify**

```bash
grep "^const VERSION" sw.js
grep "closures.json" sw.js
```

Expected: VERSION = `fc-v9`; SHELL_URLS contains `closures.json`.

- [ ] **Step 12.4: Commit**

```bash
git add sw.js
git commit -m "chore(sw): precache closures.json, bump cache to fc-v9"
```

---

## Task 13: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 13.1: Find the existing chômages section (if any)**

```bash
grep -n "chomages\|chômage\|closures" CLAUDE.md
```

Likely zero or a brief mention.

- [ ] **Step 13.2: Add a "Multi-country closures" section**

Append (or insert near the existing data-file layout section):

```markdown
## Multi-country closures (Wave 4)

Navigation closures live in `data/closures.json` as a single array, country-tagged. The Leaflet layer (`closuresGroup`, toggled via `🚧 Closures`) renders each entry as a coloured circle marker (red = active, orange = upcoming within 180 days).

**Schema:**
```jsonc
{
  "id":          "cl_fr_001",    // 'cl_<cc>_<NNN>' or legacy 'ch_NNN' for pre-Wave-4 FR entries
  "country":     "FR | NL | DE | BE | AT",
  "waterway":    "Canal du Midi",
  "section":     "Béziers — Agde",
  "lat":         43.344, "lon": 3.218,
  "start":       "2026-06-01",   // ISO date
  "end":         "2026-06-12",
  "type":        "travaux | hivernage | incident",
  "desc":        "1-line summary",
  "source_url":  "https://www.vnf.fr/.../les-chomages/"
}
```

**Refresh workflow.** Each country's closures change weekly during the season. Refresh by:
1. Visiting the authority portal (see source_url in any existing entry of that country)
2. Picking 4-8 representative active or imminent (within 90 days) closures
3. Appending entries to `data/closures.json` (or replacing the country's section)
4. Bumping the cache key `'fc-closures-v1'` in `french_canals_map.html` to invalidate old caches

**Authority portals (cached in `source_url` field):**
- 🇫🇷 FR — VNF Chômages (`https://www.vnf.fr/vnf/vnf-gere-le-reseau/les-chomages/`)
- 🇳🇱 NL — Rijkswaterstaat Stremmingen (`https://www.vaarweginformatie.nl/frp/main/#/page/sluis/stremmingen`)
- 🇩🇪 DE — ELWIS Schifffahrtspolizeiliche Bekanntmachungen
- 🇧🇪 BE — DVW (Visuris.be for Flanders) + SPW (voies-hydrauliques.wallonie.be for Wallonia)
- 🇦🇹 AT — viadonau DoRIS

**Out-of-scope countries** (no curated closures, deep-link only): 🇬🇧 UK (CRT), 🇮🇪 IE (Waterways Ireland), 🇮🇹 IT (AIPo), 🇨🇭 CH (Port of Switzerland), 🇱🇺 LU (covered by 🇩🇪 DE on the Moselle).
```

- [ ] **Step 13.3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude-md): document multi-country closures schema + refresh recipe"
```

---

## Task 14: Smoke checks

**Files:** none (validation)

- [ ] **Step 14.1: Data integrity**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
python3 << 'PYEOF'
import json
from collections import Counter
d = json.load(open('data/closures.json'))
print(f'Total entries: {len(d)}')
print('By country:', dict(Counter(x.get('country','?') for x in d)))
# Every entry must have all required fields
required = {'id','country','waterway','lat','lon','start','end','type','desc','source_url'}
missing = [(x.get('id','?'), required - set(x)) for x in d if not required.issubset(x)]
if missing:
    print(f'\n⚠ {len(missing)} entries missing fields:')
    for eid, miss in missing[:5]: print(f'   {eid}: {miss}')
else:
    print('All entries have required fields ✓')
# Lat/lon plausibility
bad_coords = [x['id'] for x in d if not (35 <= x['lat'] <= 60 and -11 <= x['lon'] <= 20)]
print(f'Out-of-Europe coords: {bad_coords or "none"}')
# IDs unique
print(f'IDs unique: {len(d) == len(set(x["id"] for x in d))}')
PYEOF
```

Expected: all 5 country codes (FR, NL, DE, BE, AT) present, no missing fields, no out-of-Europe coords, IDs unique.

- [ ] **Step 14.2: HTML structural**

```bash
echo "Old identifier 'chomages' (ASCII only): $(grep -cE '\\bchomages\\b' french_canals_map.html)"     # expect 0
echo "New identifier 'closures' lookups: $(grep -cE '\\bclosures\\b' french_canals_map.html)"          # expect ≥ 6
echo "Flag emojis in popup builder: $(grep -c 'FLAG = ' french_canals_map.html)"                       # expect 1
echo "Per-country authority labels: $(grep -c 'authorityLabel' french_canals_map.html)"                # expect ≥ 1
echo "Deep-link section: $(grep -c 'Closures (not curated)' french_canals_map.html)"                   # expect 1
echo "SW VERSION:"
grep '^const VERSION' sw.js
echo "Closures cache key:"
grep "fc-closures-v" french_canals_map.html
```

- [ ] **Step 14.3: Manual visual smoke**

Hard-refresh `http://localhost:8765/french_canals_map.html` (Cmd+Shift+R). Click the closures toggle. Pan to each of:
- Auxerre → see FR closures with 🇫🇷 + "View on VNF →"
- Amsterdam → see NL closures with 🇳🇱 + "View on Rijkswaterstaat →"
- Köln → see DE closures with 🇩🇪 + "View on WSV / ELWIS →"
- Antwerp → see BE closures with 🇧🇪 + "View on DVW / SPW →"
- Vienna → see AT closures with 🇦🇹 + "View on viadonau / DoRIS →"

Open the data-sources panel — confirm the "Closures (not curated)" section lists UK/IE/IT/CH/LU with working links.

- [ ] **Step 14.4: No commit** (validation only). Fix on this branch before pushing.

---

## Task 15: Push branch + open PR

- [ ] **Step 15.1: Push**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
git push -u origin wave4-closures-multi-country
```

- [ ] **Step 15.2: Open PR**

Fill in `<X>` placeholders with the actual per-country counts from Task 14.1.

```bash
gh pr create --title "Wave 4: multi-country closures (FR + NL + DE + BE + AT)" --body "$(cat <<'EOF'
## Summary

Extends the existing France-only chômages layer to cover navigation closures in five countries, using the proven hand-curated seed pattern (no live APIs, no CORS risk).

- Renamed `chomagesGroup`/`buildChomagesMarkers`/`layerState.chomages` → `closuresGroup`/`buildClosuresMarkers`/`layerState.closures`.
- Extracted `CHOMAGES_SEED` const → `data/closures.json` (per Wave 1's `_loadData` pattern).
- Added country flag emoji + per-country authority link in popups.
- Seeded closures for NL/DE/BE/AT from each authority's current portal (snapshot 2026-06-09).
- For UK/IE/IT/CH/LU: added a "Closures (not curated)" deep-link section in the data-sources panel.
- SW `VERSION` bumped `fc-v8` → `fc-v9`.

## Country breakdown

| Country | Entries | Source |
|---------|--------:|--------|
| 🇫🇷 FR | <X> | VNF Chômages (existing) |
| 🇳🇱 NL | <X> | Rijkswaterstaat Stremmingen |
| 🇩🇪 DE | <X> | WSV / ELWIS notices |
| 🇧🇪 BE | <X> | DVW (Flanders) + SPW (Wallonia) |
| 🇦🇹 AT | <X> | viadonau DoRIS |
| 🇬🇧🇮🇪🇮🇹🇨🇭🇱🇺 | 0 | Deep-link only (CRT / Waterways Ireland / AIPo / Port of Switzerland) |

## Why not live APIs?

The existing FR chômages have always been hand-curated, not live-fetched. The Wave 4 spec assumed live adapters, but extending the proven seed pattern is simpler, has zero CORS risk, and matches the de-facto current implementation. Live adapters can land in a future wave once a CORS-friendly proxy or working browser-side endpoint emerges per authority.

## Refresh workflow

Closures change weekly during the season. Refresh by visiting each authority's portal (links in any popup or `CLAUDE.md` → "Multi-country closures"), picking 4-8 representative active/imminent entries, and editing `data/closures.json`. Bump `'fc-closures-v1'` to invalidate caches.

## Test plan

- [x] All 5 country codes present in `data/closures.json`
- [x] Every entry has required fields (id, country, waterway, lat, lon, start, end, type, desc, source_url)
- [x] All IDs unique
- [x] All lat/lon within Europe
- [x] Identifier rename complete (no `\bchomages\b` ASCII matches remain)
- [x] Cache version bumped to `fc-v9`; `closures.json` added to SW SHELL_URLS
- [ ] Manual: 5 country closures render with correct flag + authority link
- [ ] Manual: data-sources panel shows "Closures (not curated)" with 5 working links
- [ ] Manual: France behaviour byte-identical to before (the 15 existing FR entries unchanged)

Spec: `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md` §6
Plan: `docs/superpowers/plans/2026-06-09-wave4-closures-multi-country.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 15.3: Merge after review**

```bash
gh pr merge --squash --delete-branch
```

---

## Done criteria for Wave 4

- `main` contains `data/closures.json` with entries for all 5 curated countries (FR/NL/DE/BE/AT).
- The map's "🚧 Closures" toggle shows multi-country markers, each with country flag + authority deep-link.
- The 5 deep-link-only countries (UK/IE/IT/CH/LU) appear in the data-sources panel.
- Identifier rename complete (no lingering `chomages`).
- SW `VERSION` = `fc-v9`.
- France behaviour byte-identical to pre-Wave-4 for the 15 existing entries.

---

## Out of scope (explicit non-goals)

- Live API integration for any country (deferred until a working CORS strategy emerges).
- Periodic refresh automation (GitHub Action) — closure data changes too rapidly for stale cron PRs to be useful.
- Custom marker icons per country — current red/orange dot suffices.
- Filtering closures by date in the UI — the existing 180-day forward window in `buildClosuresMarkers` is enough.

---

## Self-review notes

Spec coverage check against `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md` §6:

| Spec requirement | Implemented in |
|---|---|
| Per-country closure coverage (FR + NL + DE + BE + AT) | Tasks 2 (FR extract) + 7-10 (others) |
| Normalised closure shape (id, country, waterway, lat, lon, start, end, type, desc, source_url) | Task 2 step 2.2 + smoke test in Task 14 |
| Country flag emoji + authority link in popup | Task 5 |
| UK/IE/IT/CH/LU deep-link fallback | Task 11 |
| `chomagesGroup` → `closuresGroup` rename | Task 3 |
| `buildChomagesMarkers` → `buildClosuresMarkers` rename | Task 4 |
| Cache versioning (precache + version bump) | Task 12 |
| Documentation in CLAUDE.md | Task 13 |
| Spec's "Never cached by SW" requirement for live feeds | N/A — we use a static JSON file precached on install; closures refresh by manual edit + cache-key bump, which is even simpler than the spec's design and avoids the stale-cache problem |

No placeholders. Identifier consistency verified: `CLOSURES`, `closuresGroup`, `buildClosuresMarkers`, `layerState.closures`, `'fc-closures-v1'`, `data/closures.json` — all match across tasks.

**Acknowledged divergence from spec:** The spec described live adapters with per-country APIs. This plan delivers the same user-visible feature (country-aware closure markers with authority links) via the proven seed-array pattern instead. The user explicitly chose this approach. Live adapters can be added in a follow-up wave once a CORS strategy is clear.
