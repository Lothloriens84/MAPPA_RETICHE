"""
Rhaetian Alps — regional boundaries and hut-governing entities (Figure 1),
plus the shared base used by huts_map.py and heritage_map.py.

Pure matplotlib (no geopandas/shapely/pyproj needed): reads Natural Earth 1:10m
GeoJSON boundaries and draws

  * the study area (Rhaetian Alps, approximate orographic outline) and the
    limits between its three SOIUSA sections,
  * the territories in which each entity runs huts, coloured by entity and
    striped where several share a territory; everything outside the study
    area sits under a white veil,
  * the head office of each entity, with its logo and acronym next to it;
    dotted arrows from head offices outside the study area to the entity's
    territories inside it,
  * a Europe locator, legend, key and source line.

Projection: ETRS89-LAEA Europe (EPSG:3035), computed here (ellipsoidal
formulas, Snyder 1987), so the scale bar is exact. heritage_map.py keeps the
earlier equirectangular base unless it calls use_laea().

Usage
-----
    python rhaetian_map.py <natural-earth-geojson-dir> [--logos logos/] [--out F1_Rhaetian_alps_map]

Everything you may want to change lives in the CONFIG section.
"""

import argparse
import json
import math
import os

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.legend_handler import HandlerPatch
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, OffsetImage, TextArea, VPacker
from matplotlib.patches import PathPatch, FancyBboxPatch, Patch, Rectangle
from matplotlib.path import Path
import matplotlib.colors as mcolors
import matplotlib.patheffects as pe

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

LON_MIN, LON_MAX = 8.75, 12.95      # base extent (also used by heritage_map.py)
LAT_MIN, LAT_MAX = 45.55, 47.62

# Figure 1 frame: around the study area; head offices outside it (Bern, Milan, Munich)
# are shown by an arrow at the map edge pointing towards the city
F1_LON_MIN, F1_LON_MAX = 8.55, 12.75
F1_LAT_MIN, F1_LAT_MAX = 45.55, 47.85
EDGE_CENTRE = (10.40, 46.62)     # edge arrows point along the line from here to the city
EDGE_BADGE_KM = 40               # badge sits this far inside the map edge

# Fonts: Times New Roman if installed, else a metric-compatible serif
FONTS = ["Times New Roman", "Liberation Serif", "TeX Gyre Termes", "DejaVu Serif"]

C = dict(
    paper="#FFFFFF",
    other="#FFFFFF",
    border_admin="#D3CEC4",
    border_country="#6B6458",
    border_region="#9C9384",
    study="#3E5238",
    section="#3E5238",
    lake="#BCD3DB",
    text="#2F2B26",
    muted="#7D7568",
)

COUNTRY_FILL = {                     # heritage map only
    "Italy":         "#CFDCC4",
    "Austria":       "#E9D7BE",
    "Switzerland":   "#D9D1E3",
    "Liechtenstein": "#BBD3DC",
}
PALE_MIX = 0.55    # share of the territory colour kept outside the study area (heritage map)

# Territories are coloured by the entity (or entities) operating huts there.
# Shared territories get diagonal stripes, one per entity.
# Drawn in order: whole countries first, then the units with their own arrangement on top.
#   (admin level, country, Natural Earth name, entities)
F1_TERRITORIES = [
    ("admin0", "Italy",         "Italy",         ["CAI"]),
    ("admin0", "Germany",       "Germany",       ["DAV"]),
    ("admin0", "Switzerland",   "Switzerland",   ["SAC"]),
    ("admin0", "Austria",       "Austria",       ["OEAV"]),
    ("admin0", "Liechtenstein", "Liechtenstein", ["LAV"]),
    ("admin1", "Austria",       "Vorarlberg",    ["DAV", "OEAV"]),
    ("admin1", "Austria",       "Tirol",         ["DAV", "OEAV"]),
    ("admin1", "Italy",         "Bozen",         ["CAI", "AVS", "APS"]),
    ("admin1", "Italy",         "Trento",        ["SAT"]),
]
TINT = 0.50          # share of the entity colour in the territory fill (rest is white)
STRIPE_KM = 6.0      # stripe width
VEIL = 0.70          # white veil over everything outside the study area (0 = none)

# Locator inset (Europe), placed in the map's top-left corner
INSET = dict(lon=(-11.0, 31.0), lat=(35.0, 61.0), width=0.20)   # width as share of map width

# Study area: SOIUSA II/A-15 Western Rhaetian Alps + II/A-16 Eastern Rhaetian Alps
# + II/C-28 Southern Rhaetian Alps (Marazzi 2005). Approximate outline traced along
# the section boundaries, clockwise from the Ill–Rhine confluence:
STUDY_AREA = [
    # Ill (Walgau) – Klostertal – Arlberg – Stanzertal
    (9.58, 47.265), (9.66, 47.21), (9.82, 47.155), (9.96, 47.14), (10.06, 47.13),
    (10.21, 47.13), (10.40, 47.135), (10.565, 47.14),
    # Inn: Landeck – Imst – Telfs – Innsbruck
    (10.66, 47.20), (10.74, 47.235), (10.90, 47.27), (11.07, 47.30), (11.24, 47.275),
    (11.39, 47.265),
    # Sill (Wipptal) – Brenner
    (11.42, 47.20), (11.45, 47.13), (11.46, 47.08), (11.507, 47.003),
    # Isarco: Sterzing – Franzensfeste – Brixen – Klausen – Bolzano
    (11.44, 46.94), (11.43, 46.895), (11.53, 46.84), (11.61, 46.79), (11.655, 46.715),
    (11.565, 46.64), (11.53, 46.60), (11.45, 46.52), (11.35, 46.49),
    # Adige: Bolzano – Salorno – Mezzocorona – Trento
    (11.32, 46.40), (11.30, 46.345), (11.21, 46.24), (11.12, 46.21), (11.11, 46.14),
    (11.12, 46.07),
    # Valle dei Laghi – Sarca – Passo del Durone – Giudicarie – Chiese – Caffaro
    (11.065, 46.085), (10.995, 46.08), (10.95, 46.04), (10.87, 46.035), (10.77, 46.03),
    (10.72, 46.035), (10.665, 45.98), (10.64, 45.94), (10.60, 45.89), (10.53, 45.85),
    (10.47, 45.83),
    # Passo di Croce Domini – Breno – Val Camonica – Edolo – Aprica
    (10.41, 45.91), (10.30, 45.96), (10.35, 46.08), (10.33, 46.18), (10.15, 46.155),
    # Valtellina (Adda): Tresenda – Sondrio – Morbegno – Lake Como
    (10.105, 46.155), (9.87, 46.17), (9.57, 46.135), (9.41, 46.16),
    # Lago di Mezzola – Mera – Chiavenna – Val San Giacomo – Splügen Pass
    (9.45, 46.22), (9.40, 46.32), (9.35, 46.40), (9.36, 46.44), (9.33, 46.505),
    # Hinterrhein: Splügen – Andeer – Via Mala – Thusis – Reichenau
    (9.32, 46.55), (9.43, 46.60), (9.44, 46.70), (9.43, 46.77), (9.41, 46.82),
    # Rhine: Chur – Landquart – Bad Ragaz – Vaduz – Feldkirch
    (9.52, 46.87), (9.55, 46.96), (9.50, 47.00), (9.50, 47.06), (9.52, 47.14),
    (9.51, 47.17), (9.51, 47.22), (9.58, 47.265),
]

