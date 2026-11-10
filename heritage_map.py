"""
Rhaetian Alps — heritage claims on mountain food beyond the hut-governing entities
(companion map to Figure 1).

Companion to rhaetian_map.py (Figure 1): same extent, projection, study-area
outline and Natural Earth base, with a second layer of actors that also claim
mountain food in the area as heritage:

  * protected areas (national parks, nature parks, Swiss parks of national
    importance), each labelled by name,
  * territorial quality labels, as badges pointing to their territory,
  * a valley initiative (100% Valposchiavo),
  * intangible cultural heritage inscribed by UNESCO (transhumance, alpinism).

Usage
-----
    python heritage_map.py <natural-earth-geojson-dir> [--parks parks.geojson] [--out Rhaetian_alps_heritage_map]

Protected-area outlines
-----------------------
By default the parks are drawn from the schematic outlines in PARKS below
(digitised by hand, accurate to a few km, like the study area). For exact
boundaries, export the nine parks from the WDPA (protectedplanet.net) or the
national/provincial geoportals to one GeoJSON file, give each feature a
property "key" matching the keys of PARKS (STE, SNP, ...), and pass it with
--parks. Any park found in the file replaces its schematic outline.

Everything you may want to change lives in the CONFIG section.
"""

import argparse
import json
import os

import matplotlib.pyplot as plt
from matplotlib.legend_handler import HandlerBase
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnnotationBbox, TextArea, VPacker
from matplotlib.patches import PathPatch, FancyBboxPatch, Patch
import matplotlib.patheffects as pe

import rhaetian_map as rm
from rhaetian_map import (C, STUDY_AREA, TERRITORIES, COUNTRY_LABELS, LI_LABEL, REGION_LABELS,
                          REGION_OUTLINE, LON_MIN, LON_MAX, LAT_MIN, LAT_MAX,
                          proj, ring_path, geom_to_path, bbox_hits, dissolved_edges, load)

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════


# Protected-area categories: fill colour, hatch, legend label
PARK_KIND = {
    "national": dict(fc="#3E6B45", alpha=0.62, hatch="////", label="National park"),
    "nature":   dict(fc="#7FA35A", alpha=0.55, hatch="",     label="Nature park (regional / provincial)"),
    "swiss":    dict(fc="#5E9C8F", alpha=0.55, hatch="....", label="Swiss park of national importance"),
}

