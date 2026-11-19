"""
Build data/huts.csv from the hut workbook (sheet "Association Huts").

Only public, map-relevant fields are kept: no keepers' names, e-mails or phone numbers.
Coordinates: decimal or DMS strings from the workbook are parsed ("workbook");
missing ones can be supplied in ESTIMATES below ("estimate", to verify).

    python tools/huts_from_workbook.py path/to/Raetian_Alps_COMBINED.xlsx --out data/huts.csv
"""
import argparse, csv, re
import openpyxl

ENTITY = {"SAT": "SAT", "AVS": "AVS", "CAI": "CAI", "DAV": "DAV", "LBV": "LAV", "LAV": "LAV",
          "SAC": "SAC", "APB": "APS", "OeAV": "OEAV", "OEAV": "OEAV"}

# Approximate positions (estimated with AI assistance from general knowledge, ±1-2 km) for huts without coordinates
# in the workbook. Every one must be checked against an official source before publication.
ESTIMATES = {
    "SAT-006": (46.346, 11.000), "SAT-007": (46.444, 10.771), "SAT-008": (46.266, 10.622),
    "SAT-009": (45.917, 10.946), "SAT-010": (46.167, 10.892), "SAT-011": (46.128, 10.860),
    "SAT-012": (46.205, 10.660), "SAT-013": (46.081, 10.578), "SAT-014": (46.400, 10.630),
    "SAT-015": (46.143, 10.818),
    "AVS-002": (46.770, 10.700), "AVS-005": (46.696, 11.268),
    "CAI-001": (46.128, 10.458), "CAI-002": (46.150, 10.488), "CAI-003": (46.137, 10.438),
    "CAI-004": (46.188, 10.425), "CAI-005": (46.414, 10.591), "CAI-006": (46.498, 10.599),
    "CAI-007": (46.165, 10.567), "CAI-008": (46.380, 9.915), "CAI-009": (46.338, 9.982),
    "CAI-012": (46.471, 10.564), "CAI-013": (46.434, 10.604), "CAI-016": (46.289, 9.753),
    "CAI-017": (46.362, 10.534), "CAI-018": (46.292, 9.648), "CAI-019": (46.341, 9.804),
    "CAI-020": (46.295, 10.545), "CAI-021": (46.262, 9.604),
    "DAV-001": (46.880, 10.103), "DAV-002": (46.913, 10.267), "DAV-003": (46.883, 10.164),
    "DAV-004": (46.901, 10.070), "DAV-005": (47.086, 10.089), "DAV-006": (47.090, 9.846),
    "DAV-007": (47.050, 9.764), "DAV-008": (47.059, 9.784),
    "LBV-002": (47.104, 9.597),
    "SAC-001": (46.418, 9.937), "SAC-002": (46.624, 9.862), "SAC-003": (46.403, 9.887),
    "SAC-004": (46.613, 9.916), "SAC-005": (46.826, 10.139), "SAC-006": (46.518, 9.121),
    "SAC-007": (46.730, 9.968), "SAC-008": (46.806, 10.068), "SAC-010": (46.913, 10.267),
    "SAC-011": (46.511, 9.913), "SAC-012": (46.764, 10.312),
    "APB-005": (46.521, 10.619), "APB-006": (46.992, 11.158), "APB-008": (46.948, 11.184),
    "APB-009": (46.965, 11.216), "APB-010": (46.958, 11.219), "APB-011": (46.495, 10.649),
    "APB-012": (46.517, 10.555), "APB-013": (46.498, 10.599),
    "OeAV-009": (46.992, 11.158),
}

def dms(v):
    """Parse decimal or DMS text ('46° 20' 40,7''', '46°19′48.32″N') to decimal degrees."""
    if v is None or str(v).strip() == "":
        return None
    s = str(v).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        pass
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
    if not nums:
        return None
    d = nums[0] + (nums[1] / 60 if len(nums) > 1 else 0) + (nums[2] / 3600 if len(nums) > 2 else 0)
    return -d if re.search(r"[SW]\s*$", s) else d

def num(v):
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return ""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx"); ap.add_argument("--out", default="data/huts.csv")
    a = ap.parse_args()
    wb = openpyxl.load_workbook(a.xlsx, data_only=True, read_only=True)
    rows = list(wb["Association Huts"].iter_rows(values_only=True))
    hdr = rows[1]; ix = {h: i for i, h in enumerate(hdr)}
    out, missing = [], []
    for r in rows[2:]:
        if not r or not r[0]:
            continue
        g = lambda k: r[ix[k]] if k in ix else None
        hid = str(g("Hut ID")).strip()
        lat, lon, src = dms(g("Latitude")), dms(g("Longitude")), "workbook"
        if lat is not None and 5 < lat < 10 and lon and 9 < lon < 13:   # '6°' typed for '46°'
            lat, src = lat + 40, "workbook (latitude 6°→46° corrected)"
        if lat is None or lon is None:
            if hid in ESTIMATES:
                (lat, lon), src = ESTIMATES[hid], "estimate"
            else:
                missing.append(hid); src = "missing"
        name = (g("Name (Italian)") or g("Name (German/French)") or "").strip()
        out.append(dict(hut_id=hid, name=name, name_de_fr=(g("Name (German/French)") or "").strip(),
                        entity=ENTITY.get(str(g("Assoc.")).strip(), str(g("Assoc."))),
                        section=g("Section / Sub-association") or "", country=g("Country") or "",
                        region=g("Region / Province / Canton") or "", mountain_group=g("Mountain Group") or "",
                        altitude_m=num(g("Altitude (m)")), beds=num(g("Beds (total)")),
                        provisioning=g("Provisioning System") or "", access=g("Accessibility") or "",
                        status=g("Status") or "", raetian_scope=g("Raetian Alps Scope") or "",
                        lat=round(lat, 6) if lat is not None else "", lon=round(lon, 6) if lon is not None else "",
                        coord_source=src))
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
    by = {}
    for o in out:
        by.setdefault(o["coord_source"].split(" ")[0], 0); by[o["coord_source"].split(" ")[0]] += 1
    print(f"{len(out)} huts -> {a.out}; coordinates: {by}; missing: {missing}")

if __name__ == "__main__":
    main()
