from app.config import settings
from app.core.contour_basin_analyzer import ContourBasinAnalyzer
from app.core.elevation_service import ElevationService
from app.core.rainfall_service import RainfallService
from app.core.run_store import RunStore


def get_basin_analyzer() -> ContourBasinAnalyzer:
    return ContourBasinAnalyzer(min_basin_depth_m=settings.min_basin_depth_m)


def get_elevation_service() -> ElevationService:
    return ElevationService(
        base_url=settings.elevation_api_base_url,
        chunk_size=settings.elevation_chunk_size,
        request_delay_s=settings.elevation_request_delay_s,
    )


def get_rainfall_service() -> RainfallService:
    return RainfallService(
        base_url=settings.open_meteo_base_url, years=settings.rainfall_years
    )


def get_run_store() -> RunStore:
    return RunStore(
        base_url=settings.db_server_base_url, timeout_s=settings.db_save_timeout_s
    )
