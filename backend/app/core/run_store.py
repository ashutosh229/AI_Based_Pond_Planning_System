import httpx


class RunStoreError(RuntimeError):
    """DB server unreachable or returned something unusable."""


class RunStore:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self._transport = transport

    async def save_run(self, payload: dict) -> str | None:
        """Returns the new run id, or None if the save failed (caller
        should not treat this as fatal — see pond_pipeline.py)."""
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_s, transport=self._transport
            ) as client:
                resp = await client.post(f"{self.base_url}/runs", json=payload)
                resp.raise_for_status()
                return resp.json().get("id")
        except httpx.HTTPError:
            return None

    async def list_runs(self, limit: int = 20, mode: str | None = None) -> list[dict]:
        params = {"limit": limit}
        if mode:
            params["mode"] = mode
        async with httpx.AsyncClient(
            timeout=self.timeout_s, transport=self._transport
        ) as client:
            resp = await client.get(f"{self.base_url}/runs", params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_run(self, run_id: str) -> dict:
        async with httpx.AsyncClient(
            timeout=self.timeout_s, transport=self._transport
        ) as client:
            resp = await client.get(f"{self.base_url}/runs/{run_id}")
            if resp.status_code == 404:
                raise RunStoreError("run not found")
            resp.raise_for_status()
            return resp.json()
