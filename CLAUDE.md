# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Platform/admin capabilities for the HRB chatbot system: the CI/CD pipeline dashboard, Interview Q&A (Postgres-backed CRUD), and the MCP tool catalog - everything admin-facing that isn't core RAG business logic. Extracted as its own repo (separate from `hrb_chatbot_v2`'s RAG core) so these capabilities have their own HLD/LLD documentation and their own place in the build sequence, distinct from "build rag_retrieval_service."

Full design (purpose, scope, the co-location recommendation and its alternative) lives in `hrb_chatbot_v2`'s `docs/dev-reference/microservices-interface-matrix.html` (§5) and `docs/dev-reference/microservices-rollout-plan.html` - read those before changing anything here.

Python 3.12, FastAPI.

## ⚠ Open decision - not yet resolved

**Separate repo does not automatically mean separate deployed service.** Two real options, cost/isolation tradeoff unresolved as of repo creation (2026-10-21):

1. **Mounted inside `rag_retrieval_service`'s process** (original recommendation) - this code ships as a dependency of that service, runs in the same App Runner deployment, zero extra AWS cost. Matches the earlier "co-located, not its own deployable" decision.
2. **Its own standalone App Runner service** - real isolation (a bug here can't take down RAG retrieval), but a new always-on compute cost for low-traffic admin features.

This repo is scaffolded to run standalone (`uvicorn src.platform.main:app`) so option 2 is possible, but nothing here commits to that choice over option 1. **Confirm which before writing the first real phase's spec** - it changes the deployment target, not the code itself.

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

None of these import `llm`, `mcp` (the client extra, not this module), `storage`, or `web` from `hrb-common-libs` - zero LLM involvement, confirmed directly by journey 5 in the User Journey Capability Map.

## Spec-Driven Development

Same convention as `hrb_chatbot_v2`: a spec is a `**Spec:**` block in `ROADMAP.md`'s `## Phases` section, written before that phase's code starts. `.claude/scripts/spec_gate.py` blocks a `Write`/`Edit` under `src/platform/**` unless `ROADMAP.md` has an open, spec'd phase.

**Four working norms:**
- **One task at a time.**
- **Flag, don't fix.**
- **Nothing gets pushed without the user's own review and explicit go-ahead first.**
- **The deployment-model decision above must be confirmed before Phase 1's spec is written** - don't let it default silently to either option.

**Available skills**: `session-start`, `delivery-note`, `spec-new`, `spec-implement`.
**Subagents**: `.claude/agents/implementer.md`, `.claude/agents/code-reviewer.md`.
