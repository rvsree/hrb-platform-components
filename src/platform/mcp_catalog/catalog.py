"""Ported from hrb_chatbot_v2's ai/rag_pipeline/tools/mcp_tools/__init__.py
(Phase 239) - discover_mcp_tools()/get_mcp_tool_catalog() only (ROADMAP.md
Phase 3's spec). Uses hrb-common-libs' own hrb_common.mcp.client.
list_mcp_tools() instead of re-opening a raw MCP session - that function
already does the session-open/list_tools()/close; this module just tags
each returned tool with which configured server it came from and merges
multiple servers into one catalog, same as the original.

Phase 4 - real OAuth2 client-credentials flow (hrb_common.auth.oauth_client),
replacing Phase 3's static-token stub. Same env var names hrb_chatbot_v2's
own auth_client/oauth_client.py reads."""

from hrb_common.auth.oauth_client import OAuth2ClientCredentials
from hrb_common.mcp.client import list_mcp_tools
from hrb_common.observability.logger import get_logger
from hrb_common.observability.secrets import read_secret

logger = get_logger("mcp_catalog")

# One entry today, same as the original - extending to a second real MCP
# server means adding a dict entry, not rewriting how a tool call is routed.
MCP_SERVERS: dict[str, str] = {"hrb_lms_mcp": "HRB_LMS_MCP_URL"}

_tool_catalog_cache: dict[str, dict] | None = None

_oauth_client: OAuth2ClientCredentials | None = None


def _get_oauth_client() -> OAuth2ClientCredentials:
    """Lazy singleton, same convention as this project's other client gateways."""
    global _oauth_client
    if _oauth_client is None:
        _oauth_client = OAuth2ClientCredentials(
            token_url=read_secret("HRB_LMS_MCP_OAUTH_TOKEN_URL", "http://127.0.0.1:8190/oauth/token"),
            client_id=read_secret("HRB_LMS_MCP_OAUTH_CLIENT_ID", ""),
            client_secret=read_secret("HRB_LMS_MCP_OAUTH_CLIENT_SECRET", ""),
        )
    return _oauth_client


async def _get_access_token() -> str:
    """Real OAuth2 client-credentials flow - see module docstring."""
    return await _get_oauth_client().get_access_token()


async def discover_mcp_tools(server_id: str, url_setting_name: str) -> list[dict]:
    """One server's own real tool catalog - name/description/input_schema
    exactly as that server advertises them. Raises on failure - the caller
    (get_mcp_tool_catalog) decides how to degrade."""
    mcp_url = read_secret(url_setting_name, "http://127.0.0.1:8190/mcp")
    access_token = await _get_access_token()

    tools = await list_mcp_tools(mcp_url, access_token=access_token)
    return [
        {
            "name": tool["name"],
            "description": tool.get("description") or "",
            "input_schema": tool["inputSchema"],
            "server_id": server_id,
        }
        for tool in tools
    ]


async def get_mcp_tool_catalog(force_refresh: bool = False) -> dict:
    """Every configured server's own catalog (MCP_SERVERS), merged into one
    tool_name -> tool dict. In-process cached - force_refresh bypasses it.
    Never raises - error-as-data; a failed server's tools are simply absent
    from the merged catalog."""
    global _tool_catalog_cache
    if _tool_catalog_cache is not None and not force_refresh:
        return {"tools": list(_tool_catalog_cache.values()), "error": None}

    catalog: dict[str, dict] = {}
    errors: list[str] = []
    for server_id, url_setting_name in MCP_SERVERS.items():
        try:
            tools = await discover_mcp_tools(server_id, url_setting_name)
        except Exception as error:
            logger.warning("MCP tool discovery failed for %s: %s", server_id, error)
            errors.append(f"{server_id}: {error}")
            continue
        for tool in tools:
            catalog[tool["name"]] = tool

    _tool_catalog_cache = catalog
    return {"tools": list(catalog.values()), "error": "; ".join(errors) if errors else None}
