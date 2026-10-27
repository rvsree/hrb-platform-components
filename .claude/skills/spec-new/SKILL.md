# Write a new spec

A spec is a `**Spec:**` block written into the target phase's own bullet
in `ROADMAP.md`'s `## Phases` section, **before** that phase's code starts.

**Before writing Phase 1's spec:** confirm Phase 0 (deployment model -
standalone service vs. mounted inside `hrb_rag_retrieval_service`) is actually
resolved with the user. Don't let it default silently.

## Steps

1. Find the target phase's `- [ ]` bullet in `ROADMAP.md`'s `## Phases` section.
2. Append a nested `**Spec:**` sub-list:

   ```
   - **Spec:**
     - **Context:** why this phase, what triggered it.
     - **Source:** which hrb_chatbot_v2 file(s) this extracts from.
     - **Behavior parity:** which existing hrb_chatbot_v2 tests must pass
       unmodified against the extracted code.
     - **Out of scope:** what this phase deliberately does not do.
     - **Open questions:** anything needing a decision before/during implementation.
   ```

3. Set the phase's checkbox to `- [ ]` if not already.
4. No implementation code in this step - report the spec for review first.
