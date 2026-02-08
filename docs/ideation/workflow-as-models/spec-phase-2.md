# Implementation Spec: Workflow-as-Models - Phase 2

**PRD**: ./prd-phase-2.md
**Estimated Effort**: M

## Technical Approach

Phase 2 builds the core workflow engine on top of the clean foundation from Phase 1. The architecture has three components: **discovery** (scan a directory, import modules, build a registry), **context** (a dataclass passed to workflows), and **routing** (FastAPI endpoints that look up workflows by model name).

Discovery uses `importlib` to dynamically import `.py` files from the configured `workflows_dir`. Each module must export a `run(ctx: WorkflowContext) -> str` callable. Model name resolution: if the module has a `MODEL_NAME` string attribute, use it; otherwise, use the filename (sans `.py`). Duplicate model names fail startup.

The routing layer is simple: two new route modules (`routes_models.py` and `routes_chat.py`) registered on the FastAPI app. No catch-all dispatch — just explicit routes for `/v1/models` and `/v1/chat/completions`. The chat completions handler parses the body, looks up the model in the registry, constructs a `WorkflowContext`, calls `run()`, and wraps the returned string in OpenAI chat completion format.

## File Changes

### New Files

| File Path | Purpose |
|-----------|---------|
| `src/workflow_open_ai/discovery.py` | Scan workflows_dir, import modules, build registry |
| `src/workflow_open_ai/context.py` | WorkflowContext dataclass |
| `src/workflow_open_ai/schemas.py` | Pydantic models for OpenAI-compatible responses |
| `src/workflow_open_ai/routes_models.py` | GET /v1/models endpoint |
| `src/workflow_open_ai/routes_chat.py` | POST /v1/chat/completions endpoint |
| `workflows/default_workflow.py` | Migrated placeholder workflow |

### Modified Files

| File Path | Changes |
|-----------|---------|
| `src/workflow_open_ai/main.py` | Import discovery, register new routes, pass registry to route factories |

## Implementation Details

### 1. WorkflowContext Dataclass

**File**: `src/workflow_open_ai/context.py`

**Overview**: Immutable dataclass carrying all request context to workflows.

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowContext:
    """Full request context passed to workflow run() functions."""

    endpoint_path: str          # e.g., "/v1/chat/completions"
    body: dict[str, Any]        # Parsed JSON request body
    headers: dict[str, str]     # Request headers
    query_params: dict[str, str]  # URL query parameters
    caller_key: str             # The authenticated caller's API key
    key_entry: dict[str, Any]   # Full api_keys.yaml entry as dict (includes openai_key + extras)
```

**Key decisions**:
- `frozen=True` for immutability — workflows shouldn't mutate context
- `key_entry` is a plain dict (not ApiKeyEntry) so workflows don't depend on internal Pydantic models. Use `ApiKeyEntry.model_dump()` to convert.
- No `request: Request` object — workflows don't get raw FastAPI/Starlette access

### 2. Workflow Discovery

**File**: `src/workflow_open_ai/discovery.py`

**Overview**: Scans the workflows directory, imports each `.py` file, validates it has a `run` callable, extracts model names, and returns a registry dict.

```python
import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)


class WorkflowRegistry:
    """Maps model names to workflow modules."""

    def __init__(self) -> None:
        self._workflows: dict[str, ModuleType] = {}

    @property
    def model_names(self) -> list[str]:
        return list(self._workflows.keys())

    def get(self, model_name: str) -> ModuleType | None:
        return self._workflows.get(model_name)

    def _register(self, model_name: str, module: ModuleType, source: Path) -> None:
        if model_name in self._workflows:
            existing = self._workflows[model_name]
            raise RuntimeError(
                f"Duplicate model name '{model_name}': "
                f"already registered by {getattr(existing, '__file__', '?')}, "
                f"conflict with {source}"
            )
        self._workflows[model_name] = module


def discover_workflows(workflows_dir: str) -> WorkflowRegistry:
    """
    Scan workflows_dir for .py files, import them, validate, and build registry.

    Raises RuntimeError on: missing dir, missing run(), duplicate model names.
    """
    path = Path(workflows_dir)

    if not path.is_dir():
        raise RuntimeError(f"Workflows directory not found: {path.resolve()}")

    registry = WorkflowRegistry()

    for py_file in sorted(path.glob("*.py")):
        if py_file.name.startswith("__"):
            continue

        # Import the module
        module = _import_workflow_file(py_file)

        # Validate run() callable
        run_fn = getattr(module, "run", None)
        if not callable(run_fn):
            raise RuntimeError(
                f"Workflow '{py_file.name}' missing required 'run' function"
            )

        # Resolve model name
        model_name = _resolve_model_name(module, py_file)

        registry._register(model_name, module, py_file)
        logger.info(f"Discovered workflow: {model_name} ({py_file.name})")

    return registry


