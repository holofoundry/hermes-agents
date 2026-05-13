from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping, Callable
from functools import wraps

from eve_online_mcp.client import (
    _get, _request, _ok, _error, EsiApiError, _parse_date, 
    _clean_limit, _clean_positive_int, _clean_page, _response_headers
)
from eve_online_mcp.constants import LocationScope, OrderType, HistoricalPeriod, TrendDirection
from eve_online_mcp.tools.universe import (
    _resolve_inventory_type, _resolve_location, _resolve_market_group_id,
    _collect_market_group_type_ids, _region_aliases, _get_all_market_group_details
)

# Simple tool registry
_TOOLS = []

def tool(func: Callable):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    _TOOLS.append(func)
    return func

def get_tools():
    return _TOOLS

def _filter_orders_by_location(orders: list[dict[str, Any]], location: Mapping[str, Any], scope: str) -> list[dict[str, Any]]:
    resolved_scope = location.get("default_scope") if scope == "auto" else scope
    if resolved_scope == "station" and location.get("station_id"):
        return [order for order in orders if order.get("location_id") == location["station_id"]]
    if resolved_scope == "system" and location.get("system_id"):
        return [order for order in orders if order.get("system_id") == location["system_id"]]
    return orders

def _summarize_orders(orders: list[dict[str, Any]]) -> dict[str, Any]:
    sell_orders = [order for order in orders if not order.get("is_buy_order")]
    buy_orders = [order for order in orders if order.get("is_buy_order")]
    best_sell = min(sell_orders, key=lambda order: order["price"]) if sell_orders else None
    best_buy = max(buy_orders, key=lambda order: order["price"]) if buy_orders else None
    spread = None
    if best_sell and best_buy:
        spread = best_sell["price"] - best_buy["price"]
    return {
        "best_sell": best_sell,
        "best_buy": best_buy,
        "spread": spread,
        "sell_order_count": len(sell_orders),
        "buy_order_count": len(buy_orders),
        "total_order_count": len(orders),
        "sell_volume_remain": sum(order.get("volume_remain", 0) for order in sell_orders),
        "buy_volume_remain": sum(order.get("volume_remain", 0) for order in buy_orders),
    }

def _resolve_historical_date_range(
    *,
    period: str,
    from_date: str | None,
    to_date: str | None,
) -> tuple[date, date, str]:
    today = datetime.now(timezone.utc).date()
    latest_complete_day = today - timedelta(days=1)

    if from_date or to_date or period == "custom":
        if not from_date or not to_date:
            raise ValueError("from_date and to_date are required when period is custom or either date is provided.")
        start = _parse_date(from_date, "from_date")
        end = _parse_date(to_date, "to_date")
        if start > end:
            raise ValueError("from_date must be on or before to_date.")
        return start, end, "custom"

    if period == "last_week":
        current_week_start = today - timedelta(days=today.isoweekday() - 1)
        start = current_week_start - timedelta(days=7)
        return start, start + timedelta(days=6), "previous_complete_monday_to_sunday"

    if period == "current_week":
        start = today - timedelta(days=today.isoweekday() - 1)
        return start, latest_complete_day, "current_week_to_latest_complete_day"

    if period == "last_7_days":
        return latest_complete_day - timedelta(days=6), latest_complete_day, "rolling_last_7_complete_days"

    if period == "last_14_days":
        return latest_complete_day - timedelta(days=13), latest_complete_day, "rolling_last_14_complete_days"

    if period == "last_30_days":
        return latest_complete_day - timedelta(days=29), latest_complete_day, "rolling_last_30_complete_days"

    if period == "last_month":
        first_of_this_month = today.replace(day=1)
        last_of_previous_month = first_of_this_month - timedelta(days=1)
        first_of_previous_month = last_of_previous_month.replace(day=1)
        return first_of_previous_month, last_of_previous_month, "previous_calendar_month"

    raise ValueError(f"Unsupported period: {period!r}.")

def _previous_period(start: date, end: date) -> tuple[date, date]:
    days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    return previous_end - timedelta(days=days - 1), previous_end

