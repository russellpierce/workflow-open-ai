# Phase 2 Breakdown: Workflow Engine

**Goal**: Discovery + routing + endpoints working end-to-end.

**Phases**: 2a (foundation) → 2b (discovery) → 2c (endpoints) → 2d (integration).

---

## Phase 2a: Foundation (No Dependencies)

**Goal**: Define interfaces and schemas.

**Files**:
- `src/workflow_open_ai/context.py`
- `src/workflow_open_ai/schemas.py`
- `workflows/default_workflow.py`

**Tasks**:

1. `context.py` — WorkflowContext dataclass
   - Frozen dataclass with: `endpoint_path`, `body`, `headers`, `query_params`, `caller_key`, `key_entry` (dict)
   - No methods, just data

2. `schemas.py` — OpenAI-compatible Pydantic models
   - `ChatMessage`: role + content
   - `Choice`: index + message + finish_reason
   - `Usage`: prompt_tokens, completion_tokens, total_tokens (all default 0)
   - `ChatCompletionResponse`: id + object + created + model + choices + usage
   - `ModelInfo`: id + object + created + owned_by
   - `ModelsListResponse`: object + data (list of ModelInfo)

3. `workflows/default_workflow.py` — Placeholder workflow
   - Import WorkflowContext
   - Export `MODEL_NAME = "default_workflow"`
   - Export `async def run(ctx: WorkflowContext) -> str:` that echoes user's last message

**Validation**:
- Import context in default_workflow.py succeeds
- Type checking passes (mypy)

---

## Phase 2b: Discovery (No External Dependencies)

**Goal**: Scan directory, import modules, validate, build registry.

**File**: `src/workflow_open_ai/discovery.py`

**Tasks**:

1. `WorkflowRegistry` class
   - `__init__()`: initialize empty dict
   - `.model_names` property: return list of model names
   - `.get(model_name)` → ModuleType | None
   - `._register(model_name, module, source)`: add to dict, raise on duplicate

2. `_import_workflow_file(py_file: Path) -> ModuleType`
   - Use `importlib.util.spec_from_file_location()`
   - Execute module
   - Return module

3. `_resolve_model_name(module: ModuleType, py_file: Path) -> str`
   - Check for `module.MODEL_NAME` attribute
   - Validate it's a non-empty string
   - Fall back to `py_file.stem` (filename without .py)
   - Return trimmed string

4. `discover_workflows(workflows_dir: str) -> WorkflowRegistry`
   - Check dir exists, raise RuntimeError if not
   - Glob `*.py`, skip `__*`
   - For each file:
     - Import it via `_import_workflow_file()`
     - Validate has `run` callable
     - Get model name via `_resolve_model_name()`
     - Register via `._register()`
     - Log: "Discovered workflow: {name} ({file})"
   - Return registry
   - Fail on: missing dir, missing run(), duplicate model names, syntax errors

**Validation**:
- `discover_workflows("./workflows")` returns registry with `default_workflow`
- `registry.model_names` == `["default_workflow"]`
- `registry.get("default_workflow")` returns module
- Module's `run` is callable
- Missing dir raises RuntimeError
- Duplicate MODEL_NAMEs raise RuntimeError at startup

---

## Phase 2c: Endpoints (Uses 2a, 2b)

**Goal**: HTTP routes that list models and route chat completions.

**Files**:
- `src/workflow_open_ai/routes_models.py`
- `src/workflow_open_ai/routes_chat.py`

**Tasks**:

1. `routes_models.py`
   - `create_models_router(registry: WorkflowRegistry, auth_dependency: Callable) -> APIRouter`
   - Factory returns router with `GET /v1/models`
   - Route uses `auth_dependency` to validate token
   - Returns `ModelsListResponse` with one `ModelInfo` per registry model name
   - `ModelInfo.created` = server start timestamp (module-level constant)

2. `routes_chat.py`
   - `create_chat_router(registry: WorkflowRegistry, key_lookup: dict[str, ApiKeyEntry], auth_dependency: Callable) -> APIRouter`
   - Factory returns router with `POST /v1/chat/completions`
   - Route uses `auth_dependency` to get API key
   - Parse raw JSON body (no Pydantic validation)
   - Validate `model` field present
   - Look up workflow in registry
   - Construct `WorkflowContext` with: endpoint_path, body (raw dict), headers, query_params, caller_key, key_entry (from key_lookup, converted to dict)
   - Call `workflow.run(ctx)` (note: spec shows sync, may need async)
   - Wrap response string in `ChatCompletionResponse` format
   - Return as JSONResponse
   - Errors:
     - 400 bad JSON: "Invalid JSON body: {error}"
     - 400 missing model: "'model' field is required"
     - 400 unknown model: "Model '{model}' not found. Available: {list}"

**Validation**:
- `GET /v1/models` with valid token returns list with default_workflow
- `POST /v1/chat/completions` with valid token + valid model returns chat.completion response
- Unknown model returns 400 with model_not_found code
- Missing model field returns 400
- Bad JSON returns 400
- No token returns 401 (via existing auth)

---

## Phase 2d: Integration (Uses All Prior)

**Goal**: Wire discovery and routes into main.py.

**File**: `src/workflow_open_ai/main.py`

**Tasks**:

1. Import discovery and route factories
2. After config loads, call `discover_workflows(config.workflows_dir)`
3. Log discovery results
4. Create models router: `create_models_router(registry, auth_dependency)`
5. Create chat router: `create_chat_router(registry, key_lookup, auth_dependency)`
6. Register both routers on app (after health router)

**Validation**:
- Server starts: `uv run uvicorn workflow_open_ai.main:app`
- Logs show discovered workflows
- `/health` works (existing)
- `/v1/models` works (new)
- `/v1/chat/completions` works (new)

---

## Dependency Graph

```
context.py
  └─ (no deps)

schemas.py
  └─ (no deps)

default_workflow.py
  └─ context.py

discovery.py
  └─ (no deps)

routes_models.py
  ├─ discovery.py (WorkflowRegistry type)
  └─ schemas.py (response types)

routes_chat.py
  ├─ discovery.py (WorkflowRegistry type)
  ├─ context.py (WorkflowContext type)
  ├─ schemas.py (no response model, but JSONResponse)
  └─ key_config.py (ApiKeyEntry type, already in codebase)

main.py update
  ├─ discovery.py (discover_workflows function)
  ├─ routes_models.py (create_models_router function)
  └─ routes_chat.py (create_chat_router function)
```

---

## Implementation Order

**2a**: context + schemas + default_workflow (parallel OK)
**2b**: discovery.py (after 2a, but can overlap)
**2c**: routes_models.py + routes_chat.py (after 2a + 2b, parallel OK)
**2d**: main.py (last, needs 2a + 2b + 2c)

Est. time: 2-4 hours total if each piece coded deliberately.

---

## Testing Strategy (Phase 3, but keep in mind)

**Unit**:
- `discovery.discover_workflows()` with valid dir, missing dir, missing run(), duplicate models
- Model name resolution (file stem, MODEL_NAME override)
- `WorkflowContext` construction

**Integration**:
- `/v1/models` returns discovered list
- `/v1/chat/completions` routes to correct workflow
- Response formatting correct
- Error responses correct

**Manual**:
- Smoke test script (Phase 3)
