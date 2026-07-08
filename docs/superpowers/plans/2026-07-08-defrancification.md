# De-Francification Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the France-only assumptions left over from the EU expansion: Europe-wide map defaults, per-country authority links instead of VNF-everywhere, country grouping in the route-planner dropdowns, and country-aware hint/search text.

**Architecture:** All changes in `french_canals_map.html` (single-file vanilla JS + Leaflet, no build step). A new `AUTHORITIES` country map powers both the sidebar authority section and future popups; the route-planner selects get country optgroups appended after the French section optgroups. Verification via `node --check` on the extracted script block + live preview server (port 8766, `.claude/launch.json`).

**Tech Stack:** Vanilla JS, Leaflet 1.9.4.

**Facts discovered during planning (trust these, verify with grep):**
- Map init `center: [46.8, 2.3]` at line ~2779.
- Planner default Le Havre→Lyon hardcoded at ~5300-5315 inside the dropdown-build function.
- Dropdown grouping `bySec` at ~5278; `sectionNames` maps only sections 1-9. **1,178 EU waypoints have `section: 0`** → they land in an optgroup labeled `Section 0`; **39 anchor waypoints (`w_a…`) have `section: 1` + a `country` field** → they wrongly appear under "Section 1 · Seine".
- `VNF_TERRITORIES` + `vnfLinksHTML(section, from, to)` at ~3273-3308; called at ~3393 (sidebar) and ~4269.
- Google search link with `' France canal moorings'` at ~3381.
- Vessel profile hint `French canal locks max ~38.5 m` at ~8387.
- IGN basemap button labeled "IGN France" at ~1580 (title says best for French waterways — factually fine, keep label but this is NOT the forced default; check which layer is default before changing anything).
- Authority URLs for UK/IE already exist in the data-sources panel ~8310-8320; Wave-4 closure popups have authority names per country (~3897).

**CRITICAL RULE:** never write the literal string `</script>` inside the script block.

---

### Task 0: Branch

- [ ] `git checkout main && git pull && git checkout -b defrancification`

---

### Task 1: Europe-wide map default view

**Files:** Modify `french_canals_map.html:2779`

- [ ] **Step 1:** Change the map init:

```js
  center: [46.8, 2.3],
```
→
```js
  center: [48.6, 5.5],   // between Paris and Frankfurt — shows FR + BeNeLux + DE at z6
```
Keep the existing `zoom` value unless the preview shows it cropping the network badly; if changing, prefer zoom 6.

- [ ] **Step 2:** Verify in preview (port 8766): initial view should show France through the Netherlands/Germany with waterways visible. Screenshot-check that clusters render.

- [ ] **Step 3:** Syntax-check (extract longest `<script>` block → `node --check`). Commit: `feat(map): Europe-wide default view`

---

### Task 2: Remember last route endpoints (replace Le Havre→Lyon default)

**Files:** Modify `french_canals_map.html` (~5300-5315 default block; `setRouteEndpoint`)

- [ ] **Step 1:** Add a localStorage key near the other STORAGE consts:

```js
const LAST_ENDPOINTS_KEY = 'french_canals_last_endpoints_v1';
```

- [ ] **Step 2:** In `setRouteEndpoint(which, id)` (grep for its definition), after the existing logic, persist:

```js
  try {
    var _le = JSON.parse(localStorage.getItem(LAST_ENDPOINTS_KEY) || '{}') || {};
    _le[which] = id;
    localStorage.setItem(LAST_ENDPOINTS_KEY, JSON.stringify(_le));
  } catch(e){}
```

- [ ] **Step 3:** Replace the hardcoded Le Havre/Lyon default block (~5300) with: read `LAST_ENDPOINTS_KEY`; if stored `from`/`to` ids still exist in WAYPOINTS use them; else fall back to the existing Le Havre→Lyon lookup (keep that code as the fallback branch, it is still a sensible first-run default).

```js
  // Default endpoints: last-used (if still valid), else Le Havre → Lyon
  var _lastEp = {};
  try { _lastEp = JSON.parse(localStorage.getItem(LAST_ENDPOINTS_KEY) || '{}') || {}; } catch(e){}
  var lastFromOk = _lastEp.from && WAYPOINTS.some(w => w.id === _lastEp.from);
  var lastToOk   = _lastEp.to   && WAYPOINTS.some(w => w.id === _lastEp.to);
  if (lastFromOk) { document.getElementById('rp-from').value = _lastEp.from; setRouteEndpoint('from', _lastEp.from); }
  if (lastToOk)   { document.getElementById('rp-to').value   = _lastEp.to;   setRouteEndpoint('to',   _lastEp.to); }
  if (!lastFromOk || !lastToOk) {
    /* existing Le Havre / Lyon fallback lookups here, guarded so they only
       fill the endpoint that wasn't restored */
  }
```
Note: `setRouteEndpoint` now writes the key, so restoring via it re-persists — harmless.

