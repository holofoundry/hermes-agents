from __future__ import annotations

import asyncio
import json
from functools import wraps
from typing import Any, Mapping, Callable

from eve_online_mcp.client import (
    _get, _post, _request, _ok, _error, EsiApiError, 
    _normalize_name, _clean_limit, _clean_positive_int, _clean_page
)
from eve_online_mcp.constants import LOCATION_ALIASES, DEFAULT_MARKET_GROUP_ALIASES, Language

_MARKET_GROUP_DETAILS_CACHE: dict[int, dict[str, Any]] = {}
_MARKET_GROUP_CHILDREN_CACHE: dict[int, list[int]] | None = None
_MARKET_GROUP_TYPES_CACHE: dict[int, set[int]] = {}

# Demand-driven caches
_ITEM_ID_CACHE: dict[str, dict[str, Any]] = {}
_LOCATION_CACHE: dict[str, dict[str, Any]] = {}

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

async def _resolve_ids(names: list[str], language: str = "en") -> dict[str, Any]:
    return await _post(
        "/universe/ids/",
        names,
        params={"language": language},
    )

async def _resolve_inventory_type(item_name: str) -> dict[str, Any]:
    norm_name = _normalize_name(item_name)
    if norm_name in _ITEM_ID_CACHE:
        return {"ok": True, "data": _ITEM_ID_CACHE[norm_name]}

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
    
    result_data = matches[0]
    _ITEM_ID_CACHE[norm_name] = result_data
    return {"ok": True, "data": result_data, "resolved": resolved.get("data")}

async def _resolve_location(location_name: str) -> dict[str, Any]:
    norm_name = _normalize_name(location_name)
    if norm_name in _LOCATION_CACHE:
        return {"ok": True, "data": _LOCATION_CACHE[norm_name]}

    alias = LOCATION_ALIASES.get(norm_name)
    if alias:
        _LOCATION_CACHE[norm_name] = dict(alias)
        return {"ok": True, "data": dict(alias)}

    resolved = await _resolve_ids([location_name])
    if not resolved.get("ok"):
        return resolved
    data = resolved.get("data", {})
    regions = data.get("regions") or []
    systems = data.get("systems") or []
    stations = data.get("stations") or []
    
    result_data = None
    if regions:
        region = regions[0]
        result_data = {
            "name": region["name"],
            "region_id": region["id"],
            "region_name": region["name"],
            "default_scope": "region",
        }
    elif systems:
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
        result_data = {
            "name": system["name"],
            "region_id": region_id,
            "region_name": region_name,
            "system_id": system["id"],
            "system_name": system["name"],
            "default_scope": "system",
        }
    elif stations:
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
        result_data = {
            "name": station["name"],
            "region_id": region_id,
            "region_name": names_by_id.get(region_id),
            "system_id": system_id,
            "system_name": names_by_id.get(system_id),
            "station_id": station["id"],
            "station_name": station["name"],
            "default_scope": "station",
        }
    
    if result_data:
        _LOCATION_CACHE[norm_name] = result_data
        return {"ok": True, "data": result_data}

    return {
        "ok": False,
        "error": (
            f"No EVE region, system, or station was found for {location_name!r}. "
            "ESI name resolution requires an exact location name."
        ),
        "resolved": data,
    }

async def _get_all_market_group_details() -> dict[int, dict[str, Any]]:
    global _MARKET_GROUP_CHILDREN_CACHE
    if _MARKET_GROUP_CHILDREN_CACHE is not None:
        return _MARKET_GROUP_DETAILS_CACHE

    data, _ = await _request("GET", "/markets/groups/")
    group_ids = data or []
    semaphore = asyncio.Semaphore(20)

    async def fetch_group(group_id: int) -> tuple[int, dict[str, Any] | None]:
        async with semaphore:
            try:
                details, _ = await _request(
                    "GET",
                    f"/markets/groups/{group_id}/",
                    params={"language": "en"},
                    headers={"Accept-Language": "en"},
                )
                return group_id, details
            except EsiApiError:
                return group_id, None

    results = await asyncio.gather(*(fetch_group(group_id) for group_id in group_ids))
    children: dict[int, list[int]] = {}
    for group_id, details in results:
        if not details:
            continue
        _MARKET_GROUP_DETAILS_CACHE[group_id] = details
        parent_id = details.get("parent_group_id")
        if parent_id is not None:
            children.setdefault(parent_id, []).append(group_id)
    _MARKET_GROUP_CHILDREN_CACHE = children
    return _MARKET_GROUP_DETAILS_CACHE

