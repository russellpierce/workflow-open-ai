# Workflow-as-Models Contract

**Created**: 2026-02-07
**Confidence Score**: 95/100
**Status**: Draft

## Problem Statement

The current `skeleton_open_ai` codebase was built around a batch-proxy and override-engine architecture that routes OpenAI API requests through different "modes" (batch, passthrough, workflow) with per-route parameter overrides. This architecture is a poor fit for the actual goal: presenting custom AI workflows as OpenAI-compatible models that clients can call by name.

The batch proxy, override engine, Redis integration, passthrough mode, and mode-dispatch pattern add complexity without serving the core use case. The repo needs a hard fork: strip the infrastructure that doesn't fit and rebuild around a clean "workflows are models" paradigm.

## Goals

1. **Workflows as models**: Each workflow is auto-discovered and presented as a model via `/v1/models`. Clients select a workflow by specifying its model name in requests.
2. **Convention-based discovery**: Workflow files dropped into a configurable directory are automatically discovered at startup. Model name defaults to filename, overridable via a module-level attribute.
3. **Clean workflow interface**: Workflows receive a full request context object (body, headers, query params, endpoint path, caller key entry with OpenAI key and any extra fields) and return a plain string. The framework handles all OpenAI response formatting.
4. **Endpoint-aware routing**: Workflows know which endpoint the request arrived on (e.g., `/v1/chat/completions`), enabling future multi-endpoint support without workflow changes.
5. **Package rename**: Rename from `skeleton_open_ai` to `workflow_open_ai` and reset git history for a clean start.

## Success Criteria

- [ ] Server starts and auto-discovers workflow files from the configured directory
- [ ] `/v1/models` returns a list of discovered workflows as OpenAI-compatible model objects
- [ ] `POST /v1/chat/completions` with `model: "default_workflow"` routes to the correct workflow and returns a valid `chat.completion` response
- [ ] Workflow receives a request context containing: endpoint path, parsed body, headers, query params, caller key, and the full key entry (including openai_key and any extra fields)
- [ ] Workflow returns a plain string; framework wraps it in proper OpenAI chat completion format
- [ ] Model name defaults to filename; module-level `MODEL_NAME` attribute overrides it
- [ ] Existing placeholder workflow (echoes input) works as `default_workflow` on `/v1/chat/completions`
- [ ] API key auth (api_keys.yaml, Bearer token) works unchanged
- [ ] All batch, override, passthrough, Redis, and mode-dispatch code is removed
- [ ] Package renamed to `workflow_open_ai` throughout (imports, pyproject.toml, Dockerfile, etc.)
- [ ] Git history reset (fresh `git init`)
- [ ] Tests pass for the new architecture

## Scope Boundaries

### In Scope

- Remove batch proxy, override engine, passthrough mode, Redis integration, mode-dispatch pattern
- Convention-based workflow discovery from a configurable directory (`workflows_dir` in config.yaml)
- Workflow interface: receives request context object, returns string
- Request context includes full key entry (openai_key + any extra fields from api_keys.yaml)
- `/v1/models` endpoint listing discovered workflows
- `/v1/chat/completions` endpoint routing to workflows by model name
- Existing placeholder workflow migrated to `workflows/default_workflow.py`
- Package rename: `skeleton_open_ai` -> `workflow_open_ai`
- Git history reset
- API key auth preserved as-is
- Health endpoint preserved
- CORS config preserved
- Docker and docker-compose updated for new package name

### Out of Scope

- `/v1/responses` endpoint (Responses API) - different schema, deferred to later phase
- Streaming / SSE support - workflows return strings for now
- Structured/dict workflow return types - keep it simple with strings
- Override engine or parameter manipulation - removed entirely
- Redis or any external state store - removed
- Batch API integration - removed
- Multiple workflow return formats - single string only

### Future Considerations

- `/v1/responses` endpoint support (map input/output items to/from workflows)
- Streaming support (async generator interface for workflows)
- Structured return types (dict with choices, usage, metadata)
- Workflow middleware/hooks (pre/post processing)
- Hot-reload of workflow files without server restart

---

*This contract was generated from brain dump input. Review and approve before proceeding to PRD generation.*
