import pytest
import respx
from httpx import Response
from eve_online_mcp.client import _request, EsiApiError, _get_client, _reset_error_limit

@pytest.fixture(autouse=True)
def reset_limit():
    _reset_error_limit()

@pytest.mark.asyncio
async def test_request_success():
    with respx.mock:
        respx.get("https://esi.evetech.net/latest/test/").mock(
            return_value=Response(
                200, 
                json={"foo": "bar"},
                headers={"x-esi-error-limit-remain": "100", "x-esi-error-limit-reset": "60"}
            )
        )
        data, response = await _request("GET", "/test/")
        assert data == {"foo": "bar"}
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_request_error_limit_backoff():
    # Force low error limit by mocking a response with low headers first
    with respx.mock:
        respx.get("https://esi.evetech.net/latest/low/").mock(
            return_value=Response(
                200, 
                json={},
                headers={"x-esi-error-limit-remain": "5", "x-esi-error-limit-reset": "60"}
            )
        )
        await _request("GET", "/low/")
        
        with pytest.raises(EsiApiError) as excinfo:
            await _request("GET", "/test/")
        assert "ESI error limit almost exhausted" in str(excinfo.value)
        assert excinfo.value.status_code == 429

@pytest.mark.asyncio
async def test_request_esi_error():
    with respx.mock:
        respx.get("https://esi.evetech.net/latest/error/").mock(
            return_value=Response(400, json={"error": "bad request"})
        )
        with pytest.raises(EsiApiError) as excinfo:
            await _request("GET", "/error/")
        assert excinfo.value.status_code == 400
        assert "bad request" in str(excinfo.value)
