"""
Composes the previously-disconnected Phase 1 and Phase 2 modules into
one pipeline: contour lines -> basin/catchment detection -> historical
rainfall for the recommended site -> runoff volume -> pond depth/storage
sizing. Used by both `/api/recommendPond` (KML input) and
`/api/analyzeArea` (freeform map-drawn input) so the two input modes stay
behaviourally identical from this point onward.

Every step is timed (`Timer`) and the timings are returned to the caller
in `PondPlanningResult.timings_ms` — this is deliberate: it's the
project's only source of real performance numbers, so the report's
Performance section can cite actual measured figures instead of guesses.
"""

import time

from contextlib import contextmanager

from app.config import settings

from app.core.contour_basin_analyzer import (
    Basin,
    ContourAnalysisOutcome,
    ContourBasinAnalyzer,
)

from app.core.kml_parser import ContourLine

from app.core.rainfall_service import RainfallLookupError, RainfallService

from app.core.run_store import RunStore

from app.core.runoff import RunoffCalculator

from app.core.pond_sizing import PondSizer

from app.schemas import (
    BasinCandidate,
    Coordinates,
    PondPlanningResult,
    PondRecommendation,
)


class Timer:
    """Accumulates named step durations (milliseconds) for one request."""

    def __init__(self):
        self.timings_ms: dict[str, float] = {}

    @contextmanager
    def measure(self, label: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.timings_ms[label] = round((time.perf_counter() - start) * 1000, 2)


def basin_to_candidate(rank: int, basin: Basin) -> BasinCandidate:
    return BasinCandidate(
        rank=rank,
        site=Coordinates(
            lat=basin.pit_centroid_lat,
            lon=basin.pit_centroid_lon,
        ),
        pit_elevation_m=basin.pit_elevation_m,
        catchment_boundary_elevation_m=basin.catchment_elevation_m,
        basin_depth_m=round(basin.catchment_elevation_m - basin.pit_elevation_m, 2),
        pond_footprint_area_m2=round(basin.pit_area_m2, 1),
        catchment_area_m2=round(basin.catchment_area_m2, 1),
        catchment_boundary_geojson=basin.catchment_boundary_geojson,
    )


def build_basin_notes(
    outcome: ContourAnalysisOutcome,
    min_basin_depth_m: float,
) -> str:
    notes = (
        f"Detected contour interval: {outcome.contour_interval_m:g} m. "
        f"{outcome.closed_contours_used} closed contour rings were usable out of "
        f"{outcome.total_contours_parsed} total contour lines parsed "
        f"(open contours that touch the sampled/mapped boundary are excluded from "
        f"basin detection since containment can't be determined for them). "
        f"Basins shallower than {min_basin_depth_m:g} m were filtered out as likely noise."
    )

    if not outcome.basins:
        notes += (
            " No basin met the minimum depth threshold — "
            "consider a larger or hillier area."
        )

    return notes


async def run_pond_pipeline(
    contours: list[ContourLine],
    *,
    source_label: str,
    analyzer: ContourBasinAnalyzer,
    rainfall_service: RainfallService,
    timer: Timer,
    run_store: RunStore,
    mode: str,
    extra_notes: str = "",
) -> PondPlanningResult:

    with timer.measure("basin_analysis_ms"):
        outcome = analyzer.analyze(contours)

    candidates = [basin_to_candidate(i + 1, b) for i, b in enumerate(outcome.basins)]

    recommended = candidates[0] if candidates else None
    alternatives = candidates[1:6]

    notes = build_basin_notes(
        outcome,
        analyzer.min_basin_depth_m,
    )

    if extra_notes:
        notes = f"{extra_notes} {notes}"

    pond_recommendation = None

    if recommended is not None:
        rainfall = None

        with timer.measure("rainfall_lookup_ms"):
            try:
                rainfall = await rainfall_service.get_annual_rainfall_m(
                    recommended.site.lat,
                    recommended.site.lon,
                )
            except RainfallLookupError as exc:
                notes += f" Rainfall lookup failed ({exc}); pond sizing skipped."

        if rainfall is not None:
            with timer.measure("pond_sizing_ms"):
                runoff = RunoffCalculator.compute(
                    catchment_area_m2=recommended.catchment_area_m2,
                    annual_rainfall_m=rainfall.annual_avg_m,
                    runoff_coefficient=settings.default_runoff_coefficient,
                    capture_fraction=settings.default_capture_fraction,
                )

                sizing = PondSizer.recommend(
                    design_storage_volume_m3=runoff.design_storage_volume_m3,
                    available_surface_area_m2=recommended.pond_footprint_area_m2,
                    loss_factor=settings.default_loss_factor,
                )

                pond_recommendation = PondRecommendation(
                    annual_rainfall_m=rainfall.annual_avg_m,
                    rainfall_years_used=rainfall.years_used,
                    rainfall_source=rainfall.source,
                    annual_runoff_volume_m3=runoff.annual_runoff_volume_m3,
                    design_storage_volume_m3=runoff.design_storage_volume_m3,
                    usable_volume_m3=sizing.usable_volume_m3,
                    recommended_depth_m=sizing.recommended_depth_m,
                    is_feasible=sizing.is_feasible,
                    notes=sizing.notes,
                )

    # Persist the completed pipeline result in the database. A save
    # failure is never fatal to the response — the analysis result the
    # user is waiting on is more important than its own history entry.
    with timer.measure("db_save_ms"):
        run_id = await run_store.save_run(
            {
                "mode": mode,
                "source": source_label,
                "contour_interval_m": outcome.contour_interval_m,
                "elevation_min_m": outcome.elevation_min_m,
                "elevation_max_m": outcome.elevation_max_m,
                "candidate_basins_found": len(candidates),
                "recommended_catchment_area_m2": (
                    recommended.catchment_area_m2 if recommended else None
                ),
                "is_feasible": (
                    pond_recommendation.is_feasible if pond_recommendation else None
                ),
                "result": {
                    "source": source_label,
                    "contour_interval_m": outcome.contour_interval_m,
                    "elevation_range_m": [
                        outcome.elevation_min_m,
                        outcome.elevation_max_m,
                    ],
                    "total_contours_parsed": outcome.total_contours_parsed,
                    "closed_contours_used": outcome.closed_contours_used,
                    "candidate_basins_found": len(candidates),
                    "recommended_site": (
                        recommended.model_dump() if recommended else None
                    ),
                    "alternative_sites": [a.model_dump() for a in alternatives],
                    "pond_recommendation": (
                        pond_recommendation.model_dump()
                        if pond_recommendation
                        else None
                    ),
                    "notes": notes,
                },
            }
        )

    if run_id is None:
        notes += " (Could not persist this run — DB server unreachable.)"

    return PondPlanningResult(
        source=source_label,
        contour_interval_m=outcome.contour_interval_m,
        elevation_range_m=(
            outcome.elevation_min_m,
            outcome.elevation_max_m,
        ),
        total_contours_parsed=outcome.total_contours_parsed,
        closed_contours_used=outcome.closed_contours_used,
        candidate_basins_found=len(candidates),
        recommended_site=recommended,
        alternative_sites=alternatives,
        pond_recommendation=pond_recommendation,
        notes=notes,
        timings_ms=timer.timings_ms,
    )
