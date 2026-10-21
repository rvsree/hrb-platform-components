# hrb_platform_components Roadmap

Phase-by-phase plan and history, same convention as `hrb_chatbot_v2`'s `docs/agent-reference/RAG-ROADMAP.md`.

## Status at a glance

| Phase | Title | Status | Spec |
|---|---|---|---|
| 0 | Deployment-model decision | ⚠ Blocking | N/A - a decision, not a spec |
| 1 | interview_qa extraction | 📋 Planned | not yet written |
| 2 | build_deployment extraction | 📋 Planned | not yet written |
| 3 | mcp_catalog extraction | 📋 Planned | not yet written |

## Phases

- [ ] **Phase 0 (blocking, not a code phase) — confirm deployment model.** Standalone service vs. mounted inside `rag_retrieval_service`. See `CLAUDE.md`'s "⚠ Open decision" section. Must be resolved before Phase 1's spec is written - it changes where this code's Dockerfile/App Runner config lives, not the code itself.

- [ ] **Phase 1 (planned) — interview_qa extraction.** Port `hrb_chatbot_v2`'s `interview_qa_store.py` + the `/interview-qa` routes from `manage_admin.py`. Behavior must not change - ported tests pass unmodified.

- [ ] **Phase 2 (planned) — build_deployment extraction.** Port the CI/CD pipeline dashboard routes (`pipeline_run_store.py`, `eval_run_store.py`, `golden_dataset_store.py` and their routes).

- [ ] **Phase 3 (planned) — mcp_catalog extraction.** Port Phase 239's `get_mcp_tool_catalog()`/`discover_mcp_tools()` and the `/mcp-tools` route.
