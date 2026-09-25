# AI-Based Village Pond Planning System

A geospatial decision-support tool for identifying and sizing rainwater-harvesting ponds in rural/hilly terrain. Given either a contour map or a freeform area drawn on a map, the system finds natural depressions (basins) suitable for a pond, delineates each basin's catchment area from contour topology, looks up historical rainfall for the recommended site, and turns that into a recommended pond depth, storage volume, and feasibility verdict.

**Repository:** https://github.com/ashutosh229/AI_Based_Pond_Planning_System
<br>
**License:** MIT (see [`LICENSE`](LICENSE))
<br>
**Author:** Ashutosh Kumar Jha

Full Phase 2 write-up (approach, algorithm walkthrough, demonstration output): [`docs/phase2_report.md`](docs/phase2_report.md)

### Phase 3 — what changed

Phase 2 only accepted a pre-made KML/KMZ contour export. Phase 3 adds a second, primary input path — **drawing a freeform area directly on the map** — and composes the previously-unwired Phase 1 modules (`RunoffCalculator`, `PondSizer`) onto the Phase 2 basin analysis so every request returns all three required results in one response: **suggested pond location, catchment area, and expected water volume**.

- **`POST /api/analyzeArea`** — a freeform polygon in, a full recommendation out. Elevation is sampled over the polygon's bounding box from [OpenTopoData](https://www.opentopodata.org/) (SRTM 30m), contours are extracted from that sampled surface via marching squares (`app/core/area_contour_builder.py`), and from there it reuses the exact same `ContourBasinAnalyzer` Phase 2 already had.
- **`POST /api/recommendPond`** — the KML/KMZ upload flow, now also composed with rainfall + runoff + pond sizing (previously `RunoffCalculator`/`PondSizer` existed but had no route wiring them up — this was the Phase 2 roadmap's top item).
- Both routes share one pipeline (`app/core/pond_pipeline.py`), so the map-drawn and KML-upload input modes are functionally identical from the recommended-site onward, and both return a `timings_ms` breakdown of every step (elevation fetch, contour extraction, basin analysis, rainfall lookup, pond sizing) for reproducible performance figures.
- The frontend now offers a mode toggle: **draw an area** (Leaflet-Geoman freeform polygon tool) or **upload KML/KMZ** — both feed the same results view, with the pond's water-volume recommendation now shown alongside the catchment map.
- `POST /api/analyzeContour` is unchanged and kept for backward compatibility (contour/basin analysis only, no rainfall/sizing, no external API calls).

---

## Table of Contents

- [What this project does](#what-this-project-does)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Repository layout](#repository-layout)
- [Getting started](#getting-started)
  - [Backend](#backend)
  - [Frontend](#frontend)
- [Configuration](#configuration)
- [API Reference](#api-reference)
  - [`GET /health`](#get-health)
  - [`POST /api/analyzeContour`](#post-apianalyzecontour)
  - [`POST /api/findCatchment`](#post-apifindcatchment)
  - [`POST /api/recommendPond`](#post-apirecommendpond)
  - [`POST /api/analyzeArea`](#post-apianalyzearea)
- [The catchment-detection algorithm](#the-catchment-detection-algorithm)
- [Freeform area analysis (elevation sampling → contours)](#freeform-area-analysis-elevation-sampling--contours)
- [Phase 1 core modules (runoff & pond sizing)](#phase-1-core-modules-runoff--pond-sizing)
- [Frontend application](#frontend-application)
- [Testing](#testing)
- [Demonstration](#demonstration)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)
- [License](#license)

---

## What this project does

Villages in hilly terrain often need small check-dams or farm ponds to capture monsoon runoff. Picking a site by eye is error-prone: a good pond site needs (a) a natural low point to hold water and (b) a large enough upstream catchment to fill it. This project automates that site selection from either a contour map or a freeform area drawn on a map:

1. **Provide an area to analyze** — either **draw a freeform polygon on the map** (elevation is sampled live from an elevation API), or **upload a contour map** (KML/KMZ — the format exported by most GIS/survey tools).
2. The backend **detects closed contour rings**, builds a **containment hierarchy**, and classifies each nested low point as a genuine basin (vs. a hilltop or digitisation noise) — identical logic for both input paths.
3. For every basin, it **delineates the catchment** — the contour ring up to which water draining toward that pit is bounded — and computes the catchment's real-world area on the WGS84 ellipsoid.
4. Basins are **ranked by catchment area**, and the top candidate plus up to 5 runner-ups are returned with GeoJSON boundaries for mapping.
5. For the recommended site, historical rainfall is looked up automatically and fed through **`RunoffCalculator`/`PondSizer`** to produce a recommended pond depth, storage volume, and feasibility verdict — so every request returns all three required results: **suggested pond location, catchment area, and expected water volume.**
6. A **React/Leaflet frontend** lets you draw an area or drag-and-drop a contour file, browse ranked candidates, see each catchment boundary and the water-volume recommendation, and view everything on an interactive map.

## Architecture

<p align="center">
  <img src="docs/village_pond_architecture.svg" alt="System Architecture" width="900">
</p>

The layering is intentionally strict: `api/` contains only route handlers, all algorithmic logic lives in `core/`, and request/response contracts live in `schemas.py`. This keeps the analysis logic unit-testable without spinning up FastAPI or touching HTTP at all.

## Tech stack

| Layer                 | Technology                                                                                               |
| --------------------- | -------------------------------------------------------------------------------------------------------- |
| Backend framework     | FastAPI + Uvicorn                                                                                        |
| Geometry / geospatial | Shapely (planar geometry, containment), Pyproj (geodesic area on WGS84), Shapely STRtree (spatial index) |
| KML/KMZ parsing       | lxml (namespace-agnostic XML walking), zipfile                                                           |
| Config                | pydantic-settings (`.env`-driven)                                                                        |
| Testing               | pytest, httpx                                                                                            |
| Frontend framework    | React 18 + Vite                                                                                          |
| Mapping               | Leaflet + react-leaflet                                                                                  |
| Styling               | Hand-written CSS (dark theme, CSS custom properties)                                                     |

## Repository layout

```
backend/
  app/
    api/
      contour.py            POST /api/analyzeContour (+ /api/findCatchment alias)
    core/
      kml_parser.py          KML/KMZ → ContourLine[]
      contour_basin_analyzer.py   Basin detection + catchment delineation
      runoff.py               RunoffCalculator (Phase 1)
      pond_sizing.py           PondSizer (Phase 1)
    main.py                  FastAPI app, CORS, router registration
    config.py                pydantic-settings Settings (env-driven)
    schemas.py                Pydantic request/response models
  tests/
    test_contour_analysis.py  Basin/hill/saddle-point unit tests on synthetic KML
    test_runoff.py            RunoffCalculator unit tests
    test_pond_sizing.py       PondSizer unit tests
  requirements.txt
data/
  sample_contours/contours_1m.kml   Sample village contour export used for dev + demo
frontend/
  src/
    api.js                    fetch wrapper for /api/analyzeContour
    App.jsx / App.css         Layout, dark-theme styling
    components/
      FileUpload.jsx           Drag-and-drop KML/KMZ picker
      ResultsSummary.jsx       Parse stats (interval, elevation range, contour counts)
      BasinList.jsx            Ranked candidate list with area/depth stats
      MapView.jsx               Leaflet map: catchment polygons + pit markers
  vite.config.js               Dev-server proxy to the deployed backend
docs/
  phase2_report.md            Full write-up: approach, algorithm, demo output, API docs
README.md
LICENSE
```

## Getting started

### Backend

**Prerequisites:** Python 3.10+ (uses `X | None` union syntax and `dataclass` features).

#### Local machine

```bash
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

The API is now available at `http://localhost:8001`, with interactive Swagger docs at `http://localhost:8001/docs`.

#### Remote SSH lab systems

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

`--host 0.0.0.0` is required so the server is reachable from outside the SSH host.

#### Try it against the sample file

```bash
curl -X POST "http://10.1.75.79:3205/api/analyzeContour" \
  -F "file=@data/sample_contours/contours_1m.kml"
```

Interactive docs (deployed instance): `http://10.1.75.79:3205/docs`
<br>
Local docs: replace the host/port above with wherever you started Uvicorn.

> Both `10.1.75.79:3205` URLs referenced throughout this README and `docs/phase2_report.md` are the currently deployed instance used for grading/demo. Swap in `localhost:<port>` for local development.

### Frontend

**Prerequisites:** Node.js 18+.

```bash
cd frontend
npm install
```

Create a `.env` file in `frontend/` pointing at your backend (the app reads `VITE_API_BASE_URL` directly — it does not use the `vite.config.js` dev proxy for its own fetches):

```bash
# frontend/.env
VITE_API_BASE_URL=http://10.1.75.79:3205
# or, for a locally running backend:
# VITE_API_BASE_URL=http://localhost:8001
```

Then run the dev server:

```bash
npm run dev
```

Open the printed local URL (default `http://localhost:5173`), drag a `.kml`/`.kmz` file onto the upload panel, and the ranked basin candidates will render on the map.

Production build:

```bash
npm run build
npm run preview
```

## Configuration

All backend configuration is centralized in [`app/config.py`](backend/app/config.py) via `pydantic-settings`, overridable through a `backend/.env` file or environment variables:

| Setting                      | Default                                                         | Purpose                                                                                                                                                                           |
| ---------------------------- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app_name`                   | `Village Pond Planning System`                                  | FastAPI app title                                                                                                                                                                 |
| `database_url`               | `postgresql://pond_user:pond_pass@localhost:5432/pond_planning` | Reserved for village/rainfall persistence (Phase 1 scope; not exercised by the current contour-analysis endpoint)                                                                 |
| `open_meteo_base_url`        | `https://archive-api.open-meteo.com/v1/archive`                 | Historical rainfall source (Phase 1)                                                                                                                                              |
| `elevation_api_base_url`     | `https://api.opentopodata.org/v1/srtm30m`                       | Elevation lookup fallback (Phase 1)                                                                                                                                               |
| `default_runoff_coefficient` | `0.3`                                                           | Default input to `RunoffCalculator`                                                                                                                                               |
| `default_capture_fraction`   | `0.2`                                                           | Default input to `RunoffCalculator`                                                                                                                                               |
| `default_loss_factor`        | `0.15`                                                          | Default input to `PondSizer`                                                                                                                                                      |
| `min_basin_depth_m`          | `2.0`                                                           | Minimum (catchment elevation − pit elevation) for a depression to count as a real basin candidate rather than digitisation noise. Directly affects `/api/analyzeContour` results. |
| `area_max_grid_points`       | `256`                                                           | Target elevation-sample grid size for `/api/analyzeArea` (bounds accuracy vs. # of API calls)                                                                                    |
| `area_grid_min_side`/`area_grid_max_side` | `9` / `20`                                         | Clamp on the grid's side length regardless of `area_max_grid_points`                                                                                                              |
| `area_contour_levels`        | `15`                                                            | Target number of contour levels extracted from the sampled DEM grid                                                                                                               |
| `area_max_size_km2`          | `5.0`                                                           | Drawn-area size cap — larger areas get too coarse a grid to be meaningful at the fixed sample count                                                                              |
| `area_min_size_m2`           | `500.0`                                                         | Drawn-area minimum size — below this there's nothing to build a grid from                                                                                                          |
| `elevation_chunk_size`       | `100`                                                           | Points per OpenTopoData request (its public-instance limit)                                                                                                                       |
| `elevation_request_delay_s`  | `1.0`                                                           | Delay between elevation-fetch chunks, to respect OpenTopoData's rate limit                                                                                                        |
| `rainfall_years`             | `10`                                                            | Years of Open-Meteo daily history averaged into an annual rainfall figure                                                                                                          |

## API Reference

Base URL below is the deployed instance; substitute your own host/port for local runs.

### `GET /health`

Liveness check.

```json
{ "status": "ok", "app": "Village Pond Planning System" }
```

### `POST /api/analyzeContour`

Accepts a contour map and returns ranked candidate pond sites with catchment estimates.

**Request:** `multipart/form-data`

| Field  | Type | Required | Description                              |
| ------ | ---- | -------- | ---------------------------------------- |
| `file` | file | yes      | Contour map, `.kml` or `.kmz`, max 25 MB |

**Example:**

```bash
curl -X POST "http://10.1.75.79:3205/api/analyzeContour" \
  -F "file=@data/sample_contours/contours_1m.kml"
```

**Response `200 OK`:**

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
    "catchment_boundary_geojson": {
      "type": "Polygon",
      "coordinates": [
        [
          /* ... */
        ]
      ]
    }
  },
  "alternative_sites": [
    /* up to 5 more BasinCandidate objects */
  ],
  "notes": "Detected contour interval: 1 m. 1127 closed contour rings were usable out of 1355 total contour lines parsed (open contours that touch the map boundary are excluded from basin detection since containment can't be determined for them). Basins shallower than 2 m were filtered out as likely digitisation noise."
}
```

**Error responses:**

| Status | Meaning                                                               |
| ------ | --------------------------------------------------------------------- |
| `400`  | File extension isn't `.kml`/`.kmz`                                    |
| `413`  | File exceeds 25 MB                                                    |
| `422`  | File couldn't be parsed as a contour map (no usable Placemarks found) |

### `POST /api/findCatchment`

Identical alias for `/api/analyzeContour`, provided to match the assignment's alternate suggested route name. Hidden from the OpenAPI schema (`include_in_schema=False`) but fully functional.

### `POST /api/recommendPond`

Same input as `/api/analyzeContour` (a KML/KMZ upload), but returns the full Phase 3 recommendation: basin/catchment info **plus** rainfall-derived pond sizing.

**Request:** `multipart/form-data` — identical to `/api/analyzeContour` (`file`, `.kml`/`.kmz`, max 25 MB).

**Response `200 OK`:** a `PondPlanningResult` — see [`/api/analyzeArea`](#post-apianalyzearea) below for the shape; the only difference is `"source"` holds the uploaded filename instead of a drawn-area description, and there's a `kml_parse_ms` entry in `timings_ms` instead of `elevation_fetch_ms`/`contour_extraction_ms`.

### `POST /api/analyzeArea`

The Phase 3 entry point for the map's freeform draw tool: a polygon in, a full recommendation out. Elevation is sampled over the polygon's bounding box (with a small margin) rather than clipped exactly to the drawn outline — see [Known limitations](#known-limitations).

**Request:** `application/json`

```json
{ "polygon": [[81.302, 21.255], [81.306, 21.255], [81.306, 21.259], [81.302, 21.259]] }
```

| Field     | Type                | Required | Description                                                    |
| --------- | ------------------- | -------- | ---------------------------------------------------------------- |
| `polygon` | `[[lon, lat], ...]` | yes      | Freeform ring, ≥3 vertices. Not required to be explicitly closed. |

**Response `200 OK`:** a `PondPlanningResult`:

```json
{
  "source": "drawn area (~1.15 km², 256 elevation samples)",
  "contour_interval_m": 25.0,
  "elevation_range_m": [276.6, 551.6],
  "total_contours_parsed": 27,
  "closed_contours_used": 7,
  "candidate_basins_found": 1,
  "recommended_site": { /* same BasinCandidate shape as /api/analyzeContour */ },
  "alternative_sites": [ /* up to 5 more */ ],
  "pond_recommendation": {
    "annual_rainfall_m": 1.1,
    "rainfall_years_used": 10,
    "rainfall_source": "Open-Meteo historical archive",
    "annual_runoff_volume_m3": 348529.53,
    "design_storage_volume_m3": 69705.91,
    "usable_volume_m3": 59250.02,
    "recommended_depth_m": 0.38,
    "is_feasible": true,
    "notes": "Within practical depth range."
  },
  "notes": "...",
  "timings_ms": {
    "elevation_fetch_ms": 812.4,
    "contour_extraction_ms": 41.2,
    "basin_analysis_ms": 6.8,
    "rainfall_lookup_ms": 340.1,
    "pond_sizing_ms": 0.1
  }
}
```

`pond_recommendation` is `null` when no basin met `min_basin_depth_m`, or when the rainfall lookup failed (in which case `notes` explains why — basin/catchment info is still returned either way).

**Error responses:**

| Status | Meaning                                                                                  |
| ------ | ----------------------------------------------------------------------------------------- |
| `400`  | Polygon has fewer than 3 points, or the drawn area is outside `area_min_size_m2`/`area_max_size_km2` |
| `422`  | Sampled terrain is too flat to contain a detectable basin                                 |
| `502`  | The elevation or rainfall upstream API couldn't be reached or returned unusable data       |

## The catchment-detection algorithm

Full narrative version with rationale: [`docs/phase2_report.md`](docs/phase2_report.md#3-approach--how-catchment-estimation-works).

Phase 2's input is a set of **vector contour lines**, not a DEM raster — so rather than approximating a raster and running D8 flow-accumulation, the algorithm works directly on contour **topology**:

1. **Parse** the KML/KMZ into contour lines — each with an elevation and an ordered list of `(lon, lat)` points, flagged `closed` (a full ring) or `open` (clipped by the map boundary). Elevation is read from `<name>` first, falling back to common `ExtendedData` field names (`elevation`, `elev`, `height`, `contour`, `value`, `z`).
2. **Build closed contour polygons.** Only closed rings can be tested for containment, so open (boundary-clipped) contours are excluded from basin detection — this is called out explicitly in the response `notes`.
3. **Build a containment tree.** For every polygon, find its immediate parent: the smallest-area polygon (of any elevation) that fully contains it, using a `shapely.strtree.STRtree` spatial index instead of brute-force O(n²) containment checks.
4. **Classify basins vs. hills.** A _leaf_ polygon (nothing nested inside it) whose parent sits at a **higher** elevation is the bottom of a natural depression — a basin. If the parent is at a **lower** elevation, the leaf is a hilltop and is discarded.
5. **Delineate the catchment.** Starting at the pit, walk outward through parent rings while elevation keeps increasing. The walk stops at the first ring containing **more than one** nested basin — a drainage divide (saddle point) where two valleys meet — so it can't belong to a single catchment. The last valid ring before that point is the catchment boundary.
6. **Rank candidates** by catchment area (descending), after filtering out basins shallower than `min_basin_depth_m` (default 2 m).
7. **Rank 1 is the recommendation**; the response also returns up to 5 runner-ups.

Area is computed with `pyproj.Geod.polygon_area_perimeter` directly on WGS84 lon/lat — this avoids both the distortion of computing area from raw degree coordinates and the need to guess a UTM zone for projection.

**Generalization:** the KML parser doesn't depend on the sample file's specific folder structure (`lines`/`labels`) — it walks the whole document for the general `Placemark` → `LineString` → elevation pattern used by most contour-export tools (e.g. `gdal_contour`), and the contour interval is auto-detected from the data (most common gap between consecutive elevation levels) rather than assumed.

**Stated limitation:** this treats "catchment" as the area enclosed by contour rings, not a true hydrological watershed derived from slope/aspect on a raster surface. It's a defensible geometric approximation for reasonably dense contour data over hilly terrain (the sample map: 1 m interval, ~31 m of relief) but is less reliable on very flat terrain where contours are sparse.

## Freeform area analysis (elevation sampling → contours)

`/api/analyzeArea` (`app/core/area_contour_builder.py`) makes a drawn polygon usable by the same `ContourBasinAnalyzer` above, without a KML file:

1. **Sample a regular grid** over the polygon's bounding box (padded by a small margin), sized by `area_max_grid_points` (default 256, clamped to a 9×9–20×20 side range).
2. **Fetch elevation per grid point** from OpenTopoData (`ElevationService`), chunked to its request-size limit and rate-limited between chunks.
3. **Fill gaps** (points with no DEM coverage — usually water) via nearest-neighbour interpolation (`scipy.interpolate.griddata`) so the grid is fully populated before contouring.
4. **Choose a contour interval**: the sampled elevation range divided into `area_contour_levels` (default 15) target levels, snapped to a "nice" step (0.5 / 1 / 2 / 5 / 10 m, ...). An area with less than 0.5 m of sampled relief is rejected (`TerrainTooFlatError`, surfaced as a `422`) rather than producing meaningless contours.
5. **Extract contours via marching squares** (`skimage.measure.find_contours`) at each level, mapping pixel (row, col) coordinates back to (lon, lat). A contour path that touches the sampled grid's edge is flagged `is_closed=False` — the same semantic as a KML contour clipped by the map boundary — so it's correctly excluded from basin containment.
6. The resulting `ContourLine` list is handed to the same `ContourBasinAnalyzer.analyze()` Phase 2 already had — **no changes to the basin/catchment logic itself.**

**Stated limitation:** terrain is sampled over the polygon's *bounding box*, not clipped exactly to the hand-drawn outline, so the reported catchment can extend slightly past what was drawn (this is also stated in the response's `notes`). Grid resolution is fixed by `area_max_grid_points` regardless of the drawn area's shape, so a very elongated polygon samples less densely along its long axis than a square one of the same area — `area_max_size_km2` exists specifically to keep this from degrading too far.

## Phase 1 core modules (runoff & pond sizing) — now wired up

`RunoffCalculator` and `PondSizer` were fully built and unit-tested in Phase 1 but had no route wiring them up. Phase 3's `app/core/pond_pipeline.py` composes them onto the Phase 2 recommended basin, for both input modes:

- **`RunoffCalculator`** (`app/core/runoff.py`) — turns `catchment_area_m2` + `annual_rainfall_m` + `runoff_coefficient` into an annual runoff volume, then applies a `capture_fraction` to get a design storage volume. Also exposes a rational-method `peak_flow_m3_per_s` helper.
- **`PondSizer`** (`app/core/pond_sizing.py`) — turns a design storage volume + available surface area + `loss_factor` into a usable volume and a recommended pond depth, flagging infeasibility if the required depth falls outside a practical 0.5–4.0 m range.
- **`RainfallService`** (`app/core/rainfall_service.py`, new in Phase 3) — supplies `annual_rainfall_m` automatically from Open-Meteo's historical archive for the recommended site, so no manual rainfall input is needed.

`/api/recommendPond` and `/api/analyzeArea` both return this as `pond_recommendation` in their response; it's `null` if no basin was found or the rainfall lookup failed (basin/catchment info is still returned either way, and `notes` explains what happened).

## Frontend application

A single-page React app (`frontend/src/App.jsx`) with a mode toggle between the two input paths, and five components:

- **Mode toggle** — "Draw area on map" (default) vs. "Upload KML / KMZ", switching which input control is shown and which endpoint gets called (`analyzeArea` vs. `recommendPond`).
- **`FileUpload`** — drag-and-drop or click-to-browse picker, restricted to `.kml`/`.kmz`, used in KML mode.
- **`ResultsSummary`** — parse-level stats: contour interval, elevation range, total/closed contour counts, candidate basin count, the backend's `notes` string, and (new) the per-step `timings_ms` breakdown.
- **`PondRecommendationCard`** (new) — rainfall, runoff volume, storage volume, recommended depth, and feasibility verdict from `pond_recommendation`.
- **`BasinList`** — scrollable, clickable ranked list of candidate sites (pit elevation, basin depth, pond footprint, catchment area), synced to map selection.
- **`MapView`** — Leaflet map rendering every candidate's `catchment_boundary_geojson` as a colored polygon plus a pit marker, **plus** (in area mode) a [Leaflet-Geoman](https://geoman.io/leaflet-geoman) freeform polygon draw tool in the top-left, so the user's drawn area and the analysis results share one map instance. Clicking a polygon or list entry highlights the same site in both places, and the map auto-fits bounds to the returned catchments.

Dark theme is implemented with CSS custom properties in `App.css` (`--bg`, `--panel`, `--accent`, etc.) rather than a UI framework, keeping the bundle small.

## Testing

```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

**28 tests, all passing:**

- **7** for the Phase 2 contour/basin logic (`test_contour_analysis.py`), run against small synthetic KML fixtures built in-test (not the large sample file, so they execute in milliseconds):
  - Parses closed contour lines correctly
  - Rejects a file with no usable contours
  - Detects a single nested basin with the correct catchment boundary
  - Correctly rejects a hill (elevation increasing inward) as a non-basin
  - Correctly stops the catchment walk-up at a saddle point shared by two basins
  - Respects `min_basin_depth_m` filtering
  - Ranks basins by catchment area, descending
- **5** carried over from Phase 1 (`test_runoff.py`, `test_pond_sizing.py`) covering `RunoffCalculator` and `PondSizer`.
- **6** for the elevation and rainfall services (`test_elevation_service.py`, `test_rainfall_service.py`), each against an injected `httpx.MockTransport` rather than the real network — chunking/ordering, missing-data handling, and HTTP-error propagation.
- **6** for the area-to-contour pipeline (`test_area_contour_builder.py`) — grid sizing/clamping, missing-elevation interpolation, the flat-terrain rejection, and a synthetic paraboloid "bowl" surface that must produce a closed contour near its minimum.
- **3** for the composed pipeline (`test_pond_pipeline.py`) — a found basin producing a full `pond_recommendation` with all timing keys present, graceful degradation when the rainfall lookup fails (basin data still returned), and no rainfall lookup being attempted when no basin was found at all.

Async tests use `pytest.mark.anyio` (see `tests/conftest.py`); no real network calls are made by the test suite.

## Demonstration

Run against the provided sample map, `data/sample_contours/contours_1m.kml`:

| Metric                               | Value       |
| ------------------------------------ | ----------- |
| Contour lines parsed                 | 1,355       |
| Closed contours used                 | 1,127       |
| Contour interval (auto-detected)     | 1 m         |
| Elevation range                      | 267 – 298 m |
| Candidate basins found (depth ≥ 2 m) | 56          |

**Recommended site (Rank 1):**

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

## Known limitations

- **Not a true hydrological watershed.** Catchments are the area enclosed by contour rings, not a slope/aspect-derived drainage basin — an acceptable approximation on hilly terrain with reasonably dense contours, weaker on flat terrain with sparse contours.
- **Open (boundary-clipped) contours are excluded** from basin detection, since containment can't be determined for a ring that doesn't close. This can under-count basins near the edge of a survey area or a sampled bounding box; the response `notes` field states how many contours were excluded this way.
- **Drawn areas are analyzed over their bounding box**, not clipped exactly to the hand-drawn outline — the reported catchment can extend slightly past what was drawn (also stated in `notes`).
- **Elevation-grid resolution is capped** (`area_max_grid_points`, default 256) to bound the number of OpenTopoData calls per request — a coarser grid finds fewer/less-precise basins than the 1m-interval KML sample file does. Larger drawn areas get proportionally coarser sampling, which is why `area_max_size_km2` exists.
- **Rainfall averaging assumes complete daily data** for the requested years — a location with data gaps in Open-Meteo's archive will slightly under-count its annual total (the total is divided by the full year count, not the count of days actually returned).
- **CORS is fully open** (`allow_origins=["*"]`) — fine for a lab/demo deployment, not intended for production as-is.
- **No persistence layer is active** — `database_url` is configured but no models/migrations exist yet; results are computed per-request and not stored. `timings_ms` on every response is the current substitute for a stored performance history.
- **Single backend instance, no load balancing** — deliberate for now; the pipeline is stateless (no in-memory session or metrics store) specifically so this can be split across multiple instances later without a code change.

## Roadmap

- ~~Wire a route that composes contour analysis → `RunoffCalculator` → `PondSizer` into one call~~ — done (`/api/recommendPond`, `/api/analyzeArea`, `app/core/pond_pipeline.py`).
- ~~Pull historical rainfall automatically from the site's coordinates instead of requiring `annual_rainfall_m` as manual input~~ — done (`RainfallService`).
- ~~Add elevation lookup for sites without a contour map~~ — done (`ElevationService` + `area_contour_builder.py`, via `/api/analyzeArea`).
- Persist analysis runs (drawn area / source file, chosen basin, pond recommendation) via the reserved `database_url`, so past requests don't need to be re-run for the report.
- Clip the sampled/generated contours to the exact hand-drawn polygon rather than its bounding box.
- Load-balance the backend across the course's allocated systems once the single-instance deployment needs to scale (the pipeline is already stateless to allow this).

## License

MIT — see [`LICENSE`](LICENSE). Copyright (c) 2026 Ashutosh Kumar Jha.
