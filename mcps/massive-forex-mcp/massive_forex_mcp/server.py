from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

SERVER_NAME = "massive-forex"
DEFAULT_API_BASE = "https://api.polygon.io"

mcp = FastMCP(
    SERVER_NAME,
    instructions=(
        "Forex market data MCP server for Massive.com. "
        "Use these tools for currency conversion, latest quotes, snapshots, "
        "historical OHLC aggregates, weekly or date-range high-low lookup, "
        "previous close, and ticker reference data. "
        "Do not present outputs as investment advice or trade execution instructions."
    ),
)

CurrencyCode = str
Timespan = Literal["second", "minute", "hour", "day", "week", "month", "quarter", "year"]
SortOrder = Literal["asc", "desc"]
RelativeWeek = Literal["last", "current"]


def _api_key() -> str:
    api_key = os.getenv("MASSIVE_API_KEY") or os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing MASSIVE_API_KEY. Set MASSIVE_API_KEY in the environment or in a .env file."
        )
    return api_key


def _api_base() -> str:
    return (os.getenv("MASSIVE_API_BASE") or DEFAULT_API_BASE).rstrip("/")


def _timeout() -> float:
    raw = os.getenv("MASSIVE_REQUEST_TIMEOUT", "30")
    try:
        return float(raw)
    except ValueError:
        return 30.0


def _clean_currency(code: str) -> str:
    value = code.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise ValueError(f"Currency code must be three letters, got {code!r}.")
    return value


def _clean_forex_ticker(ticker: str) -> str:
    """Normalize EURUSD, EUR/USD, EUR-USD, or C:EURUSD to C:EURUSD."""
    value = ticker.strip().upper()
    if value.startswith("C:"):
        pair = value[2:]
    else:
        pair = value.replace("/", "").replace("-", "").replace("_", "")
    if not re.fullmatch(r"[A-Z]{6}", pair):
        raise ValueError(
            "Forex ticker must be a 6-letter pair such as EURUSD, EUR/USD, EUR-USD, or C:EURUSD."
        )
    return f"C:{pair}"


def _omit_none(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a YYYY-MM-DD date, got {value!r}.") from exc


def _resolve_week_date_range(
    *,
    from_date: str | None,
    to_date: str | None,
    week_number: int | None,
    year: int | None,
    relative_week: RelativeWeek,
) -> tuple[date, date, str]:
    if from_date or to_date:
        if not from_date or not to_date:
            raise ValueError("from_date and to_date must be provided together.")
        start = _parse_date(from_date, "from_date")
        end = _parse_date(to_date, "to_date")
        if start > end:
            raise ValueError("from_date must be on or before to_date.")
        return start, end, "date_range"

    today = datetime.now().date()
    if week_number is not None:
        if not (1 <= week_number <= 53):
            raise ValueError("week_number must be between 1 and 53.")
        iso_year = year if year is not None else today.isocalendar().year
        try:
            start = date.fromisocalendar(iso_year, week_number, 1)
        except ValueError as exc:
            raise ValueError(f"Week {week_number} is not valid for ISO year {iso_year}.") from exc
        return start, start + timedelta(days=6), "iso_week"

    current_week_start = today - timedelta(days=today.isoweekday() - 1)
    if relative_week == "current":
        return current_week_start, today, "current_week"
    if relative_week == "last":
        start = current_week_start - timedelta(days=7)
        return start, start + timedelta(days=6), "last_week"
    raise ValueError("relative_week must be 'last' or 'current'.")


def _date_from_millis(timestamp_ms: int | float | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000).date().isoformat()


async def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = dict(params or {})
    params["apiKey"] = _api_key()
    url = f"{_api_base()}{path}"
    headers = {"Accept": "application/json", "User-Agent": "massive-forex-mcp/0.1.0"}
    async with httpx.AsyncClient(timeout=_timeout(), headers=headers) as client:
        response = await client.get(url, params=_omit_none(params))
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}
    if response.status_code >= 400:
        message = body.get("error") or body.get("message") or response.text
        raise RuntimeError(
            f"Massive API request failed with HTTP {response.status_code}: {message}"
        )
    return body