# Limits between the three SOIUSA sections inside the study area (approximate):
#   Western | Eastern : Inn (Landeck – Prutz – Pfunds – Nauders) – Reschen Pass – upper Val Venosta to Prad
#   Western | Southern: Aprica – Tirano – Valtellina (Adda) – Bormio – Stelvio Pass – Trafoi – Prad
#   Eastern | Southern: Val Venosta (Adige) Prad – Schlanders – Merano – Bolzano
SECTION_LINES = [
    [(10.565, 47.14), (10.66, 47.08), (10.55, 46.97), (10.50, 46.89), (10.51, 46.84),
     (10.54, 46.80), (10.55, 46.69), (10.555, 46.67), (10.59, 46.625)],
    [(10.15, 46.155), (10.17, 46.21), (10.27, 46.30), (10.33, 46.40), (10.37, 46.47),
     (10.45, 46.53), (10.51, 46.55), (10.59, 46.625)],
    [(10.59, 46.625), (10.70, 46.62), (10.77, 46.63), (10.90, 46.645), (11.00, 46.65),
     (11.10, 46.67), (11.16, 46.67), (11.16, 46.61), (11.25, 46.53), (11.35, 46.49)],
]
SECTIONS = [   # code, name, label lon/lat (Figure 1 shows the code; the hut map shows both)
    ("II/A-15", "Western Rhaetian Alps", 9.78, 46.47),
    ("II/A-16", "Eastern Rhaetian Alps", 10.95, 46.86),
    ("II/C-28", "Southern Rhaetian Alps", 10.47, 46.30),
]

# Relief: hillshade from Copernicus DEM GLO-90 (tools/dem_hillshade.py -> ne_data/hillshade_laea.png)
RELIEF_DARK, RELIEF_LIGHT = 0.50, 0.30      # strength of shadows / highlights
DEM_CREDIT = (" Relief: Copernicus DEM GLO-90 (© DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018, "
              "provided under COPERNICUS by the European Union and ESA).")

# Rivers (Natural Earth 1:10m rivers + Europe supplement, trimmed: ne_data/ne_10m_rivers_alps.geojson)
RIVER_COLOUR = "#3F86B5"
# Lakes missing from Natural Earth 1:10m (main layer), digitised by hand (approximate)
HAND_LAKES = {
    "Lago d'Iseo": [(9.960, 45.668), (10.000, 45.660), (10.050, 45.658), (10.098, 45.688), (10.112, 45.715),
                    (10.098, 45.742), (10.110, 45.808), (10.072, 45.818), (10.062, 45.795), (10.040, 45.770),
                    (10.042, 45.712), (10.010, 45.682), (9.960, 45.668)],
    "Lago d'Idro":  [(10.530, 45.808), (10.536, 45.790), (10.528, 45.770), (10.521, 45.755), (10.508, 45.740),
                     (10.500, 45.736), (10.494, 45.742), (10.503, 45.758), (10.511, 45.775), (10.519, 45.795),
                     (10.524, 45.808), (10.530, 45.808)],
}
# Rivers missing from Natural Earth at 1:10m, digitised by hand (approximate, ±1-2 km)
HAND_RIVERS = {
    "Sarca": [(10.63, 46.175), (10.70, 46.170), (10.758, 46.168), (10.765, 46.150), (10.752, 46.118),
              (10.735, 46.075), (10.725, 46.040), (10.765, 46.038), (10.810, 46.030), (10.868, 46.040),
              (10.950, 46.040), (10.942, 45.995), (10.912, 45.960), (10.885, 45.920), (10.876, 45.876)],
}
RIVER_LABELS = [   # (names in the data, label, lon, lat): label sits on the nearest river vertex, along the river
    (("Rhein", "Rhine", "Rhin"), "Rhine", 9.62, 47.38),
    (("Inn",), "Inn", 10.98, 47.29),
    (("Adige",), "Adige", 11.17, 46.24),
    (("Adda",), "Adda", 9.72, 46.15),
    (("Oglio",), "Oglio", 10.33, 46.02),
    (("Ill",), "Ill", 9.74, 47.18),
    (("Ticino",), "Ticino", 8.80, 45.85),
    (("Sarca",), "Sarca", 10.80, 46.035),
]

# Operating territories: key -> (admin level, country, Natural Earth name, English label, label lon, lat)
TERRITORIES = {
    "GR":  ("admin1", "Switzerland",   "Graubünden",    "Graubünden",   9.95, 46.72),
    "LI":  ("admin0", "Liechtenstein", "Liechtenstein", None,           0, 0),   # labelled as a country
    "VBG": ("admin1", "Austria",       "Vorarlberg",    "Vorarlberg",   9.80, 47.43),
    "TIR": ("admin1", "Austria",       "Tirol",         "Tyrol",       11.02, 46.98),
    "SO":  ("admin1", "Italy",         "Sondrio",       "Sondrio",      9.62, 46.25),
    "BS":  ("admin1", "Italy",         "Brescia",       "Brescia",     10.22, 45.86),
    "BZ":  ("admin1", "Italy",         "Bozen",         "South Tyrol", 11.08, 46.74),
    "TN":  ("admin1", "Italy",         "Trento",        "Trentino",    10.82, 46.24),
}

