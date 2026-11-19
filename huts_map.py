"""
Rhaetian Alps — mountain huts of the hut-governing entities.

Companion to Figure 1 (rhaetian_map.py), on the same base: study area, SOIUSA
section limits, territories coloured by entity, ETRS89-LAEA projection. Adds one
marker per hut from data/huts.csv:

  * colour = entity; circle = alpine club, square = public authority;
  * size = beds (three classes);
  * filled = position from the hut workbook; hollow = estimated position, to verify;
  * a table of huts per territory and entity (territory found by point-in-polygon).

Usage
-----
    python huts_map.py <natural-earth-geojson-dir> [--huts data/huts.csv] [--out Rhaetian_alps_huts_map]

data/huts.csv is built from the hut workbook with tools/huts_from_workbook.py.
"""

import argparse
import csv
import os
import re

from matplotlib.backends.backend_pdf import PdfPages

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import matplotlib.patheffects as pe

import rhaetian_map as rm
from rhaetian_map import C, ENTITIES, proj

# ════════════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════════════

FRAME = (8.95, 11.85, 45.84, 47.45)          # lon0, lon1, lat0, lat1
TINT = 0.30                                  # lighter territory fills, so the huts stand out
BEDS = [(40, 5.5, "< 40 beds"), (80, 7.5, "40–80 beds"), (10 ** 6, 9.5, "> 80 beds")]
MS_UNKNOWN = 6.5
DUP_OFFSET_KM = 0.9                          # huts listed under two entities are drawn side by side

COUNTRY_LABELS = [("SWITZERLAND", 9.25, 46.95), ("AUSTRIA", 11.45, 47.38), ("ITALY", 11.55, 45.92),
                  ("GERMANY", 10.75, 47.42)]
LI_LABEL = ("LIECHTENSTEIN", 9.15, 47.33, 9.53, 47.14)

# Territories for the count table (key in rm.TERRITORIES), in display order
TABLE_TERRITORIES = ["LI", "VBG", "TIR", "GR", "SO", "BS", "BZ", "TN"]

SOURCE = ("Huts: author's database of association huts (November 2026); filled markers = position from the database, "
          "hollow = estimated position, to verify.\n"
          "Study area and section limits: SOIUSA (Marazzi 2005), polygons by M. Accorsi / ARPA Piemonte. Base map: Natural Earth 1:10m Cultural "
          "and Physical Vectors (public domain). Projection: ETRS89-LAEA Europe (EPSG:3035). Map: author's elaboration.")