@mcp.tool()
async def convert_currency(
    from_currency: CurrencyCode,
    to_currency: CurrencyCode,
    amount: float = 1.0,
    precision: int = 5,
) -> dict[str, Any]:
    """Convert an amount between two fiat currencies using Massive.com's real-time conversion endpoint."""
    if amount <= 0:
        raise ValueError("amount must be greater than zero.")
    src = _clean_currency(from_currency)
    dst = _clean_currency(to_currency)
    return await _get(
        f"/v1/conversion/{src}/{dst}",
        {"amount": amount, "precision": precision},
    )


@mcp.tool()
async def get_last_quote(from_currency: CurrencyCode, to_currency: CurrencyCode) -> dict[str, Any]:
    """Get the latest bid/ask quote for a forex pair."""
    src = _clean_currency(from_currency)
    dst = _clean_currency(to_currency)
    return await _get(f"/v1/last_quote/currencies/{src}/{dst}")


@mcp.tool()
async def get_forex_snapshot(ticker: str) -> dict[str, Any]:
    """Get the latest snapshot for one forex ticker, including latest quote, minute bar, day bar, and previous day."""
    normalized = _clean_forex_ticker(ticker)
    return await _get(f"/v2/snapshot/locale/global/markets/forex/tickers/{normalized}")


@mcp.tool()
async def get_forex_market_snapshot(tickers: str | None = None) -> dict[str, Any]:
    """Get a full forex market snapshot, optionally narrowed to comma-separated tickers like C:EURUSD,C:GBPUSD."""
    normalized_tickers: str | None = None
    if tickers:
        normalized_tickers = ",".join(
            _clean_forex_ticker(item) for item in tickers.split(",") if item.strip()
        )
    return await _get(
        "/v2/snapshot/locale/global/markets/forex/tickers",
        {"tickers": normalized_tickers},
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
) -> dict[str, Any]:
    """Get historical forex OHLC aggregate bars for a ticker and date range. Dates may be YYYY-MM-DD or millisecond timestamps."""
    if multiplier < 1:
        raise ValueError("multiplier must be at least 1.")
    if not (1 <= limit <= 50000):
        raise ValueError("limit must be between 1 and 50000.")
    normalized = _clean_forex_ticker(ticker)
    return await _get(
        f"/v2/aggs/ticker/{normalized}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
        {"adjusted": str(adjusted).lower(), "sort": sort, "limit": limit},
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
    normalized = _clean_forex_ticker(ticker)
    start, end, range_source = _resolve_week_date_range(
        from_date=from_date,
        to_date=to_date,
        week_number=week_number,
        year=year,
        relative_week=relative_week,
    )
    response = await _get(
        f"/v2/aggs/ticker/{normalized}/range/1/day/{start.isoformat()}/{end.isoformat()}",
        {"adjusted": str(adjusted).lower(), "sort": "asc", "limit": 5000},
    )
    results = response.get("results") or []
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

    high_bar = max(results, key=lambda bar: bar.get("h", float("-inf")))
    low_bar = min(results, key=lambda bar: bar.get("l", float("inf")))
    return {
        "ticker": normalized,
        "from_date": start.isoformat(),
        "to_date": end.isoformat(),
        "range_source": range_source,
        "status": response.get("status"),
        "high_price": high_bar.get("h"),
        "high_date": _date_from_millis(high_bar.get("t")),
        "low_price": low_bar.get("l"),
        "low_date": _date_from_millis(low_bar.get("t")),
        "bar_count": len(results),
        "adjusted": adjusted,
    }


@mcp.tool()
async def get_forex_previous_close(ticker: str, adjusted: bool = True) -> dict[str, Any]:
    """Get the previous day's OHLC close aggregate for a forex ticker."""
    normalized = _clean_forex_ticker(ticker)
    return await _get(
        f"/v2/aggs/ticker/{normalized}/prev",
        {"adjusted": str(adjusted).lower()},
    )


@mcp.tool()
async def get_forex_ticker_details(ticker: str) -> dict[str, Any]:
    """Get reference details for a forex ticker."""
    normalized = _clean_forex_ticker(ticker)
    return await _get(f"/v3/reference/tickers/{normalized}")


@mcp.tool()
async def list_forex_tickers(
    search: str | None = None,
    active: bool | None = True,
    limit: int = 100,
    cursor: str | None = None,
) -> dict[str, Any]:
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
    return await _get("/v3/reference/tickers", params)


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
