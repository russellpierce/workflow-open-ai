# Implementation Spec: Workflow-as-Models - Phase 3

**PRD**: ./prd-phase-3.md
**Estimated Effort**: M

## Technical Approach

Phase 3 adds three things: a comprehensive pytest test suite, a `scripts/smoketest.sh` for live-server validation, and cleanup of Docker/deployment config. The test suite uses FastAPI's TestClient (via httpx) for integration tests and direct function calls for unit tests. The smoke test is a standalone bash script that exercises a running server end-to-end.

Tests are organized by component: discovery, context, routes (models + chat), and error handling. Integration tests spin up a TestClient with a temporary workflows directory containing test workflow files. Unit tests validate discovery logic, model name resolution, and response formatting in isolation.

## File Changes

### New Files

| File Path | Purpose |
|-----------|---------|
| `tests/__init__.py` | Test package marker |
| `tests/conftest.py` | Shared fixtures: test app, test client, temp workflows dir |
| `tests/test_discovery.py` | Unit tests for workflow discovery and registry |
| `tests/test_context.py` | Unit tests for WorkflowContext construction |
| `tests/test_routes_models.py` | Integration tests for GET /v1/models |
| `tests/test_routes_chat.py` | Integration tests for POST /v1/chat/completions |
| `tests/test_errors.py` | Tests for error formatting and auth enforcement |
| `scripts/smoketest.sh` | Live-server smoke test script |

### Modified Files

| File Path | Changes |
|-----------|---------|
| `pyproject.toml` | Remove stale deps (redis, tenacity, fakeredis, openai), clean mypy overrides |
| `Dockerfile` | Copy workflows/ directory |
| `docker-compose.yml` | Remove Redis service, mount workflows/ |
| `config.yaml` | Final clean version with comments |
| `api_keys.yaml.example` | Updated format without batch-specific fields |

## Implementation Details

### 1. Test Fixtures

**File**: `tests/conftest.py`

**Overview**: Shared fixtures for creating test apps with temporary workflow directories.

```python
import textwrap
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from workflow_open_ai.auth import create_auth_dependency
from workflow_open_ai.context import WorkflowContext
from workflow_open_ai.discovery import discover_workflows
from workflow_open_ai.errors import register_error_handlers
from workflow_open_ai.key_config import ApiKeyEntry
from workflow_open_ai.routes_chat import create_chat_router
from workflow_open_ai.routes_models import create_models_router

TEST_API_KEY = "sk-test-key-12345"
TEST_OPENAI_KEY = "sk-openai-test-key"


@pytest.fixture
def workflows_dir(tmp_path: Path) -> Path:
    """Create a temp directory with a simple test workflow."""
    wf = tmp_path / "echo_workflow.py"
    wf.write_text(textwrap.dedent('''
        from workflow_open_ai.context import WorkflowContext

        def run(ctx: WorkflowContext) -> str:
            messages = ctx.body.get("messages", [])
            last = messages[-1]["content"] if messages else "empty"
            return f"echo: {last}"
    '''))
    return tmp_path


@pytest.fixture
def key_entry() -> ApiKeyEntry:
    return ApiKeyEntry(caller_key=TEST_API_KEY, openai_key=TEST_OPENAI_KEY)


@pytest.fixture
def key_lookup(key_entry: ApiKeyEntry) -> dict[str, ApiKeyEntry]:
    return {TEST_API_KEY: key_entry}


@pytest.fixture
def app(workflows_dir: Path, key_lookup: dict[str, ApiKeyEntry]) -> FastAPI:
    """Create a test FastAPI app with discovered workflows."""
    registry = discover_workflows(str(workflows_dir))
    auth_dep = create_auth_dependency(frozenset(key_lookup.keys()))

    test_app = FastAPI()
    register_error_handlers(test_app)
    test_app.include_router(create_models_router(registry, auth_dep))
    test_app.include_router(create_chat_router(registry, key_lookup, auth_dep))
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_API_KEY}"}
```

