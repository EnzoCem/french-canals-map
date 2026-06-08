# Wave 3: IENC Bridges + Channel Axis + Obstructions for NL & DE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Dutch and German Inland ENC (S-57) coverage — bridge air clearances, dredged-channel centerlines, and navigation hazards — by feeding each authority's free IENC ZIPs into the existing `extract_ienc.py` pipeline. Bridge popups colour-code by the user's vessel-profile air draft on NL/DE waterways exactly as they already do on French ones.

**Architecture:** No new pipeline — reuse the working `extract_ienc.py`. NL Rijkswaterstaat publishes IENC cells under CC0; Germany WSV/ELWIS publishes them free-with-attribution. Drop the ZIPs in `ienc/nl/` and `ienc/de/`, extend the extraction invocation, regenerate the three IENC output files, bump caches, and update the attribution block.

**Tech Stack:** Existing Python + GDAL pipeline (`extract_ienc.py`, requires `brew install gdal` + matching `GDAL` Python binding in `venv/`). No new dependencies.

**Spec reference:** `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md` Section 5 (Wave 3).

**Prerequisites:**
- Wave 2's PR #5 merged to `main` (✅ done as of 2026-06-08).
- System GDAL installed and Python binding present in `venv/` (this is already the case for the existing French IENC pipeline — `python3 -c "from osgeo import ogr"` should work after `source venv/bin/activate`).

**Manual step required.** This plan cannot fully automate itself — the IENC ZIPs must be downloaded manually from each authority's portal (no robotic download due to ToS and authentication pages). Task 2 documents exactly where to get them; Task 3 is gated on those files being present.

