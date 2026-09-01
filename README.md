# AI-Based Village Pond Planning System

A geospatial decision-support tool for identifying and sizing rainwater-harvesting ponds in rural/hilly terrain. Given a contour map of a village, the system finds natural depressions (basins) suitable for a pond, delineates each basin's catchment area from contour topology, and (via the Phase 1 core modules) can turn a catchment area + rainfall record into a recommended pond depth and feasibility verdict.

**Repository:** https://github.com/ashutosh229/AI_Based_Pond_Planning_System
**License:** MIT (see [`LICENSE`](LICENSE))
**Author:** Ashutosh Kumar Jha

Full Phase 2 write-up (approach, algorithm walkthrough, demonstration output): [`docs/phase2_report.md`](docs/phase2_report.md)

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
- [The catchment-detection algorithm](#the-catchment-detection-algorithm)
- [Phase 1 core modules (runoff & pond sizing)](#phase-1-core-modules-runoff--pond-sizing)
- [Frontend application](#frontend-application)
- [Testing](#testing)
- [Demonstration](#demonstration)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)
- [License](#license)

---

## What this project does

Villages in hilly terrain often need small check-dams or farm ponds to capture monsoon runoff. Picking a site by eye is error-prone: a good pond site needs (a) a natural low point to hold water and (b) a large enough upstream catchment to fill it. This project automates that site selection from a contour map:

1. **Upload a contour map** (KML/KMZ — the format exported by most GIS/survey tools).
2. The backend **detects closed contour rings**, builds a **containment hierarchy**, and classifies each nested low point as a genuine basin (vs. a hilltop or digitisation noise).
3. For every basin, it **delineates the catchment** — the contour ring up to which water draining toward that pit is bounded — and computes the catchment's real-world area on the WGS84 ellipsoid.
4. Basins are **ranked by catchment area**, and the top candidate plus up to 5 runner-ups are returned with GeoJSON boundaries for mapping.
5. A **React/Leaflet frontend** lets you drag-and-drop a contour file, browse ranked candidates, and see each catchment boundary rendered on an interactive map.
6. Separately, **Phase 1 core modules** (`RunoffCalculator`, `PondSizer`) turn a catchment area + annual rainfall into an annual runoff volume, a design storage volume, and a recommended pond depth/feasibility verdict — designed to compose directly with the Phase 2 output (see [Roadmap](#roadmap)).

## Architecture

```
                       ┌─────────────────────────────┐
                       │   Frontend (React + Vite)   │
                       │  Upload → Map → Basin List   │
                       └──────────────┬───────────────┘
                                      │ multipart/form-data
                                      ▼
                       ┌─────────────────────────────┐
                       │   FastAPI app (app/main.py)  │
                       │   CORS-open, single router   │
                       └──────────────┬───────────────┘
                                      │
                        api/contour.py (thin route handler)
                                      │
              ┌───────────────────────┴───────────────────────┐
              ▼                                                ▼
   core/kml_parser.py                             core/contour_basin_analyzer.py
   KML/KMZ → ContourLine[]                          Containment tree → Basin[]
   (elevation + point ring, closed/open)             (basin vs. hill, catchment walk-up)
                                                                │
                                                                ▼
                                                    schemas.py → ContourAnalysisResult
                                                    (JSON response, GeoJSON boundaries)

   ── not yet wired into an API route, used as a library today ──
   core/runoff.py (RunoffCalculator)  ─┐
   core/pond_sizing.py (PondSizer)     ├─ compose: catchment_area_m2 → runoff volume → recommended depth
```

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

## Phase 1 core modules (runoff & pond sizing)

Two modules from Phase 1 remain in the codebase, fully unit-tested, and are designed to compose with Phase 2's output — though no API route currently wires them up (the `villages` router is commented out in `app/main.py`):

- **`RunoffCalculator`** (`app/core/runoff.py`) — turns `catchment_area_m2` + `annual_rainfall_m` + `runoff_coefficient` into an annual runoff volume, then applies a `capture_fraction` to get a design storage volume. Also exposes a rational-method `peak_flow_m3_per_s` helper.
- **`PondSizer`** (`app/core/pond_sizing.py`) — turns a design storage volume + available surface area + `loss_factor` into a usable volume and a recommended pond depth, flagging infeasibility if the required depth falls outside a practical 0.5–4.0 m range.

A future phase could feed a basin's `catchment_area_m2` from `/api/analyzeContour` directly into `RunoffCalculator.compute()` to go from "here's a catchment" to "here's the recommended pond depth" in a single pipeline — the two modules were already designed to compose this way, and `schemas.py` already defines the `PondRecommendationRequest`/`Result` contract for it.

## Frontend application

A single-page React app (`frontend/src/App.jsx`) with four components:

- **`FileUpload`** — drag-and-drop or click-to-browse picker, restricted to `.kml`/`.kmz`.
- **`ResultsSummary`** — parse-level stats: contour interval, elevation range, total/closed contour counts, candidate basin count, and the backend's `notes` string.
- **`BasinList`** — scrollable, clickable ranked list of candidate sites (pit elevation, basin depth, pond footprint, catchment area), synced to map selection.
- **`MapView`** — Leaflet map rendering every candidate's `catchment_boundary_geojson` as a colored polygon plus a pit marker; clicking a polygon or list entry highlights the same site in both places, and the map auto-fits bounds to the returned catchments.

Dark theme is implemented with CSS custom properties in `App.css` (`--bg`, `--panel`, `--accent`, etc.) rather than a UI framework, keeping the bundle small.

## Testing

```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

**12 tests, all passing:**

- **7** for the Phase 2 contour/basin logic (`test_contour_analysis.py`), run against small synthetic KML fixtures built in-test (not the large sample file, so they execute in milliseconds):
  - Parses closed contour lines correctly
  - Rejects a file with no usable contours
  - Detects a single nested basin with the correct catchment boundary
  - Correctly rejects a hill (elevation increasing inward) as a non-basin
  - Correctly stops the catchment walk-up at a saddle point shared by two basins
  - Respects `min_basin_depth_m` filtering
  - Ranks basins by catchment area, descending
- **5** carried over from Phase 1 (`test_runoff.py`, `test_pond_sizing.py`) covering `RunoffCalculator` and `PondSizer`.

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
- **Open (boundary-clipped) contours are excluded** from basin detection, since containment can't be determined for a ring that doesn't close. This can under-count basins near the edge of a survey area; the response `notes` field states how many contours were excluded this way.
- **Phase 1 and Phase 2 aren't wired together yet** — `RunoffCalculator`/`PondSizer` exist and are tested but have no HTTP endpoint in the current snapshot; `catchment_area_m2` from a `BasinCandidate` must currently be passed into them manually.
- **CORS is fully open** (`allow_origins=["*"]`) — fine for a lab/demo deployment, not intended for production as-is.
- **No persistence layer is active** — `database_url` is configured but no models/migrations exist yet; results are computed per-request and not stored.

## Roadmap

- Wire a `POST /api/recommendPond` route that composes `/api/analyzeContour` → `RunoffCalculator` → `PondSizer` into one call, using `PondRecommendationRequest`/`Result` (already defined in `schemas.py`).
- Persist analysis runs (village, source file, chosen basin) via the reserved `database_url`.
- Pull historical rainfall from `open_meteo_base_url` automatically from the site's coordinates instead of requiring `annual_rainfall_m` as manual input.
- Add elevation lookup fallback via `elevation_api_base_url` for sites without a contour map.

## License

MIT — see [`LICENSE`](LICENSE). Copyright (c) 2026 Ashutosh Kumar Jha.
