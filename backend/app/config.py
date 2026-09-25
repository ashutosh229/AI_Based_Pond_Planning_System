from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Village Pond Planning System"
    database_url: str = "postgresql://pond_user:pond_pass@localhost:5432/pond_planning"
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
    # Regular grid resolution used when sampling elevation over a user-drawn
    # area. Bounds both accuracy (denser grid = better contours) and cost
    # (each point is a remote elevation-API call, batched and rate-limited).
    area_max_grid_points: int = 256
    area_grid_min_side: int = 9
    area_grid_max_side: int = 20
    # Target number of contour levels extracted from the sampled DEM grid.
    area_contour_levels: int = 15
    # Drawn-area size guardrails: too large and the fixed grid gets too
    # coarse to find a real basin; too small and there's nothing to sample.
    area_max_size_km2: float = 5.0
    area_min_size_m2: float = 500.0
    # OpenTopoData's public instance allows ~100 locations/request and
    # ~1 request/sec; these are respected by ElevationService.
    elevation_chunk_size: int = 100
    elevation_request_delay_s: float = 1.0
    # Years of Open-Meteo daily history averaged into an annual rainfall
    # figure for the recommended site.
    rainfall_years: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