### 2. Discovery Tests

**File**: `tests/test_discovery.py`

**Key test cases**:
- Discovers `.py` files in directory and builds registry
- Filename becomes model name when no MODEL_NAME attribute
- MODEL_NAME attribute overrides filename
- Skips `__init__.py` and `__pycache__` files
- Raises RuntimeError when directory doesn't exist
- Raises RuntimeError when workflow file missing `run()` function
- Raises RuntimeError on duplicate model names
- Empty directory returns empty registry (no error)
- Workflow with syntax error raises ImportError

```python
def test_discover_finds_workflows(tmp_path: Path) -> None:
    (tmp_path / "my_model.py").write_text(
        "from workflow_open_ai.context import WorkflowContext\n"
        "def run(ctx: WorkflowContext) -> str: return 'hello'"
    )
    registry = discover_workflows(str(tmp_path))
    assert "my_model" in registry.model_names

def test_model_name_attribute_overrides_filename(tmp_path: Path) -> None:
    (tmp_path / "my_file.py").write_text(
        "from workflow_open_ai.context import WorkflowContext\n"
        "MODEL_NAME = 'custom-name'\n"
        "def run(ctx: WorkflowContext) -> str: return 'hello'"
    )
    registry = discover_workflows(str(tmp_path))
    assert "custom-name" in registry.model_names
    assert "my_file" not in registry.model_names

def test_missing_run_raises(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("x = 1")
    with pytest.raises(RuntimeError, match="missing required 'run' function"):
        discover_workflows(str(tmp_path))

def test_duplicate_model_names_raises(tmp_path: Path) -> None:
    for name in ("a.py", "b.py"):
        (tmp_path / name).write_text(
            "from workflow_open_ai.context import WorkflowContext\n"
            "MODEL_NAME = 'same-name'\n"
            "def run(ctx: WorkflowContext) -> str: return 'x'"
        )
    with pytest.raises(RuntimeError, match="Duplicate model name"):
        discover_workflows(str(tmp_path))

def test_nonexistent_dir_raises() -> None:
    with pytest.raises(RuntimeError, match="not found"):
        discover_workflows("/nonexistent/path")

def test_empty_dir(tmp_path: Path) -> None:
    registry = discover_workflows(str(tmp_path))
    assert registry.model_names == []

def test_skips_dunder_files(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("")
    registry = discover_workflows(str(tmp_path))
    assert registry.model_names == []
```

### 3. Context Tests

**File**: `tests/test_context.py`

**Key test cases**:
- WorkflowContext is frozen (immutable)
- All fields accessible
- key_entry dict contains extra fields from ApiKeyEntry

```python
from workflow_open_ai.context import WorkflowContext

def test_context_is_frozen() -> None:
    ctx = WorkflowContext(
        endpoint_path="/v1/chat/completions",
        body={},
        headers={},
        query_params={},
        caller_key="sk-test",
        key_entry={"caller_key": "sk-test", "openai_key": "sk-oai"},
    )
    with pytest.raises(AttributeError):
        ctx.endpoint_path = "/changed"  # type: ignore[misc]

def test_key_entry_extra_fields() -> None:
    ctx = WorkflowContext(
        endpoint_path="/v1/chat/completions",
        body={},
        headers={},
        query_params={},
        caller_key="sk-test",
        key_entry={"caller_key": "sk-test", "openai_key": "sk-oai", "org": "my-org"},
    )
    assert ctx.key_entry["org"] == "my-org"
```

### 4. Models Route Tests

**File**: `tests/test_routes_models.py`

**Key test cases**:
- Returns 200 with list of models
- Each model has correct fields (id, object, created, owned_by)
- Requires auth (401 without Bearer token)
- Returns empty list when no workflows discovered