async def _resolve_market_group_id(market_group_name: str) -> int:
    normalized = _normalize_name(market_group_name)
    if normalized in DEFAULT_MARKET_GROUP_ALIASES:
        return DEFAULT_MARKET_GROUP_ALIASES[normalized]
    if normalized.isdigit():
        return int(normalized)

    details = await _get_all_market_group_details()
    for group_id, group in details.items():
        if _normalize_name(group.get("name", "")) == normalized:
            return group_id
    raise ValueError(f"No EVE market group was found for {market_group_name!r}.")

async def _collect_market_group_type_ids(market_group_id: int) -> set[int]:
    if market_group_id in _MARKET_GROUP_TYPES_CACHE:
        return _MARKET_GROUP_TYPES_CACHE[market_group_id]

    details = await _get_all_market_group_details()
    children = _MARKET_GROUP_CHILDREN_CACHE or {}
    type_ids: set[int] = set()
    stack = [market_group_id]
    seen: set[int] = set()
    while stack:
        group_id = stack.pop()
        if group_id in seen:
            continue
        seen.add(group_id)
        group = details.get(group_id) or {}
        type_ids.update(group.get("types") or [])
        stack.extend(children.get(group_id, []))

    _MARKET_GROUP_TYPES_CACHE[market_group_id] = type_ids
    return type_ids

def _region_aliases() -> list[dict[str, Any]]:
    regions_by_id: dict[int, dict[str, Any]] = {}
    for alias in LOCATION_ALIASES.values():
        if alias.get("default_scope") == "region":
            regions_by_id[alias["region_id"]] = alias
    return sorted(regions_by_id.values(), key=lambda region: region["region_name"])

# Tool definitions
@tool
async def list_market_groups() -> dict[str, Any]:
    """List public EVE market group IDs."""
    return await _get("/markets/groups/")

@tool
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

@tool
async def get_type_info(type_id: int, language: Language = "en") -> dict[str, Any]:
    """Get public universe metadata for an item type ID."""
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

@tool
async def resolve_universe_ids(names_json: str, language: Language = "en") -> dict[str, Any]:
    """Resolve exact EVE names to IDs."""
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

@tool
async def resolve_universe_names(ids_json: str) -> dict[str, Any]:
    """Resolve public EVE IDs to names and categories."""
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

@tool
async def raw_public_esi_get(path: str, params_json: str | None = None) -> dict[str, Any]:
    """Make a raw GET request to a public ESI path."""
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

@tool
async def search_market_groups(search: str) -> dict[str, Any]:
    """Search for market groups by partial name using the local alias index and ESI group list."""
    search_norm = _normalize_name(search)
    matches = []
    for name, group_id in DEFAULT_MARKET_GROUP_ALIASES.items():
        if search_norm in name:
            matches.append({"name": name, "market_group_id": group_id, "source": "alias"})
    details = await _get_all_market_group_details()
    for group_id, group in details.items():
        name = group.get("name", "")
        if search_norm in _normalize_name(name):
            matches.append({"name": name, "market_group_id": group_id, "source": "esi"})
    seen = set()
    unique_matches = []
    for m in matches:
        if m["market_group_id"] not in seen:
            seen.add(m["market_group_id"])
            unique_matches.append(m)
    return {"ok": True, "data": unique_matches[:50]}

@tool
async def list_market_group_contents(market_group_id: int, language: Language = "en") -> dict[str, Any]:
    """List child groups and item types within a specific market group."""
    clean_id = _clean_positive_int(market_group_id, "market_group_id")
    details_map = await _get_all_market_group_details()
    group = details_map.get(clean_id)
    if not group:
        return {"ok": False, "error": f"Market group {clean_id} not found."}
    children_ids = (_MARKET_GROUP_CHILDREN_CACHE or {}).get(clean_id, [])
    child_groups = []
    for c_id in children_ids:
        c_details = details_map.get(c_id)
        if c_details:
            child_groups.append({"market_group_id": c_id, "name": c_details.get("name")})
    type_ids = group.get("types", [])
    type_details = []
    if type_ids:
        n_data, _ = await _request("POST", "/universe/names/", body=type_ids[:100])
        if n_data:
            type_details = [{"type_id": entry["id"], "name": entry["name"]} for entry in n_data]
    return {
        "ok": True, 
        "data": {
            "market_group_id": clean_id,
            "name": group.get("name"),
            "description": group.get("description"),
            "child_groups": child_groups,
            "types": type_details,
            "has_more_types": len(type_ids) > 100
        }
    }
