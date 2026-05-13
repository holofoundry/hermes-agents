from __future__ import annotations

import logging
from typing import Any, Mapping

import httpx

from .config import settings

logger = logging.getLogger("capacities-mcp.client")


class CapacitiesApiError(RuntimeError):
    """Raised when Capacities returns a non-success response."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None, headers: Mapping[str, str] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers or {})


class CapacitiesClient:
    def __init__(self, *, timeout: float | None = None):
        self.timeout = timeout or settings.capacities_timeout
        self.base_url = settings.capacities_base_url.rstrip("/")
        self._http_client: httpx.AsyncClient | None = None

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.capacities_api_token}",
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
        client = self._get_http_client()
        logger.debug(f"Capacities API Request: {method.upper()} {url}")
        response = await client.request(
            method.upper(),
            url,
            headers=self._headers(),
            params={k: v for k, v in (params or {}).items() if v is not None},
            json={k: v for k, v in (json or {}).items() if v is not None} if json is not None else None,
        )

        if response.status_code >= 400:
            logger.warning(f"Capacities API error response: {response.status_code} for {method.upper()} {path}")
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

    async def get_object_content(self, space_id: str, object_id: str) -> Any:
        """Retrieve the content of a specific object."""
        try:
            return await self.request("GET", "/get-object-content", params={"spaceId": space_id, "objectId": object_id})
        except CapacitiesApiError as exc:
            if exc.status_code in {400, 404}:
                return await self.request("GET", "/get-object-content", params={"spaceid": space_id, "objectid": object_id})
            raise

    async def create_object(
        self,
        space_id: str,
        structure_id: str,
        title: str,
        content: str = "",
        collection_id: str | None = None,
    ) -> Any:
        """Create a new object in Capacities."""
        payload = {
            "spaceId": space_id,
            "structureId": structure_id,
            "title": title,
            "content": content,
        }
        if collection_id:
            payload["collectionId"] = collection_id

        # Try /objects first, then /v1/objects if it fails with 404
        try:
            return await self.request("POST", "/objects", json=payload)
        except CapacitiesApiError as exc:
            if exc.status_code == 404:
                return await self.request("POST", "/v1/objects", json=payload)
            raise
