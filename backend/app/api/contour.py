from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import settings
from app.core.contour_basin_analyzer import ContourBasinAnalyzer, ContourAnalysisOutcome
from app.core.kml_parser import KMLParseError, parse_contours
from app.schemas import BasinCandidate, ContourAnalysisResult, Coordinates

router = APIRouter(prefix="/api", tags=["contour-analysis"])

ALLOWED_EXTENSIONS = (".kml", ".kmz")
MAX_UPLOAD_BYTES = (
    25 * 1024 * 1024
)  # 25 MB — generous for a village-scale contour export


def get_basin_analyzer() -> ContourBasinAnalyzer:
    return ContourBasinAnalyzer(min_basin_depth_m=settings.min_basin_depth_m)


def _to_response(
    filename: str, outcome: ContourAnalysisOutcome
) -> ContourAnalysisResult:
    def to_candidate(rank: int, basin) -> BasinCandidate:
        return BasinCandidate(
            rank=rank,
            site=Coordinates(lat=basin.pit_centroid_lat, lon=basin.pit_centroid_lon),
            pit_elevation_m=basin.pit_elevation_m,
            catchment_boundary_elevation_m=basin.catchment_elevation_m,
            basin_depth_m=round(basin.catchment_elevation_m - basin.pit_elevation_m, 2),
            pond_footprint_area_m2=round(basin.pit_area_m2, 1),
            catchment_area_m2=round(basin.catchment_area_m2, 1),
            catchment_boundary_geojson=basin.catchment_boundary_geojson,
        )

    candidates = [to_candidate(i + 1, b) for i, b in enumerate(outcome.basins)]
    recommended = candidates[0] if candidates else None
    alternatives = candidates[1:6]  # cap the response size; top 5 runners-up

    notes = (
        f"Detected contour interval: {outcome.contour_interval_m:g} m. "
        f"{outcome.closed_contours_used} closed contour rings were usable out of "
        f"{outcome.total_contours_parsed} total contour lines parsed "
        f"(open contours that touch the map boundary are excluded from basin "
        f"detection since containment can't be determined for them). "
        f"Basins shallower than {settings.min_basin_depth_m:g} m were filtered out "
        f"as likely digitisation noise."
    )
    if recommended is None:
        notes += " No basin met the minimum depth threshold — consider lowering min_basin_depth_m."

    return ContourAnalysisResult(
        source_filename=filename,
        contour_interval_m=outcome.contour_interval_m,
        elevation_range_m=(outcome.elevation_min_m, outcome.elevation_max_m),
        total_contours_parsed=outcome.total_contours_parsed,
        closed_contours_used=outcome.closed_contours_used,
        candidate_basins_found=len(candidates),
        recommended_site=recommended,
        alternative_sites=alternatives,
        notes=notes,
    )


@router.post("/analyzeContour", response_model=ContourAnalysisResult)
async def analyze_contour(
    contour_map: UploadFile = File(..., description="Contour map in KML or KMZ format"),
    analyzer: ContourBasinAnalyzer = Depends(get_basin_analyzer),
):
    if not contour_map.filename or not contour_map.filename.lower().endswith(
        ALLOWED_EXTENSIONS
    ):
        raise HTTPException(status_code=400, detail="File must be a .kml or .kmz")

    raw = await contour_map.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 25 MB)")

    try:
        contours = parse_contours(raw, contour_map.filename)
    except KMLParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    outcome = analyzer.analyze(contours)
    return _to_response(contour_map.filename, outcome)


# Alias per the assignment's alternate suggested route name.
@router.post(
    "/findCatchment", response_model=ContourAnalysisResult, include_in_schema=False
)
async def find_catchment(
    contour_map: UploadFile = File(...),
    analyzer: ContourBasinAnalyzer = Depends(get_basin_analyzer),
):
    return await analyze_contour(contour_map, analyzer)
