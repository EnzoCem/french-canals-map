# Danube Wave 2: Budapest → Black Sea (HR / RS / RO / BG)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Extend the app down the full navigable Danube from Budapest to the Black Sea: geometry, three plannable curated routes (incl. the Iron Gates locks and the Danube–Black Sea Canal to Constanța), country wiring for Croatia/Serbia/Romania/Bulgaria, IENC bridges/hazards from the on-disk bundles, corridor OSM POIs, and closure deep-links.

**Discovered facts (verify with grep/ls, trust otherwise):**
- IENC bundles in `Inland ENC Europe 05.2022/`: Croatia/`Dunav.zip` (cells `5C7D####`, 2018; also Drava.zip/Sava.zip — SKIP, out of scope like the Tisza); Serbia/`IENC_2P7D_edition03_20211229.zip` (cells `ENC_ROOT/2P7D####`; also 2P7SA Sava + 2P7TI Tisa zips — SKIP); Romania/ six numeric zips (cells incl. `CDMN/3R7DCC##.000` = Danube–Black Sea Canal + others to inventory — list all six zips' cells first; expect `3R7D####` Danube cells); Bulgaria/`BG_IENC_2.3.zip` (cells `3B7D####`, 2022; also RIS index xlsx + buletin.pdf — human reference only).
- Existing SK/HU wave (PR #22) ended coverage at Budapest; `EU_BBOX` east = 19.3 deliberately excludes the Serbian reach. Do NOT widen EU_BBOX globally — instead make the `_extract_ways` clip bbox parametrizable per waterway: 'Danube' (and the new CDMN canal) get `DANUBE_BBOX = (42.0, 8.0, 50.5, 30.5)`; everything else keeps EU_BBOX. Implement as an optional `clip_bbox` argument threaded from `fetch_waterway` (per-waterway override map), default EU_BBOX; keep behavior for all other waterways byte-identical.
- Route numbering: curated routes end at 75. Use **76** "Donau (Budapest–Belgrade)" [countries HU/HR/RS], **77** "Donau (Belgrade–Cernavodă)" incl. Iron Gates I+II locks [RS/RO/BG], **78** "Danube–Black Sea Canal (Cernavodă–Constanța)" [RO].
- Dimension/lock data: EuroCanals guides `Croatia-Serbia4982.pdf` and `Romania-Bulgaria5649.pdf` (dimension tables near the front, like Burgundy p.8; facts only). Iron Gates: two large locks (Đerdap I ~ r.km 943, Đerdap II ~ r.km 863). CDMN: locks at Cernavodă + Agigea.
- Anchors (route/section/country style of `w_a75_*`): 76 → Vukovar (HR 45.352,18.996), Novi Sad (RS 45.255,19.85), Belgrade (RS 44.82,20.45); 77 → Drobeta-Turnu Severin (RO 44.63,22.65), Ruse (BG 43.85,25.96), Cernavodă (RO 44.34,28.03); 78 → Constanța (RO 44.10,28.63 — Agigea south port area 44.09,28.64 acceptable). Connections: [75,76,'Budapest'], [76,77,'Belgrade'], [77,78,'Cernavodă'].
- Country wiring in french_canals_map.html: `COUNTRY_NAMES` (+ Croatia/Serbia/Romania/Bulgaria), `COUNTRY_LABELS` (🇭🇷/🇷🇸/🇷🇴/🇧🇬, appended after HU), `AUTHORITIES` (curl-verify; candidates: HR Agencija za vodne putove https://www.vodniputovi.hr/; RS Plovput https://www.plovput.rs/; RO AFDJ Galați https://www.afdj.ro/ + RoRIS; BG APPD/BULRIS https://www.appd-bg.org/ or bulris.bg — pick 2 live URLs per country, notices+home, replace dead with live official).
- Closures: deep-link entries only (data-sources panel "Closures (not curated)" list) for all four countries — same style as the HU line.
- OSM POIs: add corridor bboxes to `fill_osm_pois.py` (attribution is area-based, bbox limits extent only): HR (45.1, 18.7, 45.8, 19.5), RS (44.0, 19.0, 46.2, 23.0), RO (43.6, 22.0, 45.5, 29.8), BG (43.5, 22.6, 44.3, 28.7). Run `--countries HR RS RO BG`; Overpass may 504 — the script is idempotent, retry failed countries.
- Palette: 'Canalul Dunăre-Marea Neagră' (or the exact OSM name found) needs a waterway_colors entry distinct from semaphore colours. Danube palette already exists.
- Caches to bump at the end: `WATERWAYS_CACHE_VER` v14→v15, `fc-waypoints-v7`→v8, `fc-routes-v6`→v7, `fc-moorings-v4`→v5, `fc-colors-v3`→v4, SW `fc-v23`→v24.
- CLAUDE.md/FEATURES: coverage (14 countries), counts, recipe zips, skips (Drava/Sava/Tisa, human-reference BG files), authority portals.

## Batch G1 — Geometry, routes, wiring, POIs
1. fill_waterways.py: per-waterway clip-bbox override (default EU_BBOX; Danube + CDMN → DANUBE_BBOX). Unit test the override plumbing if a pure function is extractable; otherwise verify via the driver run.
2. Add CDMN to OSM_NAME_MAP/WATERWAY_ROUTES (route 78): find the canal's OSM name first (Overpass probe: relation/way named "Canalul Dunăre-Marea Neagră" or similar).
3. Re-fetch 'Danube' + fetch CDMN via the scratchpad-driver pattern (fetch_waterway → stitch → bridge_chain_gaps → build_features → merge into waterways.geojson atomically). Verify: Danube max lon ≥ 29 (Sulina/delta area may be sparse — the navigable line must at least reach Cernavodă lon 28.0 and Brăila/Galați); report piece/gap stats; NO regression west of 19.3.
4. routes.json: routes 76/77/78 with EuroCanals-table dims + locks (Iron Gates on 77), connections, descriptions (1-2 factual sentences each). Anchors per the list. BFS check: Auxerre→Constanța path ends 75→76→77→78.
5. HTML wiring: COUNTRY_NAMES/LABELS/AUTHORITIES (+curl report), closure deep-link lines for HR/RS/RO/BG.
6. fill_osm_pois.py bboxes + sweep `--countries HR RS RO BG` (idempotent retries). Report per-country counts.
7. Tests green (84+), node --check. Commits per logical unit (conventional messages). No cache bumps yet (G2 does them all at once).

## Batch G2 — IENC + caches + docs
1. Inventory all Romanian zips' cell names first. extract_ienc.py `_waterway_for_cell` mappings: `5C7D`→'Donau', `2P7D`→'Donau', `3B7D`→'Donau', RO Danube cells→'Donau', `3R7DCC`→the CDMN app name (check ordering: most-specific prefix first). NO mappings for Drava/Sava/Tisa (zips not fed). Tests for each new prefix.
2. Full extraction: CLAUDE.md recipe zips + HR Dunav.zip + RS 2P7D zip + all six RO zips + BG zip. Watch for the surrogate-junk issue (guard exists) and AppleDouble junk (guard exists). Gates: Donau bridges grow beyond 229; zero waterways lose >5%; Unknown bucket doesn't grow; five-file before/after counts.
3. All cache bumps (see facts above) + SW fc-v24. CLAUDE.md coverage/counts/recipe/skip-notes; FEATURES row.
4. Tests + node --check.

## Batch G3 — Verification + PR
- Preview: continuous Danube Budapest→Cernavodă (+CDMN to Constanța); plan Vienna→Constanța end-to-end (locks incl. Iron Gates shown); HR/RS/RO/BG optgroups; Belgrade sidebar shows Plovput authority.
- Final whole-branch review (scrutinize: clip-override behavior for non-Danube waterways unchanged; route dims vs guide tables; authority URLs live).
- Push + PR: "Danube Wave 2: Budapest → Black Sea (HR/RS/RO/BG)".

**Out of scope (note in PR):** Drava, Sava, Tisa/Tisza rivers; Sulina maritime arm as a plannable route (geometry may include it; no route/anchors); Bega canal; HR/RS/RO/BG curated closures (deep-links only); Danube Delta.
