"""
Extract the study-area parks from Protected Planet File Geodatabase downloads
into one local GeoJSON for heritage_map.py --parks.

    python tools/wdpa_to_parks.py <download.gdb> [<more.gdb> ...] --out output/parks_wdpa.geojson

Each .gdb is read with the pure-Python reader in tools/fgdb.py (no GDAL needed).
Parks are matched to the keys in heritage_map.PARKS by name; features already in
--out are kept, so parks can be added one download at a time.

The output file is WDPA data: the licence forbids redistribution, so it is
git-ignored and must not be committed or deposited.
"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fgdb

MATCH = [  # (key, substrings in NAME / NAME_ENG, lower case); first hit wins
    ("PNAB", ["adamello brenta", "adamello-brenta"]),
    ("ADA",  ["adamello"]),
    ("STE",  ["stelvio", "stilfser"]),
    ("SNP",  ["swiss national park", "schweizerischer nationalpark", "parc naziunal"]),
    ("TEX",  ["tessa", "texel"]),
    ("OTZ",  ["ötztal", "oetztal"]),
    ("KAU",  ["kaunergrat"]),
    ("BVM",  ["müstair", "muestair", "mustair"]),
    ("ELA",  ["ela"]),
]


def key_for(row):
    name = " ".join(str(row.get(k) or "") for k in ("NAME", "NAME_ENG", "DESIG_ENG")).lower()
    for key, subs in MATCH:
        if any(s in name.split() if s == "ela" else s in name for s in subs):
            return key
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gdb", nargs="+")
    ap.add_argument("--out", default="output/parks_wdpa.geojson")
    a = ap.parse_args()
    feats = {}
    if os.path.exists(a.out):
        for f in json.load(open(a.out, encoding="utf-8"))["features"]:
            feats[f["properties"]["key"]] = f
    for gdb in a.gdb:
        for tbl in sorted(glob.glob(os.path.join(gdb, "a*.gdbtable"))):
            try:
                rows = fgdb.read_table(tbl)
            except Exception:
                continue
            for r in rows:
                if "SITE_ID" not in r:
                    continue
                if not r.get("SHAPE"):
                    print(f"{r['SITE_ID']:>8}  {r.get('NAME')}  ({r.get('DESIG_ENG')}): point only, no boundary, skipped")
                    continue
                k = key_for(r)
                print(f"{r['SITE_ID']:>8}  {r.get('NAME')}  ->  {k or 'not in PARKS, skipped'}")
                if k:
                    feats[k] = {"type": "Feature",
                                "properties": {"key": k, "SITE_ID": r["SITE_ID"], "NAME": r.get("NAME")},
                                "geometry": {"type": "Polygon" if len(r["SHAPE"]) == 1 else "MultiPolygon",
                                             "coordinates": [[list(p) for p in rg] for rg in r["SHAPE"]]
                                             if len(r["SHAPE"]) == 1 else
                                             [[[list(p) for p in rg]] for rg in r["SHAPE"]]}}
    json.dump({"type": "FeatureCollection", "features": list(feats.values())},
              open(a.out, "w", encoding="utf-8"))
    print(f"{len(feats)} park(s) in {a.out}: {', '.join(sorted(feats))}")


if __name__ == "__main__":
    main()