# Head offices (seat of each entity): city -> (lon, lat, label offset in points, label alignment)
#   LAV  Steinegerta 26, Schaan          SAC  Monbijoustrasse 61, Bern
#   CAI  Via E. Petrella 19, Milan       DAV  Anni-Albers-Straße 7, Munich
#   ÖAV  Olympiastraße 37, Innsbruck     AVS  seat in Bolzano (statute, art. 1)
#   APS  Bolzano (provincial capital)    SAT  Via Manci 57, Trento
CITIES = {
    "Schaan":    (9.508, 47.166, (-6, 0), "right"),
    "Bern":      (7.447, 46.948, (0, -9), "center"),
    "Milan":     (9.190, 45.464, (0, -9), "center"),
    "Munich":    (11.576, 48.137, (-7, 0), "right"),
    "Innsbruck": (11.393, 47.269, (0, 8), "center"),
    "Bolzano":   (11.354, 46.498, (-7, 0), "right"),
    "Trento":    (11.121, 46.067, (-7, 0), "right"),
}

# Entities.  kind = "club" (alpine club) or "authority" (public body).
#   colour  : fill colour (mostly Okabe–Ito; LAV violet and SAT slate so that neighbours and
#             similar hues (LAV/DAV, SAT/ÖAV) stay apart)
#   ink     : darker shade for text and lines
#   hq      : head-office city (key in CITIES)
#   box     : where the logo badge sits on Figure 1: "above" / "right" = directly on top of / right of the city marker,
#             or (lon, lat) with a leader line to the city
#   targets : operating territories (used by heritage_map.py)
#   reach   : for entities with a head office outside the study area, dotted arrows from
#             that city to their territories inside it: (lon, lat, curvature)
ENTITIES = {
    "LAV":  dict(kind="club", label="LAV", name="Liechtensteiner Alpenverein", colour="#8E5BB5", ink="#6A3D9A",
                 hq="Schaan", box=(8.98, 47.12), targets=[("LI", 9.56, 47.12)]),
    "SAC":  dict(kind="club", label="SAC", name="Schweizer Alpen-Club", colour="#D55E00", ink="#B34E00",
                 hq="Bern", box="edge", targets=[("GR", 9.80, 46.58)],
                 reach=[(9.72, 46.66, -0.2)]),
    "CAI":  dict(kind="club", label="CAI", name="Club Alpino Italiano", colour="#009E73", ink="#007A59",
                 hq="Milan", box="edge", targets=[("SO", 10.02, 46.36), ("BS", 10.45, 46.08)],
                 reach=[(10.42, 46.06, 0.15), (11.02, 46.62, 0.22)]),
    "DAV":  dict(kind="club", label="DAV", name="Deutscher Alpenverein", colour="#0072B2", ink="#0072B2",
                 hq="Munich", box="edge", targets=[("VBG", 9.90, 47.06), ("TIR", 10.82, 47.10)],
                 reach=[(9.92, 47.05, 0.18), (10.85, 47.08, 0.15)]),
    "OEAV": dict(kind="club", label="ÖAV", name="Österreichischer Alpenverein", colour="#E69F00", ink="#B07800",
                 hq="Innsbruck", box=(11.95, 47.72), targets=[("VBG", 10.12, 47.02), ("TIR", 11.25, 47.12)]),
    "AVS":  dict(kind="club", label="AVS", name="Alpenverein Südtirol", colour="#8C510A", ink="#8C510A",
                 hq="Bolzano", box=(12.02, 46.98), targets=[("BZ", 11.25, 46.86)]),
    "APS":  dict(kind="authority", label="APS", name="Provincia autonoma di Bolzano", colour="#CC79A7",
                 ink="#A8507F", hq="Bolzano", box=(12.02, 46.42), targets=[("BZ", 11.05, 46.58)]),
    "SAT":  dict(kind="club", label="SAT", name="Società degli Alpinisti Tridentini", colour="#64707D",
                 ink="#4B5560", hq="Trento", box=(11.92, 45.78), targets=[("TN", 11.00, 46.34)]),
}

# Logo file per entity (logos/<name>.png); SAC and APS use their emblem only
LOGO_FILES = {"SAC": "SAC_emblem", "APS": "APS_emblem"}

# Country labels (English). Liechtenstein gets a leader line.
COUNTRY_LABELS = [
    ("SWITZERLAND", 9.02, 46.88),
    ("AUSTRIA", 12.55, 47.42),
    ("GERMANY", 10.55, 47.57),
    ("ITALY", 12.40, 45.72),
]
LI_LABEL = ("LIECHTENSTEIN", 9.10, 47.41, 9.51, 47.19)   # text lon/lat, leader-tip lon/lat

# Figure 1 positions for the same labels in its wider frame
F1_COUNTRY_LABELS = [
    ("SWITZERLAND", 8.95, 46.30),
    ("AUSTRIA", 12.45, 47.40),
    ("GERMANY", 9.95, 47.78),
    ("ITALY", 12.30, 45.68),
]
F1_LI_LABEL = ("LIECHTENSTEIN", 9.05, 47.35, 9.53, 47.14)

# Region-tier labels (units the text refers to that are not operating territories)
REGION_LABELS = [
    ("LOMBARDY", 9.80, 45.82),
]
F1_REGION_LABELS = [
    ("LOMBARDY", 10.40, 45.66),
]
REGION_OUTLINE = ("Italy", "Lombardia")   # dissolved provinces -> thin region boundary

LOGO_MAX_W, LOGO_MAX_H = 58, 30   # logo inside each badge, in points
SOURCE = ("Study area: SOIUSA Western (II/A-15), Eastern (II/A-16) and Southern (II/C-28) Rhaetian Alps (Marazzi 2005); "
          "outline and section limits approximate.\n"
          "Base map: Natural Earth 1:10m Cultural and Physical Vectors (public domain). Projection: ETRS89-LAEA Europe (EPSG:3035). "
          "Map: author's elaboration.")
LOGO_CREDIT = " Logos © the respective organisations, reproduced for identification only."

# ════════════════════════════════════════════════════════════════════════════
# PROJECTION AND VIEW
# ════════════════════════════════════════════════════════════════════════════

K = math.cos(math.radians((LAT_MIN + LAT_MAX) / 2))

