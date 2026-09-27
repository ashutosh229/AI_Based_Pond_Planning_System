import httpx
import pytest

from app.core.run_store import RunStore, RunStoreError


def _create_handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/runs"
    body = request.read()
    assert b'"mode"' in body
    return httpx.Response(
        201, json={"ok": True, "id": "fake-run-id", "created_at": 1234567890}
    )


def _error_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, text="db server down")


@pytest.mark.anyio
async def test_save_run_returns_new_id():
    store = RunStore(
        base_url="https://example.test",
        transport=httpx.MockTransport(_create_handler),
    )
    run_id = await store.save_run(
        {"mode": "area", "source": "drawn area", "result": {}}
    )
    assert run_id == "fake-run-id"


@pytest.mark.anyio
async def test_save_run_returns_none_on_http_error_instead_of_raising():
    store = RunStore(
        base_url="https://example.test",
        transport=httpx.MockTransport(_error_handler),
    )
    run_id = await store.save_run({"mode": "kml", "source": "test.kml", "result": {}})
    assert run_id is None


@pytest.mark.anyio
async def test_list_runs_returns_parsed_list():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/runs"
        assert request.url.params["limit"] == "5"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "a",
                    "mode": "area",
                    "source": "x",
                    "created_at": 1,
                    "contour_interval_m": 1.0,
                    "candidate_basins_found": 2,
                    "recommended_catchment_area_m2": 100.0,
                    "is_feasible": True,
                },
            ],
        )

    store = RunStore(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    runs = await store.list_runs(limit=5)
    assert len(runs) == 1
    assert runs[0]["id"] == "a"


@pytest.mark.anyio
async def test_list_runs_filters_by_mode():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["mode"] == "kml"
        return httpx.Response(200, json=[])

    store = RunStore(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    runs = await store.list_runs(mode="kml")
    assert runs == []


@pytest.mark.anyio
async def test_get_run_returns_full_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/runs/abc123"
        return httpx.Response(
            200, json={"id": "abc123", "mode": "kml", "result": {"notes": "ok"}}
        )

    store = RunStore(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    run = await store.get_run("abc123")
    assert run["result"]["notes"] == "ok"


@pytest.mark.anyio
async def test_get_run_raises_run_store_error_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Run not found"})

    store = RunStore(
        base_url="https://example.test", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(RunStoreError):
        await store.get_run("missing-id")
