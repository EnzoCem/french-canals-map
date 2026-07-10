# EuroCanals Wave: EU Constraint Transcription + Restrictive-Arch Warnings

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** (1) Transcribe the waterway-dimension tables from the EuroCanals regional guides (folder `EuroCanal Guides/`) into `data/waterway_constraints.json` for BE/NL/DE/AT waterways not yet covered; (2) model width-dependent clearance at the known restrictive-arch pinch points (from `Vessel_Dimensions.pdf`) so wide-beam vessels get warned.

**Copyright rule:** transcribe FACTS only (numbers, names). No prose. Cite `"source": "EuroCanals <guide name> (2020)"` per entry, consistent with existing entries' source field style.

---

## Task E1: EU constraints from guide dimension tables

**Files:** `data/waterway_constraints.json`, guides in `EuroCanal Guides/`.

1. Read the dimension tables (structured table near the front of each guide, like Burgundy p.8: WATERWAY / FROM / TO / LENGTH / LOCKS / LOCK SIZE / DRAFT / HEIGHT) from: `Belgiumwwy8843.pdf`, `Netherlandwwys8359.pdf`, `Germanywwy9217.pdf`, `Rhein1637.pdf`, `Main-river2158.pdf`, `Main-Donau-Kanal2691.pdf`, `Germany_Donau6354.pdf`, `Austria_Donau4583.pdf`, `HeartofHolland2378.pdf`, `NorthSea_Germany1598.pdf`. Use the Read tool with `pages` ranges (tables are typically within pages 3-12; scan until found).
2. Merge policy (conservative):
   - NEVER modify an existing constraint entry that has a non-EuroCanals `source` (Wave-5 authority-sourced values win).
   - Add NEW keys only for waterways that exist in `waterways.geojson` names (normalised match — reuse the matching approach from `fill_waterways._norm_name` conceptually; do the check in a throwaway python script and print the mapping table before writing).
   - Lock size "38.5 x 5.1" → `length: 38.5, beam: 5.1`; DRAFT → `draft`; HEIGHT → `air`. Skip rows with missing/ambiguous numbers rather than guessing.
3. Write via a python script using the atomic tmp+replace pattern; keep JSON style identical (indentation, key order matching existing entries).
4. Bump `'fc-constraints-v2'` → `'fc-constraints-v3'` in french_canals_map.html.
5. Report the full list of added keys with values + which geojson name each matched. Expect roughly 15-40 additions; if a table row's waterway has no geojson match, list it in the report as skipped (do NOT add).
6. Commit: `feat(data): EU waterway constraints from EuroCanals guide tables (BE/NL/DE/AT)`

## Task E2: Restrictive-arch warnings (width-dependent clearance)

**Source data** (`EuroCanal Guides/Vessel_Dimensions.pdf`, EuroCanals 2011):
- Canal du Midi — Capestang & Colombiers bridges (Pk 188-201): 3.30 m centerline, **2.40 m at 5.00 m width**
- Canal du Nivernais — Seine side 3 bridges Pk 141-145, Loire side 1 bridge Pk 62: 3.00 m centerline, **2.70 m at 5.00 m width**
- Canal de Bourgogne — bridges: 3.40 m centerline; Pouilly tunnel: 3.10 m centerline, 3.10 m at 3.00 m width, **2.20 m at 5.00 m width**
- General Freycinet note: estimated safe shoulder width 3.00 m at 3.00 m height

**Schema:** extend the affected `data/waterway_constraints.json` entries with an optional `arch` object:
```json
"Canal du Midi": { ..., "arch": { "air_at_5m": 2.40, "note": "Capestang & Colombiers arched bridges (Pk 188-201): 3.30 m at centerline but 2.40 m at 5 m width", "source": "EuroCanals Vessel Dimensions (2011)" } }
```
Add `arch` to: Canal du Midi (2.40), Canal du Nivernais (2.70), Canal de Bourgogne (2.20 — use the Pouilly tunnel worst case, note both bridge + tunnel numbers).

