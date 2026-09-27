from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    lat: float
    lon: float


class VillageOut(BaseModel):
    id: int
    name: str
    centroid: Coordinates

    class Config:
        from_attributes = True


class RainfallStats(BaseModel):
    village_id: int
    annual_avg_mm: float
    years_of_data: int
    source: str


class CatchmentRequest(BaseModel):
    site: Coordinates = Field(..., description="Candidate pond location")


class CatchmentResult(BaseModel):
    site: Coordinates
    catchment_area_m2: float
    catchment_boundary_geojson: dict


class PondRecommendationRequest(BaseModel):
    site: Coordinates
    catchment_area_m2: float
    annual_rainfall_m: float
    runoff_coefficient: float | None = None
    capture_fraction: float | None = None
    available_surface_area_m2: float = Field(..., gt=0)


class PondRecommendationResult(BaseModel):
    site: Coordinates
    annual_runoff_volume_m3: float
    design_storage_volume_m3: float
    usable_volume_m3: float
    recommended_depth_m: float
    is_feasible: bool
    notes: str


# --- Phase 2: contour map analysis ---


class BasinCandidate(BaseModel):
    """One candidate pond site derived from the contour map, with its
    associated catchment. rank 1 = the recommended site."""

    rank: int
    site: Coordinates
    pit_elevation_m: float
    catchment_boundary_elevation_m: float
    basin_depth_m: float
    pond_footprint_area_m2: float
    catchment_area_m2: float
    catchment_boundary_geojson: dict


class ContourAnalysisResult(BaseModel):
    source_filename: str
    contour_interval_m: float
    elevation_range_m: tuple[float, float]
    total_contours_parsed: int
    closed_contours_used: int
    candidate_basins_found: int
    recommended_site: BasinCandidate | None
    alternative_sites: list[BasinCandidate]
    notes: str


# --- Phase 3: freeform area selection + composed pond recommendation ---


class AreaSelectionRequest(BaseModel):
    polygon: list[list[float]] = Field(
        ..., min_length=3, description="[[lon, lat], ...] vertices"
    )
    min_basin_depth_m: float | None = Field(
        None,
        ge=0,
        description="Override the server default basin-depth threshold for this request",
    )


class PondRecommendation(BaseModel):
    """Phase 1's runoff + sizing modules, composed onto the recommended
    Phase 2 basin. Present only when a basin was found and the rainfall
    lookup for its site succeeded."""

    annual_rainfall_m: float
    rainfall_years_used: int
    rainfall_source: str
    annual_runoff_volume_m3: float
    design_storage_volume_m3: float
    usable_volume_m3: float
    recommended_depth_m: float
    is_feasible: bool
    notes: str


class PondPlanningResult(BaseModel):
    """The full Phase 3 response: everything ContourAnalysisResult has,
    plus the composed pond recommendation and per-step timings. Returned
    by both /api/recommendPond (KML input) and /api/analyzeArea
    (freeform map-drawn input) so the two input modes are interchangeable
    from the frontend's point of view."""

    source: str
    contour_interval_m: float
    elevation_range_m: tuple[float, float]
    total_contours_parsed: int
    closed_contours_used: int
    candidate_basins_found: int
    recommended_site: BasinCandidate | None
    alternative_sites: list[BasinCandidate]
    pond_recommendation: PondRecommendation | None
    notes: str
    timings_ms: dict[str, float]