```python
def test_list_models(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.get("/v1/models", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert len(data["data"]) == 1
    model = data["data"][0]
    assert model["id"] == "echo_workflow"
    assert model["object"] == "model"
    assert model["owned_by"] == "workflow"

def test_models_requires_auth(client: TestClient) -> None:
    resp = client.get("/v1/models")
    assert resp.status_code == 401
```

### 5. Chat Route Tests

**File**: `tests/test_routes_chat.py`

**Key test cases**:
- Valid request returns 200 with chat.completion format
- Response contains workflow's output string
- Unknown model returns 400 with model_not_found code
- Missing model field returns 400
- Invalid JSON body returns 400
- Requires auth (401 without token)
- Workflow receives correct WorkflowContext fields

```python
def test_chat_completion(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={"model": "echo_workflow", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "echo_workflow"
    assert data["choices"][0]["message"]["content"] == "echo: hi"
    assert data["choices"][0]["finish_reason"] == "stop"

def test_unknown_model(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={"model": "nonexistent", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "model_not_found"

def test_missing_model_field(client: TestClient, auth_headers: dict[str, str]) -> None:
    resp = client.post(
        "/v1/chat/completions",
        headers=auth_headers,
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 400

def test_chat_requires_auth(client: TestClient) -> None:
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "echo_workflow", "messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401
```

### 6. Error Tests

**File**: `tests/test_errors.py`

**Key test cases**:
- AuthenticationError returns 401 with OpenAI error format
- InvalidRequestError returns 400 with OpenAI error format
- Validation errors return 400 with OpenAI error format
- Error response has correct structure: `{"error": {"message": ..., "type": ..., "code": ...}}`

### 7. Smoke Test Script

**File**: `scripts/smoketest.sh`

**Overview**: Executable bash script that validates a live server end-to-end. Accepts `--url` and `--key` args.

```bash
#!/usr/bin/env bash
set -euo pipefail

# Defaults
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-}"

usage() {
    echo "Usage: $0 [--url URL] [--key API_KEY]"
    echo ""
    echo "Smoke test for workflow_open_ai server."
    echo ""
    echo "Options:"
    echo "  --url URL    Server base URL (default: http://localhost:8000)"
    echo "  --key KEY    API key for Bearer auth (default: \$API_KEY env var)"
    echo "  --help       Show this help"
    exit 0
}

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --url) BASE_URL="$2"; shift 2 ;;
        --key) API_KEY="$2"; shift 2 ;;
        --help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

if [[ -z "$API_KEY" ]]; then
    echo "FAIL: API_KEY not set. Use --key or export API_KEY."
    exit 1
fi

PASS=0
FAIL=0

check() {
    local name="$1"
    local result="$2"
    if [[ "$result" == "ok" ]]; then
        echo "  PASS: $name"
        ((PASS++))
    else
        echo "  FAIL: $name — $result"
        ((FAIL++))
    fi
}

echo "Smoke testing: $BASE_URL"
echo ""

# 1. Health check
echo "[Health]"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
if [[ "$HTTP_CODE" == "200" ]]; then
    check "GET /health returns 200" "ok"
else
    check "GET /health returns 200" "got $HTTP_CODE"
fi

# 2. Auth enforcement
echo "[Auth]"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/models")
if [[ "$HTTP_CODE" == "401" ]]; then
    check "GET /v1/models without auth returns 401" "ok"
else
    check "GET /v1/models without auth returns 401" "got $HTTP_CODE"
fi

# 3. Models endpoint
echo "[Models]"
MODELS_RESP=$(curl -s -H "Authorization: Bearer $API_KEY" "$BASE_URL/v1/models")
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $API_KEY" "$BASE_URL/v1/models")
if [[ "$HTTP_CODE" == "200" ]]; then
    check "GET /v1/models returns 200" "ok"
else
    check "GET /v1/models returns 200" "got $HTTP_CODE"
fi

# Check response has model data
if echo "$MODELS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['object']=='list'; assert len(d['data'])>0" 2>/dev/null; then
    check "Models response has data" "ok"
else
    check "Models response has data" "empty or malformed"
fi

# 4. Chat completions
echo "[Chat Completions]"
CHAT_RESP=$(curl -s -X POST "$BASE_URL/v1/chat/completions" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"default_workflow","messages":[{"role":"user","content":"smoke test"}]}')
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/v1/chat/completions" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"default_workflow","messages":[{"role":"user","content":"smoke test"}]}')

if [[ "$HTTP_CODE" == "200" ]]; then
    check "POST /v1/chat/completions returns 200" "ok"
else
    check "POST /v1/chat/completions returns 200" "got $HTTP_CODE"
fi

if echo "$CHAT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['object']=='chat.completion'; assert d['choices'][0]['message']['role']=='assistant'" 2>/dev/null; then
    check "Chat response is valid chat.completion" "ok"
else
    check "Chat response is valid chat.completion" "malformed response"
fi

# 5. Unknown model
echo "[Error Handling]"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/v1/chat/completions" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"nonexistent-model","messages":[{"role":"user","content":"test"}]}')
if [[ "$HTTP_CODE" == "400" ]]; then
    check "Unknown model returns 400" "ok"
else
    check "Unknown model returns 400" "got $HTTP_CODE"
fi

# Summary
echo ""
echo "Results: $PASS passed, $FAIL failed"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
echo "All smoke tests passed."
```

