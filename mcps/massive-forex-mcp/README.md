# Massive Forex MCP for Hermes

A focused Model Context Protocol server that lets Hermes query the Massive.com Forex REST API.

It exposes tools for currency conversion, latest bid/ask quotes, single and full-market snapshots, historical OHLC aggregate bars, week/date-range high-low lookup, previous close data, ticker details, and ticker search.

## Why this exists

Massive has a broader experimental MCP server, but this package is intentionally smaller. It only exposes Forex/Currencies workflows so Hermes gets a tidy toolbox instead of the whole financial-market jungle.

## API coverage

The server uses these Massive Forex REST paths:

- `GET /v1/conversion/{from}/{to}` for currency conversion.
- `GET /v1/last_quote/currencies/{from}/{to}` for latest bid/ask quotes.
- `GET /v2/snapshot/locale/global/markets/forex/tickers/{ticker}` for one-ticker snapshots.
- `GET /v2/snapshot/locale/global/markets/forex/tickers` for market snapshots.
- `GET /v2/aggs/ticker/{forexTicker}/range/{multiplier}/{timespan}/{from}/{to}` for OHLC bars.
- `GET /v2/aggs/ticker/{forexTicker}/prev` for previous close.
- `GET /v3/reference/tickers/{ticker}` and `GET /v3/reference/tickers?market=fx` for reference data.

## Install

```bash
cd ~/source/holofoundry/hermes-mcps
unzip massive_forex_mcp.zip
cd massive_forex_mcp

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
cp .env.example .env
nano .env
```

Add your API key:

```bash
MASSIVE_API_KEY=your_key_here
```

## Smoke test

This starts the MCP server over stdio. It will wait for an MCP client, so no banner output is expected.

```bash
source .venv/bin/activate
python -m massive_forex_mcp.server
```

Press `Ctrl+C` to stop it.

You can also verify imports:

```bash
python -c "from massive_forex_mcp.server import mcp; print('ok')"
```

## Hermes setup

Hermes CLI versions vary, so first inspect the exact command shape:

```bash
hermes mcp --help
```

If your Hermes supports adding stdio MCP servers directly, the command will be close to this:

```bash
hermes mcp add massive-forex \
  --command "$PWD/.venv/bin/python" \
  --args "-m massive_forex_mcp.server" \
  --env MASSIVE_API_KEY="$MASSIVE_API_KEY"
```

If Hermes uses a config file, copy `config/hermes-mcp.example.json`, replace the absolute paths, and import or merge it using the command shown by `hermes mcp --help`.

## Tools exposed

### `convert_currency`

Convert an amount between two currencies.

Inputs: `from_currency`, `to_currency`, `amount`, `precision`.

### `get_last_quote`

Get the latest bid/ask quote for a currency pair.

Inputs: `from_currency`, `to_currency`.

### `get_forex_snapshot`

Get the latest snapshot for one ticker. Accepts `EURUSD`, `EUR/USD`, `EUR-USD`, or `C:EURUSD`.

### `get_forex_market_snapshot`

Get market snapshots for all forex tickers or a comma-separated list.

### `get_forex_aggregates`

Get historical OHLC bars.

Inputs: `ticker`, `multiplier`, `timespan`, `from_date`, `to_date`, `adjusted`, `sort`, `limit`.

### `get_forex_high_low_for_week`

Get the highest and lowest prices for a ticker over a resolved week or explicit date range.

Inputs: `ticker`, `relative_week`, `week_number`, `year`, `from_date`, `to_date`, `adjusted`.

Date selection precedence is explicit `from_date`/`to_date`, then ISO `week_number`/`year`, then `relative_week`. For prompts like "last week", leave `relative_week` as `last`; the server calculates the previous Monday-Sunday range from `datetime.now()`.

### `get_forex_previous_close`

Get previous-day OHLC data.

### `get_forex_ticker_details`

Get reference details for a ticker.

### `list_forex_tickers`

Search or list active forex tickers.

## Notes

This server is read-only. It does not place trades, create orders, manage accounts, or make investment recommendations.

Massive Forex symbols are normalized to `C:EURUSD` style internally.
