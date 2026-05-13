from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal, Mapping

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

SERVER_NAME = "eve-online"
DEFAULT_ESI_BASE = "https://esi.evetech.net/latest"
DEFAULT_DATASOURCE = "tranquility"

OrderType = Literal["buy", "sell", "all"]
Language = Literal["en", "de", "fr", "ja", "ru", "zh", "ko", "es"]
LocationScope = Literal["auto", "station", "system", "region"]
HistoricalPeriod = Literal[
    "last_week",
    "current_week",
    "last_7_days",
    "last_14_days",
    "last_30_days",
    "last_month",
    "custom",
]


def _region_alias(region_id: int, region_name: str) -> dict[str, Any]:
    return {
        "name": region_name,
        "region_id": region_id,
        "region_name": region_name,
        "default_scope": "region",
    }


def _station_alias(
    *,
    name: str,
    region_id: int,
    region_name: str,
    system_id: int,
    system_name: str,
    station_id: int,
    station_name: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "region_id": region_id,
        "region_name": region_name,
        "system_id": system_id,
        "system_name": system_name,
        "station_id": station_id,
        "station_name": station_name,
        "default_scope": "station",
    }


LOCATION_ALIASES: dict[str, dict[str, Any]] = {
    "a-r00001": _region_alias(11000001, "A-R00001"),
    "a-r00002": _region_alias(11000002, "A-R00002"),
    "a-r00003": _region_alias(11000003, "A-R00003"),
    "a821-a": _region_alias(10000019, "A821-A"),
    "adr01": _region_alias(12000001, "ADR01"),
    "adr02": _region_alias(12000002, "ADR02"),
    "adr03": _region_alias(12000003, "ADR03"),
    "adr04": _region_alias(12000004, "ADR04"),
    "adr05": _region_alias(12000005, "ADR05"),
    "aridia": _region_alias(10000054, "Aridia"),
    "b-r00004": _region_alias(11000004, "B-R00004"),
    "b-r00005": _region_alias(11000005, "B-R00005"),
    "b-r00006": _region_alias(11000006, "B-R00006"),
    "b-r00007": _region_alias(11000007, "B-R00007"),
    "b-r00008": _region_alias(11000008, "B-R00008"),
    "black rise": _region_alias(10000069, "Black Rise"),
    "branch": _region_alias(10000055, "Branch"),
    "c-r00009": _region_alias(11000009, "C-R00009"),
    "c-r00010": _region_alias(11000010, "C-R00010"),
    "c-r00011": _region_alias(11000011, "C-R00011"),
    "c-r00012": _region_alias(11000012, "C-R00012"),
    "c-r00013": _region_alias(11000013, "C-R00013"),
    "c-r00014": _region_alias(11000014, "C-R00014"),
    "c-r00015": _region_alias(11000015, "C-R00015"),
    "cache": _region_alias(10000007, "Cache"),
    "catch": _region_alias(10000014, "Catch"),
    "cloud ring": _region_alias(10000051, "Cloud Ring"),
    "cobalt edge": _region_alias(10000053, "Cobalt Edge"),
    "curse": _region_alias(10000012, "Curse"),
    "d-r00016": _region_alias(11000016, "D-R00016"),
    "d-r00017": _region_alias(11000017, "D-R00017"),
    "d-r00018": _region_alias(11000018, "D-R00018"),
    "d-r00019": _region_alias(11000019, "D-R00019"),
    "d-r00020": _region_alias(11000020, "D-R00020"),
    "d-r00021": _region_alias(11000021, "D-R00021"),
    "d-r00022": _region_alias(11000022, "D-R00022"),
    "d-r00023": _region_alias(11000023, "D-R00023"),
    "deklein": _region_alias(10000035, "Deklein"),
    "delve": _region_alias(10000060, "Delve"),
    "derelik": _region_alias(10000001, "Derelik"),
    "detorid": _region_alias(10000005, "Detorid"),
    "devoid": _region_alias(10000036, "Devoid"),
    "domain": _region_alias(10000043, "Domain"),
    "e-r00024": _region_alias(11000024, "E-R00024"),
    "e-r00025": _region_alias(11000025, "E-R00025"),
    "e-r00026": _region_alias(11000026, "E-R00026"),
    "e-r00027": _region_alias(11000027, "E-R00027"),
    "e-r00028": _region_alias(11000028, "E-R00028"),
    "e-r00029": _region_alias(11000029, "E-R00029"),
    "esoteria": _region_alias(10000039, "Esoteria"),
    "essence": _region_alias(10000064, "Essence"),
    "etherium reach": _region_alias(10000027, "Etherium Reach"),
    "everyshore": _region_alias(10000037, "Everyshore"),
    "exordium": _region_alias(10001004, "Exordium"),
    "f-r00030": _region_alias(11000030, "F-R00030"),
    "fade": _region_alias(10000046, "Fade"),
    "feythabolis": _region_alias(10000056, "Feythabolis"),
    "fountain": _region_alias(10000058, "Fountain"),
    "g-r00031": _region_alias(11000031, "G-R00031"),
    "geminate": _region_alias(10000029, "Geminate"),
    "genesis": _region_alias(10000067, "Genesis"),
    "gpmr-01": _region_alias(19000001, "GPMR-01"),
    "great wildlands": _region_alias(10000011, "Great Wildlands"),
    "h-r00032": _region_alias(11000032, "H-R00032"),
    "heimatar": _region_alias(10000030, "Heimatar"),
    "immensea": _region_alias(10000025, "Immensea"),
    "impass": _region_alias(10000031, "Impass"),
    "insmother": _region_alias(10000009, "Insmother"),
    "j7hz-f": _region_alias(10000017, "J7HZ-F"),
    "k-r00033": _region_alias(11000033, "K-R00033"),
    "kador": _region_alias(10000052, "Kador"),
    "khanid": _region_alias(10000049, "Khanid"),
    "kor-azor": _region_alias(10000065, "Kor-Azor"),
    "lonetrek": _region_alias(10000016, "Lonetrek"),
    "malpais": _region_alias(10000013, "Malpais"),
    "metropolis": _region_alias(10000042, "Metropolis"),
    "molden heath": _region_alias(10000028, "Molden Heath"),
    "oasa": _region_alias(10000040, "Oasa"),
    "omist": _region_alias(10000062, "Omist"),
    "outer passage": _region_alias(10000021, "Outer Passage"),
    "outer ring": _region_alias(10000057, "Outer Ring"),
    "paragon soul": _region_alias(10000059, "Paragon Soul"),
    "period basis": _region_alias(10000063, "Period Basis"),
    "perrigen falls": _region_alias(10000066, "Perrigen Falls"),
    "placid": _region_alias(10000048, "Placid"),
    "pochven": _region_alias(10000070, "Pochven"),
    "providence": _region_alias(10000047, "Providence"),
    "pure blind": _region_alias(10000023, "Pure Blind"),
    "querious": _region_alias(10000050, "Querious"),
    "scalding pass": _region_alias(10000008, "Scalding Pass"),
    "sinq laison": _region_alias(10000032, "Sinq Laison"),
    "solitude": _region_alias(10000044, "Solitude"),
    "stain": _region_alias(10000022, "Stain"),
    "syndicate": _region_alias(10000041, "Syndicate"),
    "tash-murkon": _region_alias(10000020, "Tash-Murkon"),
    "tenal": _region_alias(10000045, "Tenal"),
    "tenerifis": _region_alias(10000061, "Tenerifis"),
    "the bleak lands": _region_alias(10000038, "The Bleak Lands"),
    "the citadel": _region_alias(10000033, "The Citadel"),
    "the forge": _region_alias(10000002, "The Forge"),
    "the kalevala expanse": _region_alias(10000034, "The Kalevala Expanse"),
    "the spire": _region_alias(10000018, "The Spire"),
    "tribute": _region_alias(10000010, "Tribute"),
    "uua-f4": _region_alias(10000004, "UUA-F4"),
    "vale of the silent": _region_alias(10000003, "Vale of the Silent"),
    "venal": _region_alias(10000015, "Venal"),
    "verge vendor": _region_alias(10000068, "Verge Vendor"),
    "vr-01": _region_alias(14000001, "VR-01"),
    "vr-02": _region_alias(14000002, "VR-02"),
    "vr-03": _region_alias(14000003, "VR-03"),
    "vr-04": _region_alias(14000004, "VR-04"),
    "vr-05": _region_alias(14000005, "VR-05"),
    "wicked creek": _region_alias(10000006, "Wicked Creek"),
    "yasna zakh": _region_alias(10001000, "Yasna Zakh"),
    "amarr": _station_alias(
        name="Amarr",
        region_id=10000043,
        region_name="Domain",
        system_id=30002187,
        system_name="Amarr",
        station_id=60008494,
        station_name="Amarr VIII (Oris) - Emperor Family Academy",
    ),
    "dodixie": _station_alias(
        name="Dodixie",
        region_id=10000032,
        region_name="Sinq Laison",
        system_id=30002659,
        system_name="Dodixie",
        station_id=60011866,
        station_name="Dodixie IX - Moon 20 - Federation Navy Assembly Plant",
    ),
    "rens": _station_alias(
        name="Rens",
        region_id=10000030,
        region_name="Heimatar",
        system_id=30002510,
        system_name="Rens",
        station_id=60004588,
        station_name="Rens VI - Moon 8 - Brutor Tribe Treasury",
    ),
    "hek": _station_alias(
        name="Hek",
        region_id=10000042,
        region_name="Metropolis",
        system_id=30002053,
        system_name="Hek",
        station_id=60005686,
        station_name="Hek VIII - Moon 12 - Boundless Creation Factory",
    ),
    "jita": _station_alias(
        name="Jita",
        region_id=10000002,
        region_name="The Forge",
        system_id=30000142,
        system_name="Jita",
        station_id=60003760,
        station_name="Jita IV - Moon 4 - Caldari Navy Assembly Plant",
    ),
}

