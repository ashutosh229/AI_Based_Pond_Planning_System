from dataclasses import dataclass

from pyproj import Geod
from shapely.geometry import Polygon, mapping
from shapely.strtree import STRtree

from app.core.kml_parser import ContourLine

_GEOD = Geod(ellps="WGS84")


@dataclass(frozen=True)
class Basin:
    pit_elevation_m: float
    catchment_elevation_m: float
    pit_centroid_lon: float
    pit_centroid_lat: float
    pit_area_m2: float
    catchment_area_m2: float
    catchment_boundary_geojson: dict


@dataclass(frozen=True)
class ContourAnalysisOutcome:
    contour_interval_m: float
    elevation_min_m: float
    elevation_max_m: float
    total_contours_parsed: int
    closed_contours_used: int
    basins: list[Basin]  # sorted by catchment_area_m2 descending


def _geodesic_area_m2(polygon: Polygon) -> float:
    """Accurate area on the WGS84 ellipsoid — avoids the distortion of
    computing area directly from lon/lat degrees, and avoids having to
    guess a UTM zone for projection."""
    lons, lats = zip(*polygon.exterior.coords)
    area, _ = _GEOD.polygon_area_perimeter(lons, lats)
    return abs(area)


def _detect_contour_interval(elevations: list[float]) -> float:
    unique_sorted = sorted(set(elevations))
    if len(unique_sorted) < 2:
        return 1.0
    diffs = [round(b - a, 6) for a, b in zip(unique_sorted, unique_sorted[1:])]
    # Most common gap is the true interval; a plain min() is fragile if a
    # single pair of levels happens to be closer together due to noise.
    return min(diffs, key=diffs.count)


class ContourBasinAnalyzer:
    def __init__(self, min_basin_depth_m: float = 2.0):
        self.min_basin_depth_m = min_basin_depth_m

    def analyze(self, contours: list[ContourLine]) -> ContourAnalysisOutcome:
        elevations = [c.elevation for c in contours]
        contour_interval = _detect_contour_interval(elevations)

        closed_polygons = self._build_closed_polygons(contours)
        parent_of, children_of = self._build_containment_tree(closed_polygons)
        basins = self._find_basins(closed_polygons, parent_of, children_of)

        basins = [
            b
            for b in basins
            if b.catchment_elevation_m - b.pit_elevation_m >= self.min_basin_depth_m
        ]
        basins.sort(key=lambda b: b.catchment_area_m2, reverse=True)

        return ContourAnalysisOutcome(
            contour_interval_m=contour_interval,
            elevation_min_m=min(elevations),
            elevation_max_m=max(elevations),
            total_contours_parsed=len(contours),
            closed_contours_used=len(closed_polygons),
            basins=basins,
        )

    def _build_closed_polygons(
        self, contours: list[ContourLine]
    ) -> list[tuple[float, Polygon]]:
        polygons = []
        for c in contours:
            if not c.is_closed or len(c.points) < 4:
                continue
            try:
                poly = Polygon(c.points)
            except Exception:
                continue
            if poly.is_valid and poly.area > 0:
                polygons.append((c.elevation, poly))
        return polygons

    def _build_containment_tree(self, closed_polygons: list[tuple[float, Polygon]]):
        """For each polygon, find its immediate parent: the smallest-area
        polygon (of any elevation) that fully contains it. Spatial index
        (STRtree) keeps this fast even with thousands of rings."""
        n = len(closed_polygons)
        geoms = [poly for _, poly in closed_polygons]
        index = STRtree(geoms)

        parent_of: list[int | None] = [None] * n
        children_of: list[list[int]] = [[] for _ in range(n)]

        for i in range(n):
            poly_i = geoms[i]
            best_parent, best_area = None, None
            for j in index.query(poly_i):
                j = int(j)
                if j == i:
                    continue
                poly_j = geoms[j]
                if poly_j.area <= poly_i.area:
                    continue
                if poly_j.contains(poly_i):
                    if best_area is None or poly_j.area < best_area:
                        best_area, best_parent = poly_j.area, j
            parent_of[i] = best_parent
            if best_parent is not None:
                children_of[best_parent].append(i)

        return parent_of, children_of

    def _find_basins(self, closed_polygons, parent_of, children_of) -> list[Basin]:
        n = len(closed_polygons)
        leaves = [i for i in range(n) if not children_of[i]]

        basins: list[Basin] = []
        for leaf in leaves:
            parent = parent_of[leaf]
            if parent is None:
                continue  # isolated ring with no surrounding context — can't classify
            leaf_elev, leaf_poly = closed_polygons[leaf]
            parent_elev, _ = closed_polygons[parent]
            if parent_elev <= leaf_elev:
                continue  # elevation decreases outward -> this is a hilltop, not a basin

            catchment_idx = self._walk_up_to_catchment_boundary(
                leaf, parent_of, children_of, closed_polygons
            )
            catchment_elev, catchment_poly = closed_polygons[catchment_idx]

            centroid = leaf_poly.centroid
            basins.append(
                Basin(
                    pit_elevation_m=leaf_elev,
                    catchment_elevation_m=catchment_elev,
                    pit_centroid_lon=centroid.x,
                    pit_centroid_lat=centroid.y,
                    pit_area_m2=_geodesic_area_m2(leaf_poly),
                    catchment_area_m2=_geodesic_area_m2(catchment_poly),
                    catchment_boundary_geojson=mapping(catchment_poly),
                )
            )
        return basins

    def _walk_up_to_catchment_boundary(
        self, leaf_idx, parent_of, children_of, closed_polygons
    ) -> int:
        """Walk outward from the pit through parent rings while elevation
        keeps increasing and the parent has exactly one child (no branch
        into a separate sub-basin). Returns the index of the outermost
        polygon still uniquely associated with this basin."""
        node = leaf_idx
        while True:
            parent = parent_of[node]
            if parent is None:
                break
            node_elev, _ = closed_polygons[node]
            parent_elev, _ = closed_polygons[parent]
            if parent_elev <= node_elev:
                break
            if len(children_of[parent]) > 1:
                break  # drainage divide: parent also encloses a separate basin
            node = parent
        return node
