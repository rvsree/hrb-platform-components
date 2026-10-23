"""Ported from hrb_chatbot_v2's api/admin/manage_admin.py (line ~824) - the
1 /mcp-tools route. Same no-RBAC adaptation as Phase 1/2 (ROADMAP.md
Phase 3's spec) - require_role()/query-param identity dropped."""

from fastapi import APIRouter

from src.platform.mcp_catalog import catalog as catalog_module
from src.platform.mcp_catalog.models import McpToolCatalogResponse, McpToolSummary

router_mcp_catalog = APIRouter(tags=["mcp-catalog"])


@router_mcp_catalog.get("/mcp-tools", response_model=McpToolCatalogResponse)
async def get_mcp_tools():
    """Never 500s on an MCP-side failure - error-as-data, same convention
    every other MCP-backed call follows."""
    result = await catalog_module.get_mcp_tool_catalog()
    return McpToolCatalogResponse(tools=[McpToolSummary(**tool) for tool in result["tools"]], error=result["error"])