def read_huts(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    huts = [r for r in rows if r["lat"] and r["lon"]]
    missing = [r for r in rows if not (r["lat"] and r["lon"])]
    return huts, missing


# Subsection numbers and English names (as on the SOIUSA map)
SUBSECTION_NAMES = {
    "II/A-15.I": (1, "Oberhalbstein Range"), "II/A-15.II": (2, "Albula Alps"), "II/A-15.III": (3, "Bernina Range"),
    "II/A-15.IV": (4, "Livigno Range"), "II/A-15.V": (5, "Sesvenna Range"),
    "II/A-15.VI": (6, "Silvretta, Samnaun, Verwall"), "II/A-15.VII": (7, "Plessur Range"),
    "II/A-15.VIII": (8, "Rätikon"), "II/A-16.I": (9, "Ötztal Alps"), "II/A-16.II": (10, "Stubai Alps"),
    "II/A-16.III": (11, "Sarntal Alps"), "II/C-28.I": (12, "Ortler Alps"), "II/C-28.II": (13, "Nonstal Alps"),
    "II/C-28.III": (14, "Adamello-Presanella Alps"), "II/C-28.IV": (15, "Brenta Dolomites"),
}
NUM_SIZE = 6.8               # hut number font size (pt)


def subsection_of(lon, lat, soiusa):
    """SOIUSA subsection code of a point, or None if outside the polygons."""
    x, y = proj(lon, lat)
    for f in soiusa or []:
        if rm.geom_to_path(f["geometry"]).contains_point((x, y)):
            m = re.match(r"(II/[A-C]-\d+\.[IVX]+)", f["properties"]["CODICE"].strip())
            return m.group(1) if m else None
    return None


def place_numbers(ax, items, fs=NUM_SIZE):
    """Greedy label placement: each number goes to the free side of its marker.
    items: list of (x, y, text, colour, marker_size_pt)."""
    fig = ax.figure
    fig.canvas.draw()
    to_pt = 72.0 / fig.dpi
    pos = [(ax.transData.transform((x, y)) * to_pt) for x, y, *_ in items]
    markers = [(p[0], p[1], it[4] / 2 + 0.5) for p, it in zip(pos, items)]
    boxes = []

    def overlap(b1, b2):
        return max(0, min(b1[2], b2[2]) - max(b1[0], b2[0])) * max(0, min(b1[3], b2[3]) - max(b1[1], b2[1]))

    for (px, py), (x, y, txt, col, ms) in zip(pos, items):
        w, h = len(txt) * fs * 0.52, fs * 0.8
        r = ms / 2 + 1.2
        best = None
        for dx, dy, ha, va in [(r, 0, "left", "center"), (-r, 0, "right", "center"), (0, r, "center", "bottom"),
                               (0, -r, "center", "top"), (r * .75, r * .75, "left", "bottom"),
                               (-r * .75, r * .75, "right", "bottom"), (r * .75, -r * .75, "left", "top"),
                               (-r * .75, -r * .75, "right", "top")]:
            bx0 = px + dx - (w if ha == "right" else w / 2 if ha == "center" else 0)
            by0 = py + dy - (h if va == "top" else h / 2 if va == "center" else 0)
            box = (bx0, by0, bx0 + w, by0 + h)
            cost = sum(overlap(box, b) for b in boxes)
            cost += sum(overlap(box, (mx - mr, my - mr, mx + mr, my + mr)) for mx, my, mr in markers) * 0.8
            if best is None or cost < best[0]:
                best = (cost, dx, dy, ha, va, box)
        _, dx, dy, ha, va, box = best
        boxes.append(box)
        ax.annotate(txt, (x, y), xytext=(dx, dy), textcoords="offset points", ha=ha, va=va, size=fs,
                    weight="bold", color=col, zorder=12,
                    path_effects=[pe.withStroke(linewidth=2.0, foreground="white")])


def write_annex(rows, missing, csv_path, pdf_path):
    """Hut list for the thesis annex: CSV and an A4 PDF table."""
    cols = ["no", "hut_id", "name", "name_de_fr", "entity", "subsection_code", "subsection", "altitude_m", "beds",
            "position"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
        for m in missing:
            w.writerow(dict(no="", hut_id=m["hut_id"], name=m["name"], name_de_fr=m["name_de_fr"],
                            entity=ENTITIES[m["entity"]]["label"], subsection_code="", subsection="",
                            altitude_m=m["altitude_m"], beds=m["beds"], position="not located"))
    head = ["No.", "Hut", "Entity", "SOIUSA subsection", "Alt. (m)", "Beds", "Position"]
    body = [[str(r["no"]), (r["name"] + (f" / {r['name_de_fr']}" if r["name_de_fr"] and r["name_de_fr"] != r["name"] else ""))[:58],
             r["entity"], r["subsection"] if r["subsection"] else "outside the study area", str(r["altitude_m"]),
             str(r["beds"]), r["position"]] for r in rows]
    body += [["–", (m["name"] or "")[:58], ENTITIES[m["entity"]]["label"], "", str(m["altitude_m"]), str(m["beds"]),
              "not located"] for m in missing]
    per = 44
    with PdfPages(pdf_path) as pdf:
        for i in range(0, len(body), per):
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.text(0.07, 0.955, "Mountain huts of the hut-governing entities in the Rhaetian Alps: key to the numbers "
                     "on the hut map", size=11, weight="bold", va="top")
            fig.text(0.07, 0.93, "Numbered by SOIUSA subsection, west to east. Position: database = from the hut "
                     "database; estimate = to be verified.", size=8.5, va="top", color=C["muted"])
            ax = fig.add_axes([0.07, 0.04, 0.86, 0.87]); ax.axis("off")
            t = ax.table(cellText=body[i:i + per], colLabels=head, loc="upper center", cellLoc="left",
                         colWidths=[0.05, 0.42, 0.07, 0.24, 0.07, 0.05, 0.10])
            t.auto_set_font_size(False); t.set_fontsize(7.6); t.scale(1, 1.18)
            for (r, c), cl in t.get_celld().items():
                cl.set_edgecolor("#D9D4CA"); cl.set_linewidth(0.4)
                if r == 0:
                    cl.get_text().set_weight("bold"); cl.set_facecolor("#F1EEE8")
            fig.text(0.93, 0.02, f"{i // per + 1}", size=8, ha="right")
            pdf.savefig(fig); plt.close(fig)


def beds_size(b):
    try:
        b = int(b)
    except ValueError:
        return MS_UNKNOWN
    for lim, ms, _ in BEDS:
        if b < lim:
            return ms
    return BEDS[-1][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ne_dir")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--huts", default=os.path.join(here, "data", "huts.csv"))
    ap.add_argument("--out", default="Rhaetian_alps_huts_map")
    args = ap.parse_args()

    rm.use_laea()
    rm.set_fonts()
    rm.TINT = TINT
    huts, missing = read_huts(args.huts)

    fig = plt.figure(figsize=(11.5, 13.2), facecolor=C["paper"])
    ax = fig.add_axes([0.025, 0.325, 0.95, 0.665])
    soiusa = rm.load_soiusa()
    rm.draw_base(ax, args.ne_dir, FRAME, territory_labels=True, section_labels="full", soiusa_groups=soiusa,
                 country_labels=COUNTRY_LABELS, li_label=LI_LABEL)

    # territory polygons for the count table
    adm0 = rm.load(os.path.join(args.ne_dir, "ne_10m_admin_0_countries.geojson"))
    adm1 = rm.load(os.path.join(args.ne_dir, "ne_10m_admin_1_states_provinces.geojson"))
    geoms = {}
    for key in TABLE_TERRITORIES:
        lvl, ctry, name = rm.TERRITORIES[key][:3]
        src = adm0 if lvl == "admin0" else adm1
        for f in src:
            pr = f["properties"]
            if (lvl == "admin0" and pr["ADMIN"] == name) or (lvl == "admin1" and pr["admin"] == ctry and pr["name"] == name):
                geoms[key] = rm.geom_to_path(f["geometry"])
    study_paths = rm.study_area_paths(soiusa)

    # number huts: by SOIUSA subsection (1-15), west to east within it; huts outside the polygons last
    for h in huts:
        h["_sub"] = subsection_of(float(h["lon"]), float(h["lat"]), soiusa)
        h["_x"] = proj(float(h["lon"]), float(h["lat"]))[0]
    huts.sort(key=lambda h: (SUBSECTION_NAMES[h["_sub"]][0] if h["_sub"] else 99, h["_x"]))
    for i, h in enumerate(huts, 1):
        h["_no"] = i
    num_items = []

    # position duplicates (same hut under two entities) side by side
    seen = {}
    for h in huts:
        k = (round(float(h["lat"]), 3), round(float(h["lon"]), 3))
        seen.setdefault(k, []).append(h)
    counts, inside = {}, {}
    for k, group in seen.items():
        x0, y0 = proj(float(group[0]["lon"]), float(group[0]["lat"]))
        n = len(group)
        for i, h in enumerate(group):
            dx = (i - (n - 1) / 2) * DUP_OFFSET_KM * rm.KM * 2
            x, y = x0 + dx, y0
            a = ENTITIES[h["entity"]]
            est = h["coord_source"].startswith("estimate")
            marker = "s" if a["kind"] == "authority" else "o"
            ms = beds_size(h["beds"])
            ax.plot(x, y, marker, ms=ms, mfc="white" if est else a["colour"], mec=a["ink"] if est else C["text"],
                    mew=1.6 if est else 0.7, zorder=10 + (0 if est else 1))
            num_items.append((x, y, str(h["_no"]), a["ink"], ms))
            terr = next((t for t, p in geoms.items() if p.contains_point((x0, y0))), "other")
            counts[(terr, h["entity"])] = counts.get((terr, h["entity"]), 0) + 1
            inside[h["entity"]] = inside.get(h["entity"], 0) + int(any(p.contains_point((x0, y0)) for p in study_paths))

    rm.draw_scale_north(ax, FRAME, km=25)
    rm.draw_locator(fig, ax, args.ne_dir, FRAME, width=0.17)
    place_numbers(ax, num_items)

    # legend: entities with counts, then symbols
    ents = [k for k in ENTITIES if any(h["entity"] == k for h in huts)]
    ent_h, ent_l = [], []
    for k in ents:
        a = ENTITIES[k]
        n = sum(h["entity"] == k for h in huts)
        nwb = sum(h["entity"] == k and not h["coord_source"].startswith("estimate") for h in huts)
        ent_h.append(Line2D([], [], ls="none", marker="s" if a["kind"] == "authority" else "o", ms=8,
                            mfc=a["colour"], mec=C["text"], mew=0.7))
        ent_l.append(f"{a['label']}  {a['name']}  {n} ({nwb})")
    fig.legend(ent_h, ent_l, loc="lower left", bbox_to_anchor=(0.02, 0.205), ncol=2, frameon=False,
               fontsize=8.8, handletextpad=0.5, columnspacing=1.2, labelcolor=C["text"],
               title="Huts by entity: total (of which position from database)", title_fontsize=9.5, alignment="left")

    sym_h = [Line2D([], [], ls="none", marker="o", ms=ms, mfc="#DADADA", mec=C["text"], mew=0.7) for _, ms, _ in BEDS]
    sym_l = [lab for _, _, lab in BEDS]
    sym_h += [Line2D([], [], ls="none", marker="o", ms=7.5, mfc="#DADADA", mec=C["text"], mew=0.7),
              Line2D([], [], ls="none", marker="o", ms=7.5, mfc="white", mec="#555555", mew=1.6),
              Line2D([], [], ls="none", marker="o", ms=7.5, mfc="#DADADA", mec=C["text"]),
              Line2D([], [], ls="none", marker="s", ms=7.5, mfc="#DADADA", mec=C["text"]),
              Line2D([], [], color=C["study"], lw=1.6),
              Line2D([], [], color=C["section"], lw=0.9, ls=(0, (6, 2, 1.2, 2))),
              Patch(fc=rm.tint(ENTITIES["DAV"]["colour"]), ec="white", hatch="////",
                    hatchcolor=rm.tint(ENTITIES["OEAV"]["colour"], 0.8), lw=0)]
    sym_l += ["Position from database", "Estimated position, to verify", "Alpine club", "Public authority",
              "Rhaetian Alps (study area)", "Limit between SOIUSA sections", "Shared territory (stripes)"]
    fig.legend(sym_h, sym_l, loc="lower right", bbox_to_anchor=(0.985, 0.205), ncol=2, frameon=False,
               fontsize=9, labelcolor=C["text"], title="Symbols", title_fontsize=9.5, alignment="left")

    # count table: huts per territory and entity
    names = {k: (rm.TERRITORIES[k][3] or "Liechtenstein") for k in TABLE_TERRITORIES}
    cols = [k for k in ents]
    cell = [[str(counts.get((t, e), "")) or "–" for e in cols] + [str(sum(counts.get((t, e), 0) for e in cols))]
            for t in TABLE_TERRITORIES]
    other = [str(counts.get(("other", e), "")) or "–" for e in cols]
    if any(v != "–" for v in other):
        cell.append(other + [str(sum(counts.get(("other", e), 0) for e in cols))])
    rows = [names[t] for t in TABLE_TERRITORIES] + (["Elsewhere"] if len(cell) > len(TABLE_TERRITORIES) else [])
    cell.append([str(sum(h["entity"] == e for h in huts)) for e in cols] + [str(len(huts))])
    rows.append("Total")
    tax = fig.add_axes([0.13, 0.058, 0.80, 0.135]); tax.axis("off")
    tab = tax.table(cellText=cell, rowLabels=rows,
                    colLabels=[ENTITIES[e]["label"] for e in cols] + ["All"], loc="upper left", cellLoc="center")
    tab.auto_set_font_size(False); tab.set_fontsize(8.5); tab.scale(1, 1.0)
    for (r, c), cl in tab.get_celld().items():
        cl.set_edgecolor("#D9D4CA"); cl.set_linewidth(0.5)
        if r == 0 and 0 <= c < len(cols):
            cl.set_facecolor(rm.tint(ENTITIES[cols[c]]["colour"], 0.45)); cl.get_text().set_weight("bold")
        if c == -1 or r == len(rows):
            cl.get_text().set_weight("bold")
    tax.set_title("Huts per territory and entity (territory found from the hut position)", fontsize=9.5, loc="left", color=C["text"], pad=4)

    note = ""
    if missing:
        note = (f"Not shown (no position yet): " + ", ".join(f"{m['hut_id']} {m['name']}" for m in missing) + ".\n")
    fig.text(0.5, 0.004, note + SOURCE + (("\n" + rm.DEM_CREDIT.strip()) if rm.RELIEF_USED else ""), ha="center", va="bottom", size=7.6, color=C["muted"], linespacing=1.35)

    for ext in ("png", "pdf", "svg"):
        fig.savefig(f"{args.out}.{ext}", dpi=300, facecolor=fig.get_facecolor())
    rows = [dict(no=h["_no"], hut_id=h["hut_id"], name=h["name"], name_de_fr=h["name_de_fr"],
                 entity=ENTITIES[h["entity"]]["label"], subsection_code=h["_sub"] or "",
                 subsection=f"{SUBSECTION_NAMES[h['_sub']][0]}. {SUBSECTION_NAMES[h['_sub']][1]}" if h["_sub"] else "",
                 altitude_m=h["altitude_m"], beds=h["beds"],
                 position="estimate" if h["coord_source"].startswith("estimate") else "database") for h in huts]
    write_annex(rows, missing, f"{args.out}_list.csv", f"{args.out}_list.pdf")
    print("saved", args.out + ".{png,pdf,svg}", "| huts drawn:", len(huts), "| missing:", len(missing),
          "| inside study area:", sum(inside.values()))


if __name__ == "__main__":
    main()
