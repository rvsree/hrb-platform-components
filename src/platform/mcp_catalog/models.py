"""Ported as-is from hrb_chatbot_v2's models/admin.py (Phase 239)."""

from pydantic import BaseModel


class McpToolSummary(BaseModel):
    """One tool, exactly as its own MCP server advertises it via
    session.list_tools() - not inferred from a hardcoded wrapper function."""

    name: str
    description: str
    input_schema: dict
    server_id: str


class McpToolCatalogResponse(BaseModel):
    tools: list[McpToolSummary]
    error: str | None