def _filter_history_rows(rows: list[dict[str, Any]], start: date, end: date) -> list[dict[str, Any]]:
    selected = []
    for row in rows:
        row_date = _parse_date(row["date"], "history row date")
        if start <= row_date <= end:
            selected.append(row)
    return selected

def _percent_change(current: float | int | None, previous: float | int | None) -> float | None:
    if previous in (None, 0) or current is None:
        return None
    return ((float(current) - float(previous)) / float(previous)) * 100

def _summarize_history_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "day_count": 0,
            "total_volume": 0,
            "total_order_count": 0,
            "average_daily_volume": None,
            "weighted_average_price": None,
            "simple_average_price": None,
            "lowest_price": None,
            "highest_price": None,
            "first_date": None,
            "last_date": None,
            "first_average": None,
            "last_average": None,
            "average_price_change": None,
            "average_price_change_percent": None,
        }

    total_volume = sum(row.get("volume", 0) for row in rows)
    total_order_count = sum(row.get("order_count", 0) for row in rows)
    weighted_average_price = (
        sum(row["average"] * row.get("volume", 0) for row in rows) / total_volume
        if total_volume
        else None
    )
    first_average = rows[0]["average"]
    last_average = rows[-1]["average"]
    return {
        "day_count": len(rows),
        "total_volume": total_volume,
        "total_order_count": total_order_count,
        "average_daily_volume": total_volume / len(rows),
        "weighted_average_price": weighted_average_price,
        "simple_average_price": sum(row["average"] for row in rows) / len(rows),
        "lowest_price": min(row["lowest"] for row in rows),
        "highest_price": max(row["highest"] for row in rows),
        "first_date": rows[0]["date"],
        "last_date": rows[-1]["date"],
        "first_average": first_average,
        "last_average": last_average,
        "average_price_change": last_average - first_average,
        "average_price_change_percent": _percent_change(last_average, first_average),
    }

def _compare_history_summaries(
    summary: Mapping[str, Any],
    previous_summary: Mapping[str, Any],
    previous_start: date,
    previous_end: date,
) -> dict[str, Any]:
    return {
        "previous_from_date": previous_start.isoformat(),
        "previous_to_date": previous_end.isoformat(),
        "previous_day_count": previous_summary["day_count"],
        "previous_total_volume": previous_summary["total_volume"],
        "previous_weighted_average_price": previous_summary["weighted_average_price"],
        "volume_change": summary["total_volume"] - previous_summary["total_volume"],
        "volume_change_percent": _percent_change(
            summary["total_volume"],
            previous_summary["total_volume"],
        ),
        "weighted_average_price_change": (
            summary["weighted_average_price"] - previous_summary["weighted_average_price"]
            if summary["weighted_average_price"] is not None
            and previous_summary["weighted_average_price"] is not None
            else None
        ),
        "weighted_average_price_change_percent": _percent_change(
            summary["weighted_average_price"],
            previous_summary["weighted_average_price"],
        ),
    }

def _aggregate_global_daily_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for row in rows:
        bucket = by_date.setdefault(
            row["date"],
            {
                "date": row["date"],
                "volume": 0,
                "order_count": 0,
                "highest": None,
                "lowest": None,
                "_weighted_price_total": 0.0,
            },
        )
        volume = row.get("volume", 0)
        bucket["volume"] += volume
        bucket["order_count"] += row.get("order_count", 0)
        bucket["_weighted_price_total"] += row["average"] * volume
        bucket["highest"] = (
            row["highest"]
            if bucket["highest"] is None
            else max(bucket["highest"], row["highest"])
        )
        bucket["lowest"] = (
            row["lowest"]
            if bucket["lowest"] is None
            else min(bucket["lowest"], row["lowest"])
        )

    daily_rows = []
    for row in sorted(by_date.values(), key=lambda item: item["date"]):
        weighted_total = row.pop("_weighted_price_total")
        row["average"] = weighted_total / row["volume"] if row["volume"] else 0
        daily_rows.append(row)
    return daily_rows

