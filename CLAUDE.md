# workflow-open-ai

OpenAI-compatible API bridge for custom AI workflows. Routes requests to workflows by model name.

## Status

**Phase 1 complete** (package rename, dead code removed, boot works)
**Phase 2 next** (workflow discovery, routing, endpoints)

## Architecture

Three-part flow:
1. **Discovery**: Scan `workflows/` dir at startup, import `.py` files, register workflows by name
2. **Context**: Pass `WorkflowContext` to workflows (endpoint_path, body, headers, query_params, caller_key, key_entry)
3. **Routing**: `/v1/models` lists discovered; `/v1/chat/completions` routes to workflow by model name

Workflows are simple: receive context, return string. Framework wraps in OpenAI response format.

## Current State

### Implemented
- FastAPI app (CORS, logging, error handling)
- Bearer token auth via `api_keys.yaml`
- `GET /health`
- Config system (YAML, `workflows_dir` field)
- Error responses (OpenAI format)

### Missing (Phase 2)
- `WorkflowContext` dataclass
- Workflow discovery (importlib scan, module import, registry build)
- `GET /v1/models` (list discovered workflows)
- `POST /v1/chat/completions` (route by model, call workflow, wrap response)
- `workflows/default_workflow.py` (placeholder echo)
- Response schemas (Pydantic models for OpenAI format)

### Missing (Phase 3)
- Full test suite
- Docker updates (remove Redis)
- Smoke test script

## Key Files

### Core
- `src/workflow_open_ai/main.py` - FastAPI app boot
- `src/workflow_open_ai/config.py` - YAML config loader
- `src/workflow_open_ai/auth.py` - Bearer token verify
- `src/workflow_open_ai/key_config.py` - API key file loader
- `src/workflow_open_ai/errors.py` - OpenAI error format

### To Create (Phase 2)
- `src/workflow_open_ai/discovery.py` - Scan workflows, build registry
- `src/workflow_open_ai/context.py` - WorkflowContext dataclass
- `src/workflow_open_ai/schemas.py` - Pydantic models (chat completion response)
- `src/workflow_open_ai/routes_models.py` - GET /v1/models
- `src/workflow_open_ai/routes_chat.py` - POST /v1/chat/completions
- `workflows/default_workflow.py` - Example workflow

## Workflow Interface

Minimal. Module must export:
```python
async def run(ctx: WorkflowContext) -> str:
    # ctx.endpoint_path: "/v1/chat/completions"
    # ctx.body: parsed JSON body
    # ctx.headers: request headers
    # ctx.query_params: URL query params
    # ctx.caller_key: authenticated API key
    # ctx.key_entry: full key entry (dict with openai_key + extras)
    return "response string"
```

Optional: `MODEL_NAME = "custom_name"` to override filename default.

## Config

`config.yaml`:
```yaml
server:
  host: "0.0.0.0"
  port: 8340
auth:
  api_keys_file: "api_keys.yaml"
cors:
  allow_origins: ["*"]
workflows_dir: "./workflows"
```

`api_keys.yaml`:
```yaml
keys:
  - caller_key: "sk-abc123"
    openai_key: "sk-openai-xyz"
    extra_field: "value"
```

## Specs

See `docs/ideation/workflow-as-models/`:
- `contract.md` - Goals and scope
- `prd-phase-1.md` - Phase 1 (done): strip + rename
- `prd-phase-2.md` - Phase 2 (next): discovery + routing
- `prd-phase-3.md` - Phase 3: tests + deployment
- `spec-phase-1.md` - Phase 1 implementation (done)
- `spec-phase-2.md` - Phase 2 implementation details
- `spec-phase-3.md` - Phase 3 implementation details

## Next Step

Implement Phase 2 per `spec-phase-2.md`. Start with `discovery.py` and `context.py`.
