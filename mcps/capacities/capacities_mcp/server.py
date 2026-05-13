from __future__ import annotations

import json
from typing import Any, Literal

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .client import CapacitiesApiError, CapacitiesClient

load_dotenv()

mcp = FastMCP("capacities")


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _error(exc: CapacitiesApiError) -> dict[str, Any]:
    return {
        "ok": False,
        "error": str(exc),
        "status_code": exc.status_code,
        "body": exc.body,
        "rate_limit": exc.headers,
    }


def _client() -> CapacitiesClient:
    return CapacitiesClient()


@mcp.tool()
async def list_spaces() -> dict[str, Any]:
    """List Capacities spaces available to the authenticated account."""
    try:
        return _ok(await _client().request("GET", "/spaces"))
    except CapacitiesApiError as exc:
        return _error(exc)


@mcp.tool()
async def get_space_info(space_id: str) -> dict[str, Any]:
    """Return object types, structures, property definitions, and collections for a Capacities space."""
    try:
        return _ok(await _client().get_space_info(space_id))
    except CapacitiesApiError as exc:
        return _error(exc)


@mcp.tool()
async def lookup_content(space_id: str, search_term: str) -> dict[str, Any]:
    """Search Capacities by title using the current /lookup endpoint."""
    try:
        return _ok(await _client().request("POST", "/lookup", json={"spaceId": space_id, "searchTerm": search_term}))
    except CapacitiesApiError as exc:
        return _error(exc)


@mcp.tool()
async def save_to_daily_note(
    space_id: str,
    md_text: str,
    origin: Literal["commandPalette"] | None = "commandPalette",
    no_timestamp: bool | None = None,
) -> dict[str, Any]:
    """Append markdown text to today's daily note in a Capacities space."""
    payload = {
        "spaceId": space_id,
        "mdText": md_text,
        "origin": origin,
        "noTimestamp": no_timestamp,
    }
    try:
        return _ok(await _client().request("POST", "/save-to-daily-note", json=payload))
    except CapacitiesApiError as exc:
        return _error(exc)


@mcp.tool()
async def save_weblink(
    space_id: str,
    url: str,
    title_overwrite: str | None = None,
    description_overwrite: str | None = None,
    tags: list[str] | None = None,
    md_text: str | None = None,
) -> dict[str, Any]:
    """Save a web link to Capacities with optional title, description, tags, and markdown notes."""
    payload = {
        "spaceId": space_id,
        "url": url,
        "titleOverwrite": title_overwrite,
        "descriptionOverwrite": description_overwrite,
        "tags": tags,
        "mdText": md_text,
    }
    try:
        return _ok(await _client().request("POST", "/save-weblink", json=payload))
    except CapacitiesApiError as exc:
        return _error(exc)


@mcp.tool()
async def create_object_link(space_id: str, object_id: str, link_type: Literal["app", "web"] = "app") -> dict[str, Any]:
    """Create a Capacities object link from a space ID and object ID. This does not call the API."""
    if link_type == "web":
        link = f"https://app.capacities.io/{space_id}/{object_id}"
    else:
        link = f"capacities://{space_id}/{object_id}"
    return _ok({"link": link, "spaceId": space_id, "objectId": object_id, "linkType": link_type})


@mcp.tool()
async def raw_capacities_request(
    method: Literal["GET", "POST"],
    path: str,
    params_json: str | None = None,
    body_json: str | None = None,
) -> dict[str, Any]:
    """Make a limited raw GET or POST request to the Capacities API for newly released beta endpoints.

    path must start with /. params_json and body_json must be JSON objects encoded as strings.
    """
    if not path.startswith("/"):
        return {"ok": False, "error": "path must start with /."}
    try:
        params = json.loads(params_json) if params_json else None
        body = json.loads(body_json) if body_json else None
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Invalid JSON: {exc}"}
    if params is not None and not isinstance(params, dict):
        return {"ok": False, "error": "params_json must decode to an object."}
    if body is not None and not isinstance(body, dict):
        return {"ok": False, "error": "body_json must decode to an object."}
    try:
        return _ok(await _client().request(method, path, params=params, json=body))
    except CapacitiesApiError as exc:
        return _error(exc)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
