"""Turns a user-drawn area into the same `ContourLine` objects the KML
parser produces, so `ContourBasinAnalyzer` (Phase 2) can be reused
unchanged for freeform map-drawn areas (Phase 3).

Pipeline: sample a regular lat/lon grid over the area's bounding box ->
fetch elevation per point (ElevationService) -> fill any missing samples
-> run marching squares (skimage) at evenly spaced elevation levels ->
map the resulting pixel (row, col) paths back to (lon, lat).
"""

from dataclasses import dataclass

import numpy as np
import math
from scipy.interpolate import griddata
from skimage import measure

from app.core.kml_parser import ContourLine

_NICE_STEPS = (0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200, 500)

_EARTH_M_PER_DEGREE_LAT = 111_320.0


def estimate_grid_side(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    target_spacing_m: float,
    min_side: int,
    max_side: int,
    hard_max_points: int,
) -> int:
    """Picks a square grid side length so points land roughly
    `target_spacing_m` apart on the ground for this area's actual
    extent, clamped to [min_side, max_side] and to a hard cap on total
    points. This is what makes resolution scale with area automatically
    instead of a fixed grid size degrading silently for large areas."""
    mean_lat_rad = math.radians((min_lat + max_lat) / 2)
    lat_span_m = (max_lat - min_lat) * _EARTH_M_PER_DEGREE_LAT
    lon_span_m = (max_lon - min_lon) * _EARTH_M_PER_DEGREE_LAT * math.cos(mean_lat_rad)
    span_m = max(lat_span_m, lon_span_m, 1.0)

    desired_side = round(span_m / target_spacing_m)
    side = max(min_side, min(max_side, desired_side))

    hard_cap_side = int(math.sqrt(hard_max_points))
    return max(min_side, min(side, hard_cap_side))


class TerrainTooFlatError(ValueError):
    """The sampled area has too little relief to contain a detectable
    basin (e.g. flat farmland, or the area is mostly water)."""


@dataclass(frozen=True)
class SampleGrid:
    lats: np.ndarray  # 1D, ascending
    lons: np.ndarray  # 1D, ascending
    points: list[tuple[float, float]]  # (lat, lon), row-major: lat outer, lon inner


def _grid_side_length(target_points: int, min_side: int, max_side: int) -> int:
    side = int(round(target_points**0.5))
    return max(min_side, min(max_side, side))


def build_sample_grid(
    min_lat: float,
    min_lon: float,
    max_lat: float,
    max_lon: float,
    target_points: int = 256,
    min_side: int = 9,
    max_side: int = 20,
    margin_fraction: float = 0.05,
) -> SampleGrid:
    """A regular grid over the bounding box, padded by a small margin so
    basins near the drawn edge still get a real surrounding ring rather
    than being clipped exactly at the boundary."""
    lat_span = max(max_lat - min_lat, 1e-6)
    lon_span = max(max_lon - min_lon, 1e-6)
    lat_margin = lat_span * margin_fraction
    lon_margin = lon_span * margin_fraction
    side = _grid_side_length(target_points, min_side, max_side)

    lats = np.linspace(min_lat - lat_margin, max_lat + lat_margin, side)
    lons = np.linspace(min_lon - lon_margin, max_lon + lon_margin, side)
    points = [(lat, lon) for lat in lats for lon in lons]
    return SampleGrid(lats=lats, lons=lons, points=points)


def fill_elevation_grid(grid: SampleGrid, elevations: list[float | None]) -> np.ndarray:
    """Reshape the flat per-point elevation list into a (n_lat, n_lon)
    array, filling any missing samples (no DEM coverage, usually water)
    via nearest-neighbour interpolation from the valid samples."""
    n_lat, n_lon = len(grid.lats), len(grid.lons)
    values = np.array([np.nan if e is None else e for e in elevations], dtype=float)

    if np.isnan(values).all():
        raise ValueError("elevation service returned no usable data for this area")

    if np.isnan(values).any():
        lat_lon_pairs = np.array(grid.points)
        valid_mask = ~np.isnan(values)
        values = griddata(
            lat_lon_pairs[valid_mask],
            values[valid_mask],
            lat_lon_pairs,
            method="nearest",
        )

    return values.reshape(n_lat, n_lon)


def _choose_contour_interval(
    elev_min: float, elev_max: float, target_levels: int
) -> float:
    span = elev_max - elev_min
    if span < 0.5:
        raise TerrainTooFlatError(
            f"Elevation range in this area is only {span:.2f} m — too flat to "
            "reliably detect a basin. Try drawing a larger or hillier area."
        )
    raw_interval = span / max(target_levels, 1)
    return min(_NICE_STEPS, key=lambda step: abs(step - raw_interval))


def build_contours_from_grid(
    grid: SampleGrid, elevation_grid: np.ndarray, target_levels: int = 15
) -> tuple[list[ContourLine], float]:
    """Extract contour lines from a regular elevation grid via marching
    squares. Returns (contour_lines, contour_interval_m)."""
    elev_min = float(np.nanmin(elevation_grid))
    elev_max = float(np.nanmax(elevation_grid))
    interval = _choose_contour_interval(elev_min, elev_max, target_levels)

    n_lat, n_lon = elevation_grid.shape
    lat0, lat1 = float(grid.lats[0]), float(grid.lats[-1])
    lon0, lon1 = float(grid.lons[0]), float(grid.lons[-1])

    def to_lonlat(row: float, col: float) -> tuple[float, float]:
        lon = lon0 + (col / (n_lon - 1)) * (lon1 - lon0)
        lat = lat0 + (row / (n_lat - 1)) * (lat1 - lat0)
        return lon, lat

    contours: list[ContourLine] = []
    level = elev_min + interval
    while level < elev_max:
        for path in measure.find_contours(elevation_grid, level):
            if len(path) < 4:
                continue
            rows, cols = path[:, 0], path[:, 1]
            touches_border = (
                rows.min() <= 0
                or rows.max() >= n_lat - 1
                or cols.min() <= 0
                or cols.max() >= n_lon - 1
            )
            is_closed = (not touches_border) and bool(np.allclose(path[0], path[-1]))

            points = [to_lonlat(r, c) for r, c in path]
            contours.append(
                ContourLine(
                    elevation=round(level, 3), points=points, is_closed=is_closed
                )
            )
        level += interval

    return contours, interval
