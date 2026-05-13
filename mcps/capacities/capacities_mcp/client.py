from __future__ import annotations

import os
from typing import Any, Mapping

import httpx


class CapacitiesApiError(RuntimeError):
    """Raised when Capacities returns a non-success response."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None, headers: Mapping[str, str] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers or {})


def _token() -> str:
    token = os.getenv("CAPACITIES_API_TOKEN") or os.getenv("CAPACITIES_API_KEY")
    if not token:
        raise CapacitiesApiError(
            "Missing Capacities API token. Set CAPACITIES_API_TOKEN or CAPACITIES_API_KEY."
        )
    return token


def _base_url() -> str:
    return os.getenv("CAPACITIES_BASE_URL", "https://api.capacities.io").rstrip("/")


class CapacitiesClient:
    def __init__(self, *, timeout: float | None = None):
        self.timeout = timeout or float(os.getenv("CAPACITIES_TIMEOUT", "30"))
        self.base_url = _base_url()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "capacities-mcp/0.1.0",
        }

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any] | str | None:
        url = f"{self.base_url}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method.upper(),
                url,
                headers=self._headers(),
                params={k: v for k, v in (params or {}).items() if v is not None},
                json={k: v for k, v in (json or {}).items() if v is not None} if json is not None else None,
            )

        if response.status_code >= 400:
            try:
                body: Any = response.json()
            except ValueError:
                body = response.text
            rate = {
                key: value
                for key, value in response.headers.items()
                if key.lower().startswith("ratelimit") or key.lower() == "retry-after"
            }
            raise CapacitiesApiError(
                f"Capacities API returned HTTP {response.status_code} for {method.upper()} {path}.",
                status_code=response.status_code,
                body=body,
                headers=rate,
            )

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    async def get_space_info(self, space_id: str) -> Any:
        # The public examples use both spaceId and spaceid in the wild. Try the documented camelCase shape first,
        # then fall back to the lowercase query parameter if Capacities rejects it.
        try:
            return await self.request("GET", "/space-info", params={"spaceId": space_id})
        except CapacitiesApiError as exc:
            if exc.status_code in {400, 404}:
                return await self.request("GET", "/space-info", params={"spaceid": space_id})
            raise
