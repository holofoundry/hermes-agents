# EVE Online MCP for Hermes

A focused Model Context Protocol server for public EVE Online ESI market data.

This first version intentionally uses only unauthenticated public endpoints. It does not require an EVE SSO application, client secret, refresh token, access token, or OAuth scopes.

## Architecture

The MCP is built with a modular architecture focused on performance, maintainability, and resilience:

- **`server.py`**: Clean entry point for tool registration and bootstrapping.
- **`client.py`**: Persistent ESI client with automatic **Error Limit Awareness**. It tracks `x-esi-error-limit-remain` and proactively pauses if limits are near exhaustion.
- **`tools/market.py`**: High-performance market tools using **Parallel Aggregation** for global data and paginated orders.
- **`tools/universe.py`**: Universe resolution and discovery tools with **Demand-Driven Caching** for item and location IDs.

## API coverage

The server uses these public ESI routes:

- `GET /markets/prices/` for adjusted and average market prices.
- `GET /markets/{region_id}/orders/` for public regional buy/sell orders.
- `GET /markets/{region_id}/history/` for daily regional market history.
- `GET /markets/groups/` and `GET /markets/groups/{market_group_id}/` for market discovery.
- `POST /universe/ids/` and `POST /universe/names/` for entity resolution.

## Performance Features

- **Connection Persistence**: Uses a single `httpx.AsyncClient` to avoid TCP/TLS handshake overhead.
- **Parallel Fetching**: `get_item_global_market_history_analysis` fetches data from all 115+ EVE regions in parallel using `asyncio.gather` and semaphores.
- **On-Demand Caching**: Item names, location names, and IDs are cached in-memory after their first request to eliminate redundant API calls.

## Install

```bash
cd ~/source/holofoundry/hermes-agents/mcps/eve-online-mcp

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
cp .env.example .env
```

## Testing

The project includes a comprehensive testing suite using `pytest` and `respx`.

```bash
pytest tests/
```

## Tools exposed

### `get_item_market_quote`
Get a live market quote using item and location names.

### `get_item_global_market_history_analysis`
Analyze global volume and price trends. Aggregates data from all public regions in seconds.

### `search_market_groups` & `list_market_group_contents`
Use these to browse the EVE market hierarchy. Essential for discovering exact item names and IDs when exact matches aren't known.

### `find_regional_market_trends`
Scans a region's market for `bullish` or `bearish` items within specific categories (Ships, Drones, etc.).

## Adding New Tools

The MCP uses a simple **Registry Pattern**. To add a new tool:
1. Define your function in `eve_online_mcp/tools/market.py` or `universe.py`.
2. Decorate it with `@tool`.
3. It will be automatically registered by `server.py` on startup.

## Configuration

```bash
EVE_ESI_BASE_URL=https://esi.evetech.net/latest
EVE_ESI_DATASOURCE=tranquility
EVE_ESI_TIMEOUT=30
```

## Auth boundary

Public endpoints do not need authentication. `GET /markets/structures/{structure_id}/` is excluded as it requires EVE SSO scopes.
