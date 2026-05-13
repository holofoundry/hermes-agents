import pytest
import respx
from httpx import Response
from capacities_mcp.client import CapacitiesClient, CapacitiesApiError


@pytest.mark.asyncio
async def test_client_request_success():
    client = CapacitiesClient()
    with respx.mock:
        respx.get("https://api.capacities.io/spaces").mock(
            return_value=Response(200, json={"spaces": [{"id": "123"}]})
        )
        response = await client.request("GET", "/spaces")
        assert response == {"spaces": [{"id": "123"}]}


@pytest.mark.asyncio
async def test_client_request_error():
    client = CapacitiesClient()
    with respx.mock:
        respx.get("https://api.capacities.io/spaces").mock(
            return_value=Response(404, text="Not Found")
        )
        with pytest.raises(CapacitiesApiError) as excinfo:
            await client.request("GET", "/spaces")
        assert "HTTP 404" in str(excinfo.value)
        assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_get_space_info_fallback():
    client = CapacitiesClient()
    with respx.mock:
        # First call with spaceId fails
        respx.get("https://api.capacities.io/space-info?spaceId=abc").mock(
            return_value=Response(400, json={"error": "invalid parameter"})
        )
        # Second call with spaceid succeeds
        respx.get("https://api.capacities.io/space-info?spaceid=abc").mock(
            return_value=Response(200, json={"id": "abc", "name": "My Space"})
        )
        
        response = await client.get_space_info("abc")
        assert response == {"id": "abc", "name": "My Space"}


@pytest.mark.asyncio
async def test_client_rate_limit_parsing():
    client = CapacitiesClient()
    with respx.mock:
        headers = {"RateLimit-Limit": "100", "Retry-After": "60"}
        respx.get("https://api.capacities.io/spaces").mock(
            return_value=Response(429, headers=headers)
        )
        with pytest.raises(CapacitiesApiError) as excinfo:
            await client.request("GET", "/spaces")
        
        assert excinfo.value.status_code == 429
        # httpx/respx may normalize header keys to lowercase
        rate_headers = {k.lower(): v for k, v in excinfo.value.headers.items()}
        assert rate_headers["ratelimit-limit"] == "100"
        assert rate_headers["retry-after"] == "60"
