"""
Rhaetian Alps — SOIUSA classification and the hut-governing territories.

Same design, frame and colours as Figure 1 (rhaetian_map.py), with Copernicus DEM relief:

  * relief (hillshade) under the territory colours of the hut-governing entities;
  * the three SOIUSA sections (limits and names) and their 15 subsections, each marked
    by a numbered symbol at its main massif (subsection boundaries are not drawn);
  * a table: which territory (and hence which entity) each subsection falls into.

Usage
-----
    python alps_map.py <natural-earth-geojson-dir> [--out Rhaetian_alps_soiusa_map]
"""

import argparse

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import matplotlib.patheffects as pe

import rhaetian_map as rm
from rhaetian_map import C, ENTITIES, TERRITORIES, proj

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

FRAME = (8.85, 12.10, 45.72, 47.55)

SECTION_COLOUR = {"II/A-15": "#3B4B8C", "II/A-16": "#8C3B5E", "II/C-28": "#2E6B3A"}

# (number, code, name in English, name in Italian, marker lon/lat, label offset in points, territories)
# Territories in which each subsection lies (from Marazzi 2005; to be checked against the
# subsection sheets of the SOIUSA workbook).
SUBSECTIONS = [
    (1,  "II/A-15.I",    "Oberhalbstein Range",          "Alpi del Platta",              9.55, 46.47, (0, -14), ["GR", "SO"]),
    (2,  "II/A-15.II",   "Albula Alps",                  "Alpi dell'Albula",             9.78, 46.63, (0, -14), ["GR"]),
    (3,  "II/A-15.III",  "Bernina Range",                "Alpi del Bernina",             9.90, 46.38, (0, -14), ["GR", "SO"]),
    (4,  "II/A-15.IV",   "Livigno Range",                "Alpi di Livigno",             10.12, 46.50, (0, -14), ["GR", "SO"]),
    (5,  "II/A-15.V",    "Sesvenna Range",               "Alpi della Val Müstair",      10.38, 46.70, (0, -14), ["GR", "BZ", "TIR"]),
    (6,  "II/A-15.VI",   "Silvretta, Samnaun, Verwall",  "Alpi del Silvretta, Samnaun e Verwall", 10.15, 46.93, (0, 14), ["GR", "VBG", "TIR"]),
    (7,  "II/A-15.VII",  "Plessur Range",                "Alpi del Plessur",             9.65, 46.80, (0, -14), ["GR"]),
    (8,  "II/A-15.VIII", "Rätikon",                      "Catena del Rätikon",           9.75, 47.06, (0, 14), ["GR", "VBG", "LI"]),
    (9,  "II/A-16.I",    "Ötztal Alps",                  "Alpi Venoste",                10.85, 46.86, (0, -14), ["TIR", "BZ"]),
    (10, "II/A-16.II",   "Stubai Alps",                  "Alpi dello Stubai",           11.18, 47.07, (0, 14), ["TIR", "BZ"]),
    (11, "II/A-16.III",  "Sarntal Alps",                 "Alpi Sarentine",              11.35, 46.72, (0, -14), ["BZ"]),
    (12, "II/C-28.I",    "Ortler Alps",                  "Alpi dell'Ortles",            10.60, 46.45, (0, -14), ["BZ", "SO", "TN", "BS"]),
    (13, "II/C-28.II",   "Nonstal Alps",                 "Alpi della Val di Non",       11.05, 46.45, (0, -14), ["TN", "BZ"]),
    (14, "II/C-28.III",  "Adamello-Presanella Alps",     "Alpi dell'Adamello e della Presanella", 10.58, 46.17, (-13, 0), ["TN", "BS"]),
    (15, "II/C-28.IV",   "Brenta Dolomites",             "Dolomiti di Brenta",          10.88, 46.17, (13, 0), ["TN"]),
]

# Table columns: territory key -> entities (as on the map)
COLUMNS = [("GR", ["SAC"]), ("LI", ["LAV"]), ("VBG", ["DAV", "OEAV"]), ("TIR", ["DAV", "OEAV"]),
           ("SO", ["CAI"]), ("BS", ["CAI"]), ("BZ", ["CAI", "AVS", "APS"]), ("TN", ["SAT"])]

COUNTRY_LABELS = [("SWITZERLAND", 9.05, 46.25), ("AUSTRIA", 11.75, 47.42), ("GERMANY", 10.20, 47.50),
                  ("ITALY", 11.75, 45.80)]
LI_LABEL = ("LIECHTENSTEIN", 9.15, 47.38, 9.53, 47.14)

