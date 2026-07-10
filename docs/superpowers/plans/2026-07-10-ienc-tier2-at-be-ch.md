# IENC Tier 2: Austria + Belgium + Switzerland from local bundles (+ Rhône CNR restore)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ingest the on-disk `Inland ENC Europe 05.2022` chart bundles for AT/BE/CH through the existing `extract_ienc.py` pipeline, restore the dropped Rhône Lyon→Med CNR cells, regenerate the five IENC GeoJSONs, and clean up stale intermediates.

**Context / discovered facts:**
- Bundles live in `Inland ENC Europe 05.2022/` — Austria: `Austria/2W_Edition.zip` (base cells `2W7D*.000`; 8 later `2W_Update_*.zip` are incremental ER updates — SKIP them, base edition only, note in docs); Belgium: `Belgium/IENCMappack_*.zip` × 6 (full `.000` cells like `7V7ALB10`, one folder per cell with JPGs); Switzerland: `Switzerland/ENC_Hochrhein_Update_2021.zip` (full cell `4C7RH149.000` despite "Update" name).
- `ienc/Rhone_Lyon_Med.zip` exists but is missing from the CLAUDE.md extraction recipe — current bridges.geojson has only 11 Rhône entries vs ~88 recorded in FEATURES.md after the April CNR ingestion. Re-add it.
- `extract_ienc.py` CLI: repeatable `--zip`, outputs `--out/--out-locks/--out-moorings/--out-channel-axis/--out-obstructions`, `--reconcile french_canals_map.html`. Later zips override earlier cells; cross-zip dedup keeps conservative records.
- `_waterway_for_cell` in extract_ienc.py needs new prefix mappings: `2W7D` → "Donau (AT)"; `7V7ALB` → "Albert Canal"; other `7V7*` BE prefixes discovered via dry-run (inspect all 6 mappacks' cell names first: `unzip -l` each); `4C7RH` → "Hochrhein". Follow the existing pattern (NL/DE mappings added in Wave 3).
- venv GDAL 3.12.3 confirmed working.
- Cleanup targets (untracked or stale): `waterways_existing.geojson`, `waterways_overpass.json` (March intermediates, superseded — delete; check `git ls-files` first: if tracked, `git rm`).

## Tasks

### T1: Cell inventory + prefix mapping
- List cell names across all AT/BE/CH zips (`unzip -l | grep '\.000'`).
- Extend `_waterway_for_cell` with mappings for every new prefix (waterway display names: "Donau (AT)" or reuse "Donau"? — check how DE Donau is labeled and pick names consistent with the vessel-profile constraint keys in data/waterway_constraints.json where possible, e.g. "Albert Canal" matches an existing constraint; "Hochrhein" matches waterway_colors).
- If extract_ienc has tests covering `_waterway_for_cell`, extend them (TDD); else add minimal cases to tests/test_extract_ienc.py.

### T2: Full extraction run
Use the CLAUDE.md recipe ZIP list PLUS: `ienc/Rhone_Lyon_Med.zip`, the AT base edition, all 6 BE mappacks, the CH zip. All five outputs + `--reconcile french_canals_map.html`. Record before/after counts per file (bridges 2,485 / axis 6,576 / obstructions 2,091 / locks 644 / moorings 3,344).
Sanity-gates after the run:
- bridges.geojson: Albert Canal entries > 0, Donau (AT) > 0, Hochrhein ≥ 0 (may be sparse), Rhône count ≥ 80.
- No previously-covered waterway loses >5% of its bridges (compare per-waterway Counter before/after; the run must not regress FR/NL/DE).
- "Unknown waterway" bucket must not grow by more than the handful of genuinely unmappable new cells — if it balloons, extend mappings and re-run.

### T3: App + docs wiring
- SW `VERSION` fc-v16 → fc-v17 (bridges/obstructions are precached; axis via SWR).
- CLAUDE.md: IENC coverage section (BE/AT/CH now Tier 2 — from local 05.2022 bundles, snapshot-dated), updated counts, extraction recipe updated to include the new zips + Rhone_Lyon_Med.zip, note that AT incremental update zips are not applied.
- FEATURES.md: Tier 2 row done; counts.
- Delete stale intermediates (`waterways_existing.geojson`, `waterways_overpass.json`).

### T4: Verification + PR
- pytest suite green; node --check on extracted script block (HTML only touched by reconcile — inspect what reconcile changed and confirm it's sane before committing).
- Preview: toggle 🌉 Bridges over Antwerp/Albert Canal and Vienna; popups show clearances with the 05.2022 attribution.
- Commits per task, push, PR titled "IENC Tier 2: Austria + Belgium + Switzerland from local 05.2022 bundles + Rhône CNR restore".
