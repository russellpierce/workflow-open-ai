# PRD: Workflow-as-Models - Phase 3

**Contract**: ./contract.md
**Phase**: 3 of 3
**Focus**: Tests, Docker updates, and deployment readiness

## Phase Overview

Phase 3 hardens the new architecture with comprehensive tests and updated deployment configuration. The functional work is done in Phases 1-2; this phase ensures it's reliable and deployable.

This phase is sequenced last because tests and deployment config depend on the final architecture being stable. Writing tests against Phase 1's stripped server would be throwaway work once Phase 2 adds the real functionality.

After this phase completes: the project has test coverage for discovery, routing, endpoints, and error cases. Docker and docker-compose are updated for the new package. The project is ready for development use.

## User Stories

1. As a developer, I want comprehensive tests so that I can refactor with confidence and catch regressions.
2. As a developer, I want Docker builds to work so that I can deploy the service in containers.
3. As a developer, I want a working example workflow and clear config so that I can onboard quickly.
4. As a developer, I want a smoke test script I can run against a live server to verify everything works end-to-end without digging through test code.

## Functional Requirements

### Test Suite

- **FR-3.1**: Unit tests for workflow discovery: finds files, extracts model names, handles filename default, handles MODEL_NAME override
- **FR-3.2**: Unit tests for discovery error cases: missing `run()`, duplicate model names, empty directory, nonexistent directory
- **FR-3.3**: Unit tests for `WorkflowContext` construction from request data
- **FR-3.4**: Integration tests for `GET /v1/models`: returns discovered workflows, requires auth
- **FR-3.5**: Integration tests for `POST /v1/chat/completions`: routes to correct workflow, returns valid response, rejects unknown model, requires auth
- **FR-3.6**: Unit test for response formatting: string wrapped correctly in chat.completion shape
- **FR-3.7**: Test that workflow receives correct `WorkflowContext` fields (endpoint_path, body, headers, query_params, caller_key, key_entry)

### Docker & Deployment

- **FR-3.8**: `Dockerfile` updated: references `workflow_open_ai`, copies workflows directory
- **FR-3.9**: `docker-compose.yml` updated: remove Redis service, update service name, mount workflows directory
- **FR-3.10**: Remove Redis dependency from pyproject.toml (redis, fakeredis)
- **FR-3.11**: Remove tenacity dependency (was for batch polling)

### Smoke Test Script

- **FR-3.12**: Create `scripts/smoketest.sh` — a bash script that runs against a live server and validates the full stack
- **FR-3.13**: Smoke test checks: health endpoint returns 200, `/v1/models` returns the discovered workflow(s), `/v1/chat/completions` with a valid model returns a well-formed chat completion response, auth is enforced (request without Bearer token returns 401), unknown model returns 404
- **FR-3.14**: Script accepts server URL and API key as arguments (with sensible defaults for local dev, e.g., `http://localhost:8000`)
- **FR-3.15**: Script exits non-zero on first failure with a clear message indicating which check failed
- **FR-3.16**: Script is executable and self-documented (`--help` flag)

### Config & Documentation

- **FR-3.17**: `config.yaml` is clean and documented with comments
- **FR-3.18**: `api_keys.yaml.example` updated (remove retry_buffer_ttl_seconds, show extra fields example)

## Non-Functional Requirements

- **NFR-3.1**: Test suite runs in under 10 seconds
- **NFR-3.2**: Test coverage for all discovery, routing, and endpoint code paths
- **NFR-3.3**: Docker build completes successfully
- **NFR-3.4**: No unused dependencies in pyproject.toml

## Dependencies

### Prerequisites

- Phase 2 complete (discovery, routing, endpoints working)

### Outputs for Next Phase

- N/A (final phase)

## Acceptance Criteria

- [ ] `pytest` passes with all tests green
- [ ] Tests cover: discovery happy path, discovery errors, models endpoint, chat completions endpoint, auth enforcement, response formatting, workflow context construction
- [ ] `docker build .` succeeds
- [ ] `docker-compose up` starts the server (without Redis)
- [ ] No references to `redis`, `tenacity`, `fakeredis`, `batch`, `override` in pyproject.toml dependencies
- [ ] `scripts/smoketest.sh` exists, is executable, and passes against a running server with the default workflow
- [ ] Smoke test validates: health, models list, chat completion, auth enforcement, unknown model error
- [ ] `config.yaml` has only: server, auth, cors, workflows_dir
- [ ] `api_keys.yaml.example` reflects the new simplified format

---

*Review this PRD and provide feedback before spec generation.*
