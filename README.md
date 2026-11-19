# MAPPA_RETICHE

Source code for two maps of the PhD thesis (*Food Heritage: Cultures and Identities*, University of Coimbra):

- **Figure 1: The Rhaetian Alps: regional boundaries and hut-governing entities** (`rhaetian_map.py`)
- **The Rhaetian Alps: heritage claims on mountain food beyond the hut-governing entities** (`heritage_map.py`)

![Figure 1](output/F1_Rhaetian_alps_map.png)

The map shows the study area (SOIUSA sections II/A-15 Western, II/A-16 Eastern and
II/C-28 Southern Rhaetian Alps) and the administrative territories in which eight
hut-governing entities (seven alpine clubs and one public authority) own or operate huts.
Each territory is coloured by the entity that operates huts there, with diagonal stripes where
several entities share it (Vorarlberg and Tyrol: DAV and ÖAV; South Tyrol: CAI, AVS and the
Province). An arrow runs from each entity to the city of its head office, and a locator in the
top-left corner shows where the study area lies in Europe.

## Contents

| Path | What it is |
|---|---|
| `rhaetian_map.py` | Figure 1. All settings (outline, territories, labels, colours) are in its CONFIG section. |
| `heritage_map.py` | Companion map: protected areas, territorial quality labels, valley initiatives and UNESCO intangible heritage on the Figure 1 base. Imports the base settings from `rhaetian_map.py`. |
| `ne_data/` | Natural Earth 1:10m boundaries, trimmed to the Alpine area (5.5–14.2°E, 44.3–49.3°N), plus a simplified Europe layer for the locator. |
| `logos/` | Entity logos (PNG, trimmed), named by entity key: LAV, SAC, CAI, DAV, OEAV, AVS, APS, SAT. |
| `output/` | The rendered figure (PDF, PNG at 300 dpi, SVG). |
| `requirements.txt` | Python dependencies (matplotlib only). |

## Running it

```bash
pip install -r requirements.txt
cd output
python ../rhaetian_map.py ../ne_data --out F1_Rhaetian_alps_map
```

Heritage map:

```bash
cd output
python ../heritage_map.py ../ne_data --out Rhaetian_alps_heritage_map
```

Protected areas are drawn from schematic outlines in the script. For exact boundaries, export the nine
parks (e.g. from the WDPA, protectedplanet.net) to one GeoJSON with a `key` property matching the keys in
`PARKS` (STE, SNP, PNAB, ADA, TEX, OTZ, KAU, BVM, ELA) and add `--parks parks.geojson`.
`tools/wdpa_to_parks.py` builds that file straight from Protected Planet File Geodatabase (.gdb) downloads,
with a pure-Python reader (`tools/fgdb.py`, no GDAL needed); parks can be added one download at a time:

```bash
python tools/wdpa_to_parks.py path/to/WDPA_..._Public_6012.gdb --out output/parks_wdpa.geojson
cd output && python ../heritage_map.py ../ne_data --parks parks_wdpa.geojson
```

Parks not in the file keep their schematic outline, and the source line on the map says which are which.

![Heritage map](output/Rhaetian_alps_heritage_map.png)

Logos are read from `logos/` next to the script and drawn above each entity's box.
Use `--logos other/folder` to point elsewhere, or `--logos none` for a version without logos.

## Method notes

- **Study area.** The outline is digitised manually as about 65 points along the limits of the
  SOIUSA sections (Marazzi 2005), placed at towns, passes and river confluences. It is
  approximate (a few km) and not an official SOIUSA boundary dataset.
- **Projection.** Equirectangular, with longitude scaled by the cosine of the map's middle
  latitude (≈46.6°N). The scale bar is therefore approximate.
- **Protected areas (heritage map).** Nine outlines digitised by hand around towns, valleys and passes,
  accurate to a few km; schematic, not official boundaries, until replaced with `--parks`.
- **Shading (Figure 1).** Each operating territory takes the colour of the entity running huts there
  (`TERRITORY_ENTITIES` in the script); shared territories are striped. Everything outside the study
  area sits under a white veil, so the part of each territory inside the study area stands out.
- **Head offices (Figure 1).** LAV: Schaan; SAC: Bern; CAI: Milan; DAV: Munich; ÖAV: Innsbruck;
  AVS: Bolzano; Autonomous Province: Bolzano; SAT: Trento (from each entity's own website or statute,
  November 2026). Figure 1 uses a wider frame than the heritage map so that all of them are on the map.
- **Locator.** Europe from Natural Earth 1:10m countries, simplified (Douglas–Peucker, 0.04°).

## Sources and licences

- Base map: [Natural Earth](https://www.naturalearthdata.com) 1:10m Cultural Vectors, public domain.
- Section limits: Marazzi, S. (2005). *Atlante orografico delle Alpi. SOIUSA*. Pavone Canavese: Priuli & Verlucca.
- Logos: © the respective organisations (DAV, ÖAV, LAV, SAC, CAI, AVS, SAT, Autonome Provinz Bozen – Südtirol), reproduced for identification only. They are **not** covered by the code licence.
- Protected areas (optional `--parks` input): UNEP-WCMC and IUCN (year), *Protected Planet: The World Database on Protected Areas (WDPA)* [On-line], [month/year], Cambridge, UK: UNEP-WCMC and IUCN. Available at: www.protectedplanet.net. The WDPA licence forbids redistribution, so the boundary file is **not** included in this repository (it is git-ignored); the published map image may carry it with this citation.
- Code: GNU GPL v3 or later (see `LICENSE`).
