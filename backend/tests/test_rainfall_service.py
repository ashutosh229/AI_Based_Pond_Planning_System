import httpx
import pytest

from app.core.rainfall_service import RainfallLookupError, RainfallService


@pytest.mark.anyio
async def test_get_annual_rainfall_averages_over_configured_years():
    # 3 years of daily data, each day contributing 1mm -> 365ish mm/year,
    # averaged over 3 years should equal the same per-year figure.
    def handler(request: httpx.Request) -> httpx.Response:
        days = 365 * 3
        return httpx.Response(
            200, json={"daily": {"precipitation_sum": [1.0] * days}}
        )

    service = RainfallService(
        base_url="https://example.test/archive", years=3, transport=httpx.MockTransport(handler)
    )
    stats = await service.get_annual_rainfall_m(21.25, 81.30)
    assert stats.years_used == 3
    assert stats.annual_avg_m == pytest.approx(0.365, abs=0.001)
    assert stats.source == "Open-Meteo historical archive"


@pytest.mark.anyio
async def test_missing_precipitation_data_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"daily": {"precipitation_sum": [None, None]}})

    service = RainfallService(
        base_url="https://example.test/archive", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(RainfallLookupError):
        await service.get_annual_rainfall_m(0, 0)


@pytest.mark.anyio
async def test_http_error_raises_rainfall_lookup_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    service = RainfallService(
        base_url="https://example.test/archive", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(RainfallLookupError):
        await service.get_annual_rainfall_m(0, 0)
