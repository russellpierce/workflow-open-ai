# PRD: Workflow-as-Models - Phase 1

**Contract**: ./contract.md
**Phase**: 1 of 3
**Focus**: Strip dead code, rename package, reset git — the hard fork

## Phase Overview

Phase 1 is the demolition and renaming pass. The current `skeleton_open_ai` package carries significant batch-proxy, override-engine, passthrough, and Redis infrastructure that doesn't serve the workflow-as-models architecture. All of it gets removed.

This phase is sequenced first because every subsequent phase builds on a clean foundation. Working on top of dead code creates confusion about what's live and what's legacy. By stripping first, Phase 2 starts with a minimal, bootable server that has auth, health, CORS, error handling, and nothing else.

After this phase completes: the server boots, the health endpoint responds, API key auth works, and the codebase is clean and renamed to `workflow_open_ai`. No functional endpoints beyond health exist yet — that's Phase 2.

## User Stories

1. As a developer, I want the codebase stripped of batch/override/passthrough/Redis code so that I can reason about the architecture without dead weight.
2. As a developer, I want the package renamed to `workflow_open_ai` so that imports and naming reflect the project's purpose.
3. As a developer, I want a fresh git history so that the fork is a clean starting point.

## Functional Requirements

### Code Removal

- **FR-1.1**: Remove the entire `batch/` directory (handler, openai_client, redis_store, hasher)
- **FR-1.2**: Remove the entire `override_proxy/` directory (config, engine)
- **FR-1.3**: Remove the `modes/` directory and all mode sub-packages (batch_proxy, passthrough, workflow provider)
- **FR-1.4**: Remove `routes_dispatch.py` (mode dispatch router)
- **FR-1.5**: Remove `routes_chat.py` and `routes_models.py` (legacy routers)
- **FR-1.6**: Remove `workflow.py` (will be recreated in Phase 2 as a discovered workflow)
- **FR-1.7**: Remove `schemas.py` (will be rebuilt in Phase 2 for the new architecture)
- **FR-1.8**: Remove all existing tests in `tests/` (they test removed code)
- **FR-1.9**: Remove `docs/ideation/batch-proxy/` and `docs/ideation/override-proxy/`

### Package Rename

- **FR-1.10**: Rename package directory from `src/skeleton_open_ai/` to `src/workflow_open_ai/`
- **FR-1.11**: Update `pyproject.toml`: package name, entry points, all references
- **FR-1.12**: Update all internal imports to `workflow_open_ai`
- **FR-1.13**: Update `Dockerfile` references
- **FR-1.14**: Update `docker-compose.yml` service names and references

### Minimal Bootable Server

- **FR-1.15**: `main.py` boots a FastAPI app with CORS, error handling, and health endpoint
- **FR-1.16**: `config.py` loads a simplified `config.yaml` (server, auth, cors, workflows_dir)
- **FR-1.17**: `auth.py` and `key_config.py` preserved and working under new package name
- **FR-1.18**: `errors.py` preserved (OpenAI-compatible error responses)
- **FR-1.19**: `routes_health.py` preserved
- **FR-1.20**: `config.yaml` updated: remove routes, redis, models sections; add `workflows_dir` field

### Git Reset

- **FR-1.21**: Fresh `git init` with initial commit of the cleaned codebase

## Non-Functional Requirements

- **NFR-1.1**: Server starts in under 2 seconds with no workflows configured
- **NFR-1.2**: No import errors or missing module references after rename
- **NFR-1.3**: Zero references to `skeleton_open_ai` remain in the codebase

## Dependencies

### Prerequisites

- Existing codebase in working state (reference for what to keep)

### Outputs for Next Phase

- Clean `workflow_open_ai` package with auth, health, CORS, error handling
- Simplified `config.yaml` with `workflows_dir` field
- Bootable FastAPI server ready for new route registration

## Acceptance Criteria

- [ ] `src/workflow_open_ai/` exists; `src/skeleton_open_ai/` does not
- [ ] No `batch/`, `override_proxy/`, `modes/` directories exist
- [ ] No `routes_dispatch.py`, `routes_chat.py`, `routes_models.py`, `workflow.py`, `schemas.py`
- [ ] `pyproject.toml` references `workflow_open_ai` throughout
- [ ] Server starts: `uvicorn workflow_open_ai.main:app` succeeds
- [ ] `GET /health` returns 200
- [ ] Auth rejects requests without valid Bearer token
- [ ] `config.yaml` has `workflows_dir` field, no `routes`/`redis`/`models` sections
- [ ] `grep -r skeleton_open_ai` returns zero matches in `src/`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`
- [ ] Fresh git repo with single initial commit

---

*Review this PRD and provide feedback before spec generation.*