def _classify_trend(
    summary: Mapping[str, Any],
    comparison: Mapping[str, Any],
    min_price_change_percent: float,
) -> tuple[str, float]:
    comparison_change = comparison.get("weighted_average_price_change_percent")
    period_change = summary.get("average_price_change_percent")
    primary_change = comparison_change if comparison_change is not None else period_change
    if primary_change is None:
        return "neutral", 0.0

    volume_change = comparison.get("volume_change_percent") or 0
    score = float(primary_change) + (float(volume_change) * 0.1)
    if primary_change >= min_price_change_percent:
        return "bullish", score
    if primary_change <= -min_price_change_percent:
        return "bearish", score
    return "neutral", score

async def _get_region_market_type_ids(region_id: int, max_pages: int = 100) -> set[int]:
    type_ids: set[int] = set()
    total_pages = 1
    for page in range(1, max_pages + 1):
        data, response = await _request(
            "GET",
            f"/markets/{region_id}/types/",
            params={"page": page},
        )
        type_ids.update(data or [])
        if page == 1:
            raw_pages = response.headers.get("X-Pages") or response.headers.get("x-pages")
            total_pages = int(raw_pages) if raw_pages else 1
        if page >= total_pages:
            break
    return type_ids

# Tool definitions
@tool
async def list_market_prices() -> dict[str, Any]:
    """List current ESI adjusted and average prices for all public market item types."""
    return await _get("/markets/prices/")

@tool
async def get_market_price(type_id: int) -> dict[str, Any]:
    """Get the current adjusted and average price for one item type from the public market prices feed."""
    clean_type_id = _clean_positive_int(type_id, "type_id")
    prices = await list_market_prices()
    if not prices.get("ok"):
        return prices
    match = next((item for item in prices["data"] if item.get("type_id") == clean_type_id), None)
    return {
        "ok": True,
        "data": match,
        "meta": {
            **prices.get("meta", {}),
            "status": "found" if match else "not_found",
            "type_id": clean_type_id,
        },
    }

@tool
async def get_item_market_quote(
    item_name: str,
    location_name: str = "Jita",
    location_scope: LocationScope = "auto",
    max_pages: int = 20,
) -> dict[str, Any]:
    """Get an EVE item market quote by item name and place name."""
    max_pages = _clean_limit(max_pages, "max_pages", 100)
    item = await _resolve_inventory_type(item_name)
    if not item.get("ok"):
        return item
    location = await _resolve_location(location_name)
    if not location.get("ok"):
        return location

    type_id = item["data"]["id"]
    region_id = location["data"]["region_id"]
    all_orders: list[dict[str, Any]] = []
    pages_seen = 0
    total_pages: int | None = None
    last_headers: dict[str, str] = {}

    try:
        data, response = await _request(
            "GET",
            f"/markets/{region_id}/orders/",
            params={"order_type": "all", "type_id": type_id, "page": 1},
        )
    except EsiApiError as exc:
        return _error(exc)

    all_orders.extend(data or [])
    pages_seen = 1
    last_headers = _response_headers(response)
    raw_pages = response.headers.get("X-Pages") or response.headers.get("x-pages")
    total_pages = int(raw_pages) if raw_pages else 1

    if total_pages > 1:
        pages_to_fetch = range(2, min(total_pages + 1, max_pages + 1))
        if pages_to_fetch:
            semaphore = asyncio.Semaphore(10)
            async def fetch_page(p: int):
                async with semaphore:
                    return await _request(
                        "GET",
                        f"/markets/{region_id}/orders/",
                        params={"order_type": "all", "type_id": type_id, "page": p},
                    )
            results = await asyncio.gather(*(fetch_page(p) for p in pages_to_fetch))
            for p_data, p_response in results:
                all_orders.extend(p_data or [])
                pages_seen += 1
                last_headers = _response_headers(p_response)

    scoped_orders = _filter_orders_by_location(all_orders, location["data"], location_scope)
    global_price = await get_market_price(type_id)
    history = await get_region_market_history(region_id, type_id)
    history_rows = history.get("data") or []
    summary = _summarize_orders(scoped_orders)
    resolved_scope = location["data"].get("default_scope") if location_scope == "auto" else location_scope
    return {
        "ok": True,
        "data": {
            "item": {
                "name": item["data"]["name"],
                "type_id": type_id,
            },
            "location": {
                **location["data"],
                "scope_used": resolved_scope,
            },
            "quote": summary,
            "global_estimate": global_price.get("data") if global_price.get("ok") else None,
            "latest_regional_history": history_rows[-1] if history_rows else None,
        },
        "meta": {
            "orders_region_id": region_id,
            "orders_pages_seen": pages_seen,
            "orders_total_pages": total_pages,
            "orders_truncated": bool(total_pages and pages_seen < total_pages),
            "headers": last_headers,
            "notes": [
                "Public ESI regional orders are cached for up to 300 seconds.",
                "Global estimates from /markets/prices/ are not location-specific.",
                "Use best_sell as the lowest visible sell order and best_buy as the highest visible buy order.",
            ],
        },
    }