# Protected areas: key -> name, kind, anchor lon/lat inside the park, map label (text, lon/lat;
# a leader line is drawn to the anchor when the label sits outside), schematic outline (lon, lat)
PARKS = {
    "STE": dict(n=1, name="Stelvio National Park", kind="national", at=(10.63, 46.45), label=("Stelvio\nNational Park", (10.66, 46.44)), outline=[
        (10.27, 46.47), (10.33, 46.55), (10.42, 46.56), (10.50, 46.62), (10.62, 46.63), (10.75, 46.60),
        (10.88, 46.57), (11.00, 46.53), (11.02, 46.47), (10.92, 46.42), (10.85, 46.36), (10.72, 46.32),
        (10.60, 46.31), (10.52, 46.28), (10.44, 46.26), (10.37, 46.29), (10.35, 46.36), (10.28, 46.40)]),
    "SNP": dict(n=2, name="Swiss National Park", kind="national", at=(10.16, 46.67), label=("Swiss\nNational Park", (10.02, 46.86)), outline=[
        (10.00, 46.62), (10.05, 46.68), (10.12, 46.71), (10.20, 46.74), (10.28, 46.73), (10.32, 46.69),
        (10.28, 46.65), (10.23, 46.62), (10.17, 46.61), (10.12, 46.57), (10.05, 46.58)]),
    "PNAB": dict(n=3, name="Adamello Brenta Nature Park", kind="nature", at=(10.84, 46.14), label=("Adamello Brenta\nNature Park", (10.84, 46.14)), outline=[
        (10.54, 46.04), (10.55, 46.15), (10.58, 46.24), (10.68, 46.27), (10.80, 46.30), (10.92, 46.33),
        (11.02, 46.27), (11.00, 46.15), (10.95, 46.09), (10.88, 46.08), (10.81, 46.15), (10.75, 46.10),
        (10.68, 46.03), (10.60, 45.98)]),
    "ADA": dict(n=4, name="Adamello Regional Park", kind="nature", at=(10.46, 46.06), label=("Adamello\nRegional Park", (10.12, 45.98)), outline=[
        (10.42, 46.23), (10.50, 46.25), (10.54, 46.17), (10.52, 46.04), (10.58, 45.98), (10.50, 45.92),
        (10.42, 45.93), (10.38, 46.02), (10.38, 46.12), (10.40, 46.19)]),
    "TEX": dict(n=5, name="Texelgruppe Nature Park", kind="nature", at=(11.06, 46.745), label=("Texelgruppe\nNature Park", (11.36, 46.86)), outline=[
        (10.92, 46.67), (10.95, 46.74), (11.00, 46.79), (11.08, 46.81), (11.15, 46.78), (11.17, 46.72),
        (11.12, 46.69), (11.05, 46.70), (10.98, 46.66)]),
    "OTZ": dict(n=6, name="Ötztal Nature Park", kind="nature", at=(11.00, 46.91), label=("Ötztal\nNature Park", (11.3, 47.0)), outline=[
        (10.86, 46.80), (10.88, 46.95), (10.95, 47.02), (11.05, 47.00), (11.10, 46.92), (11.08, 46.84),
        (11.00, 46.80), (10.92, 46.78)]),
    "KAU": dict(n=7, name="Kaunergrat Nature Park", kind="nature", at=(10.77, 47.06), label=("Kaunergrat\nNature Park", (10.42, 47.22)), outline=[
        (10.66, 47.07), (10.70, 47.17), (10.78, 47.22), (10.85, 47.18), (10.87, 47.05), (10.85, 46.94),
        (10.79, 46.89), (10.72, 46.95), (10.68, 47.01)]),
    "BVM": dict(n=8, name="Biosfera Val Müstair", kind="swiss", at=(10.40, 46.62), label=("Biosfera\nVal Müstair", (10.47, 46.80)), outline=[
        (10.30, 46.63), (10.34, 46.67), (10.41, 46.68), (10.47, 46.65), (10.47, 46.60), (10.40, 46.57),
        (10.33, 46.59)]),
    "ELA": dict(n=9, name="Parc Ela", kind="swiss", at=(9.71, 46.58), label=("Parc Ela", (9.71, 46.57)), outline=[
        (9.52, 46.62), (9.60, 46.68), (9.70, 46.70), (9.80, 46.67), (9.88, 46.60), (9.82, 46.53),
        (9.73, 46.46), (9.62, 46.45), (9.55, 46.52)]),
}

# Quality labels: one per territory.  Territories absent here are drawn neutral.
LABELS = {
    "GR":  dict(label="alpinavera", sub="Graubünden", colour="#A8323E",
                badge=(-0.115, 0.56), tip=(9.62, 46.82)),
    "TIR": dict(label="Agrarmarketing\nTirol", sub="Tyrol", colour="#7A3E6E",
                badge=(0.76, 1.10), tip=(11.25, 47.16)),
    "BZ":  dict(label="Qualität\nSüdtirol", sub="South Tyrol", colour="#B07A1E",
                badge=(1.115, 0.78), tip=(11.45, 46.70)),
    "TN":  dict(label="Qualità\nTrentino", sub="Trentino", colour="#3A6EA5",
                badge=(1.115, 0.18), tip=(11.12, 46.33)),
}

# Park-level quality labels (badge points to the park, no territory tint)
PARK_LABELS = {
    "PNAB": dict(label="Qualità\nParco", sub="Adamello Brenta\nNature Park", colour="#4E7D3A",
                 badge=(1.115, 0.48), tip=(10.97, 46.24)),
}
LABEL_MIX_IN, LABEL_MIX_OUT = 0.26, 0.11   # tint strength inside / outside study area
NEUTRAL_IN = "#ECE9E2"                     # other entity territories, inside study area

# Territory-label positions moved off the park badges (lon, lat); others as in Figure 1
TERR_LABEL_POS = {"TIR": (10.42, 47.04), "BZ": (11.22, 46.55), "TN": (11.08, 46.45)}

