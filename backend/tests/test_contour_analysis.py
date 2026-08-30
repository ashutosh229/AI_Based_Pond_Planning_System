import pytest

from app.core.contour_basin_analyzer import ContourBasinAnalyzer
from app.core.kml_parser import KMLParseError, parse_contours


def _square_ring(cx, cy, half_size):
    """A small closed square contour centered at (cx, cy)."""
    return [
        (cx - half_size, cy - half_size),
        (cx + half_size, cy - half_size),
        (cx + half_size, cy + half_size),
        (cx - half_size, cy + half_size),
        (cx - half_size, cy - half_size),
    ]


def _placemark_kml(elevation, points, closed=True):
    coords_text = " ".join(f"{lon},{lat}" for lon, lat in points)
    return f"""
      <Placemark>
        <name>{elevation}</name>
        <LineString><coordinates>{coords_text}</coordinates></LineString>
      </Placemark>
    """


def _wrap_kml(placemarks_xml: str) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
      <Document>
        {placemarks_xml}
      </Document>
    </kml>""".encode("utf-8")


# --- A single nested basin: three concentric squares, elevation decreasing inward ---
# Outer ring (catchment boundary) at 110m, middle at 105m, inner pit at 100m.
NESTED_BASIN_KML = _wrap_kml(
    _placemark_kml(110, _square_ring(0, 0, 30))
    + _placemark_kml(105, _square_ring(0, 0, 20))
    + _placemark_kml(100, _square_ring(0, 0, 10))
)

# --- A hill (elevation increasing inward) — should NOT be selected as a basin ---
HILL_KML = _wrap_kml(
    _placemark_kml(100, _square_ring(0, 0, 30))
    + _placemark_kml(105, _square_ring(0, 0, 20))
    + _placemark_kml(110, _square_ring(0, 0, 10))
)

# --- Two independent basins far apart, plus a saddle-causing outer ring ---
# Basin A (pit 50) and Basin B (pit 60) both sit inside a single big ring at 70,
# which therefore has TWO children -> the walk-up must stop before including it.
TWO_BASINS_KML = _wrap_kml(
    _placemark_kml(70, _square_ring(0, 0, 100))
    + _placemark_kml(55, _square_ring(-50, 0, 20))
    + _placemark_kml(50, _square_ring(-50, 0, 10))
    + _placemark_kml(65, _square_ring(50, 0, 20))
    + _placemark_kml(60, _square_ring(50, 0, 10))
)


def test_parses_closed_contour_lines():
    contours = parse_contours(NESTED_BASIN_KML, "test.kml")
    assert len(contours) == 3
    assert all(c.is_closed for c in contours)
    assert {c.elevation for c in contours} == {100, 105, 110}


def test_rejects_file_with_no_usable_contours():
    empty_kml = _wrap_kml("<Placemark><name>not a number</name></Placemark>")
    with pytest.raises(KMLParseError):
        parse_contours(empty_kml, "empty.kml")


def test_detects_single_nested_basin_with_correct_catchment():
    contours = parse_contours(NESTED_BASIN_KML, "test.kml")
    outcome = ContourBasinAnalyzer(min_basin_depth_m=1.0).analyze(contours)

    assert outcome.contour_interval_m == pytest.approx(5.0)
    assert len(outcome.basins) == 1

    basin = outcome.basins[0]
    assert basin.pit_elevation_m == 100
    # walk-up should reach the outermost ring (110), since there's only one child at each level
    assert basin.catchment_elevation_m == 110
    # a 60x60 square (2*30) in degrees is huge in real m2 at the equator-ish scale used
    # here, but we only assert relative ordering + shape sanity, not exact geodesic figures
    assert basin.catchment_area_m2 > basin.pit_area_m2


def test_hill_is_not_classified_as_basin():
    contours = parse_contours(HILL_KML, "hill.kml")
    outcome = ContourBasinAnalyzer(min_basin_depth_m=1.0).analyze(contours)
    assert len(outcome.basins) == 0


def test_saddle_stops_catchment_walk_up_before_merging_basins():
    contours = parse_contours(TWO_BASINS_KML, "two_basins.kml")
    outcome = ContourBasinAnalyzer(min_basin_depth_m=1.0).analyze(contours)

    assert len(outcome.basins) == 2
    pit_elevations = {b.pit_elevation_m for b in outcome.basins}
    assert pit_elevations == {50, 60}

    for basin in outcome.basins:
        # neither basin's catchment boundary should reach the outer 70m ring —
        # that ring contains both basins, so it's a drainage divide, not part
        # of either individual catchment.
        assert basin.catchment_elevation_m < 70


def test_min_depth_filter_excludes_shallow_basins():
    contours = parse_contours(NESTED_BASIN_KML, "test.kml")
    # basin depth here is 110 - 100 = 10m; a 20m threshold should filter it out
    outcome = ContourBasinAnalyzer(min_basin_depth_m=20.0).analyze(contours)
    assert len(outcome.basins) == 0


def test_basins_ranked_by_catchment_area_descending():
    contours = parse_contours(TWO_BASINS_KML, "two_basins.kml")
    outcome = ContourBasinAnalyzer(min_basin_depth_m=1.0).analyze(contours)
    areas = [b.catchment_area_m2 for b in outcome.basins]
    assert areas == sorted(areas, reverse=True)
