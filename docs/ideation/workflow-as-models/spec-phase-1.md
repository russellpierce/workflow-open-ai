# Implementation Spec: Workflow-as-Models - Phase 1

**PRD**: ./prd-phase-1.md
**Estimated Effort**: M

## Technical Approach

Phase 1 is primarily a deletion and rename pass. The approach is: delete everything related to batch/override/passthrough/Redis/modes, rename the package from `skeleton_open_ai` to `workflow_open_ai`, update all references, simplify config, and verify the server boots with just health + auth.

Key decision: rather than surgically editing `main.py` to remove mode imports, we'll rewrite it from scratch since most of its logic is mode-discovery code. The new `main.py` will be minimal: load config, load keys, create FastAPI app, register health route and error handlers. The dispatch router and all mode machinery is deleted entirely.

The `schemas.py` file is mostly removed, but `HealthResponse` is needed by `routes_health.py`. We'll inline it directly into `routes_health.py` to avoid keeping a schemas file with a single model. The rest of schemas (ChatMessage, ChatCompletionRequest, ChatCompletionResponse, ModelInfo, ModelsListResponse) will be rebuilt in Phase 2.

The `errors.py` file is kept but `BatchProxyError` is removed. The `key_config.py` file is kept but `ApiKeyEntry` is modified to accept extra fields (for passing arbitrary key entry data to workflows in Phase 2). The `retry_buffer_ttl_seconds` field is removed.

## File Changes

### New Files

| File Path | Purpose |
|-----------|---------|
| `src/workflow_open_ai/__init__.py` | Package init (renamed from skeleton_open_ai) |
| `src/workflow_open_ai/main.py` | Minimal FastAPI app: config, auth, health, CORS, errors |
| `src/workflow_open_ai/config.py` | Simplified config: server, auth, cors, workflows_dir |
| `src/workflow_open_ai/auth.py` | Preserved auth dependency (updated imports) |
| `src/workflow_open_ai/key_config.py` | Key loading with extensible ApiKeyEntry |
| `src/workflow_open_ai/errors.py` | Error handling (BatchProxyError removed) |
| `src/workflow_open_ai/routes_health.py` | Health endpoint with inlined HealthResponse |

### Deleted Files

| File Path | Reason |
|-----------|--------|
| `src/skeleton_open_ai/` | Entire old package directory (replaced by workflow_open_ai) |
| `src/skeleton_open_ai/batch/` | Batch proxy infrastructure — removed |
| `src/skeleton_open_ai/override_proxy/` | Override engine — removed |
| `src/skeleton_open_ai/modes/` | Mode provider/dispatch pattern — removed |
| `src/skeleton_open_ai/routes_dispatch.py` | Mode dispatch router — removed |
| `src/skeleton_open_ai/routes_chat.py` | Legacy chat router — removed |
| `src/skeleton_open_ai/routes_models.py` | Legacy models router — removed |
| `src/skeleton_open_ai/workflow.py` | Old workflow (recreated in Phase 2 as discovered workflow) |
| `src/skeleton_open_ai/schemas.py` | Old schemas (HealthResponse inlined; rest rebuilt in Phase 2) |
| `tests/` | All existing tests (test removed code) |
| `docs/ideation/batch-proxy/` | Old batch proxy ideation docs |
| `docs/ideation/override-proxy/` | Old override proxy ideation docs |

### Modified Files

| File Path | Changes |
|-----------|---------|
| `pyproject.toml` | Rename package, remove redis/tenacity/fakeredis deps, update tool paths |
| `config.yaml` | Remove routes/redis/models sections, add workflows_dir |
| `Dockerfile` | Update module reference to workflow_open_ai |
| `docker-compose.yml` | Remove Redis service, update service config |
| `api_keys.yaml.example` | Remove retry_buffer_ttl_seconds, show extra fields |

## Implementation Details

### 1. Delete Dead Code

**Overview**: Remove all batch, override, passthrough, modes, dispatch, and legacy files.

**Implementation steps**:
1. Delete `src/skeleton_open_ai/batch/` directory
2. Delete `src/skeleton_open_ai/override_proxy/` directory
3. Delete `src/skeleton_open_ai/modes/` directory
4. Delete `src/skeleton_open_ai/routes_dispatch.py`
5. Delete `src/skeleton_open_ai/routes_chat.py`
6. Delete `src/skeleton_open_ai/routes_models.py`
7. Delete `src/skeleton_open_ai/workflow.py`
8. Delete `src/skeleton_open_ai/schemas.py`
9. Delete all files in `tests/`
10. Delete `docs/ideation/batch-proxy/` and `docs/ideation/override-proxy/`

### 2. Create Renamed Package

**Overview**: Create `src/workflow_open_ai/` with the kept files, updated.

**`__init__.py`**:
```python
"""OpenAI-compatible API server for custom AI workflows."""

__version__: str = "0.1.0"
```

**`routes_health.py`** — inline HealthResponse:
```python
import logging
from typing import Final

from fastapi import APIRouter
from pydantic import BaseModel

logger: Final = logging.getLogger(__name__)
router: Final = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str = "healthy"


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    logger.debug("Health check requested")
    return HealthResponse(status="healthy")
```