# Valley initiative
VALLEY = dict(label="100%\nValposchiavo", sub="valley initiative", colour="#B5562C",
              badge=(-0.105, 0.22), tip=(10.06, 46.32),
              outline=[(10.02, 46.42), (10.08, 46.42), (10.12, 46.35), (10.17, 46.27), (10.16, 46.22),
                       (10.11, 46.22), (10.04, 46.29), (9.99, 46.36)])

# Intangible cultural heritage (UNESCO Representative List)
ICH_COLOUR = "#2B4C7E"
TRANSHUMANCE = dict(label="Transhumance", sub="UNESCO ICH 2019\nSchnals – Ötztal sheep drive",
                    badge=(0.47, 1.10),
                    route=[(10.86, 46.70), (10.82, 46.77), (10.86, 46.81), (10.91, 46.86)])
ALPINISM = dict(label="Alpinism", sub="UNESCO ICH 2019\nFrance, Italy, Switzerland",
                badge=(0.16, 1.10))

TITLE = "The Rhaetian Alps: heritage claims on mountain food beyond the hut-governing entities"
SOURCE = ("Study area as in Figure 1 (SOIUSA II/A-15, II/A-16, II/C-28). Protected-area outlines are schematic "
          "(digitised by hand, accurate to a few km), not official boundaries.\n"
          "Transhumance: multinational inscription (Austria, Greece, Italy), Austrian element = Ötztal–Schnals sheep drive. "
          "Alpinism: multinational inscription (France, Italy, Switzerland).\n"
          "Base map: Natural Earth 1:10m Cultural Vectors (public domain), naturalearthdata.com. "
          "Map: author's elaboration.")
SOURCE_EXACT = ("Study area as in Figure 1 (SOIUSA II/A-15, II/A-16, II/C-28).\nProtected areas: {src}.\n"
                "Transhumance: multinational inscription (Austria, Greece, Italy), Austrian element = Ötztal–Schnals sheep drive. "
                "Alpinism: multinational inscription (France, Italy, Switzerland).\n"
                "Base map: Natural Earth 1:10m Cultural Vectors (public domain), naturalearthdata.com. "
                "Map: author's elaboration.")

# ════════════════════════════════════════════════════════════════════════════
# GLYPHS
# ════════════════════════════════════════════════════════════════════════════

def text_badge(head, sub, colour, head_size=10.5):
    caption = TextArea(sub, textprops=dict(size=7.0, color=C["text"], ha="center",
                                           linespacing=1.15, multialignment="center"))
    top = TextArea(head, textprops=dict(size=head_size, weight="bold", color=colour, ha="center",
                                        linespacing=1.0, multialignment="center"))
    return VPacker(children=[top, caption], align="center", pad=0, sep=3)


BOX = {
    "label":  lambda c: dict(boxstyle="round,pad=0.35,rounding_size=0.6", fc="white", ec=c, lw=1.2),
    "valley": lambda c: dict(boxstyle="round,pad=0.35,rounding_size=0.6", fc="#FBF4EF", ec=c, lw=1.3,
                             ls=(0, (4, 1.5, 1, 1.5))),
    "ich":    lambda c: dict(boxstyle="square,pad=0.35", fc="#F0F3F8", ec=c, lw=1.3, ls=(0, (3.2, 1.6))),
}


class HandlerBox(HandlerBase):
    def __init__(self, kind):
        super().__init__()
        self.kind = kind

    def create_artists(self, legend, orig, xd, yd, w, h, fs, trans):
        b = BOX[self.kind](C["text"])
        style = "square,pad=0" if b["boxstyle"].startswith("square") else "round,pad=0,rounding_size=3"
        return [FancyBboxPatch((xd + 2, yd - 1), w - 4, h + 2, boxstyle=style, fc=b["fc"], ec=C["text"],
                               lw=1.0, ls=b.get("ls", "-"), transform=trans)]


def mix(hex_colour, m):
    return rm.pale(hex_colour, m)


# ════════════════════════════════════════════════════════════════════════════
# DRAW
# ════════════════════════════════════════════════════════════════════════════

