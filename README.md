# Village Pond Planning System — Phase 2: Pond Catchment Analysis Backend

Phase 2 report (approach, API docs, demonstration output): [`docs/phase2_report.md`](docs/phase2_report.md)

## What's new in Phase 2

| File | Purpose |
|---|---|
| `backend/app/core/kml_parser.py` | Parses KML/KMZ into contour lines, generalized beyond this sample file's schema |
| `backend/app/core/contour_basin_analyzer.py` | The core algorithm: basin detection + catchment delineation from contour topology |
| `backend/app/api/contour.py` | `POST /api/analyzeContour` (+ `/api/findCatchment` alias) |
| `backend/tests/test_contour_analysis.py` | Unit tests on synthetic fixtures (basin, hill, saddle-point cases) |
| `data/sample_contours/contours_1m.kml` | The provided sample contour map, used for development and demonstration |

## Why this builds on, not replaces, Phase 1

The layering established in Phase 1 (`api/` → `core/` → `schemas.py`) carries over unchanged — `contour.py` is a thin route handler, all the actual logic lives in `core/`. `RunoffCalculator` and `PondSizer` from Phase 1 are untouched and still importable; a future phase could feed a basin's `catchment_area_m2` from this endpoint directly into `RunoffCalculator.compute()` to go from "here's a catchment" to "here's the recommended pond depth" in one pipeline — the two modules were already designed to compose this way.

## Running it

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Try it against the sample file:
```bash
curl -X POST "http://localhost:8000/api/analyzeContour" \
  -F "file=@data/sample_contours/contours_1m.kml"
```

Interactive docs: `http://localhost:8000/docs`

## Running tests

```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

12 tests, all passing: 7 for the new contour/basin logic (using small synthetic KML fixtures, not the large sample file, so they run in milliseconds), 5 carried over from Phase 1.

## Before you submit

1. Push this to a GitHub repo and add the link to `docs/phase2_report.md` (Section 1).
2. Fill in the actual API URL you'll demo with (Section 2) — localhost is fine for a lab demo.
3. Be ready to explain, live: why contour-topology containment was used instead of raster flow-accumulation, and what the saddle-point stopping condition does — these are the two things most likely to get probed.