- [ ] **Step 4:** Preview check: pick Amsterdam→Vienna, reload page, reopen planner → endpoints restored. Clear localStorage → Le Havre→Lyon appears.

- [ ] **Step 5:** Syntax-check + commit: `feat(planner): remember last route endpoints, keep Le Havre→Lyon as first-run default`

---

### Task 3: Per-country authority links

**Files:** Modify `french_canals_map.html` (~3273 area + call sites ~3393, ~4269)

- [ ] **Step 1:** Add an `AUTHORITIES` map after `VNF_TERRITORIES`:

```js
/* National waterway authorities for non-FR countries. FR keeps the richer
 * VNF_TERRITORIES treatment. URLs mirror the data-sources panel deep-links. */
const AUTHORITIES = {
  NL: { flag:'🇳🇱', name:'Rijkswaterstaat', notices:'https://www.vaarweginformatie.nl/', home:'https://www.rijkswaterstaat.nl/water' },
  DE: { flag:'🇩🇪', name:'WSV / ELWIS', notices:'https://www.elwis.de/DE/dynamisch/gewaesserkunde/', home:'https://www.elwis.de/' },
  BE: { flag:'🇧🇪', name:'De Vlaamse Waterweg / SPW', notices:'https://www.visuris.be/', home:'https://voies-hydrauliques.wallonie.be/' },
  AT: { flag:'🇦🇹', name:'viadonau / DoRIS', notices:'https://doris.bmk.gv.at/', home:'https://www.viadonau.org/' },
  CH: { flag:'🇨🇭', name:'Port of Switzerland', notices:'https://www.port-of-switzerland.ch/', home:'https://www.port-of-switzerland.ch/' },
  LU: { flag:'🇱🇺', name:'WSV (Moselle, DE-administered)', notices:'https://www.elwis.de/', home:'https://www.elwis.de/' },
  UK: { flag:'🇬🇧', name:'Canal & River Trust', notices:'https://canalrivertrust.org.uk/notices', home:'https://canalrivertrust.org.uk/' },
  IE: { flag:'🇮🇪', name:'Waterways Ireland', notices:'https://www.waterwaysireland.org/marine-notices', home:'https://www.waterwaysireland.org/' },
  IT: { flag:'🇮🇹', name:'AIPo', notices:'https://www.agenziapo.it/', home:'https://www.agenziapo.it/' },
};

function authorityLinksHTML(country) {
  const a = AUTHORITIES[country];
  if (!a) return '';
  return `
    <div class="vnf-section">
      <h4>${a.flag} ${a.name}</h4>
      <a class="vnf-btn" href="${a.notices}" target="_blank" rel="noopener">
        ⚠️ Navigation notices &amp; conditions
        <strong>Closures, water levels &amp; restrictions</strong>
      </a>
      <a class="vnf-btn" href="${a.home}" target="_blank" rel="noopener">
        🏢 ${a.name} — official site
        <strong>Contacts &amp; waterway information</strong>
      </a>
    </div>`;
}
```
(Before committing, verify each URL with a HEAD/GET curl — 200/301 acceptable; replace any dead one with the authority's homepage.)

- [ ] **Step 2:** At both `vnfLinksHTML(...)` call sites, route by waypoint country. Sidebar (~3393): the waypoint object `w` is in scope; change to:

```js
    ${w.country && w.country !== 'FR' ? authorityLinksHTML(w.country) : vnfLinksHTML(w.section, routeInfo ? routeInfo.from : '', routeInfo ? routeInfo.to : '')}
```
Second call site (~4269): inspect its context — if a waypoint/country is available apply the same pattern; if it's a FR-specific lock-hours panel, leave it and note why in the report.

- [ ] **Step 3:** Preview: open a Dutch waypoint sidebar → Rijkswaterstaat section, no VNF. Open a French one → VNF unchanged.

- [ ] **Step 4:** Syntax-check + commit: `feat(sidebar): per-country waterway authority links`

---

### Task 4: Country grouping in route-planner dropdowns

**Files:** Modify `french_canals_map.html` (~5275-5296)

- [ ] **Step 1:** In the dropdown-build function, replace the pure-section grouping. Non-FR waypoints (`w.country && w.country !== 'FR'`) group by country; the rest keep section groups:

```js
  const COUNTRY_LABELS = { NL:'🇳🇱 Netherlands', BE:'🇧🇪 Belgium', DE:'🇩🇪 Germany', CH:'🇨🇭 Switzerland',
    AT:'🇦🇹 Austria', IT:'🇮🇹 Italy', LU:'🇱🇺 Luxembourg', UK:'🇬🇧 United Kingdom', IE:'🇮🇪 Ireland' };

  const bySec = {}, byCountry = {};
  towns.forEach(w => {
    if (w.country && w.country !== 'FR') {
      (byCountry[w.country] = byCountry[w.country] || []).push(w);
    } else {
      (bySec[w.section] = bySec[w.section] || []).push(w);
    }
  });
```
Then when filling each `<select>`: first the FR section optgroups exactly as now (sections sorted numerically, label from `sectionNames`), then one optgroup per country in `Object.keys(COUNTRY_LABELS)` order (skip empty), each sorted by name:

```js
    Object.keys(COUNTRY_LABELS).forEach(cc => {
      if (!byCountry[cc]) return;
      const grp = document.createElement('optgroup');
      grp.label = COUNTRY_LABELS[cc];
      byCountry[cc].sort((a,b) => a.name.localeCompare(b.name)).forEach(w => {
        const opt = document.createElement('option');
        opt.value = w.id; opt.textContent = w.name;
        grp.appendChild(opt);
      });
      sel.appendChild(grp);
    });
```
This also fixes two latent bugs: EU OSM waypoints (`section: 0`) currently render under a bogus "Section 0" optgroup, and the 39 anchor waypoints (`section: 1`, country set) wrongly sit under "Section 1 · Seine".

- [ ] **Step 2:** Check every other consumer of `bySec`/`_stopOptionsHTML` (via-stop dropdowns reuse `_stopOptionsHTML` — they inherit the fix automatically; grep for other `bySec` builds at ~5237 and ~5603 and apply the same split ONLY if those functions also render EU waypoints — inspect first, report what you found).

- [ ] **Step 3:** Preview: open route planner → French sections first, then country groups; "Section 0" gone; Basel under Switzerland not Seine. Plan Amsterdam→Vienna via dropdowns to prove end-to-end.

- [ ] **Step 4:** Syntax-check + commit: `feat(planner): group EU waypoints by country in route dropdowns`

---

### Task 5: Country-aware search links + generalized hints

**Files:** Modify `french_canals_map.html` (~3381, ~8387)

- [ ] **Step 1:** Google moorings search (~3381): build the query from the waypoint's country:

```js
  const COUNTRY_NAMES = { FR:'France', NL:'Netherlands', BE:'Belgium', DE:'Germany', CH:'Switzerland',
    AT:'Austria', IT:'Italy', LU:'Luxembourg', UK:'UK', IE:'Ireland' };
```
(place near the link or reuse if an equivalent map now exists from Task 4 — do NOT define twice; if Task 4's `COUNTRY_LABELS` is in a different scope, define this one module-level and have Task 4 reuse it for labels via a small formatter, or keep them separate if scopes don't allow — report which you chose)

```js
  href="https://www.google.com/search?q=${encodeURIComponent(w.name + ' ' + (COUNTRY_NAMES[w.country] || 'France') + ' canal moorings')}"
```

- [ ] **Step 2:** Vessel-profile hint (~8387): `French canal locks max ~38.5 m` → `Freycinet-gauge locks (FR) max ~38.5 m — larger on Rhine/Danube`

- [ ] **Step 3:** Syntax-check + commit: `fix(ui): country-aware search links and lock-size hint`

---

### Task 6: SW bump + docs + final checks

**Files:** Modify `sw.js:17`, `CLAUDE.md`

- [ ] **Step 1:** `sw.js` VERSION `'fc-v12'` → `'fc-v13'`.
- [ ] **Step 2:** CLAUDE.md: note per-country authority links (`AUTHORITIES` / `authorityLinksHTML`), country-grouped planner dropdowns, last-endpoints localStorage key in the localStorage table (`french_canals_last_endpoints_v1`), and update the sw.js VERSION mention to fc-v13.
- [ ] **Step 3:** Full checks: `node --check` on extracted block; `python3 -m pytest tests/ -q` (should stay 65 passed); preview click-through (map loads at EU view, planner works, FR + NL sidebars correct).
- [ ] **Step 4:** Commit: `chore: bump SW to fc-v13, document de-Francification`
- [ ] **Step 5:** Push + PR titled "De-Francification: EU defaults, per-country authorities, country-grouped planner".

---

## Self-review notes
- Scope check: map default ✓, planner default ✓, authority links ✓, dropdown grouping ✓, search links ✓, lock hint ✓. The IGN basemap button keeps its label (it is accurate — IGN is FR-specific); no per-country basemaps in this pass (needs tile-provider research, out of scope).
- Vigicrues (FR-only water levels) intentionally NOT expanded here — separate feature (PEGELONLINE/RWS APIs).
- Type consistency: `authorityLinksHTML(country)` string-in string-out; `w.country` exists on all OSM-sourced and anchor waypoints, absent on curated FR ones (falsy → VNF branch, correct).
