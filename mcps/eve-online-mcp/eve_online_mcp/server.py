from __future__ import annotations

import asyncio
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from eve_online_mcp.constants import SERVER_NAME
from eve_online_mcp.tools import market, universe

load_dotenv()

mcp = FastMCP(
    SERVER_NAME,
    instructions=(
        "Public EVE Online ESI market data MCP server. "
        "Use search_market_groups and list_market_group_contents when you need to "
        "discover item names or IDs by browsing the market hierarchy. "
        "Use get_item_market_quote for price checks once you have the exact name. "
        "Use the historical analysis tools for volume and trends. "
        "This server intentionally does not call SSO-protected endpoints."
    ),
)

# Register all tools from modularized packages
for tool in market.get_tools():
    mcp.add_tool(tool)

for tool in universe.get_tools():
    mcp.add_tool(tool)


@mcp.resource("eve-online://usage")
def usage_notes() -> str:
    """Usage notes for this MCP server."""
    return (
        "This server only uses public, unauthenticated EVE Online ESI endpoints. "
        "For natural-language price requests, use get_item_market_quote first. "
        "To discover items and categories, use search_market_groups and list_market_group_contents. "
        "For global historical volume, use get_item_global_market_history_analysis. "
        "For regional historical trends, use get_item_market_history_analysis. "
        "For bullish/bearish scanning, use find_regional_market_trends."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
