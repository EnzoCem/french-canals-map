# Danube Extension Wave 1: Slovakia + Hungary (Vienna → Budapest)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Extend app scope down the Danube from Vienna to Budapest: waterway geometry through SK/HU, a plannable curated route, SK/HU country wiring (labels, authorities), and IENC bridges/hazards from the on-disk Slovakia + Hungary chart bundles. Scoped per user decision to HU+SK only (further Danube states deferred).

**Discovered facts (trust, verify with grep):**
- `EU_BBOX = (35.0, -11.0, 60.0, 19.0)` in fill_waterways.py — eastern edge clips just short of Budapest (lon 19.05). Widening east to **19.3** covers the whole SK/HU Danube (Bratislava 17.1, Komárno 18.1, Esztergom 18.7, Budapest 19.05, Danube Bend/Vác 19.13) while still excluding the Serbian reach (Novi Sad 19.85) — minimal side effects on other fetches.
- The existing 'Danube' fetch already pulls the whole OSM relation; `_extract_ways` bbox-clips it. After the bbox widen, a re-fetch of JUST the Danube (+ gap-bridging) extends the geometry — no full sweep needed (fetch one waterway via a small python driver using fill_waterways functions, then merge into waterways.geojson the way main() does for that one name, or simply re-run only the Danube through the same code path).
- IENC bundles (in `Inland ENC Europe 05.2022/`): Slovakia/ has four standalone cell zips `2D7D1709/1723/1737/1752.zip` (each contains a bare `2D7D####.000`, ~38 MB each — NOTE: no ENC_ROOT dir; check extract_ienc handles bare-cell zips, it handled `ENC_Hochrhein_Update_2021` with cells at top level). Hungary/ has `HU_D_IENC…zip` (cells `1H7D1430-…` under ENC_ROOT), `HU_SZD…zip` (`1H7SZD00` Szentendrei-Duna side arm), `HU_TI…zip` (`1H7TI*` = Tisza river — **SKIP**: no map geometry for the Tisza in this scope; bridges would float on an empty map. Note the deliberate skip in docs).
- Route numbering: curated EU routes end at 74 (Po). Next: **75**.
- Existing route 66 = "Donau (Kelheim–Vienna)" with anchor `w_a66_vienna` (Vienna, AT).
- Country plumbing to extend (all in french_canals_map.html): `COUNTRY_NAMES`, `COUNTRY_LABELS` (order drives optgroup order — append SK, HU after IE), `AUTHORITIES`, the closures FLAG maps (2 sites) can stay (no SK/HU closures curated yet). CLAUDE.md documents these.
- Authorities (curl-verify before committing, replace dead ones with the live official site): SK — Dopravný úrad / plavba (try https://nsat.sk/, https://www.arvd.sk/); HU — RSOE PannonRIS (https://www.pannonris.hu/) and OVF. Pick 2 live URLs per country (notices + home) following the AUTHORITIES shape.
- Constraints: existing key 'Donau' covers the river; optionally refine with the EuroCanals `Slovakia-Hungary2349.pdf` dimension table (facts only, cited) ONLY if it has a distinct SK/HU row that differs from the existing Donau entry — do not fork the key.

## Batch F1 — Geometry + app wiring
1. fill_waterways.py: `EU_BBOX` east 19.0 → 19.3 with a comment (scope = Danube to Budapest; Serbian reach deliberately excluded).
2. Re-fetch ONLY the Danube through the normal code path (fetch_waterway → stitch_ways → bridge_chain_gaps → build_features), replace its features in waterways.geojson via merge_geojson semantics for that one name. Verify: features now reach lon ≈ 19.1 (Budapest); gap metrics for Danube not worse than before; total feature count reported.
3. data/routes.json: add curated route 75 `{num:75, canal:'Donau (Vienna–Budapest)', from:'Vienna', to:'Budapest', dist_km:≈290, locks:2 (Gabčíkovo SK + Freudenau at Vienna is on 66 — verify against the EuroCanals Slovakia-Hungary guide table and use its numbers), max dims from the guide table, color pick a free hex distinct from semaphore colours (check data/waterway_colors.json practice), country:['SK','HU'], source:'curated', description: 1-2 factual sentences}` + connection `[66, 75, 'Vienna']`.
4. data/waypoints.json: anchor waypoints `w_a75_bratislava` (SK 48.14,17.11), `w_a75_komarno` (SK 47.757,18.13), `w_a75_esztergom` (HU 47.79,18.74), `w_a75_budapest` (HU 47.498,19.04) — route 75, section 1, country set, style matching existing `w_a66_vienna`.
5. french_canals_map.html: SK/HU in COUNTRY_NAMES ('Slovakia','Hungary'), COUNTRY_LABELS ('🇸🇰 Slovakia','🇭🇺 Hungary'), AUTHORITIES (curl-verified URLs). Verify BFS Auxerre→Budapest works (routes 4→…→66→75).
6. Caches: `WATERWAYS_CACHE_VER` v13→v14, `fc-waypoints-v5`→v6, `fc-routes-v5`→v6. Tests: pytest green; node --check.
7. Commit(s): `feat(danube): extend scope to Budapest — geometry, route 75, SK/HU wiring`

## Batch F2 — IENC Slovakia + Hungary
1. extract_ienc.py `_waterway_for_cell`: `2D7D` → 'Donau', `1H7D` → 'Donau', `1H7SZD` → 'Szentendrei-Duna'. NO mapping for `1H7TI` (Tisza zip is not fed in). Tests for the new prefixes (pytest, follow existing style).
2. Full extraction: CLAUDE.md recipe ZIP list + the 4 SK zips + `HU_D_…zip` + `HU_SZD_…zip` (NOT `HU_TI_…zip`), all five outputs + --reconcile. Gates: Donau bridge count grows (SK/HU stretch), zero waterways lose >5%, Unknown bucket doesn't grow, before/after counts reported for all five files.
3. SW VERSION fc-v20 → fc-v21. CLAUDE.md: coverage list gains 🇸🇰/🇭🇺 (05.2022 snapshot note, Tisza deliberately skipped), counts, recipe zips. FEATURES.md row.
4. Commit: `feat(ienc): Slovakia + Hungary Danube cells from local 05.2022 bundles`

## Batch F3 — Verification + PR
- pytest, node --check, preview: map shows continuous Danube Vienna→Budapest; plan Auxerre→Budapest (or Vienna→Budapest) end-to-end; SK/HU optgroups in planner; Bratislava sidebar shows SK authority.
- Final whole-branch review, push, PR: "Danube extension: Slovakia + Hungary (Vienna → Budapest)".

**Out of scope (note in PR):** Tisza river, Danube below Budapest (HR/RS/RO/BG), OSM POI sweep for SK/HU (fill_osm_pois countries list untouched — follow-up), SK/HU closures curation (deep-links only if trivial).