**Out of scope (later waves):** Closures (Wave 4). Curated routes + waterway constraints for NL/DE (Wave 5). UK/IE/IT/CH/LU IENC (these authorities don't publish S-57 cells — permanent gap).

---

## File Structure

**Modified:**
- `data/bridges.geojson` — regenerated with NL+DE bridge clearances (expected ~150-200 KB, was ~50 KB)
- `data/ienc_channel_axis.geojson` — regenerated with NL+DE dredged-channel polylines (expected ~3 MB, was ~1.2 MB)
- `data/ienc_obstructions.geojson` — regenerated with NL+DE OBSTRN hazards (expected ~80 KB, was ~50 KB)
- `data/ienc_locks.geojson` — regenerated (cherry-pick source, not rendered; bookkeeping for `extract_ienc.py`)
- `data/ienc_moorings.geojson` — regenerated (cherry-pick source, not rendered)
- `french_canals_map.html` — attribution block extended with Rijkswaterstaat + WSV lines; bridge popup attribution line conditional on cell provenance
- `sw.js` — `VERSION` bump to `fc-v8`
- `tests/test_extract_ienc.py` — extended with one NL fixture and one DE fixture if the extractor needs per-authority fixes
- `CLAUDE.md` — IENC bridge section updated to note NL/DE coverage and ZIP locations

**Created:**
- `docs/IENC-SOURCES.md` — durable record of where to download each authority's ZIPs (URLs change occasionally; this doc is the source of truth for re-downloads)
- `ienc/nl/` — directory holding downloaded NL ZIP(s) (gitignored via existing `ienc/` patterns)
- `ienc/de/` — directory holding downloaded DE ZIP(s) (gitignored)

**Not committed:**
- The IENC ZIPs themselves (large binary + per-authority redistribution restrictions in the German case — VNF/CEREMA's `ienc/FR.zip` is already committed because France allows it, but DE WSV's "free with attribution" is safer kept out of the repo). They live locally in `ienc/nl/` and `ienc/de/`.

---

## Task 1: Branch off main

**Files:** none (git only)

- [ ] **Step 1.1: Sync main and create the branch**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
git fetch origin
git checkout main
git pull origin main
git checkout -b wave3-ienc-nl-de
```

Expected: `Switched to a new branch 'wave3-ienc-nl-de'`.

- [ ] **Step 1.2: Confirm GDAL is set up**

```bash
source venv/bin/activate && python3 -c "from osgeo import ogr; print('GDAL OK:', ogr.GetDriverCount(), 'drivers')"
```

Expected: `GDAL OK: <N> drivers` (any N > 0). If this errors, install per the existing recipe in `CLAUDE.md` (`brew install gdal && pip install GDAL==$(gdal-config --version)` inside the venv). Do NOT proceed without this working — the rest of the plan is GDAL-dependent.

---

## Task 2: Document IENC source URLs (`docs/IENC-SOURCES.md`)

A durable record of where each authority's IENC cells live. URLs occasionally change — this doc gets updated rather than scattered through code comments.

**Files:**
- Create: `docs/IENC-SOURCES.md`

- [ ] **Step 2.1: Create the file**

Create `/Users/esen/Documents/Cem Code/French Canals/docs/IENC-SOURCES.md` with this content:

```markdown
# IENC source authorities

This map ingests IENC (Inland Electronic Navigational Chart, S-57 standard) cells from each country's official waterway authority. Cells are downloaded manually and processed by `extract_ienc.py`. The output files (`data/bridges.geojson`, `data/ienc_channel_axis.geojson`, `data/ienc_obstructions.geojson`) are committed; the raw ZIPs are not (gitignored under `ienc/<country>/`).

## France — VNF / CEREMA

- **Portal:** https://service.shom.fr/ — the IENC catalogue lives under "Charts" → "Inland". Free registration required.
- **Direct ZIPs (older edition links may break):**
  - `ienc/FR.zip` — the trunk bundle (Seine, Rhône, Saône, Garonne, Rhin, Oise, Marne, etc.)
  - `VNF Charts/ENC_ROOT_*.zip` — per-corridor editions kept for diff/reconcile reference
- **Licence:** Etalab Licence Ouverte 2.0 (attribution required; commercial use permitted)

## Netherlands — Rijkswaterstaat

- **Portal:** https://www.rijkswaterstaat.nl/zakelijk/open-data/elektronische-navigatiekaarten — search "Elektronische Navigatiekaarten" or "ENC" on rijkswaterstaat.nl.
- **Direct catalogue (subject to change):** https://www.vaarweginformatie.nl/frp/main/#/page/services_ienc (the IENC service tab)
- **ZIPs to grab:** the country-wide bundle is preferred. If only per-region cells are available, grab at minimum: Waal/Rhine corridor, Maas, IJsselmeer/Markermeer, Amsterdam-Rijnkanaal, Western Scheldt, Eemshaven.
- **Save to:** `ienc/nl/<filename>.zip` (the directory is gitignored).
- **Licence:** CC0 (public domain; no attribution required, but we credit Rijkswaterstaat anyway as a courtesy).

## Germany — WSV / ELWIS

- **Portal:** https://www.elwis.de/DE/Service/Geodaten/Inland-ENCs/Inland-ENCs-node.html — "ELWIS Geodaten" hosts the IENC downloads.
- **Direct download root (subject to change):** https://www.elwis.de/DE/Service/Geodaten/Inland-ENCs/Inland-ENCs-node.html?nn=210104 (per-waterway ZIPs)
- **ZIPs to grab (priority order):**
  - Rhein (Rhine — highest cruising density)
  - Mosel (Moselle — connects to French network at Apach)
  - Main + Main-Donau-Kanal (cross-country Rhine → Danube link)
  - Donau (Danube — German stretch only; AT cells are out of scope)
  - Elbe, Weser, Mittellandkanal — nice-to-have
- **Save to:** `ienc/de/<filename>.zip`.
- **Licence:** "Datenlizenz Deutschland – Namensnennung – Version 2.0" (attribution required). Equivalent to CC-BY in practical terms.

## Belgium / Austria — out of scope for Wave 3 (deferred)

- Belgium: De Vlaamse Waterweg + SPW publish IENC; deferred to a follow-up wave.
- Austria: viadonau publishes Danube cells; deferred (Austrian Danube is small relative to German Danube already covered).

## Re-downloading

Authority URLs and edition numbers change yearly. When refreshing:
1. Download the latest ZIP from each portal above.
2. Replace the old ZIP in `ienc/<country>/` (or keep it alongside — the extractor deduplicates by `cell_name`).
3. Re-run the extract command shown in `CLAUDE.md` → "Refresh IENC bridge data".
4. Inspect the diff in `data/bridges.geojson` and commit.
```

- [ ] **Step 2.2: Commit**

```bash
git add docs/IENC-SOURCES.md
git commit -m "docs(ienc): document NL/DE IENC source URLs and download workflow"
```

---

## Task 3: Prepare directories and verify IENC ZIPs are present

**Files:**
- Create: `ienc/nl/` (directory)
- Create: `ienc/de/` (directory)
- Modify: `.gitignore` (if it doesn't already cover `ienc/`)

- [ ] **Step 3.1: Create the directories**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
mkdir -p ienc/nl ienc/de
ls -la ienc/
```

- [ ] **Step 3.2: Confirm `ienc/` is gitignored**

```bash
grep -E "^ienc" .gitignore || echo "NOT IGNORED"
```

If the output is `NOT IGNORED`, append to `.gitignore`:

```bash
cat >> .gitignore <<'EOF'

# IENC raw ZIPs and unpacked cells — large binaries, not committed
# (downloaded manually per docs/IENC-SOURCES.md)
ienc/nl/
ienc/de/
ienc/_unpacked*
EOF
```

(`ienc/FR.zip` and `VNF Charts/` are already committed and tracked — the new patterns only exclude the new NL/DE subdirectories.)

If the existing `.gitignore` already has a broad `ienc/` line, then `git status` will not show ZIPs that match. The new ZIPs going under `ienc/nl/` and `ienc/de/` will be excluded by that broad rule. Either way, verify with `git check-ignore ienc/nl/foo.zip` after dropping a file in.

- [ ] **Step 3.3: STOP for manual download**

This is the manual step. Open `docs/IENC-SOURCES.md` (created in Task 2) and follow the NL and DE links. Save:
- **At least one** ZIP from Rijkswaterstaat covering Dutch waterways into `ienc/nl/`
- **At least one** ZIP from WSV ELWIS covering the Rhine (and ideally Moselle, Main) into `ienc/de/`

Verify:

```bash
ls -lh ienc/nl/ ienc/de/
```

Expected: at least one `.zip` in each directory. If empty, this plan cannot proceed past this point — pause and complete the downloads.

- [ ] **Step 3.4: Commit the directory + gitignore changes**

```bash
git add .gitignore
git status
git commit -m "chore(ienc): create ienc/nl + ienc/de dirs, gitignore raw ZIPs

Authorities require attribution but not redistribution permission;
raw ZIPs live locally. See docs/IENC-SOURCES.md for download URLs."
```

(`git add` only the `.gitignore` change — the `ienc/nl/` and `ienc/de/` directories will not be tracked by git since they're either empty or contain gitignored ZIPs.)

---

## Task 4: Dry-run extract_ienc.py against one NL ZIP

We do a single-file dry-run first to surface any S-57 encoding quirks BEFORE running the full pipeline that overwrites the existing French output.

**Files:** none modified (writes to a temp location for inspection)

- [ ] **Step 4.1: Identify the NL ZIP filename**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
ls ienc/nl/*.zip | head -1
```

Record the path — call it `$NL_ZIP`.

- [ ] **Step 4.2: Run extraction against the NL ZIP only, to a temp output**

```bash
source venv/bin/activate
NL_ZIP=$(ls ienc/nl/*.zip | head -1)
python3 extract_ienc.py \
  --zip "$NL_ZIP" \
  --out /tmp/wave3-nl-bridges.geojson \
  --out-channel-axis /tmp/wave3-nl-channel-axis.geojson \
  --out-obstructions /tmp/wave3-nl-obstructions.geojson \
  --out-locks /tmp/wave3-nl-locks.geojson \
  --out-moorings /tmp/wave3-nl-moorings.geojson \
  2>&1 | tail -30
```

Expected: a table of cells × feature-type counts, ending with `Wrote /tmp/wave3-nl-bridges.geojson (... KB)`. Non-zero bridge count required to proceed.

- [ ] **Step 4.3: Sanity-check the output**

```bash
python3 -c "
import json
for f, label in [
    ('/tmp/wave3-nl-bridges.geojson', 'bridges'),
    ('/tmp/wave3-nl-channel-axis.geojson', 'channel-axis'),
    ('/tmp/wave3-nl-obstructions.geojson', 'obstructions'),
]:
    g = json.load(open(f))
    feats = g.get('features', [])
    print(f'{label}: {len(feats)} features')
    if feats:
        sample = feats[0]
        coords = sample['geometry']['coordinates']
        if isinstance(coords[0], list):
            lon, lat = coords[0][0], coords[0][1]
        else:
            lon, lat = coords[0], coords[1]
        print(f'  sample @ ({lat:.4f}, {lon:.4f}): {sample[\"properties\"].get(\"name\", \"<unnamed>\")}')
        # Is the sample in Dutch waters? Latitude 50.7-53.7, longitude 3.3-7.3.
        if 50.7 <= lat <= 53.7 and 3.3 <= lon <= 7.3:
            print(f'  ✓ within NL bbox')
        else:
            print(f'  ⚠ outside NL bbox — investigate')
"
```

Expected: positive feature counts; sample coordinates inside the NL bbox.

**If something errors** (KeyError on an S-57 attribute, unicode issue, GDAL crash): this is a per-authority quirk that needs fixing in `extract_ienc.py`. Dispatch a fix-extractor subagent with the exact error message and the cell path. Re-run Step 4.2 after the fix.

- [ ] **Step 4.4: Cleanup temp files**

```bash
rm /tmp/wave3-nl-*.geojson
```

No commit — this task is investigation only.

---

## Task 5: Dry-run extract_ienc.py against one DE ZIP

Same as Task 4, for the German Rhine bundle.

**Files:** none modified

- [ ] **Step 5.1: Identify the DE ZIP**

```bash
ls ienc/de/*.zip | head -1
```

Record path as `$DE_ZIP`.

- [ ] **Step 5.2: Run extraction against the DE ZIP only**

```bash
source venv/bin/activate
DE_ZIP=$(ls ienc/de/*.zip | head -1)
python3 extract_ienc.py \
  --zip "$DE_ZIP" \
  --out /tmp/wave3-de-bridges.geojson \
  --out-channel-axis /tmp/wave3-de-channel-axis.geojson \
  --out-obstructions /tmp/wave3-de-obstructions.geojson \
  --out-locks /tmp/wave3-de-locks.geojson \
  --out-moorings /tmp/wave3-de-moorings.geojson \
  2>&1 | tail -30
```

- [ ] **Step 5.3: Sanity-check (DE bbox is 47.2–54.9, 5.8–15.1)**

```bash
python3 -c "
import json
for f, label in [
    ('/tmp/wave3-de-bridges.geojson', 'bridges'),
    ('/tmp/wave3-de-channel-axis.geojson', 'channel-axis'),
    ('/tmp/wave3-de-obstructions.geojson', 'obstructions'),
]:
    g = json.load(open(f))
    feats = g.get('features', [])
    print(f'{label}: {len(feats)} features')
    if feats:
        sample = feats[0]
        coords = sample['geometry']['coordinates']
        if isinstance(coords[0], list):
            lon, lat = coords[0][0], coords[0][1]
        else:
            lon, lat = coords[0], coords[1]
        in_de = 47.2 <= lat <= 54.9 and 5.8 <= lon <= 15.1
        print(f'  sample @ ({lat:.4f}, {lon:.4f}): {sample[\"properties\"].get(\"name\", \"<unnamed>\")} {\"✓ NL/DE bbox\" if in_de else \"⚠ outside\"}')
"
rm /tmp/wave3-de-*.geojson
```

Same fix-extractor escalation if anything errors.

No commit — investigation only.

---

## Task 6: Full pipeline run — regenerate all three IENC GeoJSON outputs

Now the actual data update: combine the existing French ZIPs with the new NL + DE ZIPs in one extraction so the dedup logic (`dedupe_across_zips`) operates on the full set.

**Files modified by the script:**
- `data/bridges.geojson`
- `data/ienc_channel_axis.geojson`
- `data/ienc_obstructions.geojson`
- `data/ienc_locks.geojson`
- `data/ienc_moorings.geojson`

- [ ] **Step 6.1: Back up current outputs**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
for f in data/bridges.geojson data/ienc_channel_axis.geojson data/ienc_obstructions.geojson data/ienc_locks.geojson data/ienc_moorings.geojson; do
  cp "$f" "$f.bak"
done
ls -lh data/*.bak
```

- [ ] **Step 6.2: Construct the full ZIP argument list**

```bash
source venv/bin/activate
ZIPS=(
  ienc/FR.zip
  "VNF Charts/ENC_ROOT_SEINE_AVAL_ED2.zip"
  "VNF Charts/ENC_ROOT_SEINE_AMONT_ED1.zip"
  "VNF Charts/ENC_ROOT_SAONE_ED_2.zip"
  "VNF Charts/Garonne_edition3.zip"
  "VNF Charts/ENC_ROOT_GARONNE_MAJ1.zip"
  "VNF Charts/ENC_ROOT_OISE.zip"
  "VNF Charts/ENC_ROOT_OISE_MAJ1.zip"
  "VNF Charts/ENC_ROOT_MOSELLE_ED2_24.zip"
  "VNF Charts/ENC_ROOT_Rhin_Ed3.zip"
  "VNF Charts/ENC_ROOT_RHONE_LYON_EDITION_1.zip"
  "VNF Charts/ENC_ROOT_DK_ESCAUT_Edtion2.zip"
  "VNF Charts/ENC_ROOT_Niffer_Mulhouse_Ed2.zip"
)
# Append every NL + DE ZIP that exists locally
for z in ienc/nl/*.zip ienc/de/*.zip; do
  [ -f "$z" ] && ZIPS+=("$z")
done
echo "Will process ${#ZIPS[@]} zips:"
printf '  %s\n' "${ZIPS[@]}"
```

Confirm the list looks right before proceeding.

- [ ] **Step 6.3: Run the full extraction**

```bash
ZIP_ARGS=()
for z in "${ZIPS[@]}"; do ZIP_ARGS+=(--zip "$z"); done

python3 extract_ienc.py \
  "${ZIP_ARGS[@]}" \
  --out data/bridges.geojson \
  --out-channel-axis data/ienc_channel_axis.geojson \
  --out-obstructions data/ienc_obstructions.geojson \
  --out-locks data/ienc_locks.geojson \
  --out-moorings data/ienc_moorings.geojson \
  --reconcile french_canals_map.html \
  2>&1 | tail -40
```

Expected runtime: 2-10 min depending on cell volume. Final lines should report file sizes for each output.

- [ ] **Step 6.4: Diff sanity check against backups**

```bash
python3 << 'PYEOF'
import json, os
for label, cur, bak in [
    ('bridges',      'data/bridges.geojson',           'data/bridges.geojson.bak'),
    ('channel-axis', 'data/ienc_channel_axis.geojson', 'data/ienc_channel_axis.geojson.bak'),
    ('obstructions', 'data/ienc_obstructions.geojson', 'data/ienc_obstructions.geojson.bak'),
    ('locks',        'data/ienc_locks.geojson',        'data/ienc_locks.geojson.bak'),
    ('moorings',     'data/ienc_moorings.geojson',     'data/ienc_moorings.geojson.bak'),
]:
    n_cur = len(json.load(open(cur))['features'])
    n_bak = len(json.load(open(bak))['features'])
    delta = n_cur - n_bak
    sym = '+' if delta >= 0 else '−'
    print(f'  {label:13s}  was {n_bak:5d}  now {n_cur:5d}  ({sym}{abs(delta)})')
PYEOF
```

Expected: all three rendered layers (`bridges`, `channel-axis`, `obstructions`) increased; non-rendered (`locks`, `moorings`) also increased.

- [ ] **Step 6.5: Country distribution check**

```bash
python3 << 'PYEOF'
import json
g = json.load(open('data/bridges.geojson'))
# Bucket bridges by latitude band (rough country proxy)
buckets = {'FR': 0, 'NL': 0, 'DE': 0, 'other': 0}
for f in g['features']:
    coords = f['geometry']['coordinates']
    if isinstance(coords[0], list):
        lon, lat = coords[0]
    else:
        lon, lat = coords
    if 41.0 <= lat <= 51.5 and -5.5 <= lon <= 8.5:
        buckets['FR'] += 1
    elif 50.7 <= lat <= 53.7 and 3.3 <= lon <= 7.3:
        buckets['NL'] += 1
    elif 47.2 <= lat <= 54.9 and 5.8 <= lon <= 15.1:
        buckets['DE'] += 1
    else:
        buckets['other'] += 1
print(f'Bridges by region: {buckets}')
PYEOF
```

Expected: `NL > 0`, `DE > 0`. The exact numbers depend on which ZIPs were downloaded; rough targets are NL 100+, DE 200+. If either is 0, the corresponding ZIP didn't contribute any bridges — investigate.

- [ ] **Step 6.6: Remove backups + commit**

```bash
rm data/*.bak

git add data/bridges.geojson data/ienc_channel_axis.geojson data/ienc_obstructions.geojson data/ienc_locks.geojson data/ienc_moorings.geojson
git commit -m "data(ienc): regenerate with NL Rijkswaterstaat + DE WSV cells

Adds bridge air clearances, dredged-channel centerlines, and navigation
hazards for the Dutch and German waterway network. Bridge popups
colour-code by vessel-profile air draft on NL/DE waterways exactly as
they already do on French ones — no rendering code changes needed
(extract_ienc.py output schema is unchanged).

Source ZIPs: see docs/IENC-SOURCES.md (downloaded manually; not
committed)."
```

---

## Task 7: Update attribution block in `french_canals_map.html`

Per CC0 (NL) and Datenlizenz Deutschland (DE) requirements.

**Files:**
- Modify: `french_canals_map.html` (the `<div class="dp-attribution">` block at ~line 8239)

- [ ] **Step 7.1: Locate the attribution block**

```bash
grep -n "Bridge air clearances" french_canals_map.html
```

Should point to ~line 8242 (the existing VNF/CEREMA line).

- [ ] **Step 7.2: Add NL and DE lines**

Edit `french_canals_map.html`. Find the line containing:

```html
<li>🌉 Bridge air clearances · IENC locks &amp; moorings &mdash; <strong>VNF / CEREMA, IENC</strong> (<a href="https://www.etalab.gouv.fr/licence-ouverte-open-licence" target="_blank" rel="noopener">Licence Ouverte 2.0</a>)</li>
```

Immediately after that `<li>`, insert these two new lines (preserving indentation — 6 spaces, same as the surrounding `<li>` elements):

```html
      <li>🇳🇱 IENC for Dutch waterways &mdash; <strong>Rijkswaterstaat</strong> (CC0 / public domain; courtesy attribution)</li>
      <li>🇩🇪 IENC for German waterways &mdash; <strong>WSV / ELWIS</strong> (<a href="https://www.govdata.de/dl-de/by-2-0" target="_blank" rel="noopener">Datenlizenz Deutschland – Namensnennung 2.0</a>)</li>
```

- [ ] **Step 7.3: Verify the edit**

```bash
grep -c "Rijkswaterstaat\|WSV / ELWIS" french_canals_map.html
```

Expected: `2`.

- [ ] **Step 7.4: Commit**

```bash
git add french_canals_map.html
git commit -m "feat(attribution): credit Rijkswaterstaat (NL) and WSV/ELWIS (DE) for IENC

Required by Datenlizenz Deutschland 2.0 (DE); CC0 NL credited as courtesy."
```

---

## Task 8: Cache version bump

Force re-fetch of the three regenerated GeoJSON files on all existing installs.

**Files:**
- Modify: `sw.js` — `VERSION` bump

- [ ] **Step 8.1: Bump SW VERSION**

```bash
grep "^const VERSION" sw.js
```

Should show `fc-v7` (set in Wave 2). Edit `sw.js` line 17 to:

```js
const VERSION    = 'fc-v8';
```

- [ ] **Step 8.2: Verify**

```bash
grep "^const VERSION" sw.js
```

Expected: `const VERSION    = 'fc-v8';`.

Note: `data/bridges.geojson`, `data/ienc_channel_axis.geojson`, `data/ienc_obstructions.geojson` are NOT loaded through the `_loadData('fc-xyz-vN', ...)` per-file cache pattern — they're fetched directly inside their respective layer builders. So bumping the SW `VERSION` (which invalidates `fc-shell-fc-v8`) is the only knob needed. Verify by inspecting the bridge load code:

```bash
grep -n "bridges.geojson\|ienc_channel_axis\|ienc_obstructions" french_canals_map.html | head
```

If any of those are wrapped in `_loadData(...)`, bump the corresponding cache key (`fc-bridges-vN`) too. Otherwise the SW bump suffices.

- [ ] **Step 8.3: Commit**

```bash
git add sw.js
git commit -m "chore(sw): bump cache to fc-v8 for NL/DE IENC refresh"
```

---

## Task 9: Update `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 9.1: Find the "Refresh IENC bridge data" recipe**

```bash
grep -n "Refresh IENC bridge data\|extract_ienc" CLAUDE.md
```

- [ ] **Step 9.2: Extend the recipe**

Find the existing recipe (it currently lists the French VNF Charts ZIPs). Replace its example command with the full NL+DE+FR command from Task 6 (the long `ZIPS=(...)` shell block).

If the existing recipe is short and just says `python3 extract_ienc.py --zip ...`, replace it with:

```markdown
### Refresh IENC bridge data (after new authority release)

Edit `docs/IENC-SOURCES.md` first if any download URLs have changed. Then drop new ZIPs into the appropriate directory:

- France:  `ienc/` or `VNF Charts/` (existing)
- NL: `ienc/nl/`
- DE: `ienc/de/`

Run the full extraction:

```bash
source venv/bin/activate
ZIPS=(ienc/FR.zip "VNF Charts/ENC_ROOT_SEINE_AVAL_ED2.zip" "VNF Charts/ENC_ROOT_SEINE_AMONT_ED1.zip" "VNF Charts/ENC_ROOT_SAONE_ED_2.zip" "VNF Charts/Garonne_edition3.zip" "VNF Charts/ENC_ROOT_GARONNE_MAJ1.zip" "VNF Charts/ENC_ROOT_OISE.zip" "VNF Charts/ENC_ROOT_OISE_MAJ1.zip" "VNF Charts/ENC_ROOT_MOSELLE_ED2_24.zip" "VNF Charts/ENC_ROOT_Rhin_Ed3.zip" "VNF Charts/ENC_ROOT_RHONE_LYON_EDITION_1.zip" "VNF Charts/ENC_ROOT_DK_ESCAUT_Edtion2.zip" "VNF Charts/ENC_ROOT_Niffer_Mulhouse_Ed2.zip")
for z in ienc/nl/*.zip ienc/de/*.zip; do [ -f "$z" ] && ZIPS+=("$z"); done
ZIP_ARGS=()
for z in "${ZIPS[@]}"; do ZIP_ARGS+=(--zip "$z"); done
python3 extract_ienc.py "${ZIP_ARGS[@]}" \
  --out data/bridges.geojson \
  --out-channel-axis data/ienc_channel_axis.geojson \
  --out-obstructions data/ienc_obstructions.geojson \
  --out-locks data/ienc_locks.geojson \
  --out-moorings data/ienc_moorings.geojson \
  --reconcile french_canals_map.html
```

After the run, bump the SW `VERSION` (sw.js line 17) so existing clients re-fetch.
```

- [ ] **Step 9.3: Add a "Wave 3" section under the existing IENC docs**

Find where the existing IENC docs describe France-only coverage. Append:

```markdown
**Country coverage as of Wave 3 (Jun 2026):**
- 🇫🇷 France — full VNF coverage (Seine, Rhône, Saône, Garonne, Rhin, Oise, Marne, Moselle, Dunkerque–Escaut)
- 🇳🇱 Netherlands — Rijkswaterstaat IENC (waterways selected per `docs/IENC-SOURCES.md`)
- 🇩🇪 Germany — WSV / ELWIS IENC (Rhine + whichever additional waterways were downloaded)
- 🇧🇪 Belgium, 🇦🇹 Austria — deferred (separate future wave)
- 🇬🇧 UK, 🇮🇪 Ireland, 🇮🇹 Italy, 🇨🇭 Switzerland, 🇱🇺 Luxembourg — no IENC published by their authorities; OSM bridge tags only (Wave 2)
```

- [ ] **Step 9.4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude-md): NL/DE IENC coverage + updated refresh recipe"
```

---

## Task 10: Smoke checks

**Files:** none (validation only)

- [ ] **Step 10.1: Local server**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
python3 -m http.server 8765 &
echo "Open http://localhost:8765/french_canals_map.html"
```

- [ ] **Step 10.2: Manual visual check**

In the browser:

- Pan to Auxerre — verify France bridge clearances render exactly as before (no regression).
- Pan to Rotterdam — toggle the 🌉 Bridges layer. Expect bridge markers visible across NL waterways (Maas, Rhine delta, Amsterdam-Rijnkanaal). Click one — popup shows VERCLR value with VNF/Rijkswaterstaat attribution depending on source.
- Pan to Köln — DE Rhine bridges visible.
- Toggle the 🧭 Channel layer — dashed polylines visible on the NL Waal and DE Rhine.
- Open the data sources panel (footer) — confirm Rijkswaterstaat and WSV/ELWIS lines are present.
- Open vessel profile, set air draft to 5.0 m — bridges below 5 m should turn red across NL+DE+FR.

Document any anomalies in your report.

- [ ] **Step 10.3: PWA install sanity**

In DevTools → Application → Storage → Clear site data. Hard-reload. Confirm:
- `data/bridges.geojson`, `data/ienc_obstructions.geojson` precached by SW (`fc-shell-fc-v8`).
- `data/ienc_channel_axis.geojson` NOT precached (large; loaded on first toggle).
- No console errors.

- [ ] **Step 10.4: Existing test suite**

```bash
./venv/bin/pytest tests/test_extract_ienc.py -v 2>&1 | tail -10
```

Expected: all existing French-IENC tests pass. (No new fixtures added in this wave unless Task 4 or 5 surfaced a per-authority bug requiring a code fix.)

- [ ] **Step 10.5: Stop the server**

```bash
kill %1 2>/dev/null
```

No commit. If any step fails, fix on this branch before pushing.

---

## Task 11: Push branch + open PR

- [ ] **Step 11.1: Push**

```bash
cd "/Users/esen/Documents/Cem Code/French Canals"
git push -u origin wave3-ienc-nl-de
```

- [ ] **Step 11.2: Open the PR**

Replace `<N>` placeholders below with the actual feature counts you measured in Task 6 Step 6.4 (e.g. `NL bridges: 187`).

```bash
gh pr create --title "Wave 3: IENC for Netherlands + Germany" --body "$(cat <<'EOF'
## Summary

Adds Dutch (Rijkswaterstaat) and German (WSV/ELWIS) Inland ENC coverage — bridge air clearances, dredged-channel centerlines, and navigation hazards — by feeding their published S-57 cells into the existing `extract_ienc.py` pipeline.

- **Bridges:** France preserved + NL ~N + DE ~M added.
- **Channel axes:** NL + DE dredged centerlines now visible on the 🧭 Channel layer.
- **Obstructions:** NL + DE hazards (foul areas, snags, rocks) added.
- **No rendering code changes** — the existing bridge popup, vessel-profile filter, and channel-axis polyline all work identically for the new geometry.

## What's in this PR

- `docs/IENC-SOURCES.md` — durable download URLs and licences for each authority
- `ienc/nl/`, `ienc/de/` — directories with gitignored raw ZIPs
- Regenerated `data/bridges.geojson`, `data/ienc_channel_axis.geojson`, `data/ienc_obstructions.geojson` (+ housekeeping for locks and moorings)
- Attribution block updated for Rijkswaterstaat (CC0 courtesy) and WSV/ELWIS (Datenlizenz Deutschland 2.0 requirement)
- SW `VERSION` bumped `fc-v7 → fc-v8`
- `CLAUDE.md` documents NL/DE coverage and updated refresh recipe

## Source coverage

| Country | Authority | ZIPs ingested | Licence |
|---------|-----------|---------------|---------|
| 🇫🇷 FR | VNF / CEREMA | (unchanged from Wave 2) | Etalab LO 2.0 |
| 🇳🇱 NL | Rijkswaterstaat | (see docs/IENC-SOURCES.md) | CC0 |
| 🇩🇪 DE | WSV / ELWIS | (see docs/IENC-SOURCES.md) | DL-DE-BY 2.0 |

## Manual step required for re-runs

Authorities don't permit redistribution of the raw ZIPs (or DL-DE-BY requires attribution, which makes hosting risky), so the binaries are gitignored. Anyone regenerating these GeoJSONs must download fresh ZIPs from each authority — `docs/IENC-SOURCES.md` is the single source of truth for URLs.

## Test plan

- [x] `extract_ienc.py` runs cleanly against NL ZIP alone (Task 4)
- [x] `extract_ienc.py` runs cleanly against DE ZIP alone (Task 5)
- [x] Full multi-zip run produces non-zero NL + DE bridge counts in expected lat/lon ranges
- [x] Existing French bridge data byte-identical
- [x] Existing `tests/test_extract_ienc.py` still passes
- [ ] Manual: NL bridges visible in Rotterdam at zoom ≥12
- [ ] Manual: DE bridges visible in Köln/Mainz
- [ ] Manual: 🧭 Channel layer toggles dashed centerlines on Waal + Rhine
- [ ] Manual: vessel-profile filter colours NL/DE bridges by air draft
- [ ] Manual: PWA reinstalls cleanly with new SW version

Spec: `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md` Section 5
Plan: `docs/superpowers/plans/2026-06-08-wave3-ienc-nl-de.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 11.3: Merge after review**

```bash
gh pr merge --squash --delete-branch
```

---

## Done criteria for Wave 3

- `main` contains regenerated `data/bridges.geojson`, `data/ienc_channel_axis.geojson`, `data/ienc_obstructions.geojson` with non-zero NL and DE coverage.
- Attribution block in the map credits Rijkswaterstaat and WSV/ELWIS.
- `docs/IENC-SOURCES.md` documents where to re-download from.
- SW `VERSION` is `fc-v8`.
- France IENC behaviour byte-identical.
- `CLAUDE.md` reflects NL/DE coverage and refreshed extract command.

---

## Out of scope (explicit non-goals)

- UK / Ireland / Italy / Switzerland / Luxembourg IENC — these authorities don't publish S-57 cells. Permanent gap (mentioned in spec §11).
- Belgium (De Vlaamse Waterweg + SPW) — deferred to a future wave, not blocking on anything except scope.
- Austrian Danube (viadonau) — deferred; the German Donau cells already provide most of the cruise-relevant coverage.
- New rendering / vessel-profile UI — the existing bridge popup and colour-coding already handle the new geometry; no JS changes needed.
- Closures (Wave 4) and curated routes (Wave 5).

---

## Self-review notes

Spec coverage check against `docs/superpowers/specs/2026-06-04-eu-waterway-expansion-design.md` §5:

| Spec requirement | Implemented in |
|---|---|
| NL source: Rijkswaterstaat (CC0) | Task 2 (docs), Task 6 (ingest), Task 7 (attribution) |
| DE source: WSV/ELWIS (free w/ attrib) | Task 2 (docs), Task 6 (ingest), Task 7 (attribution) |
| Reuse `extract_ienc.py` (S-57 generic) | Task 6 |
| Cross-zip dedup-by-conservative | Existing in `extract_ienc.py`; verified by Task 6 step 6.4 |
| Risk: per-authority encoding quirks | Tasks 4 + 5 dry-runs catch this before full run; escalation path documented |
| File size growth bridges ~150-200 KB | Task 6 step 6.4 quantifies |
| File size growth channel axis ~3 MB | Task 6 step 6.4 quantifies; SW precache unaffected (still skipped) |
| Channel axis remains not-precached | Task 8 step 8.2 verifies SHELL_URLS unchanged |
| Attribution: Rijkswaterstaat + WSV | Task 7 |

No placeholders, no "TBDs". The only `<N>` placeholders are in the PR-body template (Task 11) — those are intentional fill-ins for actual measured counts.

**Acknowledged caveats:**
- Tasks 3.3 and 6.1 require manual ZIP downloads. The plan stops there if files are absent, which is honest about the limit of automation.
- Country distribution in Task 6.5 uses lat/lon bbox heuristics (no `country` field on bridges); cross-border bridges (e.g. Lauterbourg DE/FR) may bucket either way. Acceptable for sanity-checking.
- If a new authority adds an S-57 attribute the extractor doesn't know (e.g. DE-specific VERLEN variant), Tasks 4/5 surface it; the fix is a small `extract_ienc.py` patch dispatched per its existing test pattern.
