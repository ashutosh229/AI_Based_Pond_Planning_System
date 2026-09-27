from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_run_store
from app.core.run_store import RunStore, RunStoreError

router = APIRouter(prefix="/api", tags=["run-history"])


@router.get("/runs")
async def list_runs(
    limit: int = 20, mode: str | None = None, store: RunStore = Depends(get_run_store)
):
    return await store.list_runs(limit=limit, mode=mode)


@router.get("/runs/{run_id}")
async def get_run(run_id: str, store: RunStore = Depends(get_run_store)):
    try:
        return await store.get_run(run_id)
    except RunStoreError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
