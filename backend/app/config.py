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

    class Config:
        env_file = ".env"


settings = Settings()