SOURCE = ("Classification: SOIUSA sections and subsections (Marazzi 2005); outline and section limits approximate; "
          "subsections marked at their main massif, boundaries not drawn.\n"
          "Base map: Natural Earth 1:10m Cultural and Physical Vectors (public domain). Projection: ETRS89-LAEA Europe "
          "(EPSG:3035). Map: author's elaboration.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ne_dir")
    ap.add_argument("--out", default="Rhaetian_alps_soiusa_map")
    args = ap.parse_args()

    rm.use_laea()
    rm.set_fonts()
    fig = plt.figure(figsize=(16.54, 11.69), facecolor=C["paper"])       # A3 landscape
    ax = fig.add_axes([0.012, 0.085, 0.70, 0.905])
    ax.set_anchor("W")
    rm.draw_base(ax, args.ne_dir, FRAME, territory_labels=True, section_labels=None, relief=True,
                 country_labels=COUNTRY_LABELS, li_label=LI_LABEL)

    # section names, coloured
    for code, name, lon, lat in rm.SECTIONS:
        lon, lat = {"II/A-15": (9.35, 46.98), "II/A-16": (11.55, 47.22), "II/C-28": (11.25, 46.02)}[code]
        ax.text(*proj(lon, lat), f"{name.upper()}\n{code}", ha="center", va="center", size=10.5,
                weight="bold", color=SECTION_COLOUR[code], zorder=6.5, linespacing=1.15,
                path_effects=[pe.withStroke(linewidth=3, foreground="white")])

    # subsections: numbered markers
    for n, code, en, it, lon, lat, off, _ in SUBSECTIONS:
        col = SECTION_COLOUR[code.split(".")[0]]
        x, y = proj(lon, lat)
        ax.plot(x, y, "o", ms=17, mfc="white", mec=col, mew=2.0, zorder=9)
        ax.text(x, y, str(n), ha="center", va="center", size=10, weight="bold", color=col, zorder=9.1)
        ha = "center" if off[0] == 0 else ("right" if off[0] < 0 else "left")
        va = "center" if off[1] == 0 else ("top" if off[1] < 0 else "bottom")
        ax.annotate(en, (x, y), xytext=off, textcoords="offset points", ha=ha, va=va, size=8.8, style="italic", color=col, zorder=9.1,
                    path_effects=[pe.withStroke(linewidth=2.6, foreground="white")])

    rm.draw_scale_north(ax, FRAME, km=25)
    rm.draw_locator(fig, ax, args.ne_dir, FRAME, width=0.16)

    # right column: subsection × territory table
    ax.apply_aspect()
    lx = ax.get_position().x1 + 0.012
    tax = fig.add_axes([lx + 0.075, 0.40, 0.99 - lx - 0.08, 0.46]); tax.axis("off")
    cols = [TERRITORIES[k][3] or "Liechtenstein" for k, _ in COLUMNS]
    rows = [f"{n}  {en}" for n, _, en, *_ in SUBSECTIONS]
    cells = [["●" if k in terrs else "" for k, _ in COLUMNS] for *_, terrs in SUBSECTIONS]
    tab = tax.table(cellText=cells, rowLabels=rows, colLabels=cols, loc="upper left", cellLoc="center")
    tab.auto_set_font_size(False); tab.set_fontsize(9)
    tab.scale(1, 1.55)
    for (r, c), cl in tab.get_celld().items():
        cl.set_edgecolor("#D9D4CA"); cl.set_linewidth(0.5)
        if r == 0 and c >= 0:
            ents = COLUMNS[c][1]
            cl.set_facecolor(rm.tint(ENTITIES[ents[0]]["colour"], 0.5))
            cl.get_text().set_rotation(90); cl.get_text().set_va("bottom"); cl.set_height(cl.get_height() * 3.6)
            cl.get_text().set_fontsize(8.8)
        elif c == -1 and r > 0:
            code = SUBSECTIONS[r - 1][1].split(".")[0]
            cl.get_text().set_color(SECTION_COLOUR[code]); cl.get_text().set_ha("left"); cl._loc = "left"
        elif r > 0:
            code = SUBSECTIONS[r - 1][1].split(".")[0]
            cl.get_text().set_color(SECTION_COLOUR[code])
    fig.text(lx, 0.975, "SOIUSA subsections and the territories they lie in", fontsize=11, ha="left", va="top",
             color=C["text"], weight="bold")

    # entity key under the table
    key_h = [Patch(fc=rm.tint(a["colour"]), ec=a["ink"], lw=1.0) for a in ENTITIES.values()]
    key_l = [f"{a['label']}  {a['name']}" for a in ENTITIES.values()]
    shared = [Patch(label="_a"), Patch(label="_b")]
    hmap = {shared[0]: rm.HandlerStripes([rm.tint(ENTITIES[e]["colour"]) for e in ["DAV", "OEAV"]]),
            shared[1]: rm.HandlerStripes([rm.tint(ENTITIES[e]["colour"]) for e in ["CAI", "AVS", "APS"]])}
    sym_h = [Line2D([], [], color=C["study"], lw=1.6),
             Line2D([], [], color=C["section"], lw=0.9, ls=(0, (6, 2, 1.2, 2))),
             Line2D([], [], ls="none", marker="o", ms=13, mfc="white", mec="#555555", mew=2.0),
             *shared]
    sym_l = ["Rhaetian Alps (study area)", "Limit between SOIUSA sections", "Subsection (number as in the table)",
             "Vorarlberg and Tyrol: DAV + ÖAV", "South Tyrol: CAI + AVS + APS"]
    fig.legend(sym_h + key_h, sym_l + key_l, loc="lower left", bbox_to_anchor=(lx, 0.085), ncol=1,
               frameon=False, fontsize=9.5, handlelength=2.4, handleheight=1.2, labelspacing=0.55,
               labelcolor=C["text"], handler_map=hmap, title="Map symbols and territory colours",
               title_fontsize=11, alignment="left")

    fig.text(0.012, 0.012, SOURCE + "\n" + rm.DEM_CREDIT.strip(), ha="left", va="bottom", size=9,
             color=C["muted"], linespacing=1.4)
    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{args.out}.{ext}", dpi=300, facecolor=fig.get_facecolor())
    print("saved", args.out + ".{png,pdf,svg}")


if __name__ == "__main__":
    main()
