"""
SQLite REST Database Server — Village Pond Planning System
============================================================
Persists each completed pond-planning analysis run (from either
/api/analyzeArea or /api/recommendPond) so past requests don't need to
be re-run. This implements the README's roadmap item:
  "Persist analysis runs (drawn area / source file, chosen basin, pond
   recommendation) via the reserved database_url."

Endpoints:
  POST   /runs            — insert a completed analysis run
  GET    /runs?limit=&mode=  — list run summaries, newest-first
  GET    /runs/{run_id}   — fetch one run's full stored payload
  GET    /health           — liveness probe

Environment variables:
  SQLITE_DB_PATH   — path to the SQLite file  (default: pond_runs.db)
  DB_SERVER_PORT   — port to listen on        (default: 5000)

Concurrency: WAL mode allows unlimited concurrent readers while a
single writer is active, so the lock below only guards INSERTs.
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

DB_PATH = os.environ.get("SQLITE_DB_PATH", "pond_runs.db")
PORT = int(os.environ.get("DB_SERVER_PORT", "5000"))

_write_lock = threading.Lock()
_conn: sqlite3.Connection = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _conn.execute("PRAGMA cache_size=-32000")
        _conn.commit()
    return _conn


def _init_schema() -> None:
    with _write_lock:
        conn = _get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id                          TEXT PRIMARY KEY,
                mode                        TEXT    NOT NULL,      -- "kml" | "area"
                source                      TEXT    NOT NULL,      -- filename or drawn-area label
                created_at                  INTEGER NOT NULL,
                contour_interval_m          REAL,
                elevation_min_m             REAL,
                elevation_max_m             REAL,
                candidate_basins_found      INTEGER,
                recommended_catchment_area_m2 REAL,
                is_feasible                 INTEGER,               -- 0/1/NULL
                result_json                 TEXT    NOT NULL        -- full PondPlanningResult
            );
            CREATE INDEX IF NOT EXISTS idx_runs_created_at
                ON runs (created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_runs_mode
                ON runs (mode, created_at DESC);
        """)
        conn.commit()
    print(f"[db_server] SQLite database ready: {os.path.abspath(DB_PATH)}")


app = FastAPI(title="Pond Planning DB Server", version="1.0")


class RunIn(BaseModel):
    mode: str
    source: str
    contour_interval_m: Optional[float] = None
    elevation_min_m: Optional[float] = None
    elevation_max_m: Optional[float] = None
    candidate_basins_found: Optional[int] = None
    recommended_catchment_area_m2: Optional[float] = None
    is_feasible: Optional[bool] = None
    result: dict[str, Any]  # the full PondPlanningResult, as JSON


@app.post("/runs", status_code=201)
def create_run(run: RunIn):
    run_id = str(uuid.uuid4())
    created_at = int(time.time())
    with _write_lock:
        conn = _get_conn()
        conn.execute(
            """
            INSERT INTO runs
                (id, mode, source, created_at, contour_interval_m,
                 elevation_min_m, elevation_max_m, candidate_basins_found,
                 recommended_catchment_area_m2, is_feasible, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                run.mode,
                run.source,
                created_at,
                run.contour_interval_m,
                run.elevation_min_m,
                run.elevation_max_m,
                run.candidate_basins_found,
                run.recommended_catchment_area_m2,
                None if run.is_feasible is None else int(run.is_feasible),
                json.dumps(run.result),
            ),
        )
        conn.commit()
    return {"ok": True, "id": run_id, "created_at": created_at}


@app.get("/runs")
def list_runs(limit: int = 20, mode: Optional[str] = None):
    """Summary rows only (no result_json) — kept unlocked, WAL allows
    this to run concurrently with writes."""
    conn = _get_conn()
    cols = """id, mode, source, created_at, contour_interval_m,
              candidate_basins_found, recommended_catchment_area_m2, is_feasible"""
    if mode:
        cursor = conn.execute(
            f"SELECT {cols} FROM runs WHERE mode = ? ORDER BY created_at DESC LIMIT ?",
            (mode, limit),
        )
    else:
        cursor = conn.execute(
            f"SELECT {cols} FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
        )
    rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        r["is_feasible"] = None if r["is_feasible"] is None else bool(r["is_feasible"])
    return rows


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    conn = _get_conn()
    row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    d = dict(row)
    d["result"] = json.loads(d.pop("result_json"))
    d["is_feasible"] = None if d["is_feasible"] is None else bool(d["is_feasible"])
    return d


@app.get("/health")
def health():
    return {"status": "ok", "db": os.path.abspath(DB_PATH)}


if __name__ == "__main__":
    _init_schema()
    print(f"[db_server] Listening on 0.0.0.0:{PORT}")
    uvicorn.run("db_server:app", host="0.0.0.0", port=PORT, log_level="warning")