**Key decisions**:
- Uses only `curl` and `python3` (available on any dev machine)
- Exits non-zero on first meaningful failure via `set -euo pipefail`, but continues through checks to report all results
- Actually, revised: runs all checks and reports pass/fail summary, exits 1 if any failed
- `--help` flag for self-documentation

**Implementation steps**:
1. Create `scripts/` directory
2. Write `smoketest.sh` with argument parsing
3. Implement each check: health, auth, models, chat, error handling
4. `chmod +x scripts/smoketest.sh`

### 8. Dependency Cleanup

**File**: `pyproject.toml`

**Changes**:
- Remove from `dependencies`: `openai`, `redis[hiredis]`, `tenacity`
- Remove from `dev` dependencies: `fakeredis`
- Remove mypy overrides for `fakeredis.*`
- Update all `skeleton_open_ai` references to `workflow_open_ai`
- Keep `httpx` in both main deps (may be needed by workflows) and dev deps (TestClient)

### 9. Docker Cleanup

**Dockerfile**:
- Add `COPY workflows/ ./workflows/` after copying src
- CMD already updated in Phase 1

**docker-compose.yml**:
- Already updated in Phase 1 (Redis removed, workflows mounted)
- Verify final state is clean

## Testing Requirements

### Unit Tests

| Test File | Coverage |
|-----------|----------|
| `tests/test_discovery.py` | Workflow scanning, model name resolution, error cases |
| `tests/test_context.py` | WorkflowContext immutability, field access |
| `tests/test_errors.py` | Error response formatting, exception types |

### Integration Tests

| Test File | Coverage |
|-----------|----------|
| `tests/test_routes_models.py` | GET /v1/models with auth |
| `tests/test_routes_chat.py` | POST /v1/chat/completions routing, response format, errors |

### Live Server Tests

| Script | Coverage |
|--------|----------|
| `scripts/smoketest.sh` | End-to-end: health, auth, models, chat, error handling |

## Validation Commands

```bash
# Run unit and integration tests
uv run pytest tests/ -v

# Type checking
uv run mypy src/workflow_open_ai tests/

# Linting
uv run ruff check src/ tests/ workflows/
uv run ruff format --check src/ tests/ workflows/

# Docker build
docker build -t workflow-open-ai .

# Run smoke test (requires running server)
# Terminal 1:
uv run uvicorn workflow_open_ai.main:app --port 8000
# Terminal 2:
./scripts/smoketest.sh --url http://localhost:8000 --key sk-your-key
```

---

*This spec is ready for implementation. Follow the patterns and validate at each step.*
