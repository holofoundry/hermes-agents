import pytest
import respx
from httpx import Response
from eve_online_mcp.tools.market import get_item_global_market_history_analysis
from eve_online_mcp.client import _reset_error_limit

@pytest.fixture(autouse=True)
def reset_limit():
    _reset_error_limit()

@pytest.mark.asyncio
async def test_global_history_aggregation():
    with respx.mock:
        # Mock universe resolution
        respx.post("https://esi.evetech.net/latest/universe/ids/").mock(
            return_value=Response(200, json={"inventory_types": [{"id": 34, "name": "Tritanium"}]})
        )
        
        # Mock history for 2 regions only to keep test simple, 
        # but in reality it will call all regions. 
        # I'll mock all to avoid errors or just a subset if I can.
        # The tool calls _region_aliases() which returns 118 regions.
        # To avoid mocking all 118, I might need to mock _region_aliases or just use a generic mock.
        
        respx.get(url__regex=r"https://esi.evetech.net/latest/markets/\d+/history/").mock(
            return_value=Response(200, json=[
                {"date": "2026-05-12", "average": 4.0, "volume": 100, "highest": 4.1, "lowest": 3.9, "order_count": 10}
            ])
        )
        
        # Mock names resolution for successful regions list
        respx.post("https://esi.evetech.net/latest/universe/names/").mock(
            return_value=Response(200, json=[{"id": 10000002, "name": "The Forge", "category": "region"}])
        )

        result = await get_item_global_market_history_analysis("Tritanium", period="last_7_days")
        
        assert result["ok"] is True
        assert result["data"]["item"]["name"] == "Tritanium"
        assert "summary" in result["data"]
        
        num_successful = len(result["meta"]["successful_regions"])
        assert result["data"]["summary"]["total_volume"] == num_successful * 100
        assert result["data"]["summary"]["weighted_average_price"] == 4.0
