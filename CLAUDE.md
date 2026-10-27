# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Platform/admin capabilities for the HRB chatbot system: the CI/CD pipeline dashboard, Interview Q&A (Postgres-backed CRUD), and the MCP tool catalog - everything admin-facing that isn't core RAG business logic. Extracted as its own repo (separate from `hrb_chatbot_v2`'s RAG core) so these capabilities have their own HLD/LLD documentation and their own place in the build sequence, distinct from "build hrb_rag_retrieval_service."

Full design (purpose, scope, the co-location recommendation and its alternative) lives in `hrb_chatbot_v2`'s `docs/dev-reference/microservices-interface-matrix.html` (§5) and `docs/dev-reference/microservices-rollout-plan.html` - read those before changing anything here.

Python 3.12, FastAPI.

## Deployment model - resolved 2026-10-21

**Standalone App Runner service, user-confirmed.** Two real options were on the table:

1. ~~Mounted inside `hrb_rag_retrieval_service`'s process~~ - not actually available today: `hrb_rag_retrieval_service` doesn't exist yet (a future RAG-service-split target, not a real service to mount into). Real isolation vs. that future service was the original tradeoff, but there's nothing to mount into right now.
2. **Its own standalone App Runner service** (chosen) - real isolation (a bug here can't take down RAG retrieval, whenever that service exists), a new always-on compute cost for low-traffic admin features, accepted. This repo was already scaffolded to run standalone (`uvicorn src.platform.main:app`), so no scaffolding change needed - this just confirms that's the real target, not a placeholder.

## Commands

```bash
# install
pip install -r requirements.txt

# run standalone (option 2) - or import as a dependency (option 1)
uvicorn src.platform.main:app --reload --port 8200

# test
pytest -v
```

## Architecture

Three sub-capabilities, each its own module, no cross-dependencies between them:
- `src/platform/interview_qa/` - Postgres-backed Interview Q&A CRUD (extracted from `hrb_chatbot_v2`'s Phase 187 `interview_qa_store.py` + `manage_admin.py` routes)
- `src/platform/build_deployment/` - CI/CD pipeline dashboard (GitHub Actions status, golden dataset gate)
- `src/platform/mcp_catalog/` - MCP tool catalog discovery (extracted from Phase 239's `mcp_tools/__init__.py` additions)

**Corrected 2026-10-21** - this used to claim none of the three import the `mcp` extra at all ("zero LLM involvement"); that was wrong for `mcp_catalog` specifically, found and fixed while scoping Phase 3: it ports Phase 239's real tool discovery (a live `session.list_tools()` call against the configured MCP server), so it genuinely needs `hrb-common-libs`' `mcp` extra (`call_mcp_tool`/`list_mcp_tools`). `interview_qa`/`build_deployment` still import none of `llm`/`mcp`/`storage`/`web` - that part was correct. No module imports `llm` - that's the real "zero LLM involvement" claim, still true.

## Spec-Driven Development

Same convention as `hrb_chatbot_v2`: a spec is a `**Spec:**` block in `ROADMAP.md`'s `## Phases` section, written before that phase's code starts. `.claude/scripts/spec_gate.py` blocks a `Write`/`Edit` under `src/platform/**` unless `ROADMAP.md` has an open, spec'd phase.

**Four working norms:**
- **One task at a time.**
- **Flag, don't fix.**
- **Nothing gets pushed without the user's own review and explicit go-ahead first.**
- **The deployment-model decision above must be confirmed before Phase 1's spec is written** - don't let it default silently to either option.

**Available skills**: `session-start`, `delivery-note`, `spec-new`, `spec-implement`.
**Subagents**: `.claude/agents/implementer.md`, `.claude/agents/code-reviewer.md`.
