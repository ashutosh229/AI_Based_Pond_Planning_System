import pytest

from app.core.contour_basin_analyzer import ContourBasinAnalyzer
from app.core.kml_parser import parse_contours
from app.core.pond_pipeline import Timer, run_pond_pipeline
from app.core.rainfall_service import RainfallLookupError, RainfallStats


class _FakeRunStore:
    """In-memory fake so pipeline tests don't touch the DB server."""

    def __init__(self, run_id=1):
        self.run_id = run_id
        self.saved_runs = []

    async def save_run(self, payload):
        self.saved_runs.append(payload)
        return self.run_id


class _FakeRainfallService:
    """Returns fixed rainfall data without making network requests."""

    async def get_annual_rainfall_m(self, lat, lon):
        return RainfallStats(
            annual_avg_m=1.2,
            years_used=10,
            source="fake-source",
        )


class _FailingRainfallService:
    async def get_annual_rainfall_m(self, lat, lon):
        raise RainfallLookupError("simulated outage")


def _square_ring(cx, cy, half_size):
    return [
        (cx - half_size, cy - half_size),
        (cx + half_size, cy - half_size),
        (cx + half_size, cy + half_size),
        (cx - half_size, cy + half_size),
        (cx - half_size, cy - half_size),
    ]


def _placemark_kml(elevation, points):
    coords_text = " ".join(f"{lon},{lat}" for lon, lat in points)
    return (
        f"<Placemark><name>{elevation}</name>"
        f"<LineString><coordinates>{coords_text}</coordinates></LineString>"
        f"</Placemark>"
    )


def _wrap_kml(placemarks_xml: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        f"{placemarks_xml}</Document></kml>"
    ).encode("utf-8")


# Same nested-basin fixture as test_contour_analysis.py:
# three concentric squares, elevation decreasing inward
# (110m -> 105m -> 100m pit).
NESTED_BASIN_KML = _wrap_kml(
    _placemark_kml(110, _square_ring(0, 0, 30))
    + _placemark_kml(105, _square_ring(0, 0, 20))
    + _placemark_kml(100, _square_ring(0, 0, 10))
)


@pytest.mark.anyio
async def test_pipeline_composes_basin_analysis_with_pond_sizing():
    contours = parse_contours(NESTED_BASIN_KML, "test.kml")
    analyzer = ContourBasinAnalyzer(min_basin_depth_m=1.0)
    timer = Timer()
    run_store = _FakeRunStore()

    result = await run_pond_pipeline(
        contours,
        source_label="test.kml",
        analyzer=analyzer,
        rainfall_service=_FakeRainfallService(),
        timer=timer,
        run_store=run_store,
    )

    assert result.recommended_site is not None
    assert result.pond_recommendation is not None
    assert result.pond_recommendation.annual_rainfall_m == 1.2
    assert result.pond_recommendation.rainfall_years_used == 10
    assert result.pond_recommendation.recommended_depth_m > 0

    # Every pipeline step should have been timed.
    assert "basin_analysis_ms" in result.timings_ms
    assert "rainfall_lookup_ms" in result.timings_ms
    assert "pond_sizing_ms" in result.timings_ms
    assert "db_save_ms" in result.timings_ms

    # Verify that the completed run was persisted.
    assert len(run_store.saved_runs) == 1

    saved = run_store.saved_runs[0]

    assert saved["source"] == "test.kml"
    assert saved["candidate_basins_found"] == result.candidate_basins_found
    assert saved["recommended_catchment_area_m2"] == (
        result.recommended_site.catchment_area_m2
    )
    assert saved["is_feasible"] == result.pond_recommendation.is_feasible
    assert saved["result"]["recommended_site"] is not None
    assert saved["result"]["pond_recommendation"] is not None
    assert saved["result"]["source"] == "test.kml"


@pytest.mark.anyio
async def test_pipeline_degrades_gracefully_when_rainfall_lookup_fails():
    contours = parse_contours(NESTED_BASIN_KML, "test.kml")
    analyzer = ContourBasinAnalyzer(min_basin_depth_m=1.0)
    timer = Timer()
    run_store = _FakeRunStore()

    result = await run_pond_pipeline(
        contours,
        source_label="test.kml",
        analyzer=analyzer,
        rainfall_service=_FailingRainfallService(),
        timer=timer,
        run_store=run_store,
    )

    # Basin/catchment info should still come through even if rainfall fails.
    assert result.recommended_site is not None
    assert result.pond_recommendation is None
    assert "simulated outage" in result.notes

    # The run should still be persisted despite rainfall failure.
    assert len(run_store.saved_runs) == 1

    saved = run_store.saved_runs[0]

    assert saved["candidate_basins_found"] > 0
    assert saved["is_feasible"] is None
    assert saved["result"]["recommended_site"] is not None
    assert saved["result"]["pond_recommendation"] is None
    assert "simulated outage" in saved["result"]["notes"]


@pytest.mark.anyio
async def test_pipeline_skips_rainfall_lookup_when_no_basin_found():
    # min_basin_depth_m of 20 filters out the 10m-deep nested basin entirely.
    contours = parse_contours(NESTED_BASIN_KML, "test.kml")
    analyzer = ContourBasinAnalyzer(min_basin_depth_m=20.0)
    timer = Timer()
    run_store = _FakeRunStore()

    result = await run_pond_pipeline(
        contours,
        source_label="test.kml",
        analyzer=analyzer,
        rainfall_service=_FakeRainfallService(),
        timer=timer,
        run_store=run_store,
    )

    assert result.recommended_site is None
    assert result.pond_recommendation is None
    assert "rainfall_lookup_ms" not in result.timings_ms

    # Even a run with no detected basin should be persisted.
    assert len(run_store.saved_runs) == 1

    saved = run_store.saved_runs[0]

    assert saved["candidate_basins_found"] == 0
    assert saved["recommended_catchment_area_m2"] is None
    assert saved["is_feasible"] is None
    assert saved["result"]["recommended_site"] is None
    assert saved["result"]["alternative_sites"] == []
    assert saved["result"]["pond_recommendation"] is None
