# Village Pond Planning System — Phase 2: Pond Catchment Analysis Backend

Phase 2 report (approach, API docs, demonstration output): [`docs/phase2_report.md`](docs/phase2_report.md)

## What's new in Phase 2

| File                                         | Purpose                                                                           |
| -------------------------------------------- | --------------------------------------------------------------------------------- |
| `backend/app/core/kml_parser.py`             | Parses KML/KMZ into contour lines, generalized beyond this sample file's schema   |
| `backend/app/core/contour_basin_analyzer.py` | The core algorithm: basin detection + catchment delineation from contour topology |
| `backend/app/api/contour.py`                 | `POST /api/analyzeContour` (+ `/api/findCatchment` alias)                         |
| `backend/tests/test_contour_analysis.py`     | Unit tests on synthetic fixtures (basin, hill, saddle-point cases)                |
| `data/sample_contours/contours_1m.kml`       | The provided sample contour map, used for development and demonstration           |

## Why this builds on, not replaces, Phase 1

The layering established in Phase 1 (`api/` → `core/` → `schemas.py`) carries over unchanged — `contour.py` is a thin route handler, all the actual logic lives in `core/`. `RunoffCalculator` and `PondSizer` from Phase 1 are untouched and still importable; a future phase could feed a basin's `catchment_area_m2` from this endpoint directly into `RunoffCalculator.compute()` to go from "here's a catchment" to "here's the recommended pond depth" in one pipeline — the two modules were already designed to compose this way.

## Running it (On the local machine)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## Running it (On any of the Remote SSH Systems)

```bash
cd backend
pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

Try it against the sample file:

```bash
curl -X POST "http://10.1.75.79:3205/api/analyzeContour" \
  -F "file=@data/sample_contours/contours_1m.kml"
```

Interactive docs: `http://10.1.75.79:3205/docs`

Both of the URLs above are the deployed URLs. If you want to test on the local system, then replace the IP with localhost and port with the port you are running the backend service on.

## Running tests

```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

12 tests, all passing: 7 for the new contour/basin logic (using small synthetic KML fixtures, not the large sample file, so they run in milliseconds), 5 carried over from Phase 1