# ETRS89-LAEA Europe (EPSG:3035): GRS80, lat0 52°N, lon0 10°E, FE 4321 km, FN 3210 km
_A, _E = 6378137.0, 0.0818191910428158
_LAT0, _LON0, _FE, _FN = math.radians(52.0), math.radians(10.0), 4321000.0, 3210000.0


def _q(phi):
    s = math.sin(phi)
    return (1 - _E ** 2) * (s / (1 - _E ** 2 * s ** 2) - (1 / (2 * _E)) * math.log((1 - _E * s) / (1 + _E * s)))


_QP = _q(math.pi / 2)
_RQ = _A * math.sqrt(_QP / 2)
_B0 = math.asin(_q(_LAT0) / _QP)
_D = _A * (math.cos(_LAT0) / math.sqrt(1 - _E ** 2 * math.sin(_LAT0) ** 2)) / (_RQ * math.cos(_B0))


def laea(lon, lat):
    """lon/lat (degrees) -> EPSG:3035 easting/northing in kilometres."""
    phi, lam = math.radians(lat), math.radians(lon)
    beta = math.asin(max(-1.0, min(1.0, _q(phi) / _QP)))
    dl = lam - _LON0
    b = _RQ * math.sqrt(2 / (1 + math.sin(_B0) * math.sin(beta) + math.cos(_B0) * math.cos(beta) * math.cos(dl)))
    x = _FE + b * _D * math.cos(beta) * math.sin(dl)
    y = _FN + (b / _D) * (math.cos(_B0) * math.sin(beta) - math.sin(_B0) * math.cos(beta) * math.cos(dl))
    return x / 1000.0, y / 1000.0


RELIEF_USED = False
_PROJ = "eqc"                 # heritage_map.py keeps this; Figure 1 and the hut map call use_laea()
KM = 1 / 111.32               # map units per kilometre
_VIEW = (LON_MIN, LON_MAX, LAT_MIN, LAT_MAX)


def use_laea():
    global _PROJ, KM
    _PROJ, KM = "laea", 1.0


def set_view(lon0, lon1, lat0, lat1):
    global _VIEW
    _VIEW = (lon0, lon1, lat0, lat1)


def proj(lon, lat):
    if _PROJ == "laea":
        return laea(lon, lat)
    return lon * K, lat


def view_limits(lon0, lon1, lat0, lat1):
    """Projected bounding box of a lon/lat box (edges sampled)."""
    pts = [proj(lon0 + (lon1 - lon0) * i / 40, lat) for i in range(41) for lat in (lat0, lat1)]
    pts += [proj(lon, lat0 + (lat1 - lat0) * i / 40) for i in range(41) for lon in (lon0, lon1)]
    xs, ys = zip(*pts)
    return (min(xs), max(xs)), (min(ys), max(ys))


# ════════════════════════════════════════════════════════════════════════════
# GEOMETRY HELPERS
# ════════════════════════════════════════════════════════════════════════════

def rings_of(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def ring_path(rings):
    verts, codes = [], []
    for ring in rings:
        pts = [proj(x, y) for x, y in ring]
        if len(pts) < 3:
            continue
        verts += pts
        codes += [Path.MOVETO] + [Path.LINETO] * (len(pts) - 2) + [Path.CLOSEPOLY]
    return Path(verts, codes) if verts else None


def geom_to_path(geom):
    return ring_path([r for poly in rings_of(geom) for r in poly])


def bbox_hits(geom, pad=1.0):
    lon0, lon1, lat0, lat1 = _VIEW
    xs, ys = [], []
    for poly in rings_of(geom):
        for x, y in poly[0]:
            xs.append(x); ys.append(y)
    if not xs:
        return False
    return not (max(xs) < lon0 - pad or min(xs) > lon1 + pad or
                max(ys) < lat0 - pad or min(ys) > lat1 + pad)


def dissolved_edges(geoms):
    """Outer boundary of a set of adjacent polygons: edges used by exactly one polygon."""
    count = {}
    for g in geoms:
        for poly in rings_of(g):
            for ring in poly:
                for a, b in zip(ring[:-1], ring[1:]):
                    k = tuple(sorted([(round(a[0], 6), round(a[1], 6)), (round(b[0], 6), round(b[1], 6))]))
                    count[k] = count.get(k, 0) + 1
    verts, codes = [], []
    for (a, b), n in count.items():
        if n == 1:
            verts += [proj(*a), proj(*b)]
            codes += [Path.MOVETO, Path.LINETO]
    return Path(verts, codes)


def pale(hex_colour, mix=PALE_MIX):
    r1, g1, b1 = mcolors.to_rgb(hex_colour)
    r0, g0, b0 = mcolors.to_rgb(C["other"])
    return (r0 + (r1 - r0) * mix, g0 + (g1 - g0) * mix, b0 + (b1 - b0) * mix)


def tint(hex_colour, share=None):
    share = TINT if share is None else share
    r, g, b = mcolors.to_rgb(hex_colour)
    return (1 - (1 - r) * share, 1 - (1 - g) * share, 1 - (1 - b) * share)


def pale_of(rgb):
    return tuple(c + (1 - c) * VEIL for c in mcolors.to_rgb(rgb))


def draw_stripes(ax, path, cols, clip_patch, width=None):
    """Diagonal stripes in the given colours, clipped to a territory."""
    width = STRIPE_KM * KM if width is None else width
    (x0, y0), (x1, y1) = path.get_extents().get_points()
    px = width / 24
    nx, ny = int((x1 - x0) / px) + 2, int((y1 - y0) / px) + 2
    xs = x0 + (np.arange(nx) + 0.5) * px
    ys = y0 + (np.arange(ny) + 0.5) * px
    band = (np.floor((xs[None, :] + ys[:, None]) / width).astype(int)) % len(cols)
    rgb = np.array([mcolors.to_rgb(c) for c in cols])[band]
    im = ax.imshow(rgb, extent=(x0, x0 + nx * px, y0, y0 + ny * px), origin="lower",
                   interpolation="nearest", zorder=2.1, aspect="auto")
    im.set_clip_path(clip_patch)
    return im


def outside_path(ax):
    """The axes area with the study area cut out (for the veil)."""
    ring = [proj(x, y) for x, y in STUDY_AREA]
    signed = sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1))
    if signed > 0:              # make the hole run opposite to the (counter-clockwise) rectangle
        ring = ring[::-1]
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    dx, dy = (x1 - x0), (y1 - y0)
    big = [(x0 - dx, y0 - dy), (x1 + dx, y0 - dy), (x1 + dx, y1 + dy), (x0 - dx, y1 + dy), (x0 - dx, y0 - dy)]
    verts = big + ring
    codes = ([Path.MOVETO] + [Path.LINETO] * 3 + [Path.CLOSEPOLY] +
             [Path.MOVETO] + [Path.LINETO] * (len(ring) - 2) + [Path.CLOSEPOLY])
    return Path(verts, codes)


