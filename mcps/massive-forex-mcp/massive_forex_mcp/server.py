from __future__ import annotations

from typing import Any, Type, TypeVar

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel

from .config import settings
from .models import (
    CurrencyConversion,
    ForexAggregatesResponse,
    ForexMarketSnapshotResponse,
    ForexSnapshotResponse,
    LastQuote,
    TickerDetails,
    TickerList,
)
from .utils import (
    CurrencyCode,
    RelativeWeek,
    SortOrder,
    Timespan,
    clean_currency,
    clean_forex_ticker,
    date_from_millis,
    omit_none,
    resolve_week_date_range,
)

SERVER_NAME = "massive-forex"

T = TypeVar("T", bound=BaseModel)

_client: httpx.AsyncClient | None = None


@FastMCP.lifespan
async def app_lifespan(server: FastMCP):
    global _client
    headers = {"Accept": "application/json", "User-Agent": "massive-forex-mcp/0.1.0"}
    _client = httpx.AsyncClient(timeout=settings.massive_request_timeout, headers=headers)
    try:
        yield
    finally:
        if _client:
            await _client.aclose()
            _client = None


mcp = FastMCP(
    SERVER_NAME,
    instructions=(
        "Forex market data MCP server for Massive.com. "
        "Use these tools for currency conversion, latest quotes, snapshots, "
        "historical OHLC aggregates, weekly or date-range high-low lookup, "
        "previous close, and ticker reference data. "
        "Do not present outputs as investment advice or trade execution instructions."
    ),
    lifespan=app_lifespan,
)


async def _get(
    path: str, params: dict[str, Any] | None = None, response_model: Type[T] | None = None
) -> T | dict[str, Any]:
    if _client is None:
        # Fallback for tests or manual invocation outside mcp.run()
        headers = {"Accept": "application/json", "User-Agent": "massive-forex-mcp/0.1.0"}
        async with httpx.AsyncClient(
            timeout=settings.massive_request_timeout, headers=headers
        ) as client:
            return await _request(client, path, params, response_model)
    return await _request(_client, path, params, response_model)


async def _request(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, Any] | None = None,
    response_model: Type[T] | None = None,
) -> T | dict[str, Any]:
    params = dict(params or {})
    params["apiKey"] = settings.api_key
    url = f"{settings.api_base}{path}"
    response = await client.get(url, params=omit_none(params))
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}
    if response.status_code >= 400:
        message = body.get("error") or body.get("message") or response.text
        raise RuntimeError(
            f"Massive API request failed with HTTP {response.status_code}: {message}"
        )

    if response_model:
        return response_model.model_validate(body)
    return body


@mcp.tool()
async def convert_currency(
    from_currency: CurrencyCode,
    to_currency: CurrencyCode,
    amount: float = 1.0,
    precision: int = 5,
) -> CurrencyConversion:
    """Convert an amount between two fiat currencies using Massive.com's real-time conversion endpoint."""
    if amount <= 0:
        raise ValueError("amount must be greater than zero.")
    src = clean_currency(from_currency)
    dst = clean_currency(to_currency)
    return await _get(
        f"/v1/conversion/{src}/{dst}",
        {"amount": amount, "precision": precision},
        response_model=CurrencyConversion,
    )


@mcp.tool()
async def get_last_quote(from_currency: CurrencyCode, to_currency: CurrencyCode) -> LastQuote:
    """Get the latest bid/ask quote for a forex pair."""
    src = clean_currency(from_currency)
    dst = clean_currency(to_currency)
    return await _get(f"/v1/last_quote/currencies/{src}/{dst}", response_model=LastQuote)


@mcp.tool()
async def get_forex_snapshot(ticker: str) -> ForexSnapshotResponse:
    """Get the latest snapshot for one forex ticker, including latest quote, minute bar, day bar, and previous day."""
    normalized = clean_forex_ticker(ticker)
    return await _get(
        f"/v2/snapshot/locale/global/markets/forex/tickers/{normalized}",
        response_model=ForexSnapshotResponse,
    )


@mcp.tool()
async def get_forex_market_snapshot(tickers: str | None = None) -> ForexMarketSnapshotResponse:
    """Get a full forex market snapshot, optionally narrowed to comma-separated tickers like C:EURUSD,C:GBPUSD."""
    normalized_tickers: str | None = None
    if tickers:
        normalized_tickers = ",".join(
            clean_forex_ticker(item) for item in tickers.split(",") if item.strip()
        )
    return await _get(
        "/v2/snapshot/locale/global/markets/forex/tickers",
        {"tickers": normalized_tickers},
        response_model=ForexMarketSnapshotResponse,
    )


