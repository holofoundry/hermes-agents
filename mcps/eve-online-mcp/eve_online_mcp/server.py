from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
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
        "'Pioneer in The Forge'. Tritanium, Pioneer, and similar names are EVE "
        "inventory types, not terrestrial commodities. Lower-level tools are also "
        "available for IDs, regional orders, regional history, market groups, and "
        "public universe item/name lookups. This server intentionally does not call "
        "SSO-protected endpoints."
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
        "Use list_market_prices or get_market_price for global estimates, "
        "get_region_market_orders for live regional orders, and get_region_market_history "
        "for daily regional statistics."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
