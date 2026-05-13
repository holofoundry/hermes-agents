# EVE Online MCP for Hermes

A focused Model Context Protocol server for public EVE Online ESI market data.

This first version intentionally uses only unauthenticated public endpoints. It does not require an EVE SSO application, client secret, refresh token, access token, or OAuth scopes.

## API coverage

The server uses these public ESI routes:

- `GET /markets/prices/` for adjusted and average market prices.
- `GET /markets/{region_id}/orders/` for public regional buy/sell orders.
- `GET /markets/{region_id}/history/` for daily regional market history for one item type.
- `GET /markets/{region_id}/types/` for type IDs traded in a region.
- `GET /markets/groups/` and `GET /markets/groups/{market_group_id}/` for market group metadata.
- `GET /universe/types/{type_id}/` for public item metadata.
- `POST /universe/ids/` for resolving exact names to IDs.
- `POST /universe/names/` for resolving IDs to names and categories.

`GET /markets/structures/{structure_id}/` is deliberately excluded because ESI marks it as SSO-protected with the `esi-markets.structure_markets.v1` scope.

## Install

```bash
cd ~/source/holofoundry/hermes-agents/mcps/eve-online-mcp

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
cp .env.example .env
```

No API key is needed. The `.env` file is only for optional ESI settings.

## Smoke test

This starts the MCP server over stdio. It will wait for an MCP client, so no banner output is expected.

```bash
source .venv/bin/activate
python -m eve_online_mcp.server
```

Press `Ctrl+C` to stop it.

You can also verify imports:

```bash
python -c "from eve_online_mcp.server import mcp; print('ok')"
```

And verify live public ESI access:

```bash
python - <<'PY'
import asyncio
from eve_online_mcp.server import get_market_price

print(asyncio.run(get_market_price(34)))
PY
```

## Hermes config

Add this as a top-level key in `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  eveonline:
    command: "/absolute/path/to/eve-online-mcp/.venv/bin/python"
    args:
      - "-m"
      - "eve_online_mcp.server"
    env:
    enabled: true
    timeout: 120
    connect_timeout: 60
    tools:
      resources: false
      prompts: false
```

Then test:

```bash
hermes mcp test eveonline
```

## Configuration

All configuration is optional:

```bash
EVE_ESI_BASE_URL=https://esi.evetech.net/latest
EVE_ESI_DATASOURCE=tranquility
EVE_ESI_COMPATIBILITY_DATE=YYYY-MM-DD
EVE_ESI_TIMEOUT=30
```

If `EVE_ESI_COMPATIBILITY_DATE` is unset, the server sends a compatibility date based on current UTC time minus 11 hours, matching CCP's guidance that compatibility dates change at 11:00 UTC and must not be in the future.

## Tools exposed

### `get_item_market_quote`

Get a market quote using item and location names.

Use this first for normal prompts like:

- "price of Tritanium in Jita"
- "Pioneer in The Forge"
- "PLEX in Jita"
- "Tritanium in Amarr"
- "PLEX in Dodixie"

Inputs: `item_name`, `location_name`, `location_scope`, `max_pages`.

For known trade hubs, `location_scope=auto` means the main market station:

```text
Jita -> Jita IV - Moon 4 - Caldari Navy Assembly Plant
station_id: 60003760, system_id: 30000142, region_id: 10000002

Amarr -> Amarr VIII (Oris) - Emperor Family Academy
station_id: 60008494, system_id: 30002187, region_id: 10000043

Dodixie -> Dodixie IX - Moon 20 - Federation Navy Assembly Plant
station_id: 60011866, system_id: 30002659, region_id: 10000032

Rens -> Rens VI - Moon 8 - Brutor Tribe Treasury
station_id: 60004588, system_id: 30002510, region_id: 10000030

Hek -> Hek VIII - Moon 12 - Boundless Creation Factory
station_id: 60005686, system_id: 30002053, region_id: 10000042
```

All ESI regions are also available as location aliases. Region names resolve with `default_scope=region`; trade hub shortcuts resolve with `default_scope=station`.

The tool returns:

- `best_sell`: the lowest visible sell order.
- `best_buy`: the highest visible buy order.
- `spread`: `best_sell - best_buy`.
- order counts and remaining volumes.
- `global_estimate` from `/markets/prices/`, which is not location-specific.
- `latest_regional_history` from `/markets/{region_id}/history/`.

### `list_market_prices`

List current ESI adjusted and average prices for all public market item types.

### `get_market_price`

Get the current adjusted and average price for one `type_id`.

Example: Tritanium is `34`.

### `get_region_market_orders`

List public market orders in a region.

Inputs: `region_id`, `order_type`, `type_id`, `page`.

Example: The Forge is `10000002`; Jita is inside The Forge.

### `get_region_market_history`

Get daily historical market statistics for one item type in a region.

Inputs: `region_id`, `type_id`.

### `list_region_market_types`

List item type IDs with public market data in a region.

Inputs: `region_id`, `page`.

### `list_market_groups`

List public EVE market group IDs.

### `get_market_group`

Get public details for a market group.

Inputs: `market_group_id`, `language`.

### `get_type_info`

Get public item metadata for a type ID.

Inputs: `type_id`, `language`.

### `resolve_universe_ids`

Resolve exact EVE names to IDs.

Input: `names_json`, a JSON array of strings such as `["Tritanium", "Pioneer", "Jita", "Amarr", "The Forge"]`.

Prefer `get_item_market_quote` for price requests; use this helper when you only need IDs.

### `resolve_universe_names`

Resolve public EVE IDs to names and categories.

Input: `ids_json`, a JSON array of integers such as `[10000002, 34]`.

### `raw_public_esi_get`

Make a raw GET request to a public ESI path for newly needed unauthenticated endpoints. This blocks `/markets/structures/...` because structure market data requires EVE SSO.

## Auth boundary

Public endpoints do not need authentication. ESI protected endpoints use EVE SSO and list their required scopes in the API Explorer. For the current market slice, the important protected endpoint is structure markets:

```text
GET /markets/structures/{structure_id}/
scope: esi-markets.structure_markets.v1
```

That can be added later as a separate authenticated client path without changing the public tools.
