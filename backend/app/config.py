from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Village Pond Planning System"
    database_url: str = "http://10.1.75.79:4205"
    open_meteo_base_url: str = "https://archive-api.open-meteo.com/v1/archive"
    elevation_api_base_url: str = "https://api.opentopodata.org/v1/srtm30m"

    default_runoff_coefficient: float = 0.3
    default_capture_fraction: float = 0.2
    default_loss_factor: float = 0.15

    # --- Phase 2: contour/basin analysis ---
    # Minimum depth (catchment elevation - pit elevation) for a depression to be
    # considered a genuine candidate basin, rather than digitisation noise from
    # the contour-generation process. Expressed in the same units as contour
    # elevations (metres).
    min_basin_depth_m: float = 2.0

    # --- Phase 3: freeform area selection (elevation sampling + rainfall) ---
    # Target ground spacing between elevation samples. 30m matches
    # OpenTopoData's SRTM30m source resolution — sampling denser than
    # this doesn't add real information. Grid size is derived from this
    # + the drawn area's actual extent (see area_contour_builder.estimate_grid_side),
    # not from a fixed point count, so resolution scales with area
    # automatically instead of degrading silently.
    area_target_spacing_m: float = 30.0
    area_grid_min_side: int = 9
    area_grid_max_side: int = 80
    # Hard ceiling on total sampled points, regardless of area size —
    # this is what actually bounds elevation-fetch cost/latency. A very
    # large drawn area still gets analyzed, just at coarser-than-target
    # spacing once this cap is hit (reported in the response notes).
    area_max_grid_points: int = 1024
    # Target number of contour levels extracted from the sampled DEM grid.
    area_contour_levels: int = 15
    # Sanity backstop only (typo/abuse guard, e.g. someone drawing a
    # whole district by accident) — NOT a resolution limit anymore,
    # since resolution now self-adjusts via area_max_grid_points above.
    area_max_size_km2: float = 500.0
    area_min_size_m2: float = 500.0
    # OpenTopoData's public instance allows ~100 locations/request and
    # ~1 request/sec; these are respected by ElevationService.
    elevation_chunk_size: int = 100
    elevation_request_delay_s: float = 1.0
    # Years of Open-Meteo daily history averaged into an annual rainfall
    # figure for the recommended site.
    rainfall_years: int = 10
    # Timeout for saving the analysis results.
    db_save_timeout_s: float = 5.0

    class Config:
        env_file = ".env"


settings = Settings()
