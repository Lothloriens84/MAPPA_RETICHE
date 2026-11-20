"""Swiss LV95 (EPSG:2056) -> WGS84 lon/lat, swisstopo approximate formulas (accuracy ~1 m)."""


def lv95_to_wgs84(E, N):
    y = (E - 2600000) / 1e6
    x = (N - 1200000) / 1e6
    lam = 2.6779094 + 4.728982 * y + 0.791484 * y * x + 0.1306 * y * x * x - 0.0436 * y ** 3
    phi = (16.9023892 + 3.238272 * x - 0.270978 * y * y - 0.002528 * x * x
           - 0.0447 * y * y * x - 0.0140 * x ** 3)
    return lam * 100 / 36, phi * 100 / 36
