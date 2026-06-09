# IENC source authorities

This map ingests IENC (Inland Electronic Navigational Chart, S-57 standard) cells from each country's official waterway authority. Cells are downloaded manually (or via the URLs below) and processed by `extract_ienc.py`. The output files (`data/bridges.geojson`, `data/ienc_channel_axis.geojson`, `data/ienc_obstructions.geojson`) are committed; the raw ZIPs are not (gitignored under `ienc/<country>/`).

## France — VNF / CEREMA

- **Portal:** https://service.shom.fr/ — IENC catalogue lives under "Charts" → "Inland". Free registration required.
- **ZIPs currently bundled in repo:**
  - `ienc/FR.zip` — trunk bundle (Seine, Rhône, Saône, Garonne, Rhin, Oise, Marne, etc.)
  - `VNF Charts/ENC_ROOT_*.zip` — per-corridor editions kept for diff/reconcile reference
- **Licence:** Etalab Licence Ouverte 2.0 (attribution required; commercial use permitted)

## Netherlands — Rijkswaterstaat

- **Portal:** https://www.vaarweginformatie.nl/frp/main/#/page/infra_enc
- **Underlying API for direct downloads (discovered 2026-06; no auth required):**
  - Listing: `GET https://www.vaarweginformatie.nl/frp/api/webcontent/downloads?pageId=infra/enc` returns JSON with `fileId` values
  - Download: `https://www.vaarweginformatie.nl/fdd/main/wicket/resource/org.apache.wicket.Application/downloadfileResource?fileId=<FILEID>`
- **Bundles ingested by this project (2026-06):**
  - `NL-Nederland-inland-2026-02-19.zip` — fileId `4564392990` — main 46 MB bundle (Maas, Waal, Rhine delta, Amsterdam-Rijnkanaal, Standing Mast Route)
  - `NL-Zeeland-2026-w23.zip` — fileId `4662009913` — Western Scheldt + southern delta
  - `NL-Waddenzee-2026-w23.zip` — fileId `4665906289` — Wadden Sea + Frisian Islands access
- **Save to:** `ienc/nl/` (gitignored)
- **Licence:** CC0 (public domain; attribution not required, but courtesy credit appears in the data-sources footer)

## Germany — WSV / ELWIS

- **Portal:** https://www.elwis.de/DE/Service/Inland-ENC-der-WSV/Inland-ENC-der-WSV-node.html
- **Direct download index:** https://www.elwis.de/DE/dynamisch/IENC/ — each waterway's link follows the form `…/IENC/File:<TOKEN>:<NAME>` where the token includes the edition date.
- **Per-waterway info pages with edition history:**
  - [Rhein](https://www.elwis.de/DE/Service/Inland-ENC-der-WSV/Rhein.html)
  - [Mosel](https://www.elwis.de/DE/Service/Inland-ENC-der-WSV/Mosel.html) — covers km 0 (Koblenz, Rhine mouth) to km 242 (Apach, French border)
  - [Main](https://www.elwis.de/DE/Service/Inland-ENC-der-WSV/Main.html)
  - [Donau](https://www.elwis.de/DE/Service/Inland-ENC-der-WSV/Donau.html)
- **Bundles ingested by this project (2026-06):**
  - `DE-Rhein.zip` (token `WW31_2026-05-22_310_866`) — German Rhine, km 310 to 866 (Mainz → Emmerich)
  - `DE-Mosel.zip` (token `WW29_2026-04-09_0_242`) — connects to French Moselle at Apach
  - `DE-Main.zip` (token `WW34_2025-11-18_0_388`) — Mainz → Bamberg
  - `DE-Main-Donau-Kanal.zip` (token `WW35_2025-07-22_0_171`) — Bamberg → Kelheim
  - `DE-Donau.zip` (token `WW33_2026-04-29_2201_2415`) — German Danube section
  - `DE-Saar.zip` (token `WW32_2025-07-25_0_105`) — connects to French Saar
- **Save to:** `ienc/de/` (gitignored)
- **Licence:** Datenlizenz Deutschland – Namensnennung – Version 2.0 (DL-DE-BY-2.0) — attribution required (we credit "WSV / ELWIS" in the data-sources footer)

## Belgium / Austria — out of scope for Wave 3 (deferred)

- Belgium: De Vlaamse Waterweg + SPW publish IENC; deferred to a follow-up wave
- Austria: viadonau publishes Austrian Danube cells; the German Donau already provides most cruise-relevant coverage

## Re-downloading

Edition tokens (DE) and `fileId` values (NL) refresh every few weeks. When refreshing:

1. **NL:** re-fetch the listing with `curl -s 'https://www.vaarweginformatie.nl/frp/api/webcontent/downloads?pageId=infra/enc' | python3 -m json.tool` to discover current `fileId` values. The "Nederland (excl Zeeland, Waddenzee)" entry is the main inland bundle.
2. **DE:** open https://www.elwis.de/DE/dynamisch/IENC/ and copy the latest links — the `WW##_DATE_RANGE` token changes per edition.
3. Save the new ZIPs into `ienc/<country>/`, replacing the old ones (or keep both — `extract_ienc.py` dedupes by cell name).
4. Re-run the extract command shown in `CLAUDE.md` → "Refresh IENC bridge data".
5. Inspect the diff in `data/bridges.geojson` and commit.
