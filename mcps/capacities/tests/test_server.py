import pytest
from capacities_mcp.server import mcp

@pytest.mark.asyncio
async def test_tool_registration():
    tools = await mcp.list_tools()
    tool_names = [tool.name for tool in tools]
    assert "list_spaces" in tool_names
    assert "get_space_info" in tool_names
    assert "lookup_content" in tool_names
    assert "save_to_daily_note" in tool_names
    assert "save_weblink" in tool_names
    assert "create_object_link" in tool_names
    assert "raw_capacities_request" in tool_names

@pytest.mark.asyncio
async def test_tool_docstrings():
    tools = await mcp.list_tools()
    list_spaces_tool = next(t for t in tools if t.name == "list_spaces")
    assert "List Capacities spaces" in list_spaces_tool.description
