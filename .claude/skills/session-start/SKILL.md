---
name: session-start
description: >
  Run at the start of a Claude Code session on hrb-platform-components.
  Loads current branch, recent commits, and open work from ROADMAP.md -
  including whether Phase 0's deployment-model decision is still blocking.
  Invoke automatically on session start, or explicitly as /session-start.
allowed-tools: Read Bash(git *) Grep
---

# Session start checklist

Run these checks and report one short summary - not a wall of text.

1. `git branch --show-current` and `git log --oneline -5`.
2. Check whether Phase 0 (deployment-model decision) in `ROADMAP.md` is
   still unresolved - if so, lead with that: no Phase 1+ work should start
   until it's confirmed.
3. Count rows in `ROADMAP.md`'s "Status at a glance" table whose Status
   column contains "📋" (Planned) or "🚧" (in progress). Report the count
   and the lowest-numbered open phase by name.
4. `git status --short` - report a count of uncommitted files, or "none".

Output format:
```
Session ready.
Branch: <branch-name> | Last commit: <one-line message>
Phase 0 (deployment model): <resolved / still blocking>
ROADMAP: <count> phase(s) still open - next: <phase name>
Uncommitted changes: <count or "none">
```

Then wait for the user's instruction. Do not start work unprompted.