@tool
async def get_region_market_orders(
    region_id: int,
    order_type: OrderType = "all",
    type_id: int | None = None,
    page: int = 1,
) -> dict[str, Any]:
    """List public market orders in a region, optionally filtered by item type and buy/sell side."""
    clean_region_id = _clean_positive_int(region_id, "region_id")
    clean_type_id = _clean_positive_int(type_id, "type_id") if type_id is not None else None
    return await _get(
        f"/markets/{clean_region_id}/orders/",
        {
            "order_type": order_type,
            "type_id": clean_type_id,
            "page": _clean_page(page),
        },
    )

@tool
async def get_region_market_history(region_id: int, type_id: int) -> dict[str, Any]:
    """Get public daily historical market statistics for one item type in a region."""
    clean_region_id = _clean_positive_int(region_id, "region_id")
    clean_type_id = _clean_positive_int(type_id, "type_id")
    return await _get(
        f"/markets/{clean_region_id}/history/",
        {"type_id": clean_type_id},
    )

@tool
async def get_item_market_history_analysis(
    item_name: str,
    location_name: str,
    period: HistoricalPeriod = "last_week",
    from_date: str | None = None,
    to_date: str | None = None,
    include_daily_rows: bool = False,
) -> dict[str, Any]:
    """Analyze historical regional market volume and price trends for an EVE item."""
    item = await _resolve_inventory_type(item_name)
    if not item.get("ok"):
        return item
    location = await _resolve_location(location_name)
    if not location.get("ok"):
        return location

    start, end, range_source = _resolve_historical_date_range(
        period=period,
        from_date=from_date,
        to_date=to_date,
    )
    previous_start, previous_end = _previous_period(start, end)

    type_id = item["data"]["id"]
    region_id = location["data"]["region_id"]
    history = await get_region_market_history(region_id, type_id)
    if not history.get("ok"):
        return history

    all_rows = history.get("data") or []
    selected_rows = _filter_history_rows(all_rows, start, end)
    previous_rows = _filter_history_rows(all_rows, previous_start, previous_end)
    summary = _summarize_history_rows(selected_rows)
    previous_summary = _summarize_history_rows(previous_rows)
    comparison = _compare_history_summaries(
        summary,
        previous_summary,
        previous_start,
        previous_end,
    )
    payload: dict[str, Any] = {
        "ok": True,
        "data": {
            "item": {
                "name": item["data"]["name"],
                "type_id": type_id,
            },
            "location": {
                **location["data"],
                "scope_used": "region",
                "history_region_id": region_id,
                "history_region_name": location["data"].get("region_name"),
            },
            "date_range": {
                "period": period,
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
                "range_source": range_source,
            },
            "summary": summary,
            "comparison": comparison,
        },
        "meta": {
            **history.get("meta", {}),
            "history_scope": "region",
            "notes": [
                "ESI market history reports completed regional market activity, not station-level sales.",
                "For station aliases such as Jita or Amarr, this tool analyzes the containing region.",
                "last_week means the previous complete Monday-Sunday window in UTC.",
                "Rolling periods end on the latest complete UTC day because today's ESI history may be incomplete.",
            ],
        },
    }
    if include_daily_rows:
        payload["data"]["daily_rows"] = selected_rows
        payload["data"]["previous_daily_rows"] = previous_rows
    return payload

