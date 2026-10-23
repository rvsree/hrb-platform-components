"""Mechanism-level tests for discover_mcp_tools()/get_mcp_tool_catalog()
(ROADMAP.md Phase 3's spec) - hrb_common.mcp.client.list_mcp_tools() is
always faked here. No real MCP server is ever contacted.

Phase 4 - _get_access_token() now does a real OAuth2 client-credentials
flow (a real HTTP call) - faked here too, same no-live-call rule."""

from src.platform.mcp_catalog import catalog as catalog_module


async def test_discover_mcp_tools_tags_server_id_and_remaps_input_schema(monkeypatch):
    async def fake_list_mcp_tools(server_url, access_token=None):
        return [{"name": "get_leave_balance", "description": "d", "inputSchema": {"type": "object"}, "annotations": None}]

    async def fake_get_access_token():
        return "fake-token"

    monkeypatch.setattr(catalog_module, "list_mcp_tools", fake_list_mcp_tools)
    monkeypatch.setattr(catalog_module, "_get_access_token", fake_get_access_token)

    tools = await catalog_module.discover_mcp_tools("hrb_lms_mcp", "HRB_LMS_MCP_URL")

    assert tools == [
        {"name": "get_leave_balance", "description": "d", "input_schema": {"type": "object"}, "server_id": "hrb_lms_mcp"}
    ]


async def test_get_mcp_tool_catalog_merges_servers_and_caches(monkeypatch):
    catalog_module._tool_catalog_cache = None
    calls = []

    async def fake_discover(server_id, url_setting_name):
        calls.append(server_id)
        return [{"name": "tool_a", "description": "", "input_schema": {}, "server_id": server_id}]

    monkeypatch.setattr(catalog_module, "discover_mcp_tools", fake_discover)

    first = await catalog_module.get_mcp_tool_catalog()
    assert first["error"] is None
    assert len(first["tools"]) == 1
    assert calls == ["hrb_lms_mcp"]

    # Second call without force_refresh should hit the cache, not call discover again.
    second = await catalog_module.get_mcp_tool_catalog()
    assert second == first
    assert calls == ["hrb_lms_mcp"]

    # force_refresh bypasses the cache.
    await catalog_module.get_mcp_tool_catalog(force_refresh=True)
    assert calls == ["hrb_lms_mcp", "hrb_lms_mcp"]


async def test_get_access_token_uses_the_real_oauth2_flow(monkeypatch):
    """Phase 4 - confirms _get_access_token() really calls
    OAuth2ClientCredentials.get_access_token(), not a static env read."""
    catalog_module._oauth_client = None
    captured = {}

    async def fake_get_access_token(self):
        captured["token_url"] = self.token_url
        captured["client_id"] = self.client_id
        return "real-token"

    monkeypatch.setenv("HRB_LMS_MCP_OAUTH_TOKEN_URL", "https://example.test/oauth/token")
    monkeypatch.setenv("HRB_LMS_MCP_OAUTH_CLIENT_ID", "hrb-platform-components")
    monkeypatch.setattr(
        catalog_module.OAuth2ClientCredentials, "get_access_token", fake_get_access_token
    )

    token = await catalog_module._get_access_token()

    assert token == "real-token"
    assert captured["token_url"] == "https://example.test/oauth/token"
    assert captured["client_id"] == "hrb-platform-components"


async def test_get_mcp_tool_catalog_is_error_as_data_on_discovery_failure(monkeypatch):
    catalog_module._tool_catalog_cache = None

    async def fake_discover_raises(server_id, url_setting_name):
        raise RuntimeError("server unreachable")

    monkeypatch.setattr(catalog_module, "discover_mcp_tools", fake_discover_raises)

    result = await catalog_module.get_mcp_tool_catalog()

    assert result["tools"] == []
    assert "hrb_lms_mcp" in result["error"]
    assert "server unreachable" in result["error"]
