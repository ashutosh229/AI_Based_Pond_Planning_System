import numpy as np
import pytest

from app.core.area_contour_builder import (
    TerrainTooFlatError,
    build_contours_from_grid,
    build_sample_grid,
    fill_elevation_grid,
)


def test_build_sample_grid_is_square_and_matches_point_count():
    grid = build_sample_grid(0, 0, 0.01, 0.01, target_points=100, min_side=9, max_side=20)
    assert len(grid.lats) == len(grid.lons)
    assert len(grid.points) == len(grid.lats) * len(grid.lons)


def test_build_sample_grid_respects_min_and_max_side():
    small = build_sample_grid(0, 0, 0.01, 0.01, target_points=4, min_side=9, max_side=20)
    assert len(small.lats) == 9
    large = build_sample_grid(0, 0, 0.01, 0.01, target_points=10_000, min_side=9, max_side=20)
    assert len(large.lats) == 20


def test_fill_elevation_grid_interpolates_missing_values():
    grid = build_sample_grid(0, 0, 0.01, 0.01, target_points=25, min_side=5, max_side=5)
    elevations = [None if i % 3 == 0 else 100.0 for i in range(len(grid.points))]
    filled = fill_elevation_grid(grid, elevations)
    assert filled.shape == (5, 5)
    assert not np.isnan(filled).any()


def test_fill_elevation_grid_raises_when_all_missing():
    grid = build_sample_grid(0, 0, 0.01, 0.01, target_points=9, min_side=3, max_side=3)
    with pytest.raises(ValueError):
        fill_elevation_grid(grid, [None] * len(grid.points))


def test_flat_terrain_raises_terrain_too_flat():
    grid = build_sample_grid(0, 0, 0.01, 0.01, target_points=25, min_side=5, max_side=5)
    flat = np.full((5, 5), 100.0)
    with pytest.raises(TerrainTooFlatError):
        build_contours_from_grid(grid, flat, target_levels=10)


def test_bowl_shaped_surface_yields_a_closed_contour_near_its_minimum():
    side = 15
    grid = build_sample_grid(0, 0, 0.02, 0.02, target_points=side * side, min_side=side, max_side=side)
    idx = np.arange(side)
    row, col = np.meshgrid(idx, idx, indexing="ij")
    center = (side - 1) / 2
    # Paraboloid bowl: low in the middle (like a basin), rising toward the edges.
    bowl = 100 + 0.4 * ((row - center) ** 2 + (col - center) ** 2)

    contours, interval = build_contours_from_grid(grid, bowl, target_levels=10)
    assert interval > 0
    assert len(contours) > 0
    assert any(c.is_closed for c in contours)
    # The lowest closed ring should sit near the true minimum elevation (100),
    # not out near the sampled maximum.
    closed_elevations = [c.elevation for c in contours if c.is_closed]
    assert min(closed_elevations) < np.mean(bowl)
