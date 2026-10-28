"""
Rhaetian Alps — regional boundaries and hut-governing entities (Figure 1).

Pure matplotlib (no geopandas/shapely needed): reads Natural Earth 1:10m
GeoJSON boundaries and draws

  * the study area (Rhaetian Alps, approximate orographic outline),
  * the administrative units in which each entity owns/operates huts —
    full tint inside the study area, pale tint for the rest of the unit,
  * a badge per entity (logo file, or a text badge), with alpine clubs and
    the public authority drawn in two distinct styles,
  * an arrow from each badge to each territory where it operates,
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

import matplotlib.pyplot as plt
from matplotlib.legend_handler import HandlerPatch
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, OffsetImage, TextArea, VPacker
from matplotlib.patches import PathPatch, FancyBboxPatch, Patch
from matplotlib.path import Path
import matplotlib.colors as mcolors
import matplotlib.patheffects as pe

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

LON_MIN, LON_MAX = 8.75, 12.95
LAT_MIN, LAT_MAX = 45.55, 47.62

C = dict(
    paper="#F4F1EA",
    other="#E6E2D8",
    border_admin="#FFFFFF",
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
PALE_MIX = 0.55    # share of the territory colour kept outside the study area

# Study area: Rhaetian Alps, approximate outline along
# Rhine – Ill – Arlberg – Inn – Brenner – Isarco – Adige – Lake Garda –
# Val Camonica – Valtellina – Lake Como – Splügen.
STUDY_AREA = [
    (9.6271, 47.3197), (9.6765, 47.2875), (9.8, 47.2446), (9.9482, 47.191),
    (10.1088, 47.1803), (10.2447, 47.1695), (10.43, 47.1695), (10.4918, 47.1695),
    (10.6647, 47.1803), (10.8747, 47.1803), (11.0847, 47.2875), (11.2824, 47.3197),
    (11.4924, 47.3626), (11.7024, 47.3197), (11.9, 47.309), (11.9247, 47.2446),
    (11.9618, 47.1695), (11.9988, 47.0837), (12.0359, 47.0301), (11.9741, 46.9658),
    (11.9371, 46.9228), (12.0482, 46.8585), (12.1594, 46.8049), (12.2212, 46.7191),
    (12.11, 46.644), (11.9618, 46.526), (11.8382, 46.4831), (11.7765, 46.3866),
    (11.6653, 46.215), (11.5541, 46.1828), (11.5541, 46.0326), (11.4924, 45.9254),
    (11.4553, 45.8396), (11.3812, 45.7967), (11.2082, 45.8289), (11.0353, 45.8074),
    (10.8871, 45.7967), (10.8129, 45.7431), (10.6894, 45.8289), (10.5412, 45.9147),
    (10.5782, 46.0326), (10.5782, 46.1506), (10.3559, 46.1184), (10.2571, 46.1506),
    (10.01, 46.1399), (9.6394, 46.1077), (9.4294, 46.1184), (9.4294, 46.3008),
    (9.3429, 46.5046), (9.3306, 46.5475), (9.4788, 46.7083), (9.4418, 46.837),
    (9.59, 46.8692), (9.6271, 46.9979), (9.4788, 47.0837), (9.5282, 47.2124),
    (9.6271, 47.3197),
]

# Operating territories: key -> (admin level, country, Natural Earth name, English label, label lon, lat)
TERRITORIES = {
    "GR":  ("admin1", "Switzerland",   "Graubünden",    "Graubünden",   9.95, 46.72),
    "LI":  ("admin0", "Liechtenstein", "Liechtenstein", None,           0, 0),   # labelled as a country
    "VBG": ("admin1", "Austria",       "Vorarlberg",    "Vorarlberg",   9.80, 47.43),
    "TIR": ("admin1", "Austria",       "Tirol",         "Tyrol",       11.20, 47.25),
    "SO":  ("admin1", "Italy",         "Sondrio",       "Sondrio",      9.85, 46.21),
    "BS":  ("admin1", "Italy",         "Brescia",       "Brescia",     10.36, 45.96),
    "BZ":  ("admin1", "Italy",         "Bozen",         "South Tyrol", 11.32, 46.78),
    "TN":  ("admin1", "Italy",         "Trento",        "Trentino",    11.00, 46.07),
}

# Entities.  kind = "club" (alpine club) or "authority" (public body).
#   badge   : badge centre in AXES fraction (values <0 or >1 sit in the margin)
#   targets : (territory key, arrow-tip lon, arrow-tip lat)
ENTITIES = {
    "LAV":  dict(kind="club", label="LAV", name="Liechtensteiner\nAlpenverein", colour="#3F6E8C",
                 badge=(-0.115, 0.86), targets=[("LI", 9.56, 47.12)]),
    "SAC":  dict(kind="club", label="SAC", name="Schweizer\nAlpen-Club", colour="#9E3B33",
                 badge=(-0.115, 0.52), targets=[("GR", 9.80, 46.58)]),
    "CAI":  dict(kind="club", label="CAI", name="Club Alpino\nItaliano", colour="#2F6B4F",
                 badge=(-0.115, 0.17), targets=[("SO", 9.95, 46.30), ("BS", 10.38, 46.06)]),
    "DAV":  dict(kind="club", label="DAV", name="Deutscher\nAlpenverein", colour="#3C4A7A",
                 badge=(0.30, 1.12), targets=[("VBG", 9.88, 47.12), ("TIR", 10.75, 47.22)]),
    "OEAV": dict(kind="club", label="ÖAV", name="Österreichischer\nAlpenverein", colour="#B5562C",
                 badge=(0.66, 1.12), targets=[("VBG", 10.10, 47.06), ("TIR", 11.70, 47.20)]),
    "AVS":  dict(kind="club", label="AVS", name="Alpenverein\nSüdtirol", colour="#7A5C2E",
                 badge=(1.115, 0.78), targets=[("BZ", 11.45, 46.92)]),
    "APS":  dict(kind="authority", label="APS", name="Provincia autonoma\ndi Bolzano",
                 colour="#6E4F7A", badge=(1.115, 0.46), targets=[("BZ", 11.72, 46.55)]),
    "SAT":  dict(kind="club", label="SAT", name="Società degli Alpinisti\nTridentini", colour="#4E7D3A",
                 badge=(1.115, 0.14), targets=[("TN", 11.15, 46.22)]),
}

# Country labels (English). Liechtenstein gets a leader line.
COUNTRY_LABELS = [
    ("SWITZERLAND", 9.02, 46.88),
    ("AUSTRIA", 12.55, 47.42),
    ("GERMANY", 10.55, 47.57),
    ("ITALY", 12.40, 45.72),
]
LI_LABEL = ("LIECHTENSTEIN", 9.10, 47.41, 9.51, 47.19)   # text lon/lat, leader-tip lon/lat

# Region-tier labels (units the text refers to that are not operating territories)
REGION_LABELS = [
    ("LOMBARDY", 9.80, 45.82),
]
REGION_OUTLINE = ("Italy", "Lombardia")   # dissolved provinces -> thin region boundary

LOGO_HEIGHT_PX = 70
TITLE = "The Rhaetian Alps: regional boundaries and hut-governing entities"
SOURCE = ("Study-area outline (approximate): Rhine – Ill – Arlberg – Inn – Brenner – Isarco – Adige – "
          "Lake Garda – Val Camonica – Valtellina – Lake Como – Splügen.\n"
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


def make_badge(key, a, logo_dir):
    img_path = None
    if logo_dir:
        for ext in (".png", ".jpg", ".jpeg"):
            p = os.path.join(logo_dir, key + ext)
            if os.path.exists(p):
                img_path = p
                break
    caption = TextArea(a["name"], textprops=dict(size=7.2, color=C["text"], ha="center",
                                                 linespacing=1.15, multialignment="center"))
    if img_path:
        img = plt.imread(img_path)
        zoom = LOGO_HEIGHT_PX / img.shape[0]
        head = OffsetImage(img, zoom=zoom * 300 / 72 / 4.17)
    else:
        head = TextArea(a["label"], textprops=dict(size=13, weight="bold", color=a["colour"], ha="center"))
    return VPacker(children=[head, caption], align="center", pad=0, sep=3), bool(img_path)


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
    ap.add_argument("--logos", default="logos")
    ap.add_argument("--out", default="F1_Rhaetian_alps_map")
    args = ap.parse_args()

    adm0 = load(os.path.join(args.ne_dir, "ne_10m_admin_0_countries.geojson"))
    adm1 = load(os.path.join(args.ne_dir, "ne_10m_admin_1_states_provinces.geojson"))
    lakes = load(os.path.join(args.ne_dir, "ne_10m_lakes.geojson"))

    plt.rcParams["font.family"] = "DejaVu Sans"
    fig = plt.figure(figsize=(11.5, 8.4), facecolor=C["paper"])
    ax = fig.add_axes([0.14, 0.155, 0.72, 0.65])
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
        ax.add_patch(PathPatch(path, fc=pale(COUNTRY_FILL[ctry]), ec="white", lw=1.0, zorder=2))
        inner = PathPatch(path, fc=COUNTRY_FILL[ctry], ec="white", lw=1.0, zorder=2.2)
        ax.add_patch(inner)
        inner.set_clip_path(study)
        if label:
            x, y = proj(lx, ly)
            halo = COUNTRY_FILL[ctry] if study.get_path().contains_point((x, y)) else pale(COUNTRY_FILL[ctry])
            ax.text(x, y, label, ha="center", va="center", size=8.6, style="italic",
                    color=C["text"], zorder=6,
                    path_effects=[pe.withStroke(linewidth=2.4, foreground=halo)])

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
    for txt, lon, lat in COUNTRY_LABELS:
        x, y = proj(lon, lat)
        ax.text(x, y, txt, ha="center", va="center", size=9.5, color=C["muted"],
                weight="bold", alpha=0.85, zorder=4)
    t, lon, lat, tlon, tlat = LI_LABEL
    ax.annotate(t, xy=proj(tlon, tlat), xytext=proj(lon, lat), ha="center", va="center",
                size=8, color=C["muted"], weight="bold", zorder=4,
                arrowprops=dict(arrowstyle="-", color=C["muted"], lw=0.7, shrinkA=2, shrinkB=0))
    for txt, lon, lat in REGION_LABELS:
        x, y = proj(lon, lat)
        ax.text(x, y, txt, ha="center", va="center", size=8.2, color=C["muted"],
                style="italic", weight="bold", zorder=4,
                path_effects=[pe.withStroke(linewidth=2.2, foreground=C["other"])])

    x0, y0 = proj(LON_MIN, LAT_MIN)
    x1, y1 = proj(LON_MAX, LAT_MAX)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor(C["border_country"]); s.set_linewidth(0.8)

    # 8 — arrows + badges
    any_logo = False
    for key, a in ENTITIES.items():
        ls = (0, (4, 2)) if a["kind"] == "authority" else "-"
        for terr, tlon, tlat in a["targets"]:
            tx, ty = proj(tlon, tlat)
            bx, by = a["badge"]
            rad = 0.18 if bx > 0.5 or by > 1 else -0.18
            ax.annotate("", xy=(tx, ty), xycoords="data",
                        xytext=(bx, by), textcoords="axes fraction",
                        arrowprops=dict(arrowstyle="-|>,head_length=0.55,head_width=0.28",
                                        color=a["colour"], lw=1.5, ls=ls, shrinkA=30, shrinkB=1,
                                        connectionstyle=f"arc3,rad={rad}"),
                        annotation_clip=False, zorder=7)
            ax.plot(tx, ty, "o", ms=3.2, mfc="white", mec=a["colour"], mew=1.2, zorder=8)
        badge, has_logo = make_badge(key, a, args.logos)
        any_logo |= has_logo
        ax.add_artist(AnnotationBbox(badge, a["badge"], xycoords="axes fraction",
                                     frameon=True, annotation_clip=False, zorder=9, pad=0.45,
                                     bboxprops=badge_box(a)))

    # 9 — scale bar and north arrow
    sb_len = 50 / 111.32
    sx, sy = proj(LON_MIN + 0.12, LAT_MIN + 0.10)
    ax.plot([sx, sx + sb_len], [sy, sy], color=C["text"], lw=2.2, solid_capstyle="butt", zorder=8)
    ax.plot([sx, sx + sb_len / 2], [sy, sy], color="white", lw=1.0, solid_capstyle="butt", zorder=9)
    for xx, t in [(sx, "0"), (sx + sb_len / 2, "25"), (sx + sb_len, "50 km")]:
        ax.text(xx, sy + 0.035, t, ha="center", va="bottom", size=7, color=C["text"], zorder=9)
    nx, ny = proj(LON_MAX - 0.18, LAT_MIN + 0.12)
    ax.annotate("N", xy=(nx, ny + 0.17), xytext=(nx, ny), ha="center", va="top",
                size=9, weight="bold", color=C["text"],
                arrowprops=dict(arrowstyle="-|>", color=C["text"], lw=1.4), zorder=9)

    # 10 — legend
    n_club = sum(a["kind"] == "club" for a in ENTITIES.values())
    n_auth = sum(a["kind"] == "authority" for a in ENTITIES.values())
    club_h, auth_h = Patch(), Patch(label="_")
    handles = [
        Line2D([], [], color=C["study"], lw=1.5),
        Patch(fc=COUNTRY_FILL["Italy"], ec="white"),
        Patch(fc=pale(COUNTRY_FILL["Italy"]), ec="white"),
        Line2D([], [], color=C["border_country"], lw=1.1, ls=(0, (5, 1.6))),
        Line2D([], [], color=C["border_region"], lw=0.9),
        club_h, auth_h,
    ]
    labels = [
        "Rhaetian Alps (study area, approx.)",
        "Operating territory, inside study area",
        "Operating territory, outside study area",
        "National border",
        "Regional border (Lombardy)",
        f"Alpine club ({n_club})",
        f"Public authority ({n_auth})",
    ]
    leg = fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.068), ncol=4,
                     frameon=False, fontsize=7.6, handlelength=2.4, handleheight=1.1,
                     columnspacing=1.6, labelcolor=C["text"],
                     handler_map={club_h: HandlerBadge(True, False), auth_h: HandlerBadge(False, True)})

    # 11 — title + source line
    fig.text(0.5, 0.975, TITLE, ha="center", va="top", size=13.5, weight="bold", color=C["text"])
    fig.text(0.5, 0.018, SOURCE + (LOGO_CREDIT if any_logo else ""), ha="center", va="bottom",
             size=7.2, color=C["muted"], linespacing=1.4)

    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{args.out}.{ext}", dpi=300, facecolor=fig.get_facecolor())
    print("saved", args.out + ".{png,pdf,svg}")


if __name__ == "__main__":
    main()
