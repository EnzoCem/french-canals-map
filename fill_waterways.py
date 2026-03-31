#!/usr/bin/env python3
"""
fill_waterways.py — Re-fetch the 42 navigable waterways from OSM,
stitch ways into continuous LineStrings, RDP-simplify, and update
waterways.geojson.

Usage:
    python fill_waterways.py            # full run (~15–30 min)
    python fill_waterways.py --dry-run  # print what would be fetched, no network calls
"""

import json
import os
import sys
import time
import tempfile
from collections import defaultdict

import requests
from rdp import rdp as _rdp


# ── Constants ────────────────────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
FRANCE_BBOX  = "(42.3,-5.2,51.1,8.3)"  # south,west,north,east — covers all of France
RDP_EPSILON  = 0.0003                   # ~33 m at French latitudes


# ── OSM name overrides ───────────────────────────────────────────────────────
# Maps app name → list of OSM names to try (relation first, then way query).
# Names are tried in order; first one that returns ways wins.

OSM_NAME_MAP = {
    'River Seine':                   ['La Seine', 'River Seine'],
    'River Saône':                   ['La Saône', 'River Saône'],
    'River Rhône':                   ['Le Rhône', 'River Rhône'],
    'River Marne':                   ['La Marne', 'River Marne'],
    'River Oise':                    ["L'Oise", 'River Oise'],
    'River Loire':                   ['La Loire', 'River Loire'],
    'River Mayenne':                 ['La Mayenne', 'River Mayenne'],
    'River Sarthe':                  ['La Sarthe', 'River Sarthe'],
    'River Charente':                ['La Charente', 'River Charente'],
    'River Rhine':                   ['Le Rhin', 'Rhein', 'River Rhine'],
    'River Aa':                      ["L'Aa", 'River Aa'],
    'River Lys':                     ['La Lys', 'Leie', 'River Lys'],
    'River Moselle':                 ['La Moselle', 'River Moselle'],
    'Canal de Garonne':              ['Canal latéral à la Garonne', 'Canal Latéral à la Garonne'],
    'Canal de la Somme':             ['Canal de la Somme'],
    'Liaison Dunkerque\u2013Escaut': ['Liaison Dunkerque\u2013Escaut', 'Canal Dunkerque-Escaut'],
    'Canal de la Marne à la Saône':  ['Canal de la Marne à la Saône', 'Canal entre Champagne et Bourgogne'],
}


# ── Route number for each app name ──────────────────────────────────────────
# Used to set the `route` property on new GeoJSON features.

WATERWAY_ROUTES = {
    'River Seine':                    1,
    'River Yonne':                    4,
    'River Marne':                    5,
    'Canal latéral à la Marne':       5,
    "Canal latéral à l'Aisne":        6,
    "Canal de l'Oise à l'Aisne":      7,
    'River Oise':                     8,
    'Canal du Loing':                10,
    'Canal latéral à la Loire':      10,
    'Canal de Briare':               10,
    'Canal du Centre':               10,
    'Canal du Nivernais':            11,
    'Canal de Bourgogne':            12,
    'River Saône':                   13,
    'Canal du Rhône au Rhin':        14,
    'River Rhône':                   16,
    'Canal de Donzère-Mondragon':    16,
    'Canal du Rhône à Sète':         18,
    'Liaison Dunkerque\u2013Escaut': 19,
    'Canal de Calais':               20,
    'River Aa':                      21,
    'River Lys':                     24,
    'Canal du Nord':                 28,
    'Canal de Saint-Quentin':        29,
    'Canal de la Somme':             31,
    'Canal des Ardennes':            32,
    'Canal de la Meuse':             33,
    'River Moselle':                 34,
    'Canal de la Marne au Rhin':     35,
    'Canal entre Champagne et Bourgogne': 36,
    'Canal de la Marne à la Saône':  36,
    'Canal des Vosges':              37,
    "Canal d'Ille-et-Rance":         41,
    'Canal de Nantes à Brest':       42,
    'River Loire':                   46,
    'River Mayenne':                 47,
    'River Sarthe':                  48,
    'Canal du Midi':                 49,
    'Canal de Garonne':              49,
    'Canal de la Robine':            50,
    'River Charente':                52,
    'River Rhine':                   40,
}

NAVIGABLE_WATERWAYS = list(WATERWAY_ROUTES.keys())


# ── Pure functions (unit-tested) ─────────────────────────────────────────────

def stitch_ways(ways, tol=5):
    """
    Join OSM ways into connected LineStrings by matching endpoints.

    ways: list of ways, each a list of [lon, lat] coordinate pairs
    tol:  decimal places for coordinate rounding (5 = ~1 m tolerance)

    Returns: list of connected LineStrings (each a list of [lon, lat] pairs).
    Disconnected segments become separate LineStrings — correct for
    waterways with branches or bypass channels.
    """
    if not ways:
        return []

    def ekey(pt):
        return (round(pt[0], tol), round(pt[1], tol))

    # endpoint_index: coord_key → list of (way_index, is_start)
    endpoint_index = defaultdict(list)
    for i, way in enumerate(ways):
        endpoint_index[ekey(way[0])].append((i, True))
        endpoint_index[ekey(way[-1])].append((i, False))

    visited = [False] * len(ways)
    chains = []

    for start in range(len(ways)):
        if visited[start]:
            continue
        visited[start] = True
        chain = list(ways[start])

        # Greedily extend forward from the chain's tail
        while True:
            tail = ekey(chain[-1])
            nxt = next(
                ((i, at_start) for i, at_start in endpoint_index[tail] if not visited[i]),
                None,
            )
            if nxt is None:
                break
            idx, at_start = nxt
            visited[idx] = True
            w = ways[idx]
            if at_start:
                chain.extend(w[1:])       # w[0] matches tail — append rest
            else:
                chain.extend(w[-2::-1])   # w[-1] matches tail — append reversed

        chains.append(chain)

    return chains