**JS (french_canals_map.html):**
1. `getWaterwayNavStatus(name)` (grep for it): where it evaluates the `air` limit against `_vesselProfile.air`, add: if the constraint has `arch` and `(p.beam > 0)`, compute the effective air limit as `arch.air_at_5m` when `p.beam >= 4.5`, else the centerline `air` — and when the effective limit blocks/margins the vessel, include the arch note in the returned reason.
2. `_vesselCheckSegment(seg)`: same effective-limit logic so the route-planner incompatibility warnings pick it up; the warning text must mention the arch (use the `note`).
3. Waypoint sidebar / waterway popups already surface constraint data via nav status reason — verify the note text flows through, no new UI needed.
4. Style: follow the existing code around those functions exactly (ES5-ish, `var`). NEVER write a literal closing script tag inside JS.
5. Tests: no JS test infra — verify with node assertions on extracted functions (stub `_vesselProfile` beam 5.0/air 2.5 on Canal du Midi → blocked with arch note; beam 3.0/air 2.5 → ok) + `node --check`.
6. Bump `'fc-constraints-v3'` remains (same PR as E1's bump — do NOT double-bump), SW `VERSION` fc-v17 → fc-v18.
7. CLAUDE.md: document the `arch` schema field in the WATERWAY_CONSTRAINTS entry example + one line in the vessel-profile section.
8. Commit: `feat(vessel): width-dependent clearance warnings at restrictive arches (Midi/Nivernais/Bourgogne)`

## Task E3: Verification + PR
- pytest green; node --check; preview: set profile beam 5.0 + air 2.5, check Canal du Midi renders blocked with arch note in planner + waterway colouring; beam 3.0 → navigable.
- Push, PR: "EuroCanals data: EU constraint tables + restrictive-arch clearance warnings".

---

## E1 outcome record (2026-07-10)

**Added (5):** Kanaal Gent-Terneuzen, Bovenschelde / Escaut, Meuse (BE/NL), Zeekanaal Brussel-Schelde - Canal maritime de Bruxelles à l'Escaut, Nederrijn.

**Transcribed but skipped — no waterways.geojson feature yet** (re-usable if geometry is ever added; values live in the guide tables, guide named per group):
- Belgiumwwy8843: Dender, Moervaart, Kanaal Bossuit-Kortrijk, Netekanaal, Lokanaal, Canal Blaton-Ath, Sambre, Ringvaart om Gent, Haut Escaut (Wallonia section)
- Netherlandwwys8359 / HeartofHolland2378: ~140 small NL rows (Vecht, Amstel, Oude Rijn, Friesland/Groningen network, Randmeren, Kanaal door Walcheren, Oosterschelde, Volkerak…)
- Germanywwy9217 / NorthSea_Germany1598: Neckar, Lahn, Ruhr, Rhein-Herne, Wesel-Datteln, Weser, Elbe, Saale, Havel/Spree network, Kiel-area small canals

**Skipped — already covered by authority-sourced keys (never overwrite):** Rhein/Rhine segments, Mosel, Main, MDK, Donau, Saar, Mittellandkanal, Dortmund-Ems, Elbe-Lübeck, Nord-Ostsee, Maas segments, Waal, Lek, IJssel, Amsterdam-Rijnkanaal, Zuid-Willemsvaart, Julianakanaal, Maas-Waalkanaal, Wilhelminakanaal, Twentekanalen, Noordzeekanaal, Hollands Diep, Dordtse Kil, Merwedes, Schelde-Rijnkanaal, Albertkanaal, Leie, Canal Charleroi-Bruxelles, Standing-Mast waterways.

**Known cosmetic gap:** a beam 3–4.5 m vessel tight against the *centerline* limit gets the plain "(tight)" message without the arch note (centerline branch wins); severity/colour correct.
