import asyncio

import httpx


class ElevationLookupError(RuntimeError):
    """Raised when the elevation API can't be reached or returns
    something we can't parse."""


class ElevationService:
    """Fetches elevation for a batch of (lat, lon) points from an
    OpenTopoData-compatible API (``GET ?locations=lat,lon|lat,lon|...``).

    Requests are chunked (the public OpenTopoData instance caps requests
    at 100 locations) and a small delay is inserted between chunks to
    respect its ~1 request/sec rate limit. A ``transport`` can be
    injected for testing (see tests/test_elevation_service.py) without
    hitting the network.
    """

    def __init__(
        self,
        base_url: str,
        chunk_size: int = 100,
        request_delay_s: float = 1.0,
        timeout_s: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url
        self.chunk_size = max(1, chunk_size)
        self.request_delay_s = request_delay_s
        self.timeout_s = timeout_s
        self._transport = transport

    async def fetch_many(self, points: list[tuple[float, float]]) -> list[float | None]:
        """points: list of (lat, lon). Returns elevations in the same
        order; a point the API couldn't resolve (e.g. missing DEM
        coverage) comes back as None rather than raising."""
        if not points:
            return []

        results: list[float | None] = [None] * len(points)
        async with httpx.AsyncClient(timeout=self.timeout_s, transport=self._transport) as client:
            for start in range(0, len(points), self.chunk_size):
                chunk = points[start : start + self.chunk_size]
                locations = "|".join(f"{lat:.6f},{lon:.6f}" for lat, lon in chunk)
                try:
                    resp = await client.get(self.base_url, params={"locations": locations})
                    resp.raise_for_status()
                    payload = resp.json()
                except httpx.HTTPError as exc:
                    raise ElevationLookupError(str(exc)) from exc
                except ValueError as exc:  # JSON decode failure
                    raise ElevationLookupError(f"could not parse elevation response: {exc}") from exc

                for i, item in enumerate(payload.get("results", [])):
                    results[start + i] = item.get("elevation")

                if start + self.chunk_size < len(points) and self.request_delay_s > 0:
                    await asyncio.sleep(self.request_delay_s)

        return results
