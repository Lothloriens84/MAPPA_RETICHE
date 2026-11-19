"""
Rhaetian Alps — SOIUSA classification and the hut-governing territories.

Same design, frame and colours as Figure 1 (rhaetian_map.py), with Copernicus DEM relief:

  * relief (hillshade) under the territory colours of the hut-governing entities;
  * the SOIUSA polygons of the Rhaetian Alps (M. Accorsi, published by ARPA Piemonte):
    study-area outline, the three sections, the 15 subsections (outlined, numbered) and,
    faintly, the mountain groups inside them;
  * a table: share of each subsection's area lying in each territory (computed by overlay).

Usage
-----
    python alps_map.py <natural-earth-geojson-dir> [--soiusa data/soiusa_retiche.geojson] [--out ...]

The SOIUSA file is not in the repository; download it with the command in README.md.
"""

import argparse
import os
import re

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path
import matplotlib.patheffects as pe

import rhaetian_map as rm
from rhaetian_map import C, ENTITIES, TERRITORIES, proj

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

FRAME = (8.85, 12.10, 45.72, 47.55)

SECTION_COLOUR = {"II/A-15": "#2F3F86", "II/A-16": "#86325A", "II/C-28": "#246332"}
SECTION_NAMES = {"II/A-15": ("Western Rhaetian Alps", 9.30, 46.98),
                 "II/A-16": ("Eastern Rhaetian Alps", 11.62, 47.22),
                 "II/C-28": ("Southern Rhaetian Alps", 11.30, 46.00)}

# subsection code -> (number, English name, label offset in points)
SUBSECTIONS = {
    "II/A-15.I":    (1,  "Oberhalbstein Range", (0, -13)),
    "II/A-15.II":   (2,  "Albula Alps", (0, -13)),
    "II/A-15.III":  (3,  "Bernina Range", (0, -13)),
    "II/A-15.IV":   (4,  "Livigno Range", (0, -13)),
    "II/A-15.V":    (5,  "Sesvenna Range", (0, -13)),
    "II/A-15.VI":   (6,  "Silvretta, Samnaun, Verwall", (0, 13)),
    "II/A-15.VII":  (7,  "Plessur Range", (0, -13)),
    "II/A-15.VIII": (8,  "Rätikon", (0, 13)),
    "II/A-16.I":    (9,  "Ötztal Alps", (0, -13)),
    "II/A-16.II":   (10, "Stubai Alps", (0, 13)),
    "II/A-16.III":  (11, "Sarntal Alps", (0, -13)),
    "II/C-28.I":    (12, "Ortler Alps", (0, -13)),
    "II/C-28.II":   (13, "Nonstal Alps", (0, -13)),
    "II/C-28.III":  (14, "Adamello-Presanella Alps", (-13, 0)),
    "II/C-28.IV":   (15, "Brenta Dolomites", (13, 0)),
}

# Hand-placed markers where the automatic point collides with other labels (lon, lat)
LABEL_AT = {"II/A-15.III": (9.93, 46.36), "II/C-28.III": (10.58, 46.17), "II/C-28.IV": (10.90, 46.20)}

# Table columns: territory key -> entities (as on the map)
COLUMNS = [("GR", ["SAC"]), ("LI", ["LAV"]), ("VBG", ["DAV", "OEAV"]), ("TIR", ["DAV", "OEAV"]),
           ("SO", ["CAI"]), ("BS", ["CAI"]), ("BZ", ["CAI", "AVS", "APS"]), ("TN", ["SAT"])]
SAMPLE_KM = 1.0          # grid spacing for the area shares

COUNTRY_LABELS = [("SWITZERLAND", 9.05, 46.25), ("AUSTRIA", 11.75, 47.42), ("GERMANY", 10.20, 47.50),
                  ("ITALY", 11.75, 45.80)]
LI_LABEL = ("LIECHTENSTEIN", 9.15, 47.38, 9.53, 47.14)

SOURCE = ("SOIUSA sections, subsections and groups of the Rhaetian Alps (Marazzi 2005), polygons digitised by "
          "M. Accorsi, published by ARPA Piemonte (webgis.arpa.piemonte.it). "
          "Shares: area of each subsection by territory, computed on a 1 km grid.\n"
          "Base map: Natural Earth 1:10m Cultural and Physical Vectors (public domain). Projection: ETRS89-LAEA Europe "
          "(EPSG:3035). Map: author's elaboration.")


def sub_code(codice):
    m = re.match(r"(II/[A-C]-\d+\.[IVX]+)", codice.strip())
    return m.group(1) if m else None