@mcp.tool()
async def get_forex_aggregates(
    ticker: str,
    multiplier: int,
    timespan: Timespan,
    from_date: str,
    to_date: str,
    adjusted: bool = True,
    sort: SortOrder = "asc",
    limit: int = 5000,
) -> ForexAggregatesResponse:
    """Get historical forex OHLC aggregate bars for a ticker and date range. Dates may be YYYY-MM-DD or millisecond timestamps."""
    if multiplier < 1:
        raise ValueError("multiplier must be at least 1.")
    if not (1 <= limit <= 50000):
        raise ValueError("limit must be between 1 and 50000.")
    normalized = clean_forex_ticker(ticker)
    return await _get(
        f"/v2/aggs/ticker/{normalized}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
        {"adjusted": str(adjusted).lower(), "sort": sort, "limit": limit},
        response_model=ForexAggregatesResponse,
    )


@mcp.tool()
async def get_forex_high_low_for_week(
    ticker: str,
    relative_week: RelativeWeek = "last",
    week_number: int | None = None,
    year: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    adjusted: bool = True,
) -> dict[str, Any]:
    """Get the highest and lowest prices for a forex ticker over a week or explicit date range.

    Date selection precedence is: explicit from_date/to_date, then ISO week_number/year,
    then relative_week. If the user asks for "last week", leave relative_week as "last";
    the server calculates the previous Monday-Sunday range from datetime.now().
    """
    normalized = clean_forex_ticker(ticker)
    start, end, range_source = resolve_week_date_range(
        from_date=from_date,
        to_date=to_date,
        week_number=week_number,
        year=year,
        relative_week=relative_week,
    )
    # Note: Using generic dict return here because it's a composite result calculated from aggregates
    response: ForexAggregatesResponse = await _get(
        f"/v2/aggs/ticker/{normalized}/range/1/day/{start.isoformat()}/{end.isoformat()}",
        {"adjusted": str(adjusted).lower(), "sort": "asc", "limit": 5000},
        response_model=ForexAggregatesResponse,
    )
    results = response.results
    if not results:
        return {
            "ticker": normalized,
            "from_date": start.isoformat(),
            "to_date": end.isoformat(),
            "range_source": range_source,
            "status": "no_data",
            "high_price": None,
            "low_price": None,
            "bar_count": 0,
        }

    high_bar = max(results, key=lambda bar: bar.h)
    low_bar = min(results, key=lambda bar: bar.l)
    return {
        "ticker": normalized,
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "range_source": range_source,
        "status": response.status,
        "high_price": high_bar.h,
        "high_date": date_from_millis(high_bar.t),
        "low_price": low_bar.l,
        "low_date": date_from_millis(low_bar.t),
        "bar_count": len(results),
        "adjusted": adjusted,
    }


@mcp.tool()
async def get_forex_previous_close(ticker: str, adjusted: bool = True) -> ForexAggregatesResponse:
    """Get the previous day's OHLC close aggregate for a forex ticker."""
    normalized = clean_forex_ticker(ticker)
    return await _get(
        f"/v2/aggs/ticker/{normalized}/prev",
        {"adjusted": str(adjusted).lower()},
        response_model=ForexAggregatesResponse,
    )


@mcp.tool()
async def get_forex_ticker_details(ticker: str) -> TickerDetails:
    """Get reference details for a forex ticker."""
    normalized = clean_forex_ticker(ticker)
    return await _get(f"/v3/reference/tickers/{normalized}", response_model=TickerDetails)


@mcp.tool()
async def list_forex_tickers(
    search: str | None = None,
    active: bool | None = True,
    limit: int = 100,
    cursor: str | None = None,
) -> TickerList:
    """List or search active forex tickers from Massive reference data."""
    if not (1 <= limit <= 1000):
        raise ValueError("limit must be between 1 and 1000.")
    params: dict[str, Any] = {
        "market": "fx",
        "search": search,
        "active": str(active).lower() if active is not None else None,
        "limit": limit,
        "cursor": cursor,
    }
    return await _get("/v3/reference/tickers", params, response_model=TickerList)


@mcp.resource("massive-forex://usage")
def usage_notes() -> str:
    """Usage notes for this MCP server."""
    return (
        "Set MASSIVE_API_KEY before launching the MCP server. "
        "Ticker tools accept EURUSD, EUR/USD, EUR-USD, or C:EURUSD and normalize to C:EURUSD. "
        "Use convert_currency for simple conversions, get_last_quote for bid/ask, "
        "get_forex_aggregates for OHLC history, get_forex_high_low_for_week for weekly or "
        "date-range high-low prices, and snapshots for current market state."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