def load_parks(path):
    """Exact park geometries from a GeoJSON with a 'key' property; returns {key: Path}."""
    with open(path, encoding="utf-8") as f:
        feats = json.load(f)["features"]
    out = {}
    for ft in feats:
        k = ft["properties"].get("key")
        if k in PARKS:
            out[k] = geom_to_path(ft["geometry"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ne_dir", help="folder with Natural Earth 10m GeoJSON files")
    ap.add_argument("--parks", default=None, help="optional GeoJSON with exact park boundaries ('key' property)")
    ap.add_argument("--parks-source", default="UNEP-WCMC and IUCN (2026), Protected Planet: WDPA, Nov 2026, protectedplanet.net",
                    help="credit line for --parks data")
    ap.add_argument("--out", default="Rhaetian_alps_heritage_map")
    args = ap.parse_args()

    adm0 = load(os.path.join(args.ne_dir, "ne_10m_admin_0_countries.geojson"))
    adm1 = load(os.path.join(args.ne_dir, "ne_10m_admin_1_states_provinces.geojson"))
    lakes = load(os.path.join(args.ne_dir, "ne_10m_lakes.geojson"))
    exact = load_parks(args.parks) if args.parks else {}

    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["hatch.linewidth"] = 0.5
    fig = plt.figure(figsize=(11.5, 9.3), facecolor=C["paper"])
    ax = fig.add_axes([0.14, 0.165, 0.72, 0.639])
    ax.set_facecolor(C["other"])

    # 1 — background admin units
    for f in adm1:
        if f["properties"]["admin"] == "Liechtenstein":
            continue
        if bbox_hits(f["geometry"]):
            p = geom_to_path(f["geometry"])
            if p:
                ax.add_patch(PathPatch(p, fc=C["other"], ec=C["border_admin"], lw=0.5, zorder=1))

    study = PathPatch(ring_path([STUDY_AREA]), fc="none", ec=C["study"], lw=1.5, zorder=5)
    ax.add_patch(study)

    # 2 — entity territories, tinted by quality label
    idx = {}
    for f in adm1:
        pr = f["properties"]
        idx[("admin1", pr["admin"], pr["name"])] = f["geometry"]
    for f in adm0:
        pr = f["properties"]
        idx[("admin0", pr["ADMIN"], pr["ADMIN"])] = f["geometry"]

    for key, (lvl, ctry, ne_name, label, lx, ly) in TERRITORIES.items():
        path = geom_to_path(idx[(lvl, ctry, ne_name)])
        if key in LABELS:
            col = LABELS[key]["colour"]
            fc_out, fc_in = mix(col, LABEL_MIX_OUT), mix(col, LABEL_MIX_IN)
        else:
            fc_out, fc_in = C["other"], NEUTRAL_IN
        ax.add_patch(PathPatch(path, fc=fc_out, ec="white", lw=1.0, zorder=2))
        inner = PathPatch(path, fc=fc_in, ec="white", lw=1.0, zorder=2.2)
        ax.add_patch(inner)
        inner.set_clip_path(study)
        if label:
            x, y = proj(*TERR_LABEL_POS.get(key, (lx, ly)))
            ax.text(x, y, label, ha="center", va="center", size=8.2, style="italic", color=C["muted"],
                    zorder=4.6, path_effects=[pe.withStroke(linewidth=2.2, foreground="white")])

    # 3 — Lombardy outline, country borders, lakes
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
                ax.add_patch(PathPatch(p, fc=C["lake"], ec="none", zorder=4.4))

    # 4 — protected areas
    for key, pk in PARKS.items():
        kd = PARK_KIND[pk["kind"]]
        path = exact.get(key) or ring_path([pk["outline"] + [pk["outline"][0]]])
        ax.add_patch(PathPatch(path, fc=kd["fc"], alpha=kd["alpha"], ec="none", zorder=4))
        ax.add_patch(PathPatch(path, fc="none", ec=kd["fc"], lw=0.9, hatch=kd["hatch"], zorder=4.1))

    # 5 — valley initiative area
    vpath = ring_path([VALLEY["outline"] + [VALLEY["outline"][0]]])
    ax.add_patch(PathPatch(vpath, fc=mix(VALLEY["colour"], 0.30), ec=VALLEY["colour"], lw=1.1,
                           ls=(0, (4, 1.5, 1, 1.5)), zorder=4.2))

    # 6 — transhumance route (double-headed: June up, September back)
    pts = [proj(*p) for p in TRANSHUMANCE["route"]]
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color="white", lw=3.6, zorder=6.4, solid_capstyle="round")
    ax.plot(xs, ys, color=ICH_COLOUR, lw=1.6, ls=(0, (3, 1.4)), zorder=6.5)
    for a, b in [(pts[-2], pts[-1]), (pts[1], pts[0])]:
        ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>,head_length=0.5,head_width=0.25",
                    color=ICH_COLOUR, lw=1.4, shrinkA=0, shrinkB=0), zorder=6.6)

    # 7 — country and region labels
    for txt, lon, lat in COUNTRY_LABELS:
        x, y = proj(lon, lat)
        ax.text(x, y, txt, ha="center", va="center", size=9.5, color=C["muted"], weight="bold",
                alpha=0.85, zorder=4.5)
    t, lon, lat, tlon, tlat = LI_LABEL
    ax.annotate(t, xy=proj(tlon, tlat), xytext=proj(lon, lat), ha="center", va="center", size=8,
                color=C["muted"], weight="bold", zorder=4.5,
                arrowprops=dict(arrowstyle="-", color=C["muted"], lw=0.7, shrinkA=2, shrinkB=0))
    for txt, lon, lat in REGION_LABELS:
        x, y = proj(lon, lat)
        ax.text(x, y, txt, ha="center", va="center", size=8.2, color=C["muted"], style="italic",
                weight="bold", zorder=4.5, path_effects=[pe.withStroke(linewidth=2.2, foreground=C["other"])])

    x0, y0 = proj(LON_MIN, LAT_MIN)
    x1, y1 = proj(LON_MAX, LAT_MAX)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor(C["border_country"]); s.set_linewidth(0.8)

    # 8 — park names (leader line to the park when the label sits outside it)
    for key, pk in PARKS.items():
        txt, (lx, ly) = pk["label"]
        ec = PARK_KIND[pk["kind"]]["fc"]
        style = dict(ha="center", va="center", size=7.0, style="italic", weight="bold", color=C["text"],
                     linespacing=1.05, zorder=8,
                     path_effects=[pe.withStroke(linewidth=2.4, foreground="white")])
        if (lx, ly) == pk["at"] or abs(lx - pk["at"][0]) + abs(ly - pk["at"][1]) < 0.06:
            ax.text(*proj(lx, ly), txt, **style)
        else:
            ax.annotate(txt, xy=proj(*pk["at"]), xytext=proj(lx, ly), **style,
                        arrowprops=dict(arrowstyle="-", color=ec, lw=0.9, shrinkA=4, shrinkB=0))
            ax.plot(*proj(*pk["at"]), "o", ms=2.6, mfc="white", mec=ec, mew=1.0, zorder=8)

    # 9 — margin badges with arrows: quality labels, valley initiative, ICH
    def badge_arrow(pos, tip, colour, ls="-"):
        tx, ty = proj(*tip)
        bx, by = pos
        rad = 0.18 if bx > 0.5 or by > 1 else -0.18
        ax.annotate("", xy=(tx, ty), xycoords="data", xytext=(bx, by), textcoords="axes fraction",
                    arrowprops=dict(arrowstyle="-|>,head_length=0.55,head_width=0.28", color=colour,
                                    lw=1.5, ls=ls, shrinkA=30, shrinkB=1, connectionstyle=f"arc3,rad={rad}"),
                    annotation_clip=False, zorder=7)
        ax.plot(tx, ty, "o", ms=3.2, mfc="white", mec=colour, mew=1.2, zorder=8)

    for key, lb in list(LABELS.items()) + list(PARK_LABELS.items()):
        badge_arrow(lb["badge"], lb["tip"], lb["colour"])
        ax.add_artist(AnnotationBbox(text_badge(lb["label"], lb["sub"], lb["colour"]), lb["badge"],
                                     xycoords="axes fraction", frameon=True, annotation_clip=False,
                                     zorder=9, pad=0.45, bboxprops=BOX["label"](lb["colour"])))

    badge_arrow(VALLEY["badge"], VALLEY["tip"], VALLEY["colour"], ls=(0, (4, 1.5, 1, 1.5)))
    ax.add_artist(AnnotationBbox(text_badge(VALLEY["label"], VALLEY["sub"], VALLEY["colour"], 9.5),
                                 VALLEY["badge"], xycoords="axes fraction", frameon=True,
                                 annotation_clip=False, zorder=9, pad=0.45,
                                 bboxprops=BOX["valley"](VALLEY["colour"])))

    mid = TRANSHUMANCE["route"][1]
    badge_arrow(TRANSHUMANCE["badge"], mid, ICH_COLOUR, ls=(0, (4, 2)))
    for item in (TRANSHUMANCE, ALPINISM):
        ax.add_artist(AnnotationBbox(text_badge(item["label"], item["sub"], ICH_COLOUR), item["badge"],
                                     xycoords="axes fraction", frameon=True, annotation_clip=False,
                                     zorder=9, pad=0.45, bboxprops=BOX["ich"](ICH_COLOUR)))

    # 10 — scale bar and north arrow
    sb_len = 50 / 111.32
    sx, sy = proj(LON_MIN + 0.12, LAT_MIN + 0.10)
    ax.plot([sx, sx + sb_len], [sy, sy], color=C["text"], lw=2.2, solid_capstyle="butt", zorder=8)
    ax.plot([sx, sx + sb_len / 2], [sy, sy], color="white", lw=1.0, solid_capstyle="butt", zorder=9)
    for xx, t in [(sx, "0"), (sx + sb_len / 2, "25"), (sx + sb_len, "50 km")]:
        ax.text(xx, sy + 0.035, t, ha="center", va="bottom", size=7, color=C["text"], zorder=9)
    nx, ny = proj(LON_MAX - 0.18, LAT_MIN + 0.12)
    ax.annotate("N", xy=(nx, ny + 0.17), xytext=(nx, ny), ha="center", va="top", size=9, weight="bold",
                color=C["text"], arrowprops=dict(arrowstyle="-|>", color=C["text"], lw=1.4), zorder=9)

    # 11 — legend (symbols) and park key
    lab_h, val_h, ich_h = Patch(), Patch(label="_a"), Patch(label="_b")
    handles = [
        Line2D([], [], color=C["study"], lw=1.5),
        Patch(fc=mix("#7A3E6E", LABEL_MIX_IN), ec="white"),
        Patch(fc=NEUTRAL_IN, ec="white"),
        Line2D([], [], color=C["border_country"], lw=1.1, ls=(0, (5, 1.6))),
    ]
    labels = [
        "Rhaetian Alps (study area, approx.)",
        "Territory with a quality label (tint = label)",
        "Other entity territory",
        "National border",
    ]
    for kd in PARK_KIND.values():
        handles.append(Patch(fc=kd["fc"], alpha=kd["alpha"], ec=kd["fc"], hatch=kd["hatch"]))
        labels.append(kd["label"])
    handles += [ lab_h, val_h, ich_h,
                Line2D([], [], color=ICH_COLOUR, lw=1.6, ls=(0, (3, 1.4)))]
    labels += ["Quality label", "Valley initiative",
               "Intangible cultural heritage (UNESCO)", "Transhumance route"]
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.068), ncol=4, frameon=False,
               fontsize=7.4, handlelength=2.4, handleheight=1.1, columnspacing=1.5, labelcolor=C["text"],
               handler_map={lab_h: HandlerBox("label"),
                            val_h: HandlerBox("valley"), ich_h: HandlerBox("ich")})

    # 12 — title + source line
    fig.text(0.5, 0.975, TITLE, ha="center", va="top", size=13.0, weight="bold", color=C["text"])
    if not exact:
        src = SOURCE
    else:
        names = [PARKS[k]["name"] for k in PARKS if k in exact]
        if len(names) == len(PARKS):
            which = args.parks_source
        else:
            which = (f"{', '.join(names)} from {args.parks_source}; "
                     "others schematic (digitised by hand, accurate to a few km)")
        src = SOURCE_EXACT.format(src=which)
    fig.text(0.5, 0.012, src, ha="center", va="bottom", size=6.6, color=C["muted"], linespacing=1.4)

    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{args.out}.{ext}", dpi=300, facecolor=fig.get_facecolor())
    print("saved", args.out + ".{png,pdf,svg}")


if __name__ == "__main__":
    main()
