"""Minimal pure-Python reader for ESRI File Geodatabase polygon tables (OpenFileGDB spec).

Reads attribute fields and polygon geometry (XY only). Usage:
    rows = read_table("x.gdb/a00000009.gdbtable")
    -> list of dicts; geometry under key 'SHAPE' as list of rings [(lon, lat), ...]
"""
import struct, sys, json


def varuint(b, i):
    shift = val = 0
    while True:
        c = b[i]; i += 1
        val |= (c & 0x7F) << shift
        if not c & 0x80:
            return val, i
        shift += 7


def varint(b, i):
    c = b[i]; i += 1
    neg = c & 0x40
    val = c & 0x3F
    shift = 6
    while c & 0x80:
        c = b[i]; i += 1
        val |= (c & 0x7F) << shift
        shift += 7
    return (-val if neg else val), i


def read_table(path):
    b = open(path, "rb").read()
    fd_off = struct.unpack_from("<q", b, 32)[0]
    i = fd_off
    hdr_size, version, flags, nfields = struct.unpack_from("<iiih", b, i)
    i += 14
    fields, geom = [], None
    for _ in range(nfields):
        n = b[i]; i += 1
        name = b[i:i + 2 * n].decode("utf-16-le"); i += 2 * n
        n = b[i]; i += 1
        i += 2 * n  # alias
        ftype = b[i]; i += 1
        nullable = True
        if ftype == 6:  # objectid
            i += 2; nullable = False
        elif ftype == 4:  # string
            i += 4; fl = b[i]; i += 1
            nullable = bool(fl & 1)
            if fl & 4:
                dl, i = varuint(b, i); i += dl
        elif ftype == 7:  # geometry
            i += 1; fl = b[i]; i += 1
            nullable = bool(fl & 1)
            wl = struct.unpack_from("<H", b, i)[0]; i += 2 + wl
            gf = b[i]; i += 1
            hasM, hasZ = bool(gf & 2), bool(gf & 4)
            xo, yo, xys = struct.unpack_from("<ddd", b, i); i += 24
            if hasM: i += 16
            if hasZ: i += 16
            i += 8
            if hasM: i += 8
            if hasZ: i += 8
            i += 32  # extent
            # optional Z extent, then grid sizes: byte 0 + int32 n + n doubles
            while True:
                if b[i] == 0 and 1 <= struct.unpack_from("<i", b, i + 1)[0] <= 3:
                    ng = struct.unpack_from("<i", b, i + 1)[0]
                    i += 5 + 8 * ng
                    break
                i += 8
            geom = dict(xo=xo, yo=yo, s=xys, hasZ=hasZ, hasM=hasM)
        elif ftype in (8,):  # binary
            i += 1; fl = b[i]; i += 1; nullable = bool(fl & 1)
        elif ftype in (10, 11, 12):
            i += 1; fl = b[i]; i += 1; nullable = bool(fl & 1)
        elif ftype == 9:
            raise SystemExit("raster field not supported")
        else:  # numeric / date types
            i += 1; fl = b[i]; i += 1; nullable = bool(fl & 1)
            dl = b[i]; i += 1
            if fl & 4:
                i += dl
        fields.append((name, ftype, nullable))

    # row offsets
    x = open(path[:-len("gdbtable")] + "gdbtablx", "rb").read()
    _, nblocks, nrows, osz = struct.unpack_from("<iiii", x, 0)
    offs = []
    for k in range(nblocks * 1024):
        p = 16 + k * osz
        if p + osz > len(x):
            break
        offs.append(int.from_bytes(x[p:p + osz], "little"))
    n_nullable = sum(1 for f in fields if f[2])
    rows = []
    for oid, off in enumerate(offs, 1):
        if not off:
            continue
        j = off + 4
        nb = (n_nullable + 7) // 8
        nulls = b[j:j + nb]; j += nb
        row, k = {"OBJECTID": oid}, 0
        for name, ft, nullable in fields:
            if ft == 6:
                continue
            if nullable:
                isnull = nulls[k // 8] & (1 << (k % 8)); k += 1
                if isnull:
                    row[name] = None; continue
            if ft == 0: row[name] = struct.unpack_from("<h", b, j)[0]; j += 2
            elif ft == 1: row[name] = struct.unpack_from("<i", b, j)[0]; j += 4
            elif ft == 2: row[name] = struct.unpack_from("<f", b, j)[0]; j += 4
            elif ft in (3, 5, 14, 15): row[name] = struct.unpack_from("<d", b, j)[0]; j += 8
            elif ft == 13: row[name] = struct.unpack_from("<q", b, j)[0]; j += 8
            elif ft == 16: j += 10; row[name] = None
            elif ft in (4, 12):
                L, j = varuint(b, j); row[name] = b[j:j + L].decode("utf-8", "replace"); j += L
            elif ft in (10, 11): j += 16; row[name] = None
            elif ft == 8:
                L, j = varuint(b, j); j += L; row[name] = None
            elif ft == 7:
                L, j = varuint(b, j); row[name] = parse_poly(b[j:j + L], geom); j += L
        rows.append(row)
    return rows


def parse_poly(g, gp):
    i = 0
    gtype, i = varuint(g, i)
    base = gtype & 0xFF
    if base not in (5, 15, 19, 25, 51):   # not a polygon (e.g. WDPA point-only records)
        return None
    curves = bool(gtype & 0x20000000)
    npts, i = varuint(g, i)
    if npts == 0:
        return []
    nparts, i = varuint(g, i)
    if curves:
        _, i = varuint(g, i)
    for _ in range(4):
        _, i = varuint(g, i)  # bbox
    counts = []
    for _ in range(nparts - 1):
        c, i = varuint(g, i); counts.append(c)
    counts.append(npts - sum(counts))
    x = y = 0
    rings = []
    for c in counts:
        ring = []
        for _ in range(c):
            dx, i = varint(g, i); dy, i = varint(g, i)
            x += dx; y += dy
            ring.append((x / gp["s"] + gp["xo"], y / gp["s"] + gp["yo"]))
        rings.append(ring)
    return rings


if __name__ == "__main__":
    rows = read_table(sys.argv[1])
    for r in rows:
        s = r.get("SHAPE")
        print({k: v for k, v in r.items() if k in ("SITE_ID", "NAME", "NAME_ENG", "DESIG_ENG", "ISO3", "GIS_AREA", "STATUS_YR")},
              "rings:", len(s) if s else 0, "pts:", sum(map(len, s)) if s else 0)