def line_path(pts):
    return Path([proj(x, y) for x, y in pts])


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]


def set_fonts():
    plt.rcParams["font.family"] = "serif"
    plt.rcParams["font.serif"] = FONTS
    plt.rcParams["mathtext.fontset"] = "stix"


# ════════════════════════════════════════════════════════════════════════════
# SHARED DRAWING
# ════════════════════════════════════════════════════════════════════════════

def draw_base(ax, ne_dir, frame, territory_labels=True, section_labels="code", veil=VEIL,
              country_labels=None, li_label=None, relief=True):
    """Territories, borders, lakes, study area, section limits, veil and labels.
    frame = (lon0, lon1, lat0, lat1). Returns the study-area patch."""
    set_view(*frame)
    adm0 = load(os.path.join(ne_dir, "ne_10m_admin_0_countries.geojson"))
    adm1 = load(os.path.join(ne_dir, "ne_10m_admin_1_states_provinces.geojson"))
    lakes = load(os.path.join(ne_dir, "ne_10m_lakes.geojson"))
    ax.set_facecolor(C["other"])

    (x0, x1), (y0, y1) = view_limits(*frame)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor(C["border_country"]); s.set_linewidth(0.8)

    # study area (also the clip path used for stripes)
    study = PathPatch(ring_path([STUDY_AREA]), fc="none", ec=C["study"], lw=1.6, zorder=5)
    ax.add_patch(study)

    idx = {}
    for f in adm1:
        pr = f["properties"]
        idx[("admin1", pr["admin"], pr["name"])] = f["geometry"]
    for f in adm0:
        pr = f["properties"]
        idx[("admin0", pr["ADMIN"], pr["ADMIN"])] = f["geometry"]

    for i, (lvl, ctry, ne_name, ents) in enumerate(F1_TERRITORIES):
        geom = idx.get((lvl, ctry, ne_name))
        if geom is None:
            raise SystemExit(f"Territory not found in Natural Earth: {lvl} {ctry} {ne_name}")
        path = geom_to_path(geom)
        z = 2 + i * 0.01
        cols = [tint(ENTITIES[e]["colour"]) for e in ents]
        shape = PathPatch(path, fc=cols[0], ec="none", zorder=z)
        ax.add_patch(shape)
        if len(cols) > 1:
            draw_stripes(ax, path, cols, shape).set_zorder(z + 0.005)
        ax.add_patch(PathPatch(path, fc="none", ec="white", lw=1.0, zorder=2.3))

    # relief (only in the LAEA maps; the hillshade grid is in EPSG:3035)
    hs_png = os.path.join(ne_dir, "hillshade_laea.png")
    if relief and _PROJ == "laea" and os.path.exists(hs_png):
        meta = json.load(open(os.path.splitext(hs_png)[0] + ".json"))
        shade = plt.imread(hs_png).astype(float)
        if shade.max() > 1:
            shade = shade / 255.0
        flat = math.sin(math.radians(45))
        dark = np.clip((flat - shade) / flat, 0, 1) * RELIEF_DARK
        light = np.clip((shade - flat) / (1 - flat), 0, 1) * RELIEF_LIGHT
        rgba = np.zeros(shade.shape + (4,))
        rgba[..., :3] = (light / np.maximum(light + dark, 1e-6))[..., None]   # white where lit, black in shadow
        rgba[..., 3] = np.maximum(dark, light)
        ax.imshow(rgba, extent=meta["extent_km"], origin="upper", interpolation="bilinear", zorder=2.35)
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
        global RELIEF_USED
        RELIEF_USED = True

    # internal borders (provinces, states, cantons) on top of the fills
    for f in adm1:
        if f["properties"]["admin"] != "Liechtenstein" and bbox_hits(f["geometry"]):
            p = geom_to_path(f["geometry"])
            if p:
                ax.add_patch(PathPatch(p, fc="none", ec="white", lw=0.55, zorder=2.25))

    if veil:
        ax.add_patch(PathPatch(outside_path(ax), fc="white", ec="none", alpha=veil, zorder=2.4))

    ctry, reg = REGION_OUTLINE
    reg_geoms = [f["geometry"] for f in adm1
                 if f["properties"]["admin"] == ctry and f["properties"].get("region") == reg]
    ax.add_patch(PathPatch(dissolved_edges(reg_geoms), fc="none", ec=C["border_region"], lw=0.9, zorder=2.6))

    for f in adm0:
        if bbox_hits(f["geometry"]):
            p = geom_to_path(f["geometry"])
            if p:
                ax.add_patch(PathPatch(p, fc="none", ec=C["border_country"], lw=1.1,
                                       ls=(0, (5, 1.6)), zorder=3))

    for f in lakes:
        if bbox_hits(f["geometry"], pad=0):
            p = geom_to_path(f["geometry"])
            if p:
                ax.add_patch(PathPatch(p, fc=C["lake"], ec="none", zorder=3.5))
    for name, ring in HAND_LAKES.items():
        ax.add_patch(PathPatch(ring_path([ring]), fc=C["lake"], ec=RIVER_COLOUR, lw=0.4, zorder=3.5))

    # rivers
    fn = os.path.join(ne_dir, "ne_10m_rivers_alps.geojson")
    if os.path.exists(fn):
        rivers = load(fn) + [{"properties": {"name": n, "scalerank": 8},
                              "geometry": {"coordinates": [pts]}} for n, pts in HAND_RIVERS.items()]
        for f in rivers:
            r = f["properties"].get("scalerank") or 10
            lw = 1.7 if r <= 6 else 1.4 if r <= 8 else 1.1
            for line in f["geometry"]["coordinates"]:
                ax.add_patch(PathPatch(line_path(line), fc="none", ec=RIVER_COLOUR, lw=lw,
                                       capstyle="round", joinstyle="round", zorder=3.45))
        (vx0, vx1), (vy0, vy1) = ax.get_xlim(), ax.get_ylim()
        for names, label, lon, lat in RIVER_LABELS:
            tx, ty = proj(lon, lat)
            if not (vx0 < tx < vx1 and vy0 < ty < vy1):
                continue
            best = None
            for f in rivers:
                if f["properties"].get("name") not in names:
                    continue
                for line in f["geometry"]["coordinates"]:
                    pts = [proj(x, y) for x, y in line]
                    for i in range(len(pts) - 1):
                        d = (pts[i][0] - tx) ** 2 + (pts[i][1] - ty) ** 2
                        if best is None or d < best[0]:
                            best = (d, pts[i], pts[i + 1])
            if best:
                (_, (x0_, y0_), (x1_, y1_)) = best
                ang = math.degrees(math.atan2(y1_ - y0_, x1_ - x0_))
                ang = ang - 180 if ang > 90 else ang + 180 if ang < -90 else ang
                ax.text((x0_ + x1_) / 2, (y0_ + y1_) / 2, label, rotation=ang, rotation_mode="anchor",
                        ha="center", va="bottom", size=9, style="italic", color="#2C6E96", zorder=6.2,
                        path_effects=[pe.withStroke(linewidth=2.2, foreground="white")])

    # SOIUSA section limits and labels
    for pts in SECTION_LINES:
        ax.add_patch(PathPatch(line_path(pts), fc="none", ec=C["section"], lw=0.9,
                               ls=(0, (6, 2, 1.2, 2)), zorder=4.9))
    if section_labels:
        for code, name, lon, lat in SECTIONS:
            txt = code if section_labels == "code" else f"{name}\n{code}"
            ax.text(*proj(lon, lat), txt, ha="center", va="center", size=8 if section_labels == "code" else 8.6,
                    color=C["section"], style="italic", weight="bold", zorder=6, linespacing=1.1,
                    path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])

    if territory_labels:
        for key, (lvl, ctry, ne_name, label, lx, ly) in TERRITORIES.items():
            if label:
                ax.text(*proj(lx, ly), label, ha="center", va="center", size=9, style="italic",
                        color=C["text"], zorder=6,
                        path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])

    for txt, lon, lat in (country_labels or []):
        ax.text(*proj(lon, lat), txt, ha="center", va="center", size=10.5, color=C["muted"],
                weight="bold", alpha=0.9, zorder=4)
    if li_label:
        t, lon, lat, tlon, tlat = li_label
        ax.annotate(t, xy=proj(tlon, tlat), xytext=proj(lon, lat), ha="center", va="center",
                    size=8.6, color=C["muted"], weight="bold", zorder=4,
                    arrowprops=dict(arrowstyle="-", color=C["muted"], lw=0.7, shrinkA=2, shrinkB=0))
    return study


