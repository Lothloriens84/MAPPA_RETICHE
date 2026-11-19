"""
Build a hillshade for the maps from Copernicus DEM GLO-90 tiles (Cloud-Optimised GeoTIFF).

Reads the 1°x1° tiles with tifffile only (the deflate + floating-point predictor is decoded
here, so no GDAL / imagecodecs is needed), mosaics them, resamples to the ETRS89-LAEA grid
used by the maps and writes a greyscale hillshade PNG plus its extent:

    python tools/dem_hillshade.py path/to/copernicus_dem_90m --out ne_data/hillshade_laea.png

The raw DEM is not redistributed; the hillshade PNG is a derived product.
Copernicus DEM: © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018,
provided under COPERNICUS by the European Union and ESA; all rights reserved.
"""
import argparse, glob, json, math, os, re, sys, zlib
import numpy as np
import tifffile
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rhaetian_map as rm


def read_tile(path):
    """Decode a deflate + floating-point-predictor float32 tiled TIFF into an array."""
    with tifffile.TiffFile(path) as t:
        p = t.pages[0]
        H, W = p.shape
        th, tw = p.tilelength, p.tilewidth
        out = np.zeros((H, W), np.float32)
        fh = t.filehandle
        ntx = (W + tw - 1) // tw
        for i, (off, cnt) in enumerate(zip(p.dataoffsets, p.databytecounts)):
            fh.seek(off)
            raw = np.frombuffer(zlib.decompress(fh.read(cnt)), np.uint8).reshape(th, tw * 4)
            if p.predictor == 3:
                raw = np.cumsum(raw, axis=1, dtype=np.uint8)            # undo byte differencing
                raw = raw.reshape(th, 4, tw).transpose(0, 2, 1)          # bytes stored plane by plane (MSB first)
                tile = raw[:, :, ::-1].copy().view("<f4")[:, :, 0] if sys.byteorder == "little" else raw.copy().view(">f4")[:, :, 0]
            else:
                tile = raw.view(p.dtype).reshape(th, tw)
            r, c = divmod(i, ntx)
            y0, x0 = r * th, c * tw
            out[y0:y0 + th, x0:x0 + tw] = tile[:min(th, H - y0), :min(tw, W - x0)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tiles_dir"); ap.add_argument("--out", default="ne_data/hillshade_laea.png")
    ap.add_argument("--px-km", type=float, default=0.25, help="output pixel size in km")
    a = ap.parse_args()

    # mosaic on a regular lon/lat grid at 1/1200° (tiles at these latitudes: 1200 rows, 1200 or 800 cols)
    tiles = {}
    for f in glob.glob(os.path.join(a.tiles_dir, "Copernicus_DSM_COG_30_N*_E*_DEM.tif")):
        m = re.search(r"_N(\d+)_00_E(\d+)_00_", f)
        tiles[(int(m.group(1)), int(m.group(2)))] = f
    lats = sorted({k[0] for k in tiles}); lons = sorted({k[1] for k in tiles})
    R = 1200
    mosaic = np.full((len(lats) * R, len(lons) * R), np.nan, np.float32)
    for (la, lo), f in tiles.items():
        d = read_tile(f)
        if d.shape[1] != R:                       # resample columns to 1200 (nearest)
            d = d[:, (np.arange(R) * d.shape[1] / R).astype(int)]
        r0 = (lats[-1] - la) * R; c0 = (lo - lons[0]) * R
        mosaic[r0:r0 + R, c0:c0 + R] = d[:R, :R]
        print("tile", la, lo, d.shape, float(np.nanmin(d)), float(np.nanmax(d)))
    north, west = lats[-1] + 1, lons[0]

    # target LAEA grid covering the tiles
    rm.use_laea()
    (x0, x1), (y0, y1) = rm.view_limits(lons[0], lons[-1] + 1, lats[0], lats[-1] + 1)
    px = a.px_km
    nx, ny = int((x1 - x0) / px), int((y1 - y0) / px)
    xs = x0 + (np.arange(nx) + 0.5) * px
    ys = y1 - (np.arange(ny) + 0.5) * px
    X, Y = np.meshgrid(xs, ys)
    lon, lat = inverse_laea(X, Y)
    rr = ((north - lat) * R).astype(int); cc = ((lon - west) * R).astype(int)
    ok = (rr >= 0) & (rr < mosaic.shape[0]) & (cc >= 0) & (cc < mosaic.shape[1])
    z = np.full(X.shape, np.nan, np.float32)
    z[ok] = mosaic[rr[ok], cc[ok]]
    z = np.nan_to_num(z, nan=0.0)

    # hillshade (azimuth 315°, altitude 45°), z in m, grid in km
    dzdx = np.gradient(z, px * 1000, axis=1); dzdy = np.gradient(z, px * 1000, axis=0) * -1
    slope = np.arctan(np.hypot(dzdx, dzdy) * 1.6)            # mild vertical exaggeration
    aspect = np.arctan2(-dzdx, dzdy)
    az, alt = math.radians(315), math.radians(45)
    hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
    hs = np.clip(hs, 0, 1)
    img = (hs * 255).astype(np.uint8)
    Image.fromarray(img, "L").save(a.out, optimize=True)
    json.dump({"extent_km": [x0, x0 + nx * px, y1 - ny * px, y1], "px_km": px,
               "source": "Copernicus DEM GLO-90", "tiles": sorted(f"N{la}E{lo:03d}" for la, lo in tiles)},
              open(os.path.splitext(a.out)[0] + ".json", "w"), indent=1)
    print("saved", a.out, img.shape)


def inverse_laea(X, Y):
    """EPSG:3035 (km) -> lon/lat degrees, ellipsoidal inverse (Snyder 1987)."""
    x = (X * 1000 - rm._FE) / rm._D
    y = (Y * 1000 - rm._FN) * rm._D
    rho = np.hypot(x, y)
    ce = 2 * np.arcsin(np.clip(rho / (2 * rm._RQ), -1, 1))
    qq = rm._QP * (np.cos(ce) * math.sin(rm._B0) + y * np.sin(ce) * math.cos(rm._B0) / np.where(rho == 0, 1, rho))
    beta = np.arcsin(np.clip(qq / rm._QP, -1, 1))
    e2 = rm._E ** 2
    lat = beta + (e2 / 3 + 31 * e2 ** 2 / 180 + 517 * e2 ** 3 / 5040) * np.sin(2 * beta) \
        + (23 * e2 ** 2 / 360 + 251 * e2 ** 3 / 3780) * np.sin(4 * beta) + (761 * e2 ** 3 / 45360) * np.sin(6 * beta)
    lon = rm._LON0 + np.arctan2(x * np.sin(ce),
                                rho * math.cos(rm._B0) * np.cos(ce) - y * math.sin(rm._B0) * np.sin(ce))
    return np.degrees(lon), np.degrees(lat)


if __name__ == "__main__":
    main()
