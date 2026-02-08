# PRD: Workflow-as-Models - Phase 2

**Contract**: ./contract.md
**Phase**: 2 of 3
**Focus**: Workflow discovery, request context, routing, and endpoints

## Phase Overview

Phase 2 is the core feature build. It implements convention-based workflow discovery, the request context protocol, model routing, and the two key endpoints: `/v1/models` and `/v1/chat/completions`.

This phase is sequenced second because it depends on the clean foundation from Phase 1 — a bootable server with auth and no dead code. All new architecture goes in here.

After this phase completes: the server discovers workflows from the configured directory, lists them as models, and routes chat completion requests to the correct workflow by model name. The existing placeholder workflow works as `default_workflow` on `/v1/chat/completions`.

## User Stories

1. As a developer, I want to drop a Python file into the workflows directory and have it automatically appear as a model, so that adding workflows requires zero boilerplate.
2. As an API client, I want to call `/v1/models` and see available workflows listed as OpenAI-compatible model objects, so that I can discover what's available.
3. As an API client, I want to POST to `/v1/chat/completions` with a workflow's model name and get a valid chat completion response, so that existing OpenAI-compatible tooling works.
4. As a workflow author, I want to receive the full request context (endpoint, body, headers, query, key entry) so that I can implement rich logic without framework limitations.
5. As a workflow author, I want to just return a string and let the framework handle OpenAI formatting, so that I can focus on logic, not API shapes.

## Functional Requirements

### Workflow Protocol

- **FR-2.1**: Define a `WorkflowContext` dataclass containing: `endpoint_path` (str), `body` (dict), `headers` (dict), `query_params` (dict), `caller_key` (str), `key_entry` (dict — the full api_keys.yaml entry as a dict, including openai_key and any extra fields)
- **FR-2.2**: Define a workflow callable protocol: a function `run(ctx: WorkflowContext) -> str`
- **FR-2.3**: Each workflow module may export `MODEL_NAME: str` (or `MODEL_NAMES: list[str]`) to override the default model name
- **FR-2.4**: If no `MODEL_NAME` attribute exists, the model name defaults to the filename without `.py` extension

### Workflow Discovery

- **FR-2.5**: At startup, read `workflows_dir` from config (default: `./workflows`)
- **FR-2.6**: Scan the directory for `.py` files (non-recursive, skip `__init__.py` and `__pycache__`)
- **FR-2.7**: Import each module dynamically and validate it exports a `run` callable
- **FR-2.8**: Extract model name(s) per FR-2.3/FR-2.4
- **FR-2.9**: Build an in-memory registry: `dict[str, WorkflowModule]` mapping model names to workflow modules
- **FR-2.10**: Log discovered workflows at startup (model name, source file)
- **FR-2.11**: Fail startup with a clear error if: duplicate model names, missing `run` function, or `workflows_dir` doesn't exist

### Models Endpoint

- **FR-2.12**: `GET /v1/models` returns an OpenAI-compatible model list response (`{"object": "list", "data": [...]}`)
- **FR-2.13**: Each model entry includes: `id` (model name), `object: "model"`, `created` (server start timestamp), `owned_by: "workflow"`
- **FR-2.14**: Endpoint requires Bearer token auth (uses existing auth system)

### Chat Completions Endpoint

- **FR-2.15**: `POST /v1/chat/completions` accepts a JSON body with at minimum `model` and `messages` fields
- **FR-2.16**: Look up `model` in the workflow registry; return 404 (OpenAI-compatible error) if not found
- **FR-2.17**: Construct `WorkflowContext` from the request
- **FR-2.18**: Call the workflow's `run(ctx)` function
- **FR-2.19**: Wrap the returned string in a valid `chat.completion` response: id, object, created, model, choices (single choice with assistant message), usage (zeros)
- **FR-2.20**: Endpoint requires Bearer token auth

### Placeholder Workflow Migration

- **FR-2.21**: Create `workflows/default_workflow.py` with the existing placeholder logic (echoes user input)
- **FR-2.22**: It should export `MODEL_NAME = "default_workflow"` (or rely on filename)
- **FR-2.23**: Its `run(ctx)` extracts messages from `ctx.body` and returns a placeholder string

## Non-Functional Requirements

- **NFR-2.1**: Workflow discovery completes in under 1 second for up to 50 workflow files
- **NFR-2.2**: Invalid workflow files (no `run` function, syntax errors) produce clear error messages at startup, not cryptic tracebacks
- **NFR-2.3**: Request handling adds less than 5ms overhead beyond the workflow's own execution time
- **NFR-2.4**: OpenAI-compatible error responses for all error cases (bad model, bad auth, malformed body)

## Dependencies

### Prerequisites

- Phase 1 complete (clean package, bootable server, auth working)

### Outputs for Next Phase

- Working workflow discovery and routing
- `/v1/models` and `/v1/chat/completions` endpoints
- `WorkflowContext` dataclass and workflow protocol
- Placeholder workflow serving as example

## Acceptance Criteria

- [ ] `workflows/default_workflow.py` exists with a `run(ctx)` function
- [ ] Server discovers it at startup and logs: `Discovered workflow: default_workflow`
- [ ] `GET /v1/models` returns `{"object": "list", "data": [{"id": "default_workflow", "object": "model", ...}]}`
- [ ] `POST /v1/chat/completions` with `{"model": "default_workflow", "messages": [{"role": "user", "content": "hello"}]}` returns a valid chat completion response
- [ ] The response contains the placeholder echo text
- [ ] Request with unknown model returns 404 with OpenAI error format
- [ ] `WorkflowContext` contains endpoint_path, body, headers, query_params, caller_key, key_entry
- [ ] A workflow file without `run()` causes startup failure with clear error message
- [ ] Duplicate model names cause startup failure with clear error message

---

*Review this PRD and provide feedback before spec generation.*
