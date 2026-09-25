from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_basin_analyzer, get_elevation_service, get_rainfall_service
from app.config import settings
from app.core.area_contour_builder import (
    TerrainTooFlatError,
    build_contours_from_grid,
    build_sample_grid,
    fill_elevation_grid,
)
from app.core.contour_basin_analyzer import ContourBasinAnalyzer
from app.core.elevation_service import ElevationLookupError, ElevationService
from app.core.geo_utils import geodesic_polygon_area_m2
from app.core.pond_pipeline import Timer, run_pond_pipeline
from app.core.rainfall_service import RainfallService
from app.schemas import AreaSelectionRequest, PondPlanningResult

router = APIRouter(prefix="/api", tags=["area-analysis"])


@router.post("/analyzeArea", response_model=PondPlanningResult)
async def analyze_area(
    request: AreaSelectionRequest,
    elevation_service: ElevationService = Depends(get_elevation_service),
    rainfall_service: RainfallService = Depends(get_rainfall_service),
    analyzer: ContourBasinAnalyzer = Depends(get_basin_analyzer),
):
    """Phase 3's main new flow: a freeform polygon the user drew on the
    map, in — a fully composed pond recommendation, out. Elevation is
    sampled over the polygon's bounding box (OpenTopoData), contours are
    extracted from that sampled surface (area_contour_builder), and from
    there this reuses the exact same basin-analysis + rainfall + sizing
    pipeline as the KML upload flow (pond_pipeline)."""
    if len(request.polygon) < 3:
        raise HTTPException(status_code=400, detail="A polygon needs at least 3 points")

    lons = [p[0] for p in request.polygon]
    lats = [p[1] for p in request.polygon]
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)

    area_m2 = geodesic_polygon_area_m2(lons + [lons[0]], lats + [lats[0]])
    area_km2 = area_m2 / 1_000_000

    if area_km2 > settings.area_max_size_km2:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Drawn area is {area_km2:.2f} km², which exceeds the "
                f"{settings.area_max_size_km2:g} km² limit for on-demand analysis. "
                "Draw a smaller area."
            ),
        )
    if area_m2 < settings.area_min_size_m2:
        raise HTTPException(
            status_code=400,
            detail=f"Drawn area is too small ({area_m2:.0f} m²) to yield a meaningful contour grid.",
        )

    timer = Timer()
    grid = build_sample_grid(
        min_lat, min_lon, max_lat, max_lon, target_points=settings.area_max_grid_points,
        min_side=settings.area_grid_min_side, max_side=settings.area_grid_max_side,
    )

    with timer.measure("elevation_fetch_ms"):
        try:
            elevations = await elevation_service.fetch_many(grid.points)
        except ElevationLookupError as exc:
            raise HTTPException(status_code=502, detail=f"Elevation lookup failed: {exc}") from exc

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
        source_label=f"drawn area (~{area_km2:.2f} km², {len(grid.points)} elevation samples)",
        analyzer=analyzer,
        rainfall_service=rainfall_service,
        timer=timer,
        extra_notes=(
            "Terrain was sampled over the drawn area's bounding box (with a small "
            "margin), not clipped exactly to the hand-drawn outline, so the reported "
            "catchment may extend slightly past what was drawn."
        ),
    )
