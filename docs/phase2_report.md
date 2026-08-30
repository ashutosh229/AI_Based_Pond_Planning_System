# Assignment 1 — Phase 2: Pond Catchment Analysis Backend — Report

## 1. GitHub Rpository

[GitHub Repository](https://github.com/ashutosh229/AI_Based_Pond_Planning_System)

## 2. Working API Route

[Docs](http://localhost:8001/docs)
[Healthcheck API Route](http://localhost:8001/docs#/default/health_check_health_get)
[Contour Analysis API Route](http://localhost:8001/docs#/contour-analysis/analyze_contour_api_analyzeContour_post)

Run locally with:

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## 3. Approach — How Catchment Estimation Works?

### Why not the Raster Flow Accumulation algorithm?

Phase 1's HLD assumed a DEM **raster** and a D8 flow-direction/accumulation algorithm — the standard hydrology approach. Phase 2's actual input is a set of vector **contour lines** (KML), not a raster grid. There is no elevation raster to run flow-accumulation on. Rather than fabricating a fake raster from the contours (lossy and slow), this phase uses an approach that works directly on contour **topology**:

### The Algorithm

1. **Parse** the KML/KMZ into contour lines: each with an elevation and a list of (lon, lat) points, flagged as closed (a full ring) or open (clipped by the map boundary).
2. **Build closed contour polygons** — only closed rings can be tested for containment, so open (boundary-clipped) contours are excluded from basin detection (this is stated explicitly in the API response's `notes` field).
3. **Build a containment tree**: for every polygon, find its immediate parent — the smallest-area polygon that fully contains it (using a spatial index for speed, not brute-force O(n²)).
4. **Classify basins vs hills**: a _leaf_ polygon (nothing nested inside it) whose parent is at a **higher** elevation is the bottom of a natural depression — water collects there. If the parent is at a **lower** elevation, the leaf is a hilltop, not a basin, and is discarded.
5. **Delineate the catchment**: starting at the pit, walk outward through parent rings while elevation keeps increasing. The walk stops at the first ring that contains **more than one** nested basin — that ring is a drainage divide (saddle point) where two separate valleys meet, so it cannot belong to a single catchment. The last valid ring before that point is the catchment boundary.
6. **Rank candidates** by catchment area (descending), after filtering out basins shallower than a configurable threshold (`min_basin_depth_m`, default 2m) to exclude likely digitisation noise from the contour-generation process.
7. The **rank-1 site is the recommendation**; the response also returns up to 5 runner-up sites.

### Stated Limitation

This treats "catchment" as the area enclosed by contour rings, not a true hydrological watershed computed from slope/aspect on a raster surface. It's a defensible geometric approximation for contour data at a reasonable interval over hilly terrain — the sample map (1m contour interval, ~31m of relief) is well-suited to it — but it would be less reliable on very flat terrain where contours are sparse.

### Generalization Aspect

- The KML parser doesn't rely on the sample file's specific folder names (`lines`/`labels`) — it walks the whole document for the general Placemark+LineString+elevation pattern used by most contour-export tools, with a fallback to ExtendedData fields if elevation isn't in `<name>`.
- The contour interval is **auto-detected** from the data (as the most common gap between consecutive elevation levels), not assumed.
- `min_basin_depth_m` is a named, documented parameter, not a magic number buried in logic.
- The algorithm was unit-tested against small synthetic KML fixtures (not just the sample file) — including a basin, a hill (correctly rejected), and two adjacent basins sharing an outer ring (correctly kept separate at the saddle point) — see `backend/tests/test_contour_analysis.py`.

## 4. Demonstration — Actual output on the provided sample map

Run against `data/sample_contours/contours_1m.kml`:

| Metric                              | Value       |
| ----------------------------------- | ----------- |
| Contour lines parsed                | 1355        |
| Closed contours used                | 1127        |
| Contour interval (auto-detected)    | 1 m         |
| Elevation range                     | 267 – 298 m |
| Candidate basins found (depth ≥ 2m) | 56          |

**Recommended Site (Rank 1):**

| Field                        | Value                      |
| ---------------------------- | -------------------------- |
| Location                     | 21.256846° N, 81.302578° E |
| Pit elevation                | 280 m                      |
| Catchment boundary elevation | 288 m                      |
| Basin depth                  | 8 m                        |
| Pond footprint area          | 1,292.7 m²                 |
| Catchment area               | 27,648.1 m² (~2.76 ha)     |

**Top 5 alternative sites:**

| Rank | Pit elev. | Catchment elev. | Depth | Catchment area |
| ---- | --------- | --------------- | ----- | -------------- |
| 2    | 267 m     | 272 m           | 5 m   | 25,708 m²      |
| 3    | 278 m     | 280 m           | 2 m   | 23,525 m²      |
| 4    | 283 m     | 287 m           | 4 m   | 22,955 m²      |
| 5    | 277 m     | 280 m           | 3 m   | 22,106 m²      |

Sample request (curl):

```bash
curl -X POST "http://localhost:8001/api/analyzeContour" \
  -F "file=@data/sample_contours/contours_1m.kml"
```

## 5. API Documentation

### `POST /api/analyzeContour`

Accepts a contour map and returns ranked candidate pond sites with catchment estimates.

**Request**: `multipart/form-data`
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | yes | Contour map, `.kml` or `.kmz`, max 25MB |

**Response** `200 OK`: `application/json`

```json
{
  "source_filename": "contours_1m.kml",
  "contour_interval_m": 1.0,
  "elevation_range_m": [267.0, 298.0],
  "total_contours_parsed": 1355,
  "closed_contours_used": 1127,
  "candidate_basins_found": 56,
  "recommended_site": {
    "rank": 1,
    "site": { "lat": 21.256846, "lon": 81.302578 },
    "pit_elevation_m": 280.0,
    "catchment_boundary_elevation_m": 288.0,
    "basin_depth_m": 8.0,
    "pond_footprint_area_m2": 1292.7,
    "catchment_area_m2": 27648.1,
    "catchment_boundary_geojson": { "type": "Polygon", "coordinates": [ [...] ] }
  },
  "alternative_sites": [ /* up to 5 more BasinCandidate objects */ ],
  "notes": "Detected contour interval: 1 m. 1127 closed contour rings were usable out of 1355 total contour lines parsed ..."
}
```

**Error responses**:
| Status | Meaning |
|---|---|
| `400` | File extension isn't `.kml`/`.kmz` |
| `413` | File exceeds 25MB |
| `422` | File couldn't be parsed as a contour map (no usable Placemarks found) |

An alias route `POST /api/findCatchment` is also registered and behaves identically.