def draw_scale_north(ax, frame, km=50):
    lon0, lon1, lat0, lat1 = frame
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    sx, sy = x0 + (x1 - x0) * 0.035, y0 + (y1 - y0) * 0.04
    L = km * KM
    ax.plot([sx, sx + L], [sy, sy], color=C["text"], lw=2.4, solid_capstyle="butt", zorder=8)
    ax.plot([sx, sx + L / 2], [sy, sy], color="white", lw=1.1, solid_capstyle="butt", zorder=9)
    for xx, t in [(sx, "0"), (sx + L / 2, f"{km // 2}"), (sx + L, f"{km} km")]:
        ax.text(xx, sy + 3.5 * KM, t, ha="center", va="bottom", size=8, color=C["text"], zorder=9)
    nx, ny = x1 - (x1 - x0) * 0.035, y0 + (y1 - y0) * 0.04
    ax.annotate("N", xy=(nx, ny + 20 * KM), xytext=(nx, ny), ha="center", va="top",
                size=10, weight="bold", color=C["text"],
                arrowprops=dict(arrowstyle="-|>", color=C["text"], lw=1.4), zorder=9)


def draw_locator(fig, ax, ne_dir, frame, width=None):
    """Europe locator in the top-left corner of the map, with the study area in red."""
    fn = os.path.join(ne_dir, "ne_europe_simplified.geojson")
    if not os.path.exists(fn):
        return
    ax.apply_aspect()
    pos = ax.get_position()
    (l0, l1), (b0, b1) = INSET["lon"], INSET["lat"]
    k = math.cos(math.radians((b0 + b1) / 2))
    w = pos.width * (width or INSET["width"])
    fw, fh = fig.get_size_inches()
    h = w * fw / fh * (b1 - b0) / ((l1 - l0) * k)
    ia = fig.add_axes([pos.x0 + 0.004, pos.y1 - h - 0.004 * fw / fh, w, h], zorder=20)
    ia.set_facecolor("#E9F1F4")
    for f in load(fn):
        for poly in rings_of(f["geometry"]):
            ia.add_patch(plt.Polygon([(x * k, y) for x, y in poly[0]], closed=True,
                                     fc="#FFFFFF", ec="#B9B2A6", lw=0.3))
    ia.add_patch(plt.Polygon([(x * k, y) for x, y in STUDY_AREA], closed=True,
                             fc="#C0392B", ec="#7B241C", lw=0.4, zorder=5))
    fx0, fx1, fy0, fy1 = frame
    ia.add_patch(Rectangle((fx0 * k, fy0), (fx1 - fx0) * k, fy1 - fy0, fc="none",
                           ec=C["text"], lw=0.8, zorder=6))
    ia.set_xlim(l0 * k, l1 * k); ia.set_ylim(b0, b1)
    ia.set_xticks([]); ia.set_yticks([])
    for sp in ia.spines.values():
        sp.set_edgecolor(C["border_country"]); sp.set_linewidth(0.8)
    ia.text(0.03, 0.03, "Europe", transform=ia.transAxes, size=7.5, color=C["muted"],
            style="italic", va="bottom")
    return ia


# ════════════════════════════════════════════════════════════════════════════
# BADGES
# ════════════════════════════════════════════════════════════════════════════

def badge_box(a):
    if a["kind"] == "authority":
        return dict(boxstyle="square,pad=0.3", fc="#FBF5F8", ec=a["ink"], lw=1.3, ls=(0, (3.2, 1.6)))
    return dict(boxstyle="round,pad=0.3,rounding_size=0.5", fc="white", ec=a["ink"], lw=1.2)