def label_point(paths):
    """A point well inside the largest polygon (grid search: farthest from its outline)."""
    p = max(paths, key=lambda q: np.ptp(q.vertices[:, 0]) * np.ptp(q.vertices[:, 1]))
    (x0, y0), (x1, y1) = p.get_extents().get_points()
    xs, ys = np.meshgrid(np.linspace(x0, x1, 40), np.linspace(y0, y1, 40))
    pts = np.c_[xs.ravel(), ys.ravel()]
    inside = pts[p.contains_points(pts)]
    v = p.vertices
    d = np.min(np.hypot(inside[:, None, 0] - v[None, :, 0], inside[:, None, 1] - v[None, :, 1]), axis=1)
    return inside[np.argmax(d)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ne_dir")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--soiusa", default=os.path.join(here, "data", "soiusa_retiche.geojson"))
    ap.add_argument("--out", default="Rhaetian_alps_soiusa_map")
    args = ap.parse_args()

    rm.use_laea()
    rm.set_fonts()
    groups = rm.load(args.soiusa)
    rings = [r for f in groups for poly in rm.rings_of(f["geometry"]) for r in poly[:1]]

    fig = plt.figure(figsize=(16.54, 11.69), facecolor=C["paper"])       # A3 landscape
    ax = fig.add_axes([0.012, 0.085, 0.70, 0.905])
    ax.set_anchor("W")
    rm.draw_base(ax, args.ne_dir, FRAME, territory_labels=True, section_labels=None, relief=True,
                 country_labels=COUNTRY_LABELS, li_label=LI_LABEL, study_polys=rings, section_lines=False)

    # groups (faint), subsections (outlined), sections (bold)
    by_sub, by_sec = {}, {}
    for f in groups:
        code = sub_code(f["properties"]["CODICE"])
        by_sub.setdefault(code, []).append(f["geometry"])
        by_sec.setdefault(code.split(".")[0], []).append(f["geometry"])
        col = SECTION_COLOUR[code.split(".")[0]]
        ax.add_patch(PathPatch(rm.geom_to_path(f["geometry"]), fc="none", ec=col, lw=0.4, alpha=0.55,
                               ls=(0, (2, 1.5)), zorder=4.95))
    for code, geoms in by_sub.items():
        ax.add_patch(PathPatch(rm.dissolved_edges(geoms), fc="none", ec=SECTION_COLOUR[code.split(".")[0]],
                               lw=1.3, zorder=5.0))
    for code, geoms in by_sec.items():
        ax.add_patch(PathPatch(rm.dissolved_edges(geoms), fc="none", ec=SECTION_COLOUR[code], lw=2.6,
                               alpha=0.85, zorder=5.05))

    for code, (name, lon, lat) in SECTION_NAMES.items():
        ax.text(*proj(lon, lat), f"{name.upper()}\n{code}", ha="center", va="center", size=10.5,
                weight="bold", color=SECTION_COLOUR[code], zorder=6.5, linespacing=1.15,
                path_effects=[pe.withStroke(linewidth=3, foreground="white")])

    sub_paths = {code: [rm.geom_to_path(g) for g in geoms] for code, geoms in by_sub.items()}
    for code, (n, en, off) in SUBSECTIONS.items():
        if code not in sub_paths:
            continue
        col = SECTION_COLOUR[code.split(".")[0]]
        x, y = proj(*LABEL_AT[code]) if code in LABEL_AT else label_point(sub_paths[code])
        ax.plot(x, y, "o", ms=17, mfc="white", mec=col, mew=2.0, zorder=9)
        ax.text(x, y, str(n), ha="center", va="center", size=10, weight="bold", color=col, zorder=9.1)
        ha = "center" if off[0] == 0 else ("right" if off[0] < 0 else "left")
        va = "center" if off[1] == 0 else ("top" if off[1] < 0 else "bottom")
        ax.annotate(en, (x, y), xytext=off, textcoords="offset points", ha=ha, va=va, size=8.8,
                    style="italic", color=col, zorder=9.1,
                    path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])

    rm.draw_scale_north(ax, FRAME, km=25)
    rm.draw_locator(fig, ax, args.ne_dir, FRAME, width=0.16)

    # area shares: subsection x territory, on a regular grid
    adm0 = rm.load(os.path.join(args.ne_dir, "ne_10m_admin_0_countries.geojson"))
    adm1 = rm.load(os.path.join(args.ne_dir, "ne_10m_admin_1_states_provinces.geojson"))
    terr = {}
    for key, _ in COLUMNS:
        lvl, ctry, name = TERRITORIES[key][:3]
        for f in (adm0 if lvl == "admin0" else adm1):
            pr = f["properties"]
            if (lvl == "admin0" and pr["ADMIN"] == name) or (lvl == "admin1" and pr["admin"] == ctry and pr["name"] == name):
                terr[key] = rm.geom_to_path(f["geometry"])
    shares = {}
    for code, paths in sub_paths.items():
        allv = np.vstack([p.vertices for p in paths])
        (x0, y0), (x1, y1) = allv.min(axis=0), allv.max(axis=0)
        xs, ys = np.meshgrid(np.arange(x0, x1, SAMPLE_KM * rm.KM), np.arange(y0, y1, SAMPLE_KM * rm.KM))
        pts = np.c_[xs.ravel(), ys.ravel()]
        inside = np.zeros(len(pts), bool)
        for p in paths:
            inside |= p.contains_points(pts)
        pts = pts[inside]
        shares[code] = {k: 100.0 * terr[k].contains_points(pts).sum() / max(len(pts), 1) for k, _ in COLUMNS}
        shares[code]["_other"] = 100.0 - sum(shares[code].values())
        shares[code]["_km2"] = len(pts) * SAMPLE_KM ** 2

    def fmt(v):
        return "" if v < 0.5 else ("<1" if v < 1 else f"{v:.0f}")

    ax.apply_aspect()
    lx = ax.get_position().x1 + 0.012
    order = sorted(SUBSECTIONS, key=lambda c: SUBSECTIONS[c][0])
    rows = [f"{SUBSECTIONS[c][0]}  {SUBSECTIONS[c][1]}" for c in order]
    cols = [TERRITORIES[k][3] or "Liechtenstein" for k, _ in COLUMNS] + ["Elsewhere", "Area (km²)"]
    cells = [[fmt(shares[c][k]) for k, _ in COLUMNS] + [fmt(shares[c]["_other"]), f"{shares[c]['_km2']:,.0f}"]
             for c in order]
    tax = fig.add_axes([lx + 0.075, 0.40, 0.99 - lx - 0.08, 0.46]); tax.axis("off")
    tab = tax.table(cellText=cells, rowLabels=rows, colLabels=cols, loc="upper left", cellLoc="center")
    tab.auto_set_font_size(False); tab.set_fontsize(8.6)
    tab.scale(1, 1.55)
    for (r, c), cl in tab.get_celld().items():
        cl.set_edgecolor("#D9D4CA"); cl.set_linewidth(0.5)
        if r == 0 and c >= 0:
            if c < len(COLUMNS):
                cl.set_facecolor(rm.tint(ENTITIES[COLUMNS[c][1][0]]["colour"], 0.5))
            cl.get_text().set_rotation(90); cl.get_text().set_va("bottom"); cl.set_height(cl.get_height() * 3.6)
            cl.get_text().set_fontsize(8.6)
        elif r > 0:
            col = SECTION_COLOUR[order[r - 1].split(".")[0]]
            cl.get_text().set_color(col)
            if c == -1:
                cl._loc = "left"
            elif c < len(COLUMNS):
                v = shares[order[r - 1]][COLUMNS[c][0]]
                if v >= 0.5:
                    cl.set_facecolor(rm.tint(ENTITIES[COLUMNS[c][1][0]]["colour"], 0.15 + 0.5 * v / 100))
    fig.text(lx, 0.975, "Share of each subsection's area by territory (%)", fontsize=11, ha="left", va="top",
             color=C["text"], weight="bold")

    # legend: symbols and territory colours
    key_h = [Patch(fc=rm.tint(a["colour"]), ec=a["ink"], lw=1.0) for a in ENTITIES.values()]
    key_l = [f"{a['label']}  {a['name']}" for a in ENTITIES.values()]
    shared = [Patch(label="_a"), Patch(label="_b")]
    hmap = {shared[0]: rm.HandlerStripes([rm.tint(ENTITIES[e]["colour"]) for e in ["DAV", "OEAV"]]),
            shared[1]: rm.HandlerStripes([rm.tint(ENTITIES[e]["colour"]) for e in ["CAI", "AVS", "APS"]])}
    sym_h = [Line2D([], [], color=C["study"], lw=1.8),
             Line2D([], [], color="#555555", lw=2.6, alpha=0.85),
             Line2D([], [], color="#555555", lw=1.3),
             Line2D([], [], color="#555555", lw=0.5, ls=(0, (2, 1.5))),
             Line2D([], [], ls="none", marker="o", ms=13, mfc="white", mec="#555555", mew=2.0),
             *shared]
    sym_l = ["Rhaetian Alps (study area)", "Section (colour: Western / Eastern / Southern)", "Subsection",
             "Mountain group", "Subsection number (as in the table)",
             "Vorarlberg and Tyrol: DAV + ÖAV", "South Tyrol: CAI + AVS + APS"]
    fig.legend(sym_h + key_h, sym_l + key_l, loc="lower left", bbox_to_anchor=(lx, 0.085), ncol=1,
               frameon=False, fontsize=9.5, handlelength=2.4, handleheight=1.2, labelspacing=0.5,
               labelcolor=C["text"], handler_map=hmap, title="Map symbols and territory colours",
               title_fontsize=11, alignment="left")

    fig.text(0.012, 0.012, SOURCE + "\n" + rm.DEM_CREDIT.strip(), ha="left", va="bottom", size=9,
             color=C["muted"], linespacing=1.4)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{args.out}.{ext}", dpi=300, facecolor=fig.get_facecolor())
    print("saved", args.out + ".{png,pdf,svg}")
    for c in order:
        print(SUBSECTIONS[c][0], SUBSECTIONS[c][1], {k: round(v) for k, v in shares[c].items() if v >= 0.5})


if __name__ == "__main__":
    main()
