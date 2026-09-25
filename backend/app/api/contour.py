from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_basin_analyzer, get_rainfall_service
from app.core.contour_basin_analyzer import ContourAnalysisOutcome, ContourBasinAnalyzer
from app.core.kml_parser import KMLParseError, parse_contours
from app.core.pond_pipeline import Timer, basin_to_candidate, build_basin_notes, run_pond_pipeline
from app.core.rainfall_service import RainfallService
from app.schemas import ContourAnalysisResult, PondPlanningResult

router = APIRouter(prefix="/api", tags=["contour-analysis"])

ALLOWED_EXTENSIONS = (".kml", ".kmz")
MAX_UPLOAD_BYTES = (
    25 * 1024 * 1024
)  # 25 MB — generous for a village-scale contour export


def _to_response(
    filename: str, outcome: ContourAnalysisOutcome, min_basin_depth_m: float
) -> ContourAnalysisResult:
    candidates = [basin_to_candidate(i + 1, b) for i, b in enumerate(outcome.basins)]
    recommended = candidates[0] if candidates else None
    alternatives = candidates[1:6]  # cap the response size; top 5 runners-up

    return ContourAnalysisResult(
        source_filename=filename,
        contour_interval_m=outcome.contour_interval_m,
        elevation_range_m=(outcome.elevation_min_m, outcome.elevation_max_m),
        total_contours_parsed=outcome.total_contours_parsed,
        closed_contours_used=outcome.closed_contours_used,
        candidate_basins_found=len(candidates),
        recommended_site=recommended,
        alternative_sites=alternatives,
        notes=build_basin_notes(outcome, min_basin_depth_m),
    )


async def _read_and_parse(file: UploadFile) -> list:
    if not file.filename or not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="File must be a .kml or .kmz")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 25 MB)")

    try:
        return parse_contours(raw, file.filename)
    except KMLParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/analyzeContour", response_model=ContourAnalysisResult)
async def analyze_contour(
    file: UploadFile = File(..., description="Contour map in KML or KMZ format"),
    analyzer: ContourBasinAnalyzer = Depends(get_basin_analyzer),
):
    contours = await _read_and_parse(file)
    outcome = analyzer.analyze(contours)
    return _to_response(file.filename, outcome, analyzer.min_basin_depth_m)


# Alias per the assignment's alternate suggested route name.
@router.post(
    "/findCatchment", response_model=ContourAnalysisResult, include_in_schema=False
)
async def find_catchment(
    file: UploadFile = File(...),
    analyzer: ContourBasinAnalyzer = Depends(get_basin_analyzer),
):
    return await analyze_contour(file, analyzer)


@router.post("/recommendPond", response_model=PondPlanningResult)
async def recommend_pond(
    file: UploadFile = File(..., description="Contour map in KML or KMZ format"),
    analyzer: ContourBasinAnalyzer = Depends(get_basin_analyzer),
    rainfall_service: RainfallService = Depends(get_rainfall_service),
):
    """Phase 3: composes the Phase 2 contour/basin analysis with Phase 1's
    rainfall -> runoff -> pond-sizing chain for a KML/KMZ upload — the
    same full recommendation `/api/analyzeArea` produces for a map-drawn
    area, just sourced from a file instead of live elevation sampling."""
    timer = Timer()
    with timer.measure("kml_parse_ms"):
        contours = await _read_and_parse(file)

    return await run_pond_pipeline(
        contours,
        source_label=file.filename,
        analyzer=analyzer,
        rainfall_service=rainfall_service,
        timer=timer,
    )
