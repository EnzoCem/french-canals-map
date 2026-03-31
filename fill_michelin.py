#!/usr/bin/env python3
"""
fill_michelin.py — Update MICHELIN_RESTAURANTS in french_canals_map.html

Downloads the latest Michelin restaurant data from:
  https://github.com/ngshiheng/michelin-my-maps

Filters to France, excludes "Selected Restaurants" (unstarred/non-Bib),
sorts by star count (3→2→1→Bib), and regenerates the
MICHELIN_RESTAURANTS constant in french_canals_map.html.

Usage:
    python3 fill_michelin.py              # update in-place + print report
    python3 fill_michelin.py --preview    # print report only, don't write

Run once per year after the February Michelin Guide announcements.
After running, deploy with:
    git add french_canals_map.html
    git commit -m "Update Michelin restaurants YYYY"
    git push
"""

import csv
import io
import re
import sys
import urllib.request
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────

CSV_URL = (
    'https://raw.githubusercontent.com/ngshiheng/michelin-my-maps'
    '/main/data/michelin_my_maps.csv'
)

HTML_FILE = Path(__file__).parent / 'french_canals_map.html'

# Award strings → star count.  "Selected Restaurants" → None (excluded).
AWARD_MAP = {
    '3 stars':        3,
    '2 stars':        2,
    '1 star':         1,
    'bib gourmand':   0,
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_award(raw: str):
    """Return star count (0 = Bib Gourmand) or None to skip the row."""
    return AWARD_MAP.get(raw.strip().lower())


def js_str(s: str) -> str:
    """Escape a Python string for embedding in a JS single-quoted literal."""
    return s.replace('\\', '\\\\').replace("'", "\\'")


def count_existing(html: str) -> int:
    m = re.search(r"id:'mr_(\d+)'", html)
    if not m:
        return 0
    # Find the last id in the block
    all_ids = re.findall(r"id:'mr_(\d+)'", html)
    return int(all_ids[-1]) if all_ids else 0


# ── Main logic ─────────────────────────────────────────────────────────────────

def fetch_csv() -> str:
    print(f'⬇  Fetching {CSV_URL} …')
    req = urllib.request.Request(CSV_URL, headers={'User-Agent': 'fill_michelin/1.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode('utf-8')


def parse_france(csv_text: str):
    """
    Parse the CSV and return a list of dicts for French restaurants only
    (Stars 1/2/3 + Bib Gourmand; Selected Restaurants excluded).
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    entries = []
    skipped_country = 0
    skipped_award   = 0
    skipped_coords  = 0

    for row in reader:
        location = row.get('Location', '')

        # ── Country filter ──────────────────────────────────────────────────
        if ', France' not in location:
            skipped_country += 1
            continue

        # ── Award filter ────────────────────────────────────────────────────
        stars = parse_award(row.get('Award', ''))
        if stars is None:          # "Selected Restaurants" or unknown
            skipped_award += 1
            continue

        # ── Coordinates ─────────────────────────────────────────────────────
        try:
            lat = float(row['Latitude'])
            lon = float(row['Longitude'])
        except (KeyError, ValueError):
            skipped_coords += 1
            continue

        # ── Fields ──────────────────────────────────────────────────────────
        name    = row.get('Name',       '').strip()
        cuisine = row.get('Cuisine',    '').strip()
        url     = row.get('Url',        '').strip()

        # City = first segment of "City, France" or "City, Region, France"
        city = location.split(',')[0].strip()

        entries.append({
            'name':    name,
            'lat':     lat,
            'lon':     lon,
            'stars':   stars,
            'cuisine': cuisine,
            'city':    city,
            'url':     url,
        })

    return entries, skipped_country, skipped_award, skipped_coords


def build_js_block(entries: list) -> str:
    """Return the full const MICHELIN_RESTAURANTS = [...]; JS block."""
    lines = []
    for i, e in enumerate(entries):
        idx  = str(i + 1).zfill(3)
        comma = ',' if i < len(entries) - 1 else ''
        lines.append(
            f"  {{id:'mr_{idx}',"
            f"name:'{js_str(e['name'])}',"
            f"lat:{e['lat']},"
            f"lon:{e['lon']},"
            f"stars:{e['stars']},"
            f"cuisine:'{js_str(e['cuisine'])}',"
            f"city:'{js_str(e['city'])}',"
            f"url:'{js_str(e['url'])}'}}{comma}"
        )
    return 'const MICHELIN_RESTAURANTS = [\n' + '\n'.join(lines) + '\n];'


def replace_block(html: str, new_block: str) -> str:
    """Replace the MICHELIN_RESTAURANTS block in the HTML source."""
    # Match from the const declaration to the first ]; that closes the array.
    # The array entries all use {id:'mr_NNN',...} so we anchor on that pattern.
    pattern = re.compile(
        r"const MICHELIN_RESTAURANTS = \[.*?\];",
        re.DOTALL
    )
    new_html, n = pattern.subn(new_block, html, count=1)
    if n == 0:
        print('ERROR: Could not find MICHELIN_RESTAURANTS block in HTML.')
        sys.exit(1)
    return new_html


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    preview = '--preview' in sys.argv

    # 1. Fetch
    csv_text = fetch_csv()

    # 2. Parse
    entries, s_country, s_award, s_coords = parse_france(csv_text)

    # 3. Sort: 3★ → 2★ → 1★ → Bib, then alphabetically within each tier
    entries.sort(key=lambda e: (-e['stars'], e['city'].lower(), e['name'].lower()))

    # 4. Report
    by_stars = {}
    for e in entries:
        by_stars[e['stars']] = by_stars.get(e['stars'], 0) + 1

    html_text = HTML_FILE.read_text(encoding='utf-8')
    existing = count_existing(html_text)

    print()
    print('── Michelin France ──────────────────────────────')
    print(f'  3 ★★★      : {by_stars.get(3, 0):>4}')
    print(f'  2 ★★       : {by_stars.get(2, 0):>4}')
    print(f'  1 ★        : {by_stars.get(1, 0):>4}')
    print(f'  Bib Gourmand: {by_stars.get(0, 0):>4}')
    print(f'  ─────────────────────')
    print(f'  Total       : {len(entries):>4}  (was {existing})')
    print()
    print(f'  Skipped — not France       : {s_country}')
    print(f'  Skipped — Selected/unknown : {s_award}')
    print(f'  Skipped — no coordinates   : {s_coords}')
    print()

    if preview:
        print('--preview mode: HTML not modified.')
        return

    # 5. Build + inject
    new_block = build_js_block(entries)
    new_html  = replace_block(html_text, new_block)

    HTML_FILE.write_text(new_html, encoding='utf-8')

    delta = len(entries) - existing
    sign  = '+' if delta >= 0 else ''
    print(f'✓  Updated {HTML_FILE.name}  ({sign}{delta} entries, {len(entries)} total)')
    print()
    print('Deploy:')
    print('  git add french_canals_map.html')
    print(f'  git commit -m "Update Michelin restaurants ({len(entries)} French entries)"')
    print('  git push')


if __name__ == '__main__':
    main()
