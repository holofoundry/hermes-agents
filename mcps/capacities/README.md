# Capacities MCP for Hermes

A small local stdio MCP server for the Capacities REST API.

## What it exposes

- `list_spaces`
- `get_space_info`
- `lookup_content`
- `save_to_daily_note`
- `save_weblink`
- `create_object_link`
- `raw_capacities_request`

The server uses the Capacities REST API at `https://api.capacities.io` with a bearer token from the desktop app: Settings > Capacities API.

Capacities also offers an official hosted MCP server at `https://api.capacities.io/mcp`. This local MCP exists for Hermes-style stdio workflows or for cases where you want direct REST wrapper tools.

## Install

```bash
cd /path/to/capacities-mcp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
cp .env.example .env
nano .env
```

Set:

```bash
CAPACITIES_API_TOKEN=your_token_here
```

## Smoke test

```bash
source .venv/bin/activate
python -c "from capacities_mcp.server import mcp; print('import ok')"
python -m capacities_mcp.server
```

The second command should stay running silently because it is waiting for MCP messages over stdio. Stop it with Ctrl+C.

## Hermes config

Add this as a top-level key in `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  capacities:
    command: "/absolute/path/to/capacities-mcp/.venv/bin/python"
    args:
      - "-m"
      - "capacities_mcp.server"
    env:
      CAPACITIES_API_TOKEN: "your_capacities_api_token_here"
    enabled: true
    timeout: 120
    connect_timeout: 60
    tools:
      resources: false
      prompts: false
```

Then test:

```bash
hermes mcp test capacities
```

## Security notes

Do not commit `.env` or your Hermes config if it contains your Capacities API token. The token can access your Capacities data. Rotate it immediately if it is exposed.
