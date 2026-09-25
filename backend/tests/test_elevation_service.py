import httpx
import pytest

from app.core.elevation_service import ElevationLookupError, ElevationService


def _ok_handler(request: httpx.Request) -> httpx.Response:
    n = len(request.url.params["locations"].split("|"))
    return httpx.Response(200, json={"results": [{"elevation": 100.0 + i} for i in range(n)]})


def _error_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(500, text="upstream error")


@pytest.mark.anyio
async def test_fetch_many_returns_elevations_in_original_order_across_chunks():
    service = ElevationService(
        base_url="https://example.test/elevation",
        chunk_size=2,
        request_delay_s=0,
        transport=httpx.MockTransport(_ok_handler),
    )
    result = await service.fetch_many([(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)])
    # Two requests: chunk of 2 -> [100, 101], chunk of 1 -> [100]
    assert result == [100.0, 101.0, 100.0]


@pytest.mark.anyio
async def test_fetch_many_empty_input_makes_no_request():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"results": []})

    service = ElevationService(
        base_url="https://example.test/elevation", transport=httpx.MockTransport(handler)
    )
    result = await service.fetch_many([])
    assert result == []
    assert calls == []


@pytest.mark.anyio
async def test_fetch_many_raises_on_http_error():
    service = ElevationService(
        base_url="https://example.test/elevation", transport=httpx.MockTransport(_error_handler)
    )
    with pytest.raises(ElevationLookupError):
        await service.fetch_many([(1.0, 1.0)])


@pytest.mark.anyio
async def test_fetch_many_missing_point_comes_back_as_none():
    def handler(request):
        return httpx.Response(200, json={"results": [{"elevation": None}]})

    service = ElevationService(
        base_url="https://example.test/elevation", transport=httpx.MockTransport(handler)
    )
    result = await service.fetch_many([(1.0, 1.0)])
    assert result == [None]
