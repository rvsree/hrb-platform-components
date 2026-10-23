"""Route-level test for GET /v1/admin/mcp-tools (ROADMAP.md Phase 3's spec).
No real MCP server is ever contacted - get_mcp_tool_catalog() is faked."""

from fastapi.testclient import TestClient

from src.platform.mcp_catalog import catalog as catalog_module
from src.platform.main import app

client = TestClient(app)


def test_get_mcp_tools_returns_the_catalog(monkeypatch):
    async def fake_get_mcp_tool_catalog(force_refresh=False):
        return {
            "tools": [{"name": "get_leave_balance", "description": "d", "input_schema": {"type": "object"}, "server_id": "hrb_lms_mcp"}],
            "error": None,
        }

    monkeypatch.setattr(catalog_module, "get_mcp_tool_catalog", fake_get_mcp_tool_catalog)

    response = client.get("/v1/admin/mcp-tools")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["tools"][0]["name"] == "get_leave_balance"


def test_get_mcp_tools_never_500s_on_discovery_error(monkeypatch):
    async def fake_get_mcp_tool_catalog(force_refresh=False):
        return {"tools": [], "error": "hrb_lms_mcp: server unreachable"}

    monkeypatch.setattr(catalog_module, "get_mcp_tool_catalog", fake_get_mcp_tool_catalog)

    response = client.get("/v1/admin/mcp-tools")

    assert response.status_code == 200
    body = response.json()
    assert body["tools"] == []
    assert "server unreachable" in body["error"]