@tool
async def get_item_global_market_history_analysis(
    item_name: str,
    period: HistoricalPeriod = "last_week",
    from_date: str | None = None,
    to_date: str | None = None,
    include_daily_rows: bool = False,
    include_region_breakdown: bool = True,
) -> dict[str, Any]:
    """Analyze global historical market volume and price trends for an EVE item."""
    item = await _resolve_inventory_type(item_name)
    if not item.get("ok"):
        return item

    start, end, range_source = _resolve_historical_date_range(
        period=period,
        from_date=from_date,
        to_date=to_date,
    )
    previous_start, previous_end = _previous_period(start, end)
    type_id = item["data"]["id"]

    selected_regional_rows: list[dict[str, Any]] = []
    previous_regional_rows: list[dict[str, Any]] = []
    region_breakdown: list[dict[str, Any]] = []
    successful_regions: list[dict[str, Any]] = []
    empty_regions: list[dict[str, Any]] = []
    failed_regions: list[dict[str, Any]] = []

    semaphore = asyncio.Semaphore(20)
    async def fetch_region_history(region: dict[str, Any]):
        region_id = region["region_id"]
        async with semaphore:
            history = await get_region_market_history(region_id, type_id)
        return region, history

    tasks = [fetch_region_history(region) for region in _region_aliases()]
    results = await asyncio.gather(*tasks)

    for region, history in results:
        region_id = region["region_id"]
        region_info = {"region_id": region_id, "region_name": region["region_name"]}
        if not history.get("ok"):
            status_code = history.get("status_code")
            if status_code in {400, 404, 422}:
                empty_regions.append({**region_info, "status_code": status_code})
            else:
                failed_regions.append({**region_info, "status_code": status_code, "error": history.get("error")})
            continue

        all_rows = history.get("data") or []
        selected_rows = _filter_history_rows(all_rows, start, end)
        previous_rows = _filter_history_rows(all_rows, previous_start, previous_end)
        if not selected_rows and not previous_rows:
            empty_regions.append(region_info)
            successful_regions.append(region_info)
            continue

        successful_regions.append(region_info)
        selected_regional_rows.extend(selected_rows)
        previous_regional_rows.extend(previous_rows)
        if include_region_breakdown:
            region_summary = _summarize_history_rows(selected_rows)
            previous_region_summary = _summarize_history_rows(previous_rows)
            region_breakdown.append({
                **region_info,
                "summary": region_summary,
                "comparison": _compare_history_summaries(region_summary, previous_region_summary, previous_start, previous_end),
            })

    if not successful_regions:
        return {"ok": False, "error": "Failed to fetch historical market data for all public ESI regions.", "failed_regions": failed_regions, "empty_regions": empty_regions}

    global_daily_rows = _aggregate_global_daily_rows(selected_regional_rows)
    previous_global_daily_rows = _aggregate_global_daily_rows(previous_regional_rows)
    summary = _summarize_history_rows(global_daily_rows)
    previous_summary = _summarize_history_rows(previous_global_daily_rows)
    region_breakdown.sort(key=lambda item: item["summary"]["total_volume"], reverse=True)

    payload: dict[str, Any] = {
        "ok": True,
        "data": {
            "item": {"name": item["data"]["name"], "type_id": type_id},
            "market_scope": "global",
            "date_range": {"period": period, "from_date": start.isoformat(), "to_date": end.isoformat(), "range_source": range_source},
            "summary": summary,
            "comparison": _compare_history_summaries(summary, previous_summary, previous_start, previous_end),
        },
        "meta": {
            "history_scope": "global",
            "region_count": len(_region_aliases()),
            "successful_region_count": len(successful_regions),
            "empty_region_count": len(empty_regions),
            "failed_region_count": len(failed_regions),
            "successful_regions": successful_regions,
            "empty_regions": empty_regions,
            "failed_regions": failed_regions,
            "notes": [
                "Global history is synthesized by aggregating public ESI regional history.",
                "Structure markets are not included because they require EVE SSO.",
                "Use get_item_market_history_analysis only when the user specifies a region or location.",
                "last_week means the previous complete Monday-Sunday window in UTC.",
                "Rolling periods end on the latest complete UTC day because today's ESI history may be incomplete.",
            ],
        },
    }
    if include_region_breakdown: payload["data"]["region_breakdown"] = region_breakdown
    if include_daily_rows:
        payload["data"]["daily_rows"] = global_daily_rows
        payload["data"]["previous_daily_rows"] = previous_global_daily_rows
    return payload

