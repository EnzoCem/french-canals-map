# Waterways Continuity & Name Normalisation — Design Spec

**Date:** 2026-03-31
**Status:** Approved

---

## Problem

The `waterways.geojson` overlay was built piecemeal via a 12-region Overpass sweep. Two distinct issues exist:

1. **Visual gaps** — many of the 42 navigable waterways have severely fragmented geometry (Canal des Vosges: 97% dangling endpoints, Canal de Nantes à Brest: 95%, Canal du Nivernais: 95%, River Rhine: 73%, etc.). On screen these appear as broken lines, especially at higher zoom levels.

2. **Name mismatches** — 24 of 52 `WATERWAY_CONSTRAINTS` keys do not match any GeoJSON feature name (e.g. constraint uses `'Saône'`, GeoJSON uses `'River Saône'`; constraint uses `'Canal latéral à la Garonne'`, GeoJSON uses `'Canal Latéral à la Garonne'`). This silently breaks vessel-profile waterway colouring for ~46% of constrained waterways. Additionally, several waterways have duplicate case-variant names in the GeoJSON (e.g. `Canal Entre Champagne et Bourgogne` vs `Canal entre Champagne et Bourgogne`).

---

## Scope

Fix only the **42 waterways referenced by `ROUTE_TO_WATERWAYS`** (the route planner's navigable network). All other features in the GeoJSON (~170 names) are left untouched.

`Canals of Paris` (route 9) is excluded — it is a display label, not an OSM name. The Paris canals exist in the GeoJSON under their individual names and are unaffected.

---

## Architecture

Two deliverables:

| Deliverable | What it does |
|---|---|
| `fill_waterways.py` | Fetches 42 waterways from OSM, stitches ways into continuous LineStrings, RDP-simplifies, merges into `waterways.geojson` |
| JS patch in `french_canals_map.html` | Adds `constraintLookup()` helper + bumps cache version |

---

## Part 1 — `fill_waterways.py`

### Fetch strategy (per waterway)

```
1. Try: relation[type=waterway][name="<osm_name>"] within France bounding box
2. If relation found → extract all member ways → collect their node coordinates
3. If no relation → fallback: way[waterway][name="<osm_name>"] within France bbox
4. Stitch → RDP simplify → store under app name
```

### OSM name map

Some `ROUTE_TO_WATERWAYS` names differ from OSM names. The script carries an explicit `OSM_NAME_MAP` dict:

| App name | OSM query name |
|---|---|
| `River Seine` | `La Seine` |
| `River Saône` | `La Saône` (also try `River Saône`) |
| `River Rhône` | `Le Rhône` (also try `River Rhône`) |
| `River Marne` | `La Marne` |
| `River Oise` | `L'Oise` |
| `Canal de Garonne` | `Canal latéral à la Garonne` |
| `Canal de la Somme` | `Canal de la Somme` |
| `River Charente` | `La Charente` (also try `River Charente`) |

All other app names are queried as-is.

Features are stored in the GeoJSON under the **app name** (not the OSM name), so `ROUTE_TO_WATERWAYS` and route highlighting continue to work without JS changes.

### The 42 waterways

```
River Seine, River Yonne, River Marne, Canal latéral à la Marne,
Canal latéral à l'Aisne, Canal de l'Oise à l'Aisne, River Oise,
Canal du Loing, Canal latéral à la Loire, Canal de Briare,
Canal du Centre, Canal du Nivernais, Canal de Bourgogne,
River Saône, Canal du Rhône au Rhin, River Rhône,
Canal de Donzère-Mondragon, Canal du Rhône à Sète,
Liaison Dunkerque–Escaut, Canal de Calais, River Aa, River Lys,
Canal du Nord, Canal de Saint-Quentin, Canal de la Somme,
Canal des Ardennes, Canal de la Meuse, River Moselle,
Canal de la Marne au Rhin, Canal entre Champagne et Bourgogne,
Canal des Vosges, Canal d'Ille-et-Rance, Canal de Nantes à Brest,
River Loire, River Mayenne, River Sarthe, Canal du Midi,
Canal de Garonne, Canal de la Robine, River Charente, River Rhine,
Canal de la Marne à la Saône
```

### Way stitching algorithm

```
1. Build endpoint index: coord (rounded to 1e-5°, ~1m) → list of way IDs
2. Walk greedily from each unvisited way:
     a. Append current way's coordinates to the active chain
     b. Look up the chain's tail coordinate in the endpoint index
     c. If an unvisited neighbour is found → extend (reverse if needed)
     d. If none found → save chain as a LineString, start a new chain
3. Output: 1–N connected LineStrings per waterway
   (branches, bypasses, and lock cuts become separate features — correct behaviour)
```

Coordinate tolerance for endpoint matching: **1e-5 degrees** (~1m). Tight enough to avoid false joins, loose enough for float rounding in OSM exports.

### RDP simplification

- Tolerance: **33m** (≈ 0.0003° at French latitudes) — same as the original script
- Applied per LineString after stitching
- Library: `rdp` Python package

### GeoJSON merge

```
1. Load existing waterways.geojson
2. Remove all features whose `properties.name` is in the 42-waterway list
   (this also removes duplicate case-variants like "Canal Entre Champagne et Bourgogne")
3. Append the freshly fetched + stitched features
4. Write to a temp file, then rename atomically
5. Print summary: features removed / features added / final total
```

Output format: minified single-line JSON (matches current file format).

**Feature properties on new features:** `{name: <app_name>, route: <first route number from ROUTE_TO_WATERWAYS>, section: 1}`. Where a waterway serves multiple routes (e.g. `Canal du Centre` appears in route 10), the first route number is used — this is sufficient for the colour-lookup and highlight logic.

**Expected feature count change:** from ~7,300 features down to ~500–800 (stitching collapses hundreds of short ways into a few long LineStrings per waterway). File size stays well under 2MB.

### Script dependencies

```
pip install requests rdp
```

No other dependencies beyond the Python standard library.

---

## Part 2 — JS name normalisation

### Problem

`getWaterwayNavStatus()` does an exact string lookup:
```js
const c = WATERWAY_CONSTRAINTS[name];
```

This misses 24 of 52 constraint keys due to prefix differences (`River`, `La`, `Le`, `L'`) and capitalisation variants.

### Fix

Add `constraintLookup(name)` helper in `french_canals_map.html`:

```js
function constraintLookup(name) {
  if (!name) return null;
  const norm = s => s.toLowerCase()
    .replace(/^(river |la |le |l'|les |the )/i, '')
    .trim();
  const key = norm(name);
  for (const [k, v] of Object.entries(WATERWAY_CONSTRAINTS)) {
    if (norm(k) === key) return v;
  }
  return null;
}
```

Replace the single `WATERWAY_CONSTRAINTS[name]` call in `getWaterwayNavStatus()` with `constraintLookup(name)`.

**Duplicate case-variants** (e.g. `Canal Entre Champagne et Bourgogne` vs `Canal entre Champagne et Bourgogne`) are resolved automatically — both normalise to the same key. No GeoJSON surgery needed beyond the merge step above.

**Scope:** ~12 lines added/changed in `french_canals_map.html`. No changes to `WATERWAY_CONSTRAINTS` keys themselves.

### Cache version bump

```js
// french_canals_map.html — bump so all browsers re-fetch updated geojson
const WATERWAY_CACHE_VERSION = 'waterways-v3';  // was 'waterways-v2'
```

---

## What is not in scope

- Fixing the ~170 non-navigable waterways in the GeoJSON
- Re-fetching `Canals of Paris` (route 9)
- Changes to `ROUTE_TO_WATERWAYS`, `WATERWAY_CONSTRAINTS` key names, or route planner logic
- Any changes to marker data, sidebar, or other app features