mcp = FastMCP(
    SERVER_NAME,
    instructions=(
        "Public EVE Online ESI market data MCP server. "
        "Use get_item_market_quote when a user asks for the price of an EVE item "
        "by name in a place by name, for example 'Tritanium in Jita' or "
        "'Pioneer in The Forge'. Use get_item_global_market_history_analysis when "
        "a user asks about sold volume, historical prices, or trends without a "
        "region or location, for example 'What volume of Pioneers sold last week?'. "
        "Use get_item_market_history_analysis only when the user explicitly names "
        "a region or location, for example 'Pioneers in The Forge last week'. "
        "Tritanium, Pioneer, and similar names are EVE inventory types, not terrestrial commodities. "
        "Lower-level tools are also available for IDs, regional orders, regional "
        "history, market groups, and public universe item/name lookups. This server "
        "intentionally does not call SSO-protected endpoints."
    ),
)


class EsiApiError(RuntimeError):
    """Raised when ESI returns a non-success response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: Any = None,
        headers: Mapping[str, str] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers or {})


def _esi_base() -> str:
    return (os.getenv("EVE_ESI_BASE_URL") or DEFAULT_ESI_BASE).rstrip("/")


def _datasource() -> str:
    return os.getenv("EVE_ESI_DATASOURCE", DEFAULT_DATASOURCE)


def _timeout() -> float:
    raw = os.getenv("EVE_ESI_TIMEOUT", "30")
    try:
        return float(raw)
    except ValueError:
        return 30.0


def _compatibility_date() -> str:
    configured = os.getenv("EVE_ESI_COMPATIBILITY_DATE")
    if configured:
        return configured
    return (datetime.now(timezone.utc) - timedelta(hours=11)).date().isoformat()


def _clean_positive_int(value: int, field_name: str) -> int:
    if value < 1:
        raise ValueError(f"{field_name} must be greater than zero.")
    return value


def _clean_page(value: int) -> int:
    if not (1 <= value <= 10000):
        raise ValueError("page must be between 1 and 10000.")
    return value


def _clean_limit(value: int, field_name: str, max_value: int) -> int:
    if not (1 <= value <= max_value):
        raise ValueError(f"{field_name} must be between 1 and {max_value}.")
    return value


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a YYYY-MM-DD date, got {value!r}.") from exc


def _omit_none(params: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value is not None}


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _esi_headers(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "eve-online-mcp/0.1.0",
        "X-Compatibility-Date": _compatibility_date(),
    }
    headers.update(extra or {})
    return headers


def _response_headers(response: httpx.Response) -> dict[str, str]:
    interesting = {
        "cache-control",
        "etag",
        "expires",
        "last-modified",
        "retry-after",
        "x-compatibility-date",
        "x-esi-error-limit-remain",
        "x-esi-error-limit-reset",
        "x-pages",
        "x-ratelimit-group",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-used",
    }
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() in interesting
    }


def _ok(data: Any, response: httpx.Response | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "data": data}
    if response is not None:
        payload["meta"] = {
            "status_code": response.status_code,
            "headers": _response_headers(response),
        }
    return payload


def _error(exc: EsiApiError) -> dict[str, Any]:
    return {
        "ok": False,
        "error": str(exc),
        "status_code": exc.status_code,
        "body": exc.body,
        "headers": exc.headers,
    }


async def _request(
    method: str,
    path: str,
    *,
    params: Mapping[str, Any] | None = None,
    body: Any = None,
    headers: Mapping[str, str] | None = None,
) -> tuple[Any, httpx.Response]:
    request_params = {"datasource": _datasource(), **dict(params or {})}
    url = f"{_esi_base()}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=_timeout()) as client:
        response = await client.request(
            method.upper(),
            url,
            params=_omit_none(request_params),
            json=body,
            headers=_esi_headers(headers),
        )

    if response.status_code == 304:
        return None, response

    try:
        data = response.json()
    except ValueError:
        data = response.text

    if response.status_code >= 400:
        message = data.get("error") if isinstance(data, dict) else response.text
        raise EsiApiError(
            f"ESI returned HTTP {response.status_code} for {method.upper()} {path}: {message}",
            status_code=response.status_code,
            body=data,
            headers=_response_headers(response),
        )

    return data, response


async def _get(path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    try:
        data, response = await _request("GET", path, params=params)
        return _ok(data, response)
    except EsiApiError as exc:
        return _error(exc)


async def _post(path: str, body: Any, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    try:
        data, response = await _request("POST", path, params=params, body=body)
        return _ok(data, response)
    except EsiApiError as exc:
        return _error(exc)


async def _resolve_ids(names: list[str], language: Language = "en") -> dict[str, Any]:
    return await _post(
        "/universe/ids/",
        names,
        params={"language": language},
    )


async def _resolve_inventory_type(item_name: str) -> dict[str, Any]:
    resolved = await _resolve_ids([item_name])
    if not resolved.get("ok"):
        return resolved
    matches = resolved.get("data", {}).get("inventory_types") or []
    if not matches and item_name.strip().lower().endswith("s"):
        singular = item_name.strip()[:-1]
        resolved = await _resolve_ids([singular])
        if not resolved.get("ok"):
            return resolved
        matches = resolved.get("data", {}).get("inventory_types") or []
    if not matches:
        return {
            "ok": False,
            "error": (
                f"No EVE inventory type was found for {item_name!r}. "
                "ESI name resolution requires an exact item name."
            ),
            "resolved": resolved.get("data"),
        }
    return {"ok": True, "data": matches[0], "resolved": resolved.get("data")}


async def _resolve_location(location_name: str) -> dict[str, Any]:
    alias = LOCATION_ALIASES.get(_normalize_name(location_name))
    if alias:
        return {"ok": True, "data": dict(alias)}

    resolved = await _resolve_ids([location_name])
    if not resolved.get("ok"):
        return resolved
    data = resolved.get("data", {})
    regions = data.get("regions") or []
    systems = data.get("systems") or []
    stations = data.get("stations") or []
    if regions:
        region = regions[0]
        return {
            "ok": True,
            "data": {
                "name": region["name"],
                "region_id": region["id"],
                "region_name": region["name"],
                "default_scope": "region",
            },
        }
    if systems:
        system = systems[0]
        system_info = await _get(f"/universe/systems/{system['id']}/")
        if not system_info.get("ok"):
            return system_info
        constellation_id = system_info["data"]["constellation_id"]
        constellation = await _get(f"/universe/constellations/{constellation_id}/")
        if not constellation.get("ok"):
            return constellation
        region_id = constellation["data"]["region_id"]
        names = await _post("/universe/names/", [region_id])
        region_name = None
        if names.get("ok") and names.get("data"):
            region_name = names["data"][0].get("name")
        return {
            "ok": True,
            "data": {
                "name": system["name"],
                "region_id": region_id,
                "region_name": region_name,
                "system_id": system["id"],
                "system_name": system["name"],
                "default_scope": "system",
            },
        }
    if stations:
        station = stations[0]
        station_info = await _get(f"/universe/stations/{station['id']}/")
        if not station_info.get("ok"):
            return station_info
        system_id = station_info["data"]["system_id"]
        system_info = await _get(f"/universe/systems/{system_id}/")
        if not system_info.get("ok"):
            return system_info
        constellation = await _get(f"/universe/constellations/{system_info['data']['constellation_id']}/")
        if not constellation.get("ok"):
            return constellation
        region_id = constellation["data"]["region_id"]
        names = await _post("/universe/names/", [region_id, system_id])
        names_by_id = {entry["id"]: entry["name"] for entry in names.get("data", [])} if names.get("ok") else {}
        return {
            "ok": True,
            "data": {
                "name": station["name"],
                "region_id": region_id,
                "region_name": names_by_id.get(region_id),
                "system_id": system_id,
                "system_name": names_by_id.get(system_id),
                "station_id": station["id"],
                "station_name": station["name"],
                "default_scope": "station",
            },
        }
    return {
        "ok": False,
        "error": (
            f"No EVE region, system, or station was found for {location_name!r}. "
            "ESI name resolution requires an exact location name."
        ),
        "resolved": data,
    }


def _filter_orders_by_location(orders: list[dict[str, Any]], location: Mapping[str, Any], scope: LocationScope) -> list[dict[str, Any]]:
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
    period: HistoricalPeriod,
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


def _region_aliases() -> list[dict[str, Any]]:
    regions_by_id: dict[int, dict[str, Any]] = {}
    for alias in LOCATION_ALIASES.values():
        if alias.get("default_scope") == "region":
            regions_by_id[alias["region_id"]] = alias
    return sorted(regions_by_id.values(), key=lambda region: region["region_name"])


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


@mcp.tool()
async def list_market_prices() -> dict[str, Any]:
    """List current ESI adjusted and average prices for all public market item types."""
    return await _get("/markets/prices/")


@mcp.tool()
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


@mcp.tool()
async def get_item_market_quote(
    item_name: str,
    location_name: str = "Jita",
    location_scope: LocationScope = "auto",
    max_pages: int = 20,
) -> dict[str, Any]:
    """Get an EVE item market quote by item name and place name.

    Use this first for natural-language price requests such as "price of Tritanium in Jita",
    "Pioneer in The Forge", or "PLEX in Jita". It resolves the item name to an inventory
    type, resolves the place to a region/system/station, fetches public regional market
    orders, filters to the requested place when possible, and returns best sell, best buy,
    spread, volumes, global ESI estimate, and the latest daily regional history row.

    For Jita, location_scope="auto" means the Jita 4-4 trade hub station. Use
    location_scope="system" for the whole Jita solar system or "region" for The Forge.
    """
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

    for page in range(1, max_pages + 1):
        try:
            data, response = await _request(
                "GET",
                f"/markets/{region_id}/orders/",
                params={"order_type": "all", "type_id": type_id, "page": page},
            )
        except EsiApiError as exc:
            return _error(exc)
        pages_seen = page
        last_headers = _response_headers(response)
        if total_pages is None:
            raw_pages = response.headers.get("X-Pages") or response.headers.get("x-pages")
            total_pages = int(raw_pages) if raw_pages else 1
        all_orders.extend(data or [])
        if page >= total_pages:
            break

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


@mcp.tool()
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


@mcp.tool()
async def get_region_market_history(region_id: int, type_id: int) -> dict[str, Any]:
    """Get public daily historical market statistics for one item type in a region."""
    clean_region_id = _clean_positive_int(region_id, "region_id")
    clean_type_id = _clean_positive_int(type_id, "type_id")
    return await _get(
        f"/markets/{clean_region_id}/history/",
        {"type_id": clean_type_id},
    )


@mcp.tool()
async def get_item_market_history_analysis(
    item_name: str,
    location_name: str,
    period: HistoricalPeriod = "last_week",
    from_date: str | None = None,
    to_date: str | None = None,
    include_daily_rows: bool = False,
) -> dict[str, Any]:
    """Analyze historical regional market volume and price trends for an EVE item.

    Use this only when the user explicitly names a region or location, such as
    "Pioneers in The Forge last week", "Tritanium in Jita over the last 30 days",
    or "PLEX volume in Amarr from 2026-05-01 to 2026-05-07". It resolves item and
    location names, fetches public ESI daily regional history, filters the requested
    date window, totals sold volume and order count, calculates weighted/simple
    average prices, high/low range, first-to-last price movement, and compares with
    the previous equal-length period.

    Use get_item_global_market_history_analysis instead when the user asks for
    historical volume or trends without specifying a region or location.

    ESI market history is regional only. If location_name is a station or system
    such as Jita, Amarr, Dodixie, Rens, or Hek, this tool analyzes the containing
    region, not station-level or system-level completed sales.
    """
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


@mcp.tool()
async def get_item_global_market_history_analysis(
    item_name: str,
    period: HistoricalPeriod = "last_week",
    from_date: str | None = None,
    to_date: str | None = None,
    include_daily_rows: bool = False,
    include_region_breakdown: bool = True,
) -> dict[str, Any]:
    """Analyze global historical market volume and price trends for an EVE item.

    Use this by default for historical volume or trend questions that do not name a
    region or location, such as "What volume of Pioneers was sold last week?" or
    "How is Tritanium trending?". It resolves the item name, fetches public ESI
    daily regional history for every public region alias, aggregates those regional
    rows into a global daily timeline, and compares the selected period with the
    previous equal-length period.

    "Global" means all public ESI regions. Structure markets are not included
    because they require EVE SSO.
    """
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

    for region in _region_aliases():
        region_id = region["region_id"]
        history = await get_region_market_history(region_id, type_id)
        region_info = {
            "region_id": region_id,
            "region_name": region["region_name"],
        }
        if not history.get("ok"):
            status_code = history.get("status_code")
            if status_code in {400, 404, 422}:
                empty_regions.append({**region_info, "status_code": status_code})
            else:
                failed_regions.append(
                    {
                        **region_info,
                        "status_code": status_code,
                        "error": history.get("error"),
                    }
                )
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
            region_breakdown.append(
                {
                    **region_info,
                    "summary": region_summary,
                    "comparison": _compare_history_summaries(
                        region_summary,
                        previous_region_summary,
                        previous_start,
                        previous_end,
                    ),
                }
            )

    if not successful_regions:
        return {
            "ok": False,
            "error": "Failed to fetch historical market data for all public ESI regions.",
            "failed_regions": failed_regions,
            "empty_regions": empty_regions,
        }

    global_daily_rows = _aggregate_global_daily_rows(selected_regional_rows)
    previous_global_daily_rows = _aggregate_global_daily_rows(previous_regional_rows)
    summary = _summarize_history_rows(global_daily_rows)
    previous_summary = _summarize_history_rows(previous_global_daily_rows)
    region_breakdown.sort(
        key=lambda item: item["summary"]["total_volume"],
        reverse=True,
    )

    payload: dict[str, Any] = {
        "ok": True,
        "data": {
            "item": {
                "name": item["data"]["name"],
                "type_id": type_id,
            },
            "market_scope": "global",
            "date_range": {
                "period": period,
                "from_date": start.isoformat(),
                "to_date": end.isoformat(),
                "range_source": range_source,
            },
            "summary": summary,
            "comparison": _compare_history_summaries(
                summary,
                previous_summary,
                previous_start,
                previous_end,
            ),
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
    if include_region_breakdown:
        payload["data"]["region_breakdown"] = region_breakdown
    if include_daily_rows:
        payload["data"]["daily_rows"] = global_daily_rows
        payload["data"]["previous_daily_rows"] = previous_global_daily_rows
    return payload


@mcp.tool()
async def list_region_market_types(region_id: int, page: int = 1) -> dict[str, Any]:
    """List item type IDs that have public market data in a region."""
    clean_region_id = _clean_positive_int(region_id, "region_id")
    return await _get(f"/markets/{clean_region_id}/types/", {"page": _clean_page(page)})


@mcp.tool()
async def list_market_groups() -> dict[str, Any]:
    """List public EVE market group IDs."""
    return await _get("/markets/groups/")


@mcp.tool()
async def get_market_group(market_group_id: int, language: Language = "en") -> dict[str, Any]:
    """Get public details for an EVE market group, including child type IDs."""
    clean_group_id = _clean_positive_int(market_group_id, "market_group_id")
    try:
        data, response = await _request(
            "GET",
            f"/markets/groups/{clean_group_id}/",
            params={"language": language},
            headers={"Accept-Language": language},
        )
        return _ok(data, response)
    except EsiApiError as exc:
        return _error(exc)


@mcp.tool()
async def get_type_info(type_id: int, language: Language = "en") -> dict[str, Any]:
    """Get public universe metadata for an item type ID, such as name, group, and published status."""
    clean_type_id = _clean_positive_int(type_id, "type_id")
    try:
        data, response = await _request(
            "GET",
            f"/universe/types/{clean_type_id}/",
            params={"language": language},
            headers={"Accept-Language": language},
        )
        return _ok(data, response)
    except EsiApiError as exc:
        return _error(exc)


@mcp.tool()
async def resolve_universe_ids(names_json: str, language: Language = "en") -> dict[str, Any]:
    """Resolve exact EVE names to IDs.

    Use this when the user gives names instead of IDs. It can resolve inventory_types
    such as Tritanium or Pioneer, regions such as The Forge, systems such as Jita,
    and stations such as Jita IV - Moon 4 - Caldari Navy Assembly Plant.

    names_json must be a JSON array of 1 to 500 strings.
    """
    try:
        names = json.loads(names_json)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid JSON: {exc}"}
    if not isinstance(names, list) or not all(isinstance(item, str) for item in names):
        return {"ok": False, "error": "names_json must decode to an array of strings."}
    _clean_limit(len(names), "names_json length", 500)
    if any(not item.strip() for item in names):
        return {"ok": False, "error": "names_json cannot include empty names."}
    return await _resolve_ids(names, language)


@mcp.tool()
async def resolve_universe_names(ids_json: str) -> dict[str, Any]:
    """Resolve public EVE IDs to names and categories.

    ids_json must be a JSON array of 1 to 1000 integer IDs.
    """
    try:
        ids = json.loads(ids_json)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid JSON: {exc}"}
    if not isinstance(ids, list) or not all(isinstance(item, int) for item in ids):
        return {"ok": False, "error": "ids_json must decode to an array of integer IDs."}
    _clean_limit(len(ids), "ids_json length", 1000)
    try:
        data, response = await _request("POST", "/universe/names/", body=ids)
        return _ok(data, response)
    except EsiApiError as exc:
        return _error(exc)


@mcp.tool()
async def raw_public_esi_get(path: str, params_json: str | None = None) -> dict[str, Any]:
    """Make a raw GET request to a public ESI path for newly needed unauthenticated endpoints.

    The path must start with / and must not target SSO-protected structure market routes.
    params_json, when provided, must be a JSON object encoded as a string.
    """
    if not path.startswith("/"):
        return {"ok": False, "error": "path must start with /."}
    if path.startswith("/markets/structures/"):
        return {"ok": False, "error": "Structure market routes require EVE SSO and are intentionally out of scope."}
    try:
        params = json.loads(params_json) if params_json else None
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid JSON: {exc}"}
    if params is not None and not isinstance(params, dict):
        return {"ok": False, "error": "params_json must decode to an object."}
    return await _get(path, params)


@mcp.resource("eve-online://usage")
def usage_notes() -> str:
    """Usage notes for this MCP server."""
    return (
        "This server only uses public, unauthenticated EVE Online ESI endpoints. "
        "No EVE SSO app, client secret, refresh token, or OAuth scope is required. "
        "Set EVE_ESI_COMPATIBILITY_DATE to pin ESI behavior, or leave it unset to use "
        "a UTC date adjusted by 11 hours as CCP recommends. "
        "For natural-language price requests, use get_item_market_quote first. "
        "It accepts item and location names such as Tritanium in Jita, Pioneer in The Forge, "
        "or PLEX in Jita. Common IDs: The Forge region is 10000002, Jita system is "
        "30000142, Jita 4-4 station is 60003760, and Tritanium type_id is 34. "
        "For historical volume, sold-volume, or trend questions without a named "
        "region or location, use get_item_global_market_history_analysis. Use "
        "get_item_market_history_analysis only when the user specifies a region or "
        "location; ESI regional history means station aliases are analyzed through "
        "their containing region. "
        "Use list_market_prices or get_market_price for global estimates, "
        "get_region_market_orders for live regional orders, and get_region_market_history "
        "for daily regional statistics."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