@tool
async def find_regional_market_trends(
    location_name: str,
    market_group_name: str = "Ships",
    period: HistoricalPeriod = "last_7_days",
    from_date: str | None = None,
    to_date: str | None = None,
    direction: TrendDirection = "all",
    result_limit: int = 25,
    max_items: int = 500,
    min_total_volume: int = 1,
    min_price_change_percent: float = 2.0,
    include_neutral: bool = False,
) -> dict[str, Any]:
    """Find bullish and bearish EVE market trends in a requested region or trade hub."""
    result_limit = _clean_limit(result_limit, "result_limit", 100)
    max_items = _clean_limit(max_items, "max_items", 1000)
    if min_total_volume < 0: raise ValueError("min_total_volume must be zero or greater.")
    if min_price_change_percent < 0: raise ValueError("min_price_change_percent must be zero or greater.")

    location = await _resolve_location(location_name)
    if not location.get("ok"): return location
    region_id = location["data"]["region_id"]
    market_group_id = await _resolve_market_group_id(market_group_name)
    market_group_details = (await _get_all_market_group_details()).get(market_group_id, {})
    group_type_ids = await _collect_market_group_type_ids(market_group_id)
    region_type_ids = await _get_region_market_type_ids(region_id)
    candidate_type_ids = sorted(group_type_ids & region_type_ids)[:max_items]
    total_candidates = len(candidate_type_ids)

    start, end, range_source = _resolve_historical_date_range(period=period, from_date=from_date, to_date=to_date)
    previous_start, previous_end = _previous_period(start, end)
    semaphore = asyncio.Semaphore(20)

    async def analyze_type(type_id: int):
        async with semaphore:
            history = await get_region_market_history(region_id, type_id)
        if not history.get("ok"): return None
        all_rows = history.get("data") or []
        selected_rows = _filter_history_rows(all_rows, start, end)
        if not selected_rows: return None
        summary = _summarize_history_rows(selected_rows)
        if summary["total_volume"] < min_total_volume: return None
        previous_rows = _filter_history_rows(all_rows, previous_start, previous_end)
        previous_summary = _summarize_history_rows(previous_rows)
        comparison = _compare_history_summaries(summary, previous_summary, previous_start, previous_end)
        trend, score = _classify_trend(summary, comparison, min_price_change_percent)
        if trend == "neutral" and not include_neutral: return None
        if direction != "all" and trend != direction: return None
        return {"type_id": type_id, "trend": trend, "trend_score": score, "summary": summary, "comparison": comparison}

    raw_results = await asyncio.gather(*(analyze_type(type_id) for type_id in candidate_type_ids))
    results = [r for r in raw_results if r is not None]
    if direction == "bullish": results.sort(key=lambda x: x["trend_score"], reverse=True)
    elif direction == "bearish": results.sort(key=lambda x: x["trend_score"])
    else: results.sort(key=lambda x: abs(x["trend_score"]), reverse=True)
    results = results[:result_limit]

    if results:
        names_response = await _request("POST", "/universe/names/", body=[r["type_id"] for r in results])
        names = {entry["id"]: entry["name"] for entry in names_response[0]} if names_response[1].status_code < 400 else {}
        for r in results: r["name"] = names.get(r["type_id"])

    return {
        "ok": True,
        "data": {
            "location": {**location["data"], "scope_used": "region", "trend_region_id": region_id, "trend_region_name": location["data"].get("region_name")},
            "market_group": {"market_group_id": market_group_id, "name": market_group_details.get("name")},
            "date_range": {"period": period, "from_date": start.isoformat(), "to_date": end.isoformat(), "range_source": range_source},
            "results": results,
        },
        "meta": {"direction": direction, "result_limit": result_limit, "max_items": max_items, "min_total_volume": min_total_volume, "min_price_change_percent": min_price_change_percent, "candidate_count": total_candidates, "analyzed_count": len(candidate_type_ids), "returned_count": len(results)},
    }

@tool
async def list_region_market_types(region_id: int, page: int = 1) -> dict[str, Any]:
    """List item type IDs that have public market data in a region."""
    clean_region_id = _clean_positive_int(region_id, "region_id")
    return await _get(f"/markets/{clean_region_id}/types/", {"page": _clean_page(page)})
