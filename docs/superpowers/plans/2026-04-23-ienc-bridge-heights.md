# IENC Data Mining — Bridge Heights & Precision Chart Data

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Source data:** A 13 MB zip (`FR.zip` at `/Users/esen/Downloads/FR.zip` as of 2026-04-23, final destination TBD) containing 119 files across ~60 S-57 ENC cells. Coverage — **commercial-class waterways only**:

| Prefix pattern | Waterway | Cell count |
|----------------|----------|-----------|
| `1W7RH*`       | Rhône (Lyon → Mediterranean) | 20 |
| `1W7RRS*`      | Rhône-Saône confluence | 1 |
| `1W7SR*`       | Saône | 2 |
| `4V5MOS*`      | Moselle (French) | 11 |
| `4V5001DE – 4V5019DE` | Moselle (shared French/German) | 19 |
| `4V5RHO* / 4V5SAO*` | Extra Rhône / Saône overlap | 3 |
| `4V7SEI*`      | Seine | 17 |
| `7V7LEIE4`     | Leie (FR/BE border) | 1 |
| `7V7PLDU4`     | Nieuwpoort – Dunkerque canal | 1 |

**NOT covered** (don't raise expectations): Canal du Midi, Canal de Bourgogne, Nivernais, Briare, Centre, Champagne, Marne-Rhin, Garonne — i.e. the recreational canal network. IENC is produced only for the large-gauge commercial rivers.

---

**Goal:** Extract the navigationally-useful datasets from the S-57 cells and surface them in the map as three new layers — primarily **exact bridge air clearances** per bridge on the big rivers, plus lock-position corrections and precision mooring data as stretch goals.

**Non-goal:** Rendering the charts with S-52 symbology. That's a multi-week project and irrelevant to pleasure-craft route planning. We treat the zip as a one-shot data-mining source.

**Architecture:** A new Python script `extract_ienc.py` reads each `.000` cell via GDAL/OGR, pulls the handful of S-57 object classes we care about, deduplicates across overlapping cells, and emits three compact GeoJSON files. The HTML app adds a Bridges layer with vessel-profile-aware colouring (green/amber/red vs. air draught), and optionally merges the lock/mooring corrections into existing layers via Edit Locations overrides.

**Tech stack:** Python 3 (`gdal`/`osgeo.ogr` bindings — same ecosystem as `fill_waterways.py`), S-57 reader driver built into GDAL, GeoJSON output, vanilla Leaflet + JS on the client.

**Licensing:** VNF IENCs are redistributable under the French open-licence (Licence Ouverte / Etalab 2.0) with attribution. Add a small attribution line in the About / Data panel: *"Bridge & chart data © VNF / CEREMA — IENC, Licence Ouverte 2.0"*.

---

## File structure

| Action | Path | Responsibility |
|---|---|---|
| Create | `extract_ienc.py` | Unzip, walk cells, OGR-read S-57 layers, emit GeoJSON |
| Create (by script) | `data/bridges.geojson` | Bridge points with air clearance per vessel profile |
| Create (by script) | `data/ienc_locks.geojson` | Precision lock positions + chamber dims (for cross-reference) |
| Create (by script) | `data/ienc_moorings.geojson` | Quays / pontoons / mooring facilities from IENC |
| Modify | `french_canals_map.html` | Add `bridgesGroup` layer, toggle button, popup + vessel-profile colouring |
| Modify | `CLAUDE.md` | Document new data pipeline + layer |
| Modify | `FEATURES.md` | Move "Bridge height markers" from Low → Done |

---

## Task 1: Spike — confirm GDAL reads the cells

**Files:** none (exploratory)

- [ ] **Step 1:** Install GDAL Python bindings: `pip install --user GDAL` (or `brew install gdal && pip install GDAL==$(gdal-config --version)`).
- [ ] **Step 2:** Unzip `FR.zip` to a scratch dir. Pick one cell, e.g. `4V7SEI10/4V7SEI10.000` (Seine mid-section).
- [ ] **Step 3:** Run `ogrinfo -ro 4V7SEI10.000` and confirm it enumerates S-57 layers. Expected layer names include: `DEPARE`, `DEPCNT`, `SOUNDG`, `BRIDGE`, `LOKBSN`, `PILPNT`, `BERTHS`, `ACHARE`, `RESARE`, `DISMAR`, `NAVLNE`.
- [ ] **Step 4:** `ogrinfo -ro -al -where "OBJL=42" 4V7SEI10.000` (OBJL 42 = bridge) — confirm there are BRIDGE features and that `VERCLR` (air clearance, metres) is populated.
- [ ] **Step 5:** Document the exact field names found (they sometimes vary: `VERCLR`, `VERCCL`, `verclr`) in a comment at the top of the plan before starting Task 2.

**Stop condition:** If GDAL refuses to read the cells (e.g. encoding errors on the French-producer cells), try again with `GDAL_DATA` env var set and `OGR_S57_OPTIONS="RETURN_PRIMITIVES=OFF,RETURN_LINKAGES=OFF,LNAM_REFS=ON,SPLIT_MULTIPOINT=ON,ADD_SOUNDG_DEPTH=YES"`. If still failing, fall back to the Python `python-s57` or `pys57` libraries.

---

## Task 2: Write `extract_ienc.py` — bridge extraction only

**Files:**
- Create: `extract_ienc.py`
- Create: `tests/test_extract_ienc.py`

- [ ] **Step 1:** Write `iter_cells(zip_path)` → yields `(cell_name, local_path_to_000_file)`. Unzip to a temp dir.
- [ ] **Step 2:** Write `extract_bridges(cell_path) -> list[dict]`. Each dict: `{ name, lat, lon, verclr_m, horclr_m, cell, waterway }`. Derive `waterway` from the cell prefix (`4V7SEI*` → "Seine", `1W7RH*` → "Rhône", etc.).
- [ ] **Step 3:** Write `dedupe_bridges(bridges) -> list[dict]`. Overlapping cells will produce duplicate bridge features at near-identical coordinates. Dedupe by rounding lat/lon to 4 dp + name match.
- [ ] **Step 4:** Write `emit_geojson(features, path)`. Simple GeoJSON writer; use `separators=(',', ':')` like the other scripts.
- [ ] **Step 5:** Write unit tests: deterministic cell path + expected bridge count for one known cell (e.g. `4V7SEI10` which crosses central Paris and has many bridges).
- [ ] **Step 6:** Run end-to-end: `python3 extract_ienc.py --zip /Users/esen/Downloads/FR.zip --out data/bridges.geojson --layer bridges`. Expected output: ~200–400 bridge features across Rhône/Saône/Seine/Moselle.
- [ ] **Step 7:** Spot-check three known bridges against published VNF clearance tables (e.g. Pont d'Austerlitz on the Seine, Pont Bonaparte on the Rhône). Clearances should match within ±0.05 m.

**Stop condition:** If dedup reduces total count by >50%, the rounding threshold is too aggressive — re-check.

---

## Task 3: Add Bridges layer to the map

**Files:**
- Modify: `french_canals_map.html`

- [ ] **Step 1:** Add a fetch for `data/bridges.geojson` during map init (parallel to the `waterways.geojson` cache load; cache it under a new `fc-bridges-v1` key).
- [ ] **Step 2:** Declare `const bridgesGroup = L.layerGroup()` in the layer-groups block.
- [ ] **Step 3:** Write `buildBridgeMarkers()` (~70 lines). Uses a small divIcon (🌉) with colour determined by vessel air draught vs. `verclr_m`:
  - green if `verclr_m - air ≥ 0.5` (comfortable clearance)
  - amber if `0 ≤ verclr_m - air < 0.5` (marginal — check water level)
  - red if `verclr_m < air` (will not pass)
  - grey if no profile set
- [ ] **Step 4:** Popup shows: bridge name · waterway · PK if available · air clearance (large type) · horizontal clearance · source: "IENC © VNF".
- [ ] **Step 5:** Add a controls-bar toggle `🌉 Bridges` wired into the existing `layerState` / `toggleLayer('bridges')` pattern.
- [ ] **Step 6:** Update `FEATURES.md`: strike through "Bridge height markers" and add it to the Done table.

**Stop condition:** If marker density visually clutters the map (likely in central Paris, ~30 bridges in 3 km), switch the bridges layer to a cluster group — reuse existing MarkerCluster.

---

## Task 4 (stretch): Lock & mooring cross-reference export

**Files:**
- Modify: `extract_ienc.py`
- Create: `data/ienc_locks.geojson`, `data/ienc_moorings.geojson`

- [ ] **Step 1:** Extend `extract_ienc.py` with `extract_locks()` and `extract_moorings()` functions reading `LOKBSN` / `LOCK` / `BERTHS` / `MORFAC` layers.
- [ ] **Step 2:** Run a **reconciliation report** (not an auto-merge): for each IENC lock, find the nearest OSM / existing curated lock within 200 m. Emit a CSV `data/lock_reconciliation.csv` with columns `ienc_name, osm_name, distance_m, ienc_lat, ienc_lon, existing_lat, existing_lon, delta`. User eyeballs + decides whether to apply.
- [ ] **Step 3:** Same for moorings vs. `MOORINGS[]`.
- [ ] **Step 4:** Add the reconciliation CSV generation behind a `--reconcile` flag, so Task 3 can ship without waiting on manual review.

**Stop condition:** This task is low-priority. Only proceed if Task 3 is shipped and stable.

---

## Task 5: Documentation + commit

**Files:**
- Modify: `CLAUDE.md` (document `extract_ienc.py`, new layer, licensing line)
- Modify: `FEATURES.md` (move bridge heights to Done)
- Modify: `README.md` if it lists features / data sources

- [ ] **Step 1:** Add `extract_ienc.py` to the file-structure table in `CLAUDE.md`.
- [ ] **Step 2:** Add a new "IENC bridge data" subsection describing the pipeline.
- [ ] **Step 3:** Add the VNF attribution string to the Data Backup panel or About section in the HTML.
- [ ] **Step 4:** Commit in logical chunks (script + data + HTML wiring separately, so the diff stays reviewable).

---

## Risk log

| Risk | Mitigation |
|------|-----------|
| GDAL S-57 driver fails on French-producer cells | Try `OGR_S57_OPTIONS` tuning; fall back to Python `pys57` |
| `VERCLR` values are reference-level not actual-water-level | Document: "clearances are at reference water level; actual clearance drops in high water." Add a warning line in the popup. |
| Bridge marker density clutters central Paris | Switch to MarkerCluster for `bridgesGroup` |
| IENC licence requires specific attribution wording | Verify on vnf.fr / data.gouv.fr at import time; worst case pin the attribution line verbatim |
| File size (`bridges.geojson`) balloons | Expected <100 KB (~300 bridges). If >500 KB, investigate — we're pulling too many fields. |

---

## Out of scope (do NOT do)

- Rendering S-52 chart symbology (buoys, depth-tinted water, soundings). Massive project, wrong product.
- Depth contour overlay — pleasure craft on large French rivers never hit depth issues; low value.
- German IENC (`4V5*DE`) processing beyond bridges — out of scope for a French-canals app; bridges happen to be cheap to include.
- Live IENC update subscription via VNF distribution service. One-shot manual refresh is enough for now.
