from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from .client import CapacitiesApiError, CapacitiesClient

# Constants for Holo Foundry
HOLO_FOUNDRY_SPACE_ID = "0baa9384-e3a6-48c3-8f46-a72e941debaa"
WEEK_NOTES_COLLECTION_ID = "3cec11ee-aaf3-42f1-9647-58cb4516ca2e"
ROOT_PAGE_STRUCTURE_ID = "RootPage"
ROOT_DAILY_NOTE_STRUCTURE_ID = "RootDailyNote"

# Configure logging to stderr so it doesn't interfere with the MCP stdout protocol
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("capacities-mcp")

mcp = FastMCP("capacities")


_client_instance = CapacitiesClient()


def _client() -> CapacitiesClient:
    return _client_instance


@mcp.tool()
async def list_spaces() -> Any:
    """List Capacities spaces available to the authenticated account."""
    logger.info("Calling list_spaces")
    return await _client().request("GET", "/spaces")


@mcp.tool()
async def get_space_info(space_id: str) -> Any:
    """Return object types, structures, property definitions, and collections for a Capacities space."""
    logger.info(f"Calling get_space_info for space: {space_id}")
    return await _client().get_space_info(space_id)


@mcp.tool()
async def lookup_content(space_id: str, search_term: str) -> Any:
    """Search Capacities by title using the current /lookup endpoint."""
    logger.info(f"Calling lookup_content in space {space_id} for '{search_term}'")
    return await _client().request("POST", "/lookup", json={"spaceId": space_id, "searchTerm": search_term})


@mcp.tool()
async def save_to_daily_note(
    space_id: str,
    md_text: str,
    origin: Literal["commandPalette"] | None = "commandPalette",
    no_timestamp: bool | None = None,
) -> Any:
    """Append markdown text to today's daily note in a Capacities space."""
    logger.info(f"Calling save_to_daily_note for space: {space_id}")
    payload = {
        "spaceId": space_id,
        "mdText": md_text,
        "origin": origin,
        "noTimestamp": no_timestamp,
    }
    return await _client().request("POST", "/save-to-daily-note", json=payload)


@mcp.tool()
async def save_weblink(
    space_id: str,
    url: str,
    title_overwrite: str | None = None,
    description_overwrite: str | None = None,
    tags: list[str] | None = None,
    md_text: str | None = None,
) -> Any:
    """Save a web link to Capacities with optional title, description, tags, and markdown notes."""
    logger.info(f"Calling save_weblink for space: {space_id}, url: {url}")
    payload = {
        "spaceId": space_id,
        "url": url,
        "titleOverwrite": title_overwrite,
        "descriptionOverwrite": description_overwrite,
        "tags": tags,
        "mdText": md_text,
    }
    return await _client().request("POST", "/save-weblink", json=payload)


@mcp.tool()
async def create_object_link(space_id: str, object_id: str, link_type: Literal["app", "web"] = "app") -> dict[str, Any]:
    """Create a Capacities object link from a space ID and object ID. This does not call the API."""
    logger.info(f"Calling create_object_link for space: {space_id}, object: {object_id}")
    if link_type == "web":
        link = f"https://app.capacities.io/{space_id}/{object_id}"
    else:
        link = f"capacities://{space_id}/{object_id}"
    return {"link": link, "spaceId": space_id, "objectId": object_id, "linkType": link_type}


@mcp.tool()
async def raw_capacities_request(
    method: Literal["GET", "POST"],
    path: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    """Make a limited raw GET or POST request to the Capacities API for newly released beta endpoints.

    path must start with /. params and body must be JSON objects (dictionaries).
    """
    logger.info(f"Calling raw_capacities_request: {method} {path}")
    if not path.startswith("/"):
        raise ValueError("path must start with /.")

    return await _client().request(method, path, params=params, json=body)


@mcp.tool()
async def create_week_note(week_type: Literal["current", "previous"]) -> dict[str, Any]:
    """Create a week note by aggregating daily notes from the current or previous week.

    The week note is created in the 'Week Notes' collection in Holo Foundry.
    """
    logger.info(f"Creating week note for {week_type} week")

    # Calculate date range
    today = datetime.now().date()
    if week_type == "current":
        # Monday of current week
        start_date = today - timedelta(days=today.weekday())
    else:
        # Monday of previous week
        start_date = today - timedelta(days=today.weekday() + 7)

    end_date = start_date + timedelta(days=6)
    date_range_str = f"{start_date.isoformat()} to {end_date.isoformat()}"
    logger.info(f"Target week range: {date_range_str}")

    aggregated_content = f"# Week Note: {date_range_str}\n\n"
    aggregated_content += f"Aggregated from daily notes in Holo Foundry.\n\n"

    found_any = False
    for i in range(7):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.isoformat()

        logger.info(f"Retrieving daily note for {date_str}...")
        try:
            # Lookup the daily note
            lookup_results = await _client().request(
                "POST", "/lookup", json={"spaceId": HOLO_FOUNDRY_SPACE_ID, "searchTerm": date_str}
            )

            daily_note_id = None
            if lookup_results and "results" in lookup_results:
                for result in lookup_results["results"]:
                    if result.get("structureId") == ROOT_DAILY_NOTE_STRUCTURE_ID:
                        daily_note_id = result.get("id")
                        break

            if daily_note_id:
                # Get the content
                content_data = await _client().get_object_content(HOLO_FOUNDRY_SPACE_ID, daily_note_id)
                # content_data is expected to be a dict with 'content' or similar, or just markdown
                content = ""
                if isinstance(content_data, str):
                    content = content_data
                elif isinstance(content_data, dict):
                    content = content_data.get("content") or content_data.get("markdown") or str(content_data)
                
                if content:
                    aggregated_content += f"## {date_str}\n\n{content}\n\n---\n\n"
                    found_any = True
                else:
                    aggregated_content += f"## {date_str}\n\n*No content found.*\n\n---\n\n"
            else:
                aggregated_content += f"## {date_str}\n\n*Daily note not found.*\n\n---\n\n"

        except Exception as e:
            logger.warning(f"Error retrieving daily note for {date_str}: {e}")
            aggregated_content += f"## {date_str}\n\n*Error retrieving daily note.*\n\n---\n\n"

    if not found_any:
        logger.warning("No daily notes with content found for the selected week.")

    # Create the week note page
    title = f"Week Note: {date_range_str}"
    try:
        result = await _client().create_object(
            space_id=HOLO_FOUNDRY_SPACE_ID,
            structure_id=ROOT_PAGE_STRUCTURE_ID,
            title=title,
            content=aggregated_content,
            collection_id=WEEK_NOTES_COLLECTION_ID,
        )
        logger.info(f"Successfully created week note: {title}")
        return {"status": "success", "title": title, "result": result}
    except Exception as e:
        logger.error(f"Failed to create week note: {e}")
        return {"status": "error", "message": str(e), "title": title, "aggregated_content": aggregated_content}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