def _import_workflow_file(py_file: Path) -> ModuleType:
    """Import a single .py file as a module."""
    module_name = f"workflows.{py_file.stem}"
    spec = importlib.util.spec_from_file_location(module_name, py_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load workflow: {py_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_model_name(module: ModuleType, py_file: Path) -> str:
    """Get model name from MODULE_NAME attribute or filename."""
    model_name = getattr(module, "MODEL_NAME", None)
    if model_name is not None:
        if not isinstance(model_name, str) or not model_name.strip():
            raise RuntimeError(
                f"Workflow '{py_file.name}': MODEL_NAME must be a non-empty string"
            )
        return model_name.strip()
    return py_file.stem
```

**Key decisions**:
- `importlib.util.spec_from_file_location` rather than manipulating `sys.path` — cleaner, avoids polluting the import namespace
- `sorted()` for deterministic discovery order
- Skip files starting with `__` (init, pycache entries)
- Fail-fast on all errors at startup — no partial registries

**Implementation steps**:
1. Create `discovery.py` with `WorkflowRegistry` class
2. Implement `discover_workflows()` with file scanning
3. Implement `_import_workflow_file()` using importlib
4. Implement `_resolve_model_name()` with MODEL_NAME fallback

### 3. OpenAI-Compatible Schemas

**File**: `src/workflow_open_ai/schemas.py`

**Overview**: Pydantic models for chat completion responses and model listing. Request validation is minimal — we pass the raw body dict to workflows.

```python
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class Choice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage = Field(default_factory=Usage)


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "workflow"


class ModelsListResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]
```

**Key decisions**:
- `owned_by: "workflow"` distinguishes these from OpenAI's own models
- No `ChatCompletionRequest` Pydantic model — the body is passed as a raw dict to workflows via `WorkflowContext.body`. This avoids rejecting requests with fields we don't know about.

### 4. Models Endpoint

**File**: `src/workflow_open_ai/routes_models.py`

**Overview**: `GET /v1/models` returns discovered workflows as OpenAI-compatible model objects.

```python
import time
from collections.abc import Callable

from fastapi import APIRouter, Depends

from workflow_open_ai.discovery import WorkflowRegistry
from workflow_open_ai.schemas import ModelInfo, ModelsListResponse

_SERVER_START_TIME = int(time.time())


def create_models_router(
    registry: WorkflowRegistry,
    auth_dependency: Callable[..., str],
) -> APIRouter:
    router = APIRouter(tags=["models"])

    @router.get("/v1/models", response_model=ModelsListResponse)
    def list_models(api_key: str = Depends(auth_dependency)) -> ModelsListResponse:
        models = [
            ModelInfo(id=name, created=_SERVER_START_TIME)
            for name in registry.model_names
        ]
        return ModelsListResponse(data=models)

    return router
```

**Implementation steps**:
1. Create `routes_models.py` with factory function
2. Accept registry and auth dependency as parameters
3. Return ModelsListResponse with one ModelInfo per discovered workflow

### 5. Chat Completions Endpoint

**File**: `src/workflow_open_ai/routes_chat.py`

**Overview**: `POST /v1/chat/completions` validates model, constructs WorkflowContext, calls workflow, wraps string response.

```python
import json
import time
import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from workflow_open_ai.context import WorkflowContext
from workflow_open_ai.discovery import WorkflowRegistry
from workflow_open_ai.errors import InvalidRequestError
from workflow_open_ai.key_config import ApiKeyEntry


def create_chat_router(
    registry: WorkflowRegistry,
    key_lookup: dict[str, ApiKeyEntry],
    auth_dependency: Callable[..., str],
) -> APIRouter:
    router = APIRouter(tags=["chat"])

    @router.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        api_key: str = Depends(auth_dependency),
    ) -> JSONResponse:
        # Parse body
        raw_body = await request.body()
        try:
            body: dict = json.loads(raw_body) if raw_body else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise InvalidRequestError(
                message=f"Invalid JSON body: {e}",
                error_code="invalid_request",
            )

        model = body.get("model", "")
        if not model:
            raise InvalidRequestError(
                message="'model' field is required",
                error_code="invalid_request",
            )

        # Look up workflow
        workflow = registry.get(model)
        if workflow is None:
            raise InvalidRequestError(
                message=f"Model '{model}' not found. Available: {registry.model_names}",
                error_code="model_not_found",
            )

        # Build context
        key_entry = key_lookup[api_key]
        ctx = WorkflowContext(
            endpoint_path="/v1/chat/completions",
            body=body,
            headers=dict(request.headers),
            query_params=dict(request.query_params),
            caller_key=api_key,
            key_entry=key_entry.model_dump(),
        )

        # Call workflow
        response_text = workflow.run(ctx)

        # Wrap in OpenAI format
        return JSONResponse(content={
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    return router
```

**Key decisions**:
- Parse body as raw JSON dict, not Pydantic model — avoids rejecting unknown fields
- `model_not_found` error code matches OpenAI's convention
- `key_entry.model_dump()` converts Pydantic model to dict (includes all extra fields)
- Status code for model not found: 400 with `model_not_found` code (matching OpenAI's behavior, not 404)

**Implementation steps**:
1. Create `routes_chat.py` with factory function
2. Parse raw JSON body
3. Validate model field present
4. Look up workflow in registry
5. Construct WorkflowContext
6. Call `workflow.run(ctx)`
7. Wrap string in chat completion response

### 6. Updated main.py

**Overview**: Wire discovery and new routes into the app.

```python
from workflow_open_ai.discovery import discover_workflows
from workflow_open_ai.routes_chat import create_chat_router
from workflow_open_ai.routes_models import create_models_router

# ... after config and auth setup ...

# Discover workflows
registry = discover_workflows(config.workflows_dir)

# Register routes
app.include_router(create_models_router(registry, auth_dependency))
app.include_router(create_chat_router(registry, key_lookup, auth_dependency))
app.include_router(health_router)

logger.info(f"Discovered workflows: {registry.model_names}")
```

**Implementation steps**:
1. Import discovery and route factories
2. Call `discover_workflows(config.workflows_dir)` after config loads
3. Register models and chat routers with registry and auth
4. Log discovered workflows

### 7. Placeholder Workflow

**File**: `workflows/default_workflow.py`

**Overview**: Migrated from old `workflow.py`. Demonstrates the workflow interface.

```python
"""
Default placeholder workflow.

Demonstrates the workflow interface: receives WorkflowContext, returns a string.
"""

from workflow_open_ai.context import WorkflowContext

MODEL_NAME = "default_workflow"


def run(ctx: WorkflowContext) -> str:
    """Echo the user's last message back as a placeholder response."""
    messages = ctx.body.get("messages", [])
    last_message = messages[-1]["content"] if messages else "No messages provided"

    return (
        f"This is a placeholder response from model '{ctx.body.get('model', 'unknown')}'. "
        f"Your message was: '{last_message}'. "
        f"Implement your workflow in the workflows/ directory."
    )
```

**Key decisions**:
- Imports `WorkflowContext` for type hints — workflows CAN import from the main package
- `MODEL_NAME` is explicit even though it matches the filename — serves as documentation
- Accesses messages from `ctx.body` (raw dict), not a parsed schema

**Implementation steps**:
1. Create `workflows/` directory at project root
2. Create `default_workflow.py` with MODEL_NAME and run()

## API Design

### Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `GET` | `/v1/models` | List discovered workflows as models | Required |
| `POST` | `/v1/chat/completions` | Route chat completion to workflow | Required |
| `GET` | `/health` | Health check | Not required |

### Request/Response Examples

```
# GET /v1/models
# Response:
{
    "object": "list",
    "data": [
        {
            "id": "default_workflow",
            "object": "model",
            "created": 1738900000,
            "owned_by": "workflow"
        }
    ]
}

# POST /v1/chat/completions
# Request:
{
    "model": "default_workflow",
    "messages": [
        {"role": "user", "content": "Hello!"}
    ]
}

# Response:
{
    "id": "chatcmpl-abc123...",
    "object": "chat.completion",
    "created": 1738900001,
    "model": "default_workflow",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is a placeholder response..."
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0
    }
}

# POST /v1/chat/completions with unknown model
# Response (400):
{
    "error": {
        "message": "Model 'bad-model' not found. Available: ['default_workflow']",
        "type": "invalid_request_error",
        "code": "model_not_found"
    }
}
```

## Error Handling

| Error Scenario | Handling Strategy |
|----------------|-------------------|
| workflows_dir doesn't exist | RuntimeError at startup with clear path message |
| Workflow file missing `run()` | RuntimeError at startup naming the file |
| Duplicate model names | RuntimeError at startup naming both files |
| Workflow file has syntax error | ImportError at startup with traceback |
| Unknown model in request | 400 with model_not_found error code |
| Missing `model` field | 400 with invalid_request error code |
| Invalid JSON body | 400 with invalid_request error code |
| Workflow `run()` raises exception | 500 — unhandled, fail-fast (no try/catch) |
| Missing auth | 401 via existing auth dependency |

## Validation Commands

```bash
# Start the server
uv run uvicorn workflow_open_ai.main:app --host 0.0.0.0 --port 8000

# Test models endpoint
curl -H "Authorization: Bearer sk-your-key" http://localhost:8000/v1/models

# Test chat completions
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-your-key" \
  -H "Content-Type: application/json" \
  -d '{"model": "default_workflow", "messages": [{"role": "user", "content": "hello"}]}'

# Type checking
uv run mypy src/workflow_open_ai

# Linting
uv run ruff check src/ workflows/
uv run ruff format --check src/ workflows/
```

---

*This spec is ready for implementation. Follow the patterns and validate at each step.*