def find_logo(key, logo_dir):
    if not logo_dir or logo_dir == "none":
        return None
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(logo_dir, LOGO_FILES.get(key, key) + ext)
        if os.path.exists(p):
            return p
    return None


def make_logo(path, max_w=None, max_h=None):
    img = plt.imread(path)
    h, w = img.shape[:2]
    return OffsetImage(img, zoom=min((max_w or LOGO_MAX_W) / w, (max_h or LOGO_MAX_H) / h),
                       interpolation="lanczos")


def make_badge(a, logo=None):
    """Logo (if any) above the acronym."""
    head = TextArea(a["label"], textprops=dict(size=11, weight="bold", color=a["ink"], ha="center"))
    kids = [make_logo(logo), head] if logo else [head]
    return VPacker(children=kids, align="center", pad=0, sep=2)


class HandlerStripes(HandlerPatch):
    """Legend glyph with diagonal stripes in the given colours (as drawn on the map)."""
    def __init__(self, cols):
        super().__init__()
        self.cols = cols

    def create_artists(self, legend, orig, xd, yd, w, h, fs, trans):
        box = Rectangle((xd, yd), w, h, fc="none", ec="none", transform=trans)
        out = [box]
        sw = h * 0.7                                   # stripe width in legend units
        k = 0
        x = xd - h
        while x < xd + w + h:
            poly = plt.Polygon([(x, yd), (x + sw, yd), (x + sw + h, yd + h), (x + h, yd + h)], closed=True,
                               fc=self.cols[k % len(self.cols)], ec="none", transform=trans)
            poly.set_clip_path(box)
            out.append(poly)
            x += sw; k += 1
        out.append(Rectangle((xd, yd), w, h, fc="none", ec="#BBBBBB", lw=0.5, transform=trans))
        return out


