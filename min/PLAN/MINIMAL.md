# MINIMAL.md
This file provides guidance to Minimal when working in this repository.

## Architecture
This is a multi-component LLM-assisted development system:
- **RepoContext** (`PLAN-init-1-repo-engine.md`) — scans repository structure, extracts symbols and metadata
- **ContextManager** (`PLAN.md`) — manages chat context: add, drop, ls, get_messages for session state
- **EditEngine** (`PLAN.md`) — applies, validates, rolls back changes; streams chat responses
- **Frontend** (`PLAN-init-3-frontend-prompt.md`) — browseDir, filterName, rawEntries, matches for file discovery
- **Backend** (`PLAN-init-2-backend.md`) — repo_map generation and _build_init_context for LLM initialization

## Gotchas
- Frontend init uses `afterCmd`, `lastSlash` pattern for command parsing — these are critical for path handling
- The `init_system` flag gates initialization behavior — check this before assuming context is loaded
- ContextManager requires explicit `drop` calls — orphaned context accumulates otherwise

## Commands
No runnable manifests detected in repo map. Check for `package.json`, `Cargo.toml`, or similar in root for build/test commands.
