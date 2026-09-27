from fastapi import APIRouter, Depends, HTTPException
import math

from app.api.deps import (
    get_basin_analyzer,
    get_elevation_service,
    get_rainfall_service,
    get_run_store,
)
from app.config import settings
from app.core.area_contour_builder import (
    TerrainTooFlatError,
    build_contours_from_grid,
    build_sample_grid,
    estimate_grid_side,  # new
    fill_elevation_grid,
)
from app.core.contour_basin_analyzer import ContourBasinAnalyzer
from app.core.elevation_service import ElevationLookupError, ElevationService
from app.core.geo_utils import geodesic_polygon_area_m2
from app.core.pond_pipeline import Timer, run_pond_pipeline
from app.core.rainfall_service import RainfallService
from app.core.run_store import RunStore
from app.schemas import AreaSelectionRequest, PondPlanningResult

router = APIRouter(prefix="/api", tags=["area-analysis"])


@router.post("/analyzeArea", response_model=PondPlanningResult)
async def analyze_area(
    request: AreaSelectionRequest,
    elevation_service: ElevationService = Depends(get_elevation_service),
    rainfall_service: RainfallService = Depends(get_rainfall_service),
    run_store: RunStore = Depends(get_run_store),
):
    """Phase 3's main new flow: a freeform polygon the user drew on the
    map, in — a fully composed pond recommendation, out. Elevation is
    sampled over the polygon's bounding box (OpenTopoData), contours are
    extracted from that sampled surface (area_contour_builder), and from
    there this reuses the exact same basin-analysis + rainfall + sizing
    pipeline as the KML upload flow (pond_pipeline).

    Grid resolution is spacing-driven (estimate_grid_side), not a fixed
    point count: it targets area_target_spacing_m and only degrades
    (coarsens) once area_max_grid_points is hit, rather than rejecting
    the area outright. area_max_size_km2 is a sanity backstop only.

    min_basin_depth_m can be overridden per-request (request body) so the
    sensitivity threshold can be tuned live from the frontend without a
    server restart — useful since real terrain frequently has zero
    closed-ring basins at the default 2m threshold and that's often a
    genuine result, not a bug, worth confirming interactively."""
    if len(request.polygon) < 3:
        raise HTTPException(status_code=400, detail="A polygon needs at least 3 points")

    lons = [p[0] for p in request.polygon]
    lats = [p[1] for p in request.polygon]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)

    area_m2 = geodesic_polygon_area_m2(lons + [lons[0]], lats + [lats[0]])
    area_km2 = area_m2 / 1_000_000

    # Sanity backstop only — resolution itself scales with area via
    # estimate_grid_side below, so this just guards against pathological
    # input (e.g. an accidentally continent-sized polygon).
    if area_km2 > settings.area_max_size_km2:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Drawn area is {area_km2:.2f} km², which exceeds the "
                f"{settings.area_max_size_km2:g} km² sanity limit. "
                "Draw a smaller area."
            ),
        )
    if area_m2 < settings.area_min_size_m2:
        raise HTTPException(
            status_code=400,
            detail=f"Drawn area is too small ({area_m2:.0f} m²) to yield a meaningful contour grid.",
        )

    analyzer = ContourBasinAnalyzer(
        min_basin_depth_m=(
            request.min_basin_depth_m
            if request.min_basin_depth_m is not None
            else settings.min_basin_depth_m
        )
    )

    timer = Timer()

    side = estimate_grid_side(
        min_lat,
        min_lon,
        max_lat,
        max_lon,
        target_spacing_m=settings.area_target_spacing_m,
        min_side=settings.area_grid_min_side,
        max_side=settings.area_grid_max_side,
        hard_max_points=settings.area_max_grid_points,
    )
    grid = build_sample_grid(
        min_lat,
        min_lon,
        max_lat,
        max_lon,
        target_points=side * side,
        min_side=side,
        max_side=side,
    )

    mean_lat_rad = math.radians((min_lat + max_lat) / 2)
    span_m = max(
        (max_lat - min_lat) * 111_320.0,
        (max_lon - min_lon) * 111_320.0 * math.cos(mean_lat_rad),
    )
    effective_spacing_m = span_m / max(side - 1, 1)

    with timer.measure("elevation_fetch_ms"):
        try:
            elevations = await elevation_service.fetch_many(grid.points)
        except ElevationLookupError as exc:
            raise HTTPException(
                status_code=502, detail=f"Elevation lookup failed: {exc}"
            ) from exc

    with timer.measure("contour_extraction_ms"):
        try:
            elevation_grid = fill_elevation_grid(grid, elevations)
            contours, _interval = build_contours_from_grid(
                grid, elevation_grid, target_levels=settings.area_contour_levels
            )
        except TerrainTooFlatError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return await run_pond_pipeline(
        contours,
        source_label=(
            f"drawn area (~{area_km2:.2f} km², {len(grid.points)} elevation samples, "
            f"~{effective_spacing_m:.0f} m spacing)"
        ),
        analyzer=analyzer,
        rainfall_service=rainfall_service,
        timer=timer,
        run_store=run_store,
        mode="area",
        extra_notes=(
            f"Terrain was sampled over the drawn area's bounding box at ~{effective_spacing_m:.0f} m "
            f"spacing (target: {settings.area_target_spacing_m:g} m — coarser than target means the "
            f"{settings.area_max_grid_points}-sample-point cap was reached for this area size), not "
            "clipped exactly to the hand-drawn outline, so the reported catchment may extend slightly "
            "past what was drawn."
        ),
    )
