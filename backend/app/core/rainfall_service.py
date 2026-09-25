import datetime as dt
from dataclasses import dataclass

import httpx


class RainfallLookupError(RuntimeError):
    """Raised when the rainfall API can't be reached or has no usable
    precipitation data for the requested site."""


@dataclass(frozen=True)
class RainfallStats:
    annual_avg_m: float
    years_used: int
    source: str


class RainfallService:
    """Looks up average annual rainfall for a site from Open-Meteo's
    historical archive (daily precipitation, summed per year and
    averaged over ``years`` of history). A ``transport`` can be injected
    for testing without hitting the network.
    """

    def __init__(
        self,
        base_url: str,
        years: int = 10,
        timeout_s: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url
        self.years = max(1, years)
        self.timeout_s = timeout_s
        self._transport = transport

    def _date_range(self) -> tuple[str, str]:
        # Use the last N *fully completed* calendar years, so we're never
        # averaging in a partial current year.
        end_year = dt.date.today().year - 1
        start_year = end_year - self.years + 1
        return f"{start_year}-01-01", f"{end_year}-12-31"

    async def get_annual_rainfall_m(self, lat: float, lon: float) -> RainfallStats:
        start_date, end_date = self._date_range()
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": "precipitation_sum",
            "timezone": "UTC",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, transport=self._transport) as client:
                resp = await client.get(self.base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise RainfallLookupError(str(exc)) from exc
        except ValueError as exc:
            raise RainfallLookupError(f"could not parse rainfall response: {exc}") from exc

        values = (data.get("daily") or {}).get("precipitation_sum") or []
        valid = [v for v in values if v is not None]
        if not valid:
            raise RainfallLookupError("no precipitation data returned for this location")

        total_mm = sum(valid)
        annual_avg_mm = total_mm / self.years
        return RainfallStats(
            annual_avg_m=round(annual_avg_mm / 1000, 4),
            years_used=self.years,
            source="Open-Meteo historical archive",
        )
