"""FastAPI app entrypoint - CLAUDE.md's own run command (`uvicorn
src.platform.main:app`) referenced this file before it existed; created here
as part of Phase 1 since interview_qa's router needs somewhere to mount.
No RBAC/gateway layer yet (ROADMAP.md Phase 1's spec) - routes are open."""

from fastapi import FastAPI

from src.platform.build_deployment.routes import router_build_deployment
from src.platform.interview_qa.routes import router_interview_qa
from src.platform.mcp_catalog.routes import router_mcp_catalog

app = FastAPI(title="hrb_platform_components")

app.include_router(router_interview_qa, prefix="/v1/admin")
app.include_router(router_build_deployment, prefix="/v1/admin")
app.include_router(router_mcp_catalog, prefix="/v1/admin")


@app.get("/ping")
async def ping():
    return {"status": "ok"}
