from pyproj import Geod

_GEOD = Geod(ellps="WGS84")


def geodesic_polygon_area_m2(lons: list[float], lats: list[float]) -> float:
    """Accurate area on the WGS84 ellipsoid for a ring given as parallel
    lon/lat sequences. Avoids both the distortion of computing area
    directly from lon/lat degrees and the need to guess a UTM zone for
    projection. The ring need not be explicitly closed (pyproj closes it
    implicitly), but it's harmless if it is.
    """
    area, _ = _GEOD.polygon_area_perimeter(lons, lats)
    return abs(area)