class HandlerBadge(HandlerPatch):
    """Legend glyph that looks like a badge (rounded/solid or square/dashed)."""
    def __init__(self, rounded, dashed):
        super().__init__()
        self.rounded, self.dashed = rounded, dashed

    def create_artists(self, legend, orig, xd, yd, w, h, fs, trans):
        style = "round,pad=0,rounding_size=3" if self.rounded else "square,pad=0"
        p = FancyBboxPatch((xd + 2, yd - 1), w - 4, h + 2, boxstyle=style,
                           fc="#FBF5F8" if self.dashed else "white", ec=C["text"], lw=1.0,
                           ls=(0, (3, 1.5)) if self.dashed else "-", transform=trans)
        return [p]


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 1
# ════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ne_dir", help="folder with Natural Earth 10m GeoJSON files")
    ap.add_argument("--logos", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "logos"),
                    help="folder with <KEY>.png logos (default: logos/ next to this script); 'none' to disable")
    ap.add_argument("--out", default="F1_Rhaetian_alps_map")
    args = ap.parse_args()

    use_laea()
    set_fonts()
    frame = (F1_LON_MIN, F1_LON_MAX, F1_LAT_MIN, F1_LAT_MAX)
    fig = plt.figure(figsize=(16.54, 11.69), facecolor=C["paper"])          # A3 landscape (foldout)
    ax = fig.add_axes([0.012, 0.085, 0.775, 0.905])
    ax.set_anchor("W")
    draw_base(ax, args.ne_dir, frame, section_labels="full", relief=False,
              country_labels=F1_COUNTRY_LABELS, li_label=F1_LI_LABEL)
    for txt, lon, lat in F1_REGION_LABELS:
        ax.text(*proj(lon, lat), txt, ha="center", va="center", size=9, color=C["muted"],
                style="italic", weight="bold", zorder=4,
                path_effects=[pe.withStroke(linewidth=2.2, foreground="white")])

    # head-office cities inside the frame
    (fx0, fx1), (fy0, fy1) = ax.get_xlim(), ax.get_ylim()
    for city, (lon, lat, off, ha) in CITIES.items():
        x, y = proj(lon, lat)
        if not (fx0 < x < fx1 and fy0 < y < fy1):
            continue
        ax.plot(x, y, "o", ms=7, mfc="white", mec=C["text"], mew=1.7, zorder=8.5)
        ax.plot(x, y, "o", ms=2.4, mfc=C["text"], mec="none", zorder=8.6)
        ax.annotate(city, (x, y), xytext=off, textcoords="offset points", ha=ha, va="center",
                    size=9.5, weight="bold", color=C["text"], zorder=8.7,
                    path_effects=[pe.withStroke(linewidth=2.8, foreground="white")])

    # badges next to the cities, leaders, and reach arrows
    any_logo = False
    for key, a in ENTITIES.items():
        clon, clat = CITIES[a["hq"]][:2]
        cx, cy = proj(clon, clat)
        on_city = a["box"] in ("above", "right")
        if a["box"] == "edge":
            # point where the line from EDGE_CENTRE to the city leaves the map
            ox, oy = proj(*EDGE_CENTRE)
            dx, dy = cx - ox, cy - oy
            n = math.hypot(dx, dy); ux, uy = dx / n, dy / n
            ts = [t for t in ((fx0 - ox) / dx if dx else None, (fx1 - ox) / dx if dx else None,
                              (fy0 - oy) / dy if dy else None, (fy1 - oy) / dy if dy else None) if t and t > 0]
            t = min(ts)
            ex, ey = ox + dx * t, oy + dy * t
            ex, ey = ex - ux * 2 * KM, ey - uy * 2 * KM          # just inside the frame line
            bx, by = ex - ux * EDGE_BADGE_KM * KM, ey - uy * EDGE_BADGE_KM * KM
            ax.annotate("", xy=(ex, ey), xytext=(bx, by),
                        arrowprops=dict(arrowstyle="-|>,head_length=0.9,head_width=0.45", color=a["ink"],
                                        lw=2.2, shrinkA=26, shrinkB=0), zorder=8.8)
            dist = round(math.hypot(cx - ex, cy - ey) / KM / 5) * 5
            ang = math.degrees(math.atan2(uy, ux))
            txt_ang = ang - 180 if ang > 90 else ang + 180 if ang < -90 else ang
            px_, py_ = -uy, ux                                        # perpendicular, for the label offset
            mx, my = (ex + bx) / 2 + px_ * 0 , (ey + by) / 2
            ax.annotate(a["hq"], (ex - ux * 12 * KM, ey - uy * 12 * KM), xytext=(px_ * 11, py_ * 11),
                        textcoords="offset points", rotation=txt_ang, rotation_mode="anchor",
                        ha="center", va="center", size=9.5, weight="bold", color=a["ink"], zorder=8.9,
                        path_effects=[pe.withStroke(linewidth=2.8, foreground="white")])
            cx, cy = bx, by                                           # reach arrows start from the badge
        elif not on_city:
            bx, by = proj(*a["box"])
            ls = (0, (4, 2)) if a["kind"] == "authority" else "-"
            ax.annotate("", xy=(cx, cy), xytext=(bx, by),
                        arrowprops=dict(arrowstyle="-", color=a["ink"], lw=1.3, ls=ls, shrinkA=0, shrinkB=5),
                        zorder=7.5)
        for rlon, rlat, rrad in a.get("reach", []):
            ax.annotate("", xy=proj(rlon, rlat), xytext=(cx, cy),
                        arrowprops=dict(arrowstyle="-|>,head_length=0.5,head_width=0.24",
                                        color=a["ink"], lw=1.2, ls=(0, (1.5, 1.5)),
                                        shrinkA=5, shrinkB=2.5, connectionstyle=f"arc3,rad={rrad}"),
                        zorder=7)
            ax.plot(*proj(rlon, rlat), "o", ms=3.6, mfc="white", mec=a["ink"], mew=1.3, zorder=8)
        logo = find_logo(key, args.logos)
        any_logo |= bool(logo)
        if a["box"] == "edge":
            ax.add_artist(AnnotationBbox(make_badge(a, logo), (bx, by), xycoords="data", frameon=True,
                                         zorder=9, pad=0.3, bboxprops=badge_box(a)))
        elif on_city:    # badge sits just above / right of the city marker
            off, align = ((0, 9), (0.5, 0)) if a["box"] == "above" else ((9, 0), (0, 0.5))
            ax.add_artist(AnnotationBbox(make_badge(a, logo), (cx, cy), xycoords="data", frameon=True,
                                         xybox=off, boxcoords="offset points", box_alignment=align,
                                         zorder=9, pad=0.3, bboxprops=badge_box(a)))
        else:
            ax.add_artist(AnnotationBbox(make_badge(a, logo), (bx, by), xycoords="data", frameon=True,
                                         zorder=9, pad=0.3, bboxprops=badge_box(a)))

    draw_scale_north(ax, frame)
    draw_locator(fig, ax, args.ne_dir, frame, width=0.17)

    # legend (map symbols) and key (entities), in a column right of the map
    ax.apply_aspect()
    lx = ax.get_position().x1 + 0.012
    n_club = sum(a["kind"] == "club" for a in ENTITIES.values())
    n_auth = sum(a["kind"] == "authority" for a in ENTITIES.values())
    club_h, auth_h = Patch(), Patch(label="_")
    shared = [(TERRITORIES[k][3], ents) for k, ents in (("TIR", ["DAV", "OEAV"]), ("BZ", ["CAI", "AVS", "APS"]))]
    stripe_h = [Patch(label=f"_s{i}") for i in range(len(shared))]
    handles = [
        Line2D([], [], color=C["study"], lw=1.6),
        Line2D([], [], color=C["section"], lw=0.9, ls=(0, (6, 2, 1.2, 2))),
        *stripe_h,
        Patch(fc=pale_of(tint(ENTITIES["CAI"]["colour"])), ec="#BBBBBB", lw=0.5),
        Line2D([], [], color=C["border_country"], lw=1.1, ls=(0, (5, 1.6))),
        Line2D([], [], color=C["border_region"], lw=0.9),
        Line2D([], [], color=RIVER_COLOUR, lw=1.2),
        Line2D([], [], ls="none", marker="o", ms=7, mfc="white", mec=C["text"], mew=1.7),
        Line2D([], [], ls="none", marker=r"$\rightarrow$", ms=14, color=C["text"]),
        Line2D([], [], color=C["text"], lw=1.2, ls=(0, (1.5, 1.5)), marker="o", ms=3.6,
               mfc="white", mec=C["text"], markevery=[1]),
        club_h, auth_h,
    ]
    labels = [
        "Rhaetian Alps (study area)",
        "Limit between SOIUSA sections",
        *[("Vorarlberg and Tyrol" if name == "Tyrol" else name) + ": shared by\n" +
          " + ".join(ENTITIES[e]["label"] for e in ents) for name, ents in shared],
        "Outside the study area (paler)",
        "National border",
        "Regional border (Lombardy)",
        "River",
        "Head office",
        "Direction of a head office\nbeyond the map",
        "From an entity based beyond\nthe map to its territories",
        f"Alpine club ({n_club})",
        f"Public authority ({n_auth})",
    ]
    hmap = {club_h: HandlerBadge(True, False), auth_h: HandlerBadge(False, True)}
    for h, (_, ents) in zip(stripe_h, shared):
        hmap[h] = HandlerStripes([tint(ENTITIES[e]["colour"]) for e in ents])
    leg = fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(lx, 0.99), ncol=1,
                     frameon=False, fontsize=10, handlelength=2.6, handleheight=1.3, labelspacing=0.75,
                     labelcolor=C["text"], handler_map=hmap, title="Map symbols", title_fontsize=11,
                     alignment="left")
    fig.add_artist(leg)

    key_h = [Patch(fc=tint(a["colour"]), ec=a["ink"], lw=1.0) for a in ENTITIES.values()]
    key_l = [f"{a['label']}  {a['name']}\n        head office: {a['hq']}" for a in ENTITIES.values()]
    fig.legend(key_h, key_l, loc="lower left", bbox_to_anchor=(lx, 0.085), ncol=1,
               frameon=False, fontsize=10, handlelength=2.0, handleheight=1.3, labelspacing=0.7,
               labelcolor=C["text"], title="Entities (territory colour)", title_fontsize=11, alignment="left")

    fig.text(0.012, 0.012, SOURCE + (LOGO_CREDIT if any_logo else "") + (("\n" + DEM_CREDIT.strip()) if RELIEF_USED else ""),
             ha="left", va="bottom", size=9, color=C["muted"], linespacing=1.4)

    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{args.out}.{ext}", dpi=300, facecolor=fig.get_facecolor())
    print("saved", args.out + ".{png,pdf,svg}")


if __name__ == "__main__":
    main()
