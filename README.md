# hrb_platform_components

Platform/admin capabilities for the HRB chatbot system: CI/CD dashboard, Interview Q&A, MCP tool catalog. No core RAG business logic, no LLM involvement.

Full design doc: `hrb_chatbot_service`'s `docs/dev-reference/microservices-interface-matrix.html` (§5) and `docs/dev-reference/microservices-rollout-plan.html`.

**Open decision, resolved 2026-10-21: standalone.** Deploys as its own App Runner service, not mounted inside `rag_retrieval_service`'s process - see `CLAUDE.md`'s "Deployment model - resolved" section.

**Status, 2026-10-23: live in production.** Deployed to AWS App Runner (`https://pgmzxemv5z.us-east-1.awsapprunner.com`), real OAuth2 client-credentials auth to `hrb_lms_mcp` (Phase 4). Smoke-tested live via `GET /v1/admin/mcp-tools`, which reached its own real config/secrets and made a real outbound call. See `ROADMAP.md` for phase history. 3 orphan admin routes (admin-docs-sync-to-S3, request-metrics, FAQ submissions) still have no confirmed home in this repo or `rag_retrieval_service` - flagged, not resolved.