**`errors.py`** — remove BatchProxyError, keep everything else:
```python
# Keep: ErrorDetail, ErrorResponse, OpenAICompatibleError,
#       AuthenticationError, InvalidRequestError,
#       _create_error_response, openai_compatible_error_handler,
#       validation_error_handler, register_error_handlers
# Remove: BatchProxyError class
```

**`key_config.py`** — make ApiKeyEntry extensible:
```python
from pydantic import BaseModel, ConfigDict, Field

class ApiKeyEntry(BaseModel):
    """Single API key mapping. Extra fields are preserved and passed to workflows."""
    model_config = ConfigDict(extra="allow")

    caller_key: str
    openai_key: str = ""
```
Remove `retry_buffer_ttl_seconds`. Add `ConfigDict(extra="allow")` so arbitrary extra fields from api_keys.yaml are preserved on the model instance.

**`config.py`** — simplified:
```python
class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    auth: AuthConfig
    cors: CorsConfig = Field(default_factory=CorsConfig)
    workflows_dir: str = "./workflows"
```
Remove: `models`, `routes`, `redis` fields. Remove `RouteConfig` import. Remove `models_not_empty` validator. Add `workflows_dir: str`.

**`main.py`** — minimal:
```python
config: AppConfig = load_config(CONFIG_PATH)

keys_config = load_api_keys_config(config.auth.api_keys_file)
key_lookup = build_key_lookup(keys_config)
auth_dependency = create_auth_dependency(frozenset(key_lookup.keys()))

app: Final = FastAPI(
    title="Workflow OpenAI",
    description="Custom AI workflows behind an OpenAI-compatible interface",
    version=__version__,
)

# CORS, error handlers, health route — same as before
# NO mode discovery, NO dispatch router, NO Redis
```

**`auth.py`** — just update import path from `skeleton_open_ai.errors` to `workflow_open_ai.errors`. Logic unchanged.

### 3. Update pyproject.toml

```toml
[project]
name = "workflow-open-ai"
version = "0.1.0"
description = "OpenAI-compatible API server for custom AI workflows"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.10.0",
    "pyyaml>=6.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "types-PyYAML>=6.0.0",
    "pre-commit>=4.0.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/workflow_open_ai"]

[tool.mypy]
files = ["src/workflow_open_ai", "tests"]
```

Remove: `openai`, `redis[hiredis]`, `tenacity` from deps. Remove `fakeredis` from dev deps.

### 4. Update config.yaml

```yaml
server:
  host: "0.0.0.0"
  port: 8000

auth:
  api_keys_file: "api_keys.yaml"

# Directory containing workflow Python files (auto-discovered at startup)
workflows_dir: "./workflows"

cors:
  allow_origins:
    - "*"
```

### 5. Update Dockerfile

```dockerfile
# Change CMD line:
CMD ["uv", "run", "uvicorn", "workflow_open_ai.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Add workflows directory copy:
COPY workflows/ ./workflows/
```

### 6. Update docker-compose.yml

Remove entire `redis` service and `volumes` section. Remove `depends_on` from api service. Add workflows mount:
```yaml
services:
  api:
    build: .
    ports:
      - "${API_PORT:-8000}:8000"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./api_keys.yaml:/app/api_keys.yaml:ro
      - ./workflows:/app/workflows:ro
    environment:
      - CONFIG_PATH=/app/config.yaml
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

### 7. Update api_keys.yaml.example

```yaml
# API Keys Configuration
# Copy to api_keys.yaml and fill in your actual keys.
#
# Extra fields beyond caller_key and openai_key are passed through
# to workflows via the request context.
#
# Generate secure caller keys:
#   python -c "import secrets; print('sk-' + secrets.token_hex(32))"

keys:
  - caller_key: "sk-your-caller-key-here"
    openai_key: "sk-your-openai-key-here"
    # Add any extra fields you want available in workflows:
    # org_name: "my-org"
    # tier: "premium"
```

### 8. Git Reset

**Implementation steps**:
1. Delete `.git/` directory
2. Run `git init`
3. Create `.gitignore` (preserve existing or create standard Python one)
4. `git add .` and `git commit -m "Initial commit: workflow_open_ai fork"`

## Error Handling

| Error Scenario | Handling Strategy |
|----------------|-------------------|
| Missing config.yaml | Existing behavior: log critical + sys.exit(1) |
| Missing api_keys.yaml | Existing behavior: log critical + sys.exit(1) |
| Import errors from deleted code | Caught at startup — verify no stale imports remain |

## Validation Commands

```bash
# Verify no references to old package name
grep -r "skeleton_open_ai" src/ pyproject.toml Dockerfile docker-compose.yml

# Verify server boots
uv run uvicorn workflow_open_ai.main:app --host 0.0.0.0 --port 8000 &
curl http://localhost:8000/health

# Type checking
uv run mypy src/workflow_open_ai

# Linting
uv run ruff check src/
uv run ruff format --check src/
```

---

*This spec is ready for implementation. Follow the patterns and validate at each step.*
