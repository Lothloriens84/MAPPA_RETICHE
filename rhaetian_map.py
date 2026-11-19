"""
Rhaetian Alps — regional boundaries and hut-governing entities (Figure 1).

Pure matplotlib (no geopandas/shapely needed): reads Natural Earth 1:10m
GeoJSON boundaries and draws

  * the study area (Rhaetian Alps, approximate orographic outline),
  * the administrative units in which each entity owns/operates huts —
    full tint inside the study area, pale tint for the rest of the unit,
  * a badge per entity (logo file, or a text badge), with alpine clubs and
    the public authority drawn in two distinct styles,
  * the head-office city of each entity, with an arrow from its badge,
  * a legend and a source line.

Usage
-----
    python rhaetian_map.py <natural-earth-geojson-dir> [--logos logos/] [--out F1_Rhaetian_alps_map]

Logos
-----
One image per entity in the logos folder, named by its key in ENTITIES
(e.g. logos/SAT.png). Missing files fall back to a text badge. If at least one
logo is used, the source line automatically credits the logo owners.

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

# Figure 1 frame: wider than the base extent so that every head office is on the map
F1_LON_MIN, F1_LON_MAX = 7.10, 12.35
F1_LAT_MIN, F1_LAT_MAX = 45.28, 48.32

C = dict(
    paper="#FFFFFF",
    other="#FFFFFF",
    border_admin="#D3CEC4",
    border_country="#6B6458",
    border_region="#9C9384",
    study="#4A5D43",
    lake="#BCD3DB",
    text="#2F2B26",
    muted="#8A8275",
)

COUNTRY_FILL = {
    "Italy":         "#CFDCC4",   # meadow
    "Austria":       "#E9D7BE",   # larch
    "Switzerland":   "#D9D1E3",   # heather
    "Liechtenstein": "#BBD3DC",   # glacier
}
PALE_MIX = 0.55    # share of the territory colour kept outside the study area (heritage map)

# Figure 1: territories are coloured by the entity (or entities) operating huts there.
# Shared territories get diagonal stripes, one per entity.
TERRITORY_ENTITIES = {
    "LI":  ["LAV"],
    "GR":  ["SAC"],
    "VBG": ["DAV", "OEAV"],
    "TIR": ["DAV", "OEAV"],
    "SO":  ["CAI"],
    "BS":  ["CAI"],
    "BZ":  ["CAI", "AVS", "APS"],
    "TN":  ["SAT"],
}
TINT = 0.50          # share of the entity colour in the territory fill (rest is white)
STRIPE_W = 0.075     # stripe width, map units (~6 km)
VEIL = 0.62          # white veil over everything outside the study area (0 = none)

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
    "Milan":     (9.190, 45.464, (7, 0), "left"),
    "Munich":    (11.576, 48.137, (-7, 0), "right"),
    "Innsbruck": (11.393, 47.269, (0, 7), "center"),
    "Bolzano":   (11.354, 46.498, (7, 0), "left"),
    "Trento":    (11.121, 46.067, (7, -2), "left"),
}

# Entities.  kind = "club" (alpine club) or "authority" (public body).
#   badge   : badge centre in AXES fraction (values <0 or >1 sit in the margin)
#   hq      : head-office city (key in CITIES); the arrow runs from the badge to it
#   rad     : curvature of that arrow
#   targets : operating territories (used by heritage_map.py)
ENTITIES = {
    "LAV":  dict(kind="club", label="LAV", name="Liechtensteiner\nAlpenverein", colour="#3F6E8C",
                 badge=(0.30, 1.07), hq="Schaan", rad=0.15, targets=[("LI", 9.56, 47.12)]),
    "SAC":  dict(kind="club", label="SAC", name="Schweizer\nAlpen-Club", colour="#9E3B33",
                 badge=(-0.115, 0.62), hq="Bern", rad=-0.15, targets=[("GR", 9.80, 46.58)]),
    "CAI":  dict(kind="club", label="CAI", name="Club Alpino\nItaliano", colour="#2F6B4F",
                 badge=(-0.115, 0.20), hq="Milan", rad=0.20, targets=[("SO", 10.02, 46.36), ("BS", 10.45, 46.08)]),
    "DAV":  dict(kind="club", label="DAV", name="Deutscher\nAlpenverein", colour="#3C4A7A",
                 badge=(0.62, 1.07), hq="Munich", rad=-0.2, targets=[("VBG", 9.90, 47.06), ("TIR", 10.82, 47.10)]),
    "OEAV": dict(kind="club", label="ÖAV", name="Österreichischer\nAlpenverein", colour="#B5562C",
                 badge=(1.115, 0.86), hq="Innsbruck", rad=0.15, targets=[("VBG", 10.12, 47.02), ("TIR", 11.25, 47.12)]),
    "AVS":  dict(kind="club", label="AVS", name="Alpenverein\nSüdtirol", colour="#7A5C2E",
                 badge=(1.115, 0.60), hq="Bolzano", rad=0.12, targets=[("BZ", 11.25, 46.86)]),
    "APS":  dict(kind="authority", label="APS", name="Provincia autonoma\ndi Bolzano",
                 colour="#6E4F7A", badge=(1.115, 0.36), hq="Bolzano", rad=-0.12, targets=[("BZ", 11.05, 46.58)]),
    "SAT":  dict(kind="club", label="SAT", name="Società degli Alpinisti\nTridentini", colour="#B8860B",
                 badge=(1.115, 0.11), hq="Trento", rad=-0.15, targets=[("TN", 11.00, 46.34)]),
}

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
    ("SWITZERLAND", 8.15, 46.55),
    ("AUSTRIA", 12.00, 47.55),
    ("GERMANY", 10.20, 48.05),
    ("ITALY", 11.90, 45.55),
]
F1_LI_LABEL = ("LIECHTENSTEIN", 8.75, 47.40, 9.53, 47.14)

# Region-tier labels (units the text refers to that are not operating territories)
REGION_LABELS = [
    ("LOMBARDY", 9.80, 45.82),
]
REGION_OUTLINE = ("Italy", "Lombardia")   # dissolved provinces -> thin region boundary

LOGO_MAX_W, LOGO_MAX_H = 100, 40   # logo box above each badge, in points
LOGO_GAP = 5                      # points between logo and badge
TITLE = "The Rhaetian Alps: regional boundaries and hut-governing entities"
SOURCE = ("Study area: SOIUSA Western (II/A-15), Eastern (II/A-16) and Southern (II/C-28) Rhaetian Alps.\nOutline (approximate): "
          "Lake Como – Splügen – Hinterrhein – Rhine – Ill – Arlberg – Inn – Sill – Brenner – Isarco – Adige – "
          "Valle dei Laghi – Giudicarie – Croce Domini – Val Camonica – Aprica – Valtellina.\n"
          "Base map: Natural Earth 1:10m Cultural Vectors (public domain), naturalearthdata.com. "
          "Map: author's elaboration.")
LOGO_CREDIT = " Logos © the respective organisations, reproduced for identification only."

# ════════════════════════════════════════════════════════════════════════════
# GEOMETRY HELPERS
# ════════════════════════════════════════════════════════════════════════════

K = math.cos(math.radians((LAT_MIN + LAT_MAX) / 2))


def proj(lon, lat):
    return lon * K, lat


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
    xs, ys = [], []
    for poly in rings_of(geom):
        for x, y in poly[0]:
            xs.append(x); ys.append(y)
    if not xs:
        return False
    return not (max(xs) < LON_MIN - pad or min(xs) > LON_MAX + pad or
                max(ys) < LAT_MIN - pad or min(ys) > LAT_MAX + pad)


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


def draw_stripes(ax, path, cols, clip_patch, width=None):
    """Diagonal stripes in the given colours, clipped to a territory."""
    width = STRIPE_W if width is None else width
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


def pale_of(rgb):
    return tuple(c + (1 - c) * VEIL for c in mcolors.to_rgb(rgb))


def outside_path():
    """A large rectangle with the study area cut out (for the veil)."""
    ring = [proj(x, y) for x, y in STUDY_AREA]
    signed = sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1))
    if signed > 0:              # make the hole run opposite to the (counter-clockwise) rectangle
        ring = ring[::-1]
    big = [proj(-30, 20), proj(60, 20), proj(60, 75), proj(-30, 75), proj(-30, 20)]
    verts = big + ring
    codes = ([Path.MOVETO] + [Path.LINETO] * 3 + [Path.CLOSEPOLY] +
             [Path.MOVETO] + [Path.LINETO] * (len(ring) - 2) + [Path.CLOSEPOLY])
    return Path(verts, codes)


def draw_locator(fig, ax, ne_dir, frame):
    """Europe locator in the top-left corner of the map, with the study area in red."""
    fn = os.path.join(ne_dir, "ne_europe_simplified.geojson")
    if not os.path.exists(fn):
        return
    ax.apply_aspect()
    pos = ax.get_position()
    (l0, l1), (b0, b1) = INSET["lon"], INSET["lat"]
    k = math.cos(math.radians((b0 + b1) / 2))
    w = pos.width * INSET["width"]
    fw, fh = fig.get_size_inches()
    h = w * fw / fh * (b1 - b0) / ((l1 - l0) * k)
    ia = fig.add_axes([pos.x0 + 0.004, pos.y1 - h - 0.004 * fw / fh, w, h], zorder=20)
    ia.set_facecolor("#E9F1F4")
    for f in load(fn):
        pp = []
        for poly in rings_of(f["geometry"]):
            pp.append([(x * k, y) for x, y in poly[0]])
        for r in pp:
            ia.add_patch(plt.Polygon(r, closed=True, fc="#FFFFFF", ec="#B9B2A6", lw=0.3))
    ia.add_patch(plt.Polygon([(x * k, y) for x, y in STUDY_AREA], closed=True,
                             fc="#C0392B", ec="#7B241C", lw=0.4, zorder=5))
    (fx0, fy0), (fx1, fy1) = frame
    ia.add_patch(Rectangle((fx0 * k, fy0), (fx1 - fx0) * k, fy1 - fy0, fc="none",
                           ec=C["text"], lw=0.8, zorder=6))
    ia.set_xlim(l0 * k, l1 * k); ia.set_ylim(b0, b1)
    ia.set_xticks([]); ia.set_yticks([])
    for sp in ia.spines.values():
        sp.set_edgecolor(C["border_country"]); sp.set_linewidth(0.8)
    ia.text(0.03, 0.03, "Europe", transform=ia.transAxes, size=6.5, color=C["muted"],
            style="italic", va="bottom")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["features"]


# ════════════════════════════════════════════════════════════════════════════
# BADGES
# ════════════════════════════════════════════════════════════════════════════

def badge_box(a):
    if a["kind"] == "authority":
        return dict(boxstyle="square,pad=0.35", fc="#F6F2F7", ec=a["colour"], lw=1.3, ls=(0, (3.2, 1.6)))
    return dict(boxstyle="round,pad=0.35,rounding_size=0.6", fc="white", ec=a["colour"], lw=1.2)


def make_badge(a):
    """Box content: acronym + full name."""
    caption = TextArea(a["name"], textprops=dict(size=7.2, color=C["text"], ha="center",
                                                 linespacing=1.15, multialignment="center"))
    head = TextArea(a["label"], textprops=dict(size=13, weight="bold", color=a["colour"], ha="center"))
    return VPacker(children=[head, caption], align="center", pad=0, sep=3)


def find_logo(key, logo_dir):
    if not logo_dir:
        return None
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(logo_dir, key + ext)
        if os.path.exists(p):
            return p
    return None


def make_logo(path):
    """Logo scaled to fit LOGO_MAX_W x LOGO_MAX_H points."""
    img = plt.imread(path)
    h, w = img.shape[:2]
    return OffsetImage(img, zoom=min(LOGO_MAX_W / w, LOGO_MAX_H / h), interpolation="lanczos")


class HandlerBadge(HandlerPatch):
    """Legend glyph that looks like a badge (rounded/solid or square/dashed)."""
    def __init__(self, rounded, dashed):
        super().__init__()
        self.rounded, self.dashed = rounded, dashed

    def create_artists(self, legend, orig, xd, yd, w, h, fs, trans):
        style = "round,pad=0,rounding_size=3" if self.rounded else "square,pad=0"
        p = FancyBboxPatch((xd + 2, yd - 1), w - 4, h + 2, boxstyle=style,
                           fc="#F6F2F7" if self.dashed else "white", ec=C["text"], lw=1.0,
                           ls=(0, (3, 1.5)) if self.dashed else "-", transform=trans)
        return [p]


# ════════════════════════════════════════════════════════════════════════════
# DRAW
# ════════════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ne_dir", help="folder with Natural Earth 10m GeoJSON files")
    ap.add_argument("--logos", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "logos"),
                    help="folder with <KEY>.png logos (default: logos/ next to this script); 'none' to disable")
    ap.add_argument("--out", default="F1_Rhaetian_alps_map")
    args = ap.parse_args()

    adm0 = load(os.path.join(args.ne_dir, "ne_10m_admin_0_countries.geojson"))
    adm1 = load(os.path.join(args.ne_dir, "ne_10m_admin_1_states_provinces.geojson"))
    lakes = load(os.path.join(args.ne_dir, "ne_10m_lakes.geojson"))

    plt.rcParams["font.family"] = "DejaVu Sans"
    fig = plt.figure(figsize=(11.5, 10.0), facecolor=C["paper"])
    ax = fig.add_axes([0.14, 0.13, 0.72, 0.665])
    ax.set_facecolor(C["other"])

    # 1 — background admin units
    for f in adm1:
        if f["properties"]["admin"] == "Liechtenstein":
            continue
        if bbox_hits(f["geometry"]):
            p = geom_to_path(f["geometry"])
            if p:
                ax.add_patch(PathPatch(p, fc=C["other"], ec=C["border_admin"], lw=0.5, zorder=1))

    # 2 — study area (also the clip path for the full-tint fills)
    study = PathPatch(ring_path([STUDY_AREA]), fc="none", ec=C["study"], lw=1.5, zorder=5)
    ax.add_patch(study)

    # 3 — operating territories: pale whole unit, full tint inside study area
    idx = {}
    for f in adm1:
        pr = f["properties"]
        idx[("admin1", pr["admin"], pr["name"])] = f["geometry"]
    for f in adm0:
        pr = f["properties"]
        idx[("admin0", pr["ADMIN"], pr["ADMIN"])] = f["geometry"]

    for key, (lvl, ctry, ne_name, label, lx, ly) in TERRITORIES.items():
        geom = idx.get((lvl, ctry, ne_name))
        if geom is None:
            raise SystemExit(f"Territory not found in Natural Earth: {lvl} {ctry} {ne_name}")
        path = geom_to_path(geom)
        cols = [tint(ENTITIES[e]["colour"]) for e in TERRITORY_ENTITIES[key]]
        shape = PathPatch(path, fc=cols[0], ec="none", zorder=2)
        ax.add_patch(shape)
        if len(cols) > 1:
            draw_stripes(ax, path, cols, shape)
        ax.add_patch(PathPatch(path, fc="none", ec="white", lw=1.0, zorder=2.3))
        if label:
            x, y = proj(lx, ly)
            ax.text(x, y, label, ha="center", va="center", size=8.6, style="italic",
                    color=C["text"], zorder=6,
                    path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])

    # 3b — white veil outside the study area: everything there reads paler
    if VEIL:
        ax.add_patch(PathPatch(outside_path(), fc="white", ec="none", alpha=VEIL, zorder=2.4))

    # 4 — region boundary (Lombardy, dissolved from its provinces)
    ctry, reg = REGION_OUTLINE
    reg_geoms = [f["geometry"] for f in adm1
                 if f["properties"]["admin"] == ctry and f["properties"].get("region") == reg]
    ax.add_patch(PathPatch(dissolved_edges(reg_geoms), fc="none", ec=C["border_region"],
                           lw=0.9, zorder=2.6))

    # 5 — country borders
    for f in adm0:
        if bbox_hits(f["geometry"]):
            p = geom_to_path(f["geometry"])
            if p:
                ax.add_patch(PathPatch(p, fc="none", ec=C["border_country"], lw=1.1,
                                       ls=(0, (5, 1.6)), zorder=3))

    # 6 — lakes
    for f in lakes:
        if bbox_hits(f["geometry"], pad=0):
            p = geom_to_path(f["geometry"])
            if p:
                ax.add_patch(PathPatch(p, fc=C["lake"], ec="none", zorder=3.5))

    # 7 — country and region labels
    for txt, lon, lat in F1_COUNTRY_LABELS:
        x, y = proj(lon, lat)
        ax.text(x, y, txt, ha="center", va="center", size=9.5, color=C["muted"],
                weight="bold", alpha=0.85, zorder=4)
    t, lon, lat, tlon, tlat = F1_LI_LABEL
    ax.annotate(t, xy=proj(tlon, tlat), xytext=proj(lon, lat), ha="center", va="center",
                size=8, color=C["muted"], weight="bold", zorder=4,
                arrowprops=dict(arrowstyle="-", color=C["muted"], lw=0.7, shrinkA=2, shrinkB=0))
    for txt, lon, lat in REGION_LABELS:
        x, y = proj(lon, lat)
        ax.text(x, y, txt, ha="center", va="center", size=8.2, color=C["muted"],
                style="italic", weight="bold", zorder=4,
                path_effects=[pe.withStroke(linewidth=2.2, foreground=C["other"])])

    x0, y0 = proj(F1_LON_MIN, F1_LAT_MIN)
    x1, y1 = proj(F1_LON_MAX, F1_LAT_MAX)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor(C["border_country"]); s.set_linewidth(0.8)

    # 8 — head-office cities, arrows from each badge to its city, badges
    for city, (lon, lat, off, ha) in CITIES.items():
        x, y = proj(lon, lat)
        ax.plot(x, y, "o", ms=6.5, mfc="white", mec=C["text"], mew=1.6, zorder=8.5)
        ax.plot(x, y, "o", ms=2.2, mfc=C["text"], mec="none", zorder=8.6)
        ax.annotate(city, (x, y), xytext=off, textcoords="offset points", ha=ha, va="center",
                    size=8.4, weight="bold", color=C["text"], zorder=8.7,
                    path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])

    badges_with_logo = []
    for key, a in ENTITIES.items():
        ls = (0, (4, 2)) if a["kind"] == "authority" else "-"
        lon, lat = CITIES[a["hq"]][:2]
        ax.annotate("", xy=proj(lon, lat), xycoords="data",
                    xytext=a["badge"], textcoords="axes fraction",
                    arrowprops=dict(arrowstyle="-|>,head_length=0.55,head_width=0.28",
                                    color=a["colour"], lw=1.5, ls=ls, shrinkA=30, shrinkB=4.5,
                                    connectionstyle=f"arc3,rad={a['rad']}"),
                    annotation_clip=False, zorder=7)
        ab = AnnotationBbox(make_badge(a), a["badge"], xycoords="axes fraction",
                            frameon=True, annotation_clip=False, zorder=9, pad=0.45,
                            bboxprops=badge_box(a))
        ax.add_artist(ab)
        logo = find_logo(key, args.logos)
        if logo:
            badges_with_logo.append((ab, a, logo))

    # 8b — logos above their badges (needs the badges' rendered height)
    any_logo = bool(badges_with_logo)
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    for ab, a, logo in badges_with_logo:
        bb = ab.get_window_extent(r)
        cx, cy = ax.transAxes.transform(a["badge"])
        dy = (bb.y1 - cy) * 72 / fig.dpi + LOGO_GAP
        ax.add_artist(AnnotationBbox(make_logo(logo), a["badge"], xycoords="axes fraction",
                                     xybox=(0, dy), boxcoords="offset points", box_alignment=(0.5, 0),
                                     frameon=False, annotation_clip=False, zorder=9))

    # 9 — scale bar and north arrow
    sb_len = 50 / 111.32
    sx, sy = proj(F1_LON_MIN + 0.15, F1_LAT_MIN + 0.12)
    ax.plot([sx, sx + sb_len], [sy, sy], color=C["text"], lw=2.2, solid_capstyle="butt", zorder=8)
    ax.plot([sx, sx + sb_len / 2], [sy, sy], color="white", lw=1.0, solid_capstyle="butt", zorder=9)
    for xx, t in [(sx, "0"), (sx + sb_len / 2, "25"), (sx + sb_len, "50 km")]:
        ax.text(xx, sy + 0.035, t, ha="center", va="bottom", size=7, color=C["text"], zorder=9)
    nx, ny = proj(F1_LON_MAX - 0.2, F1_LAT_MIN + 0.14)
    ax.annotate("N", xy=(nx, ny + 0.17), xytext=(nx, ny), ha="center", va="top",
                size=9, weight="bold", color=C["text"],
                arrowprops=dict(arrowstyle="-|>", color=C["text"], lw=1.4), zorder=9)

    # 10 — legend
    n_club = sum(a["kind"] == "club" for a in ENTITIES.values())
    n_auth = sum(a["kind"] == "authority" for a in ENTITIES.values())
    club_h, auth_h = Patch(), Patch(label="_")
    handles = [
        Line2D([], [], color=C["study"], lw=1.5),
        Patch(fc=tint(ENTITIES["CAI"]["colour"]), ec="white"),
        Patch(fc=tint(ENTITIES["DAV"]["colour"]), ec="white", hatch="////",
              hatchcolor=tint(ENTITIES["OEAV"]["colour"], 0.75), lw=0),
        Patch(fc=pale_of(tint(ENTITIES["CAI"]["colour"])), ec="white"),
        Line2D([], [], color=C["border_country"], lw=1.1, ls=(0, (5, 1.6))),
        Line2D([], [], color=C["border_region"], lw=0.9),
        Line2D([], [], ls="none", marker="o", ms=6.5, mfc="white", mec=C["text"], mew=1.6),
        club_h, auth_h,
    ]
    labels = [
        "Rhaetian Alps (study area, approx.)",
        "Operating territory (colour of the entity)",
        "Territory shared by several entities",
        "Operating territory, outside study area",
        "National border",
        "Regional border (Lombardy)",
        "Head office (arrow from the entity)",
        f"Alpine club ({n_club})",
        f"Public authority ({n_auth})",
    ]
    leg = fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.052), ncol=4,
                     frameon=False, fontsize=7.6, handlelength=2.4, handleheight=1.1,
                     columnspacing=1.6, labelcolor=C["text"],
                     handler_map={club_h: HandlerBadge(True, False), auth_h: HandlerBadge(False, True)})

    # 10b — Europe locator
    draw_locator(fig, ax, args.ne_dir, ((F1_LON_MIN, F1_LAT_MIN), (F1_LON_MAX, F1_LAT_MAX)))

    # 11 — title + source line
    fig.text(0.5, 0.975, TITLE, ha="center", va="top", size=13.5, weight="bold", color=C["text"])
    fig.text(0.5, 0.015, SOURCE + (LOGO_CREDIT if any_logo else ""), ha="center", va="bottom",
             size=7.2, color=C["muted"], linespacing=1.4)

    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{args.out}.{ext}", dpi=300, facecolor=fig.get_facecolor())
    print("saved", args.out + ".{png,pdf,svg}")


if __name__ == "__main__":
    main()
