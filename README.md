# hrb_platform_components

Platform/admin capabilities for the HRB chatbot system: CI/CD dashboard, Interview Q&A, MCP tool catalog. No core RAG business logic, no LLM involvement.

Full design doc: `hrb_chatbot_v2`'s `docs/dev-reference/microservices-interface-matrix.html` (§5) and `docs/dev-reference/microservices-rollout-plan.html`.

**Open decision, not yet resolved:** does this deploy as its own standalone service, or mount inside `rag_retrieval_service`'s process? See `CLAUDE.md`'s "⚠ Open decision" section before writing Phase 1's spec.

Status: scaffolding only - no implementation yet. See `ROADMAP.md`.
