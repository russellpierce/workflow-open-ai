# workflow-open-ai

**AI-authored. Human review + editing of documentation. Only included tests and scripts tested.**

FastAPI server exposing OpenAI-compatible API for custom workflows. Each workflow file in `workflows/` auto-registers as a model.

## Features

- OpenAI-compatible endpoints (`/v1/chat/completions`, `/v1/models`)
- Auto-discover workflows from `workflows/` dir
- Bearer token authentication
- YAML config
- Docker ready

## Quick Start

### Local Development

```bash
uv sync --all-extras
uv run pre-commit install
cp api_keys.yaml.example api_keys.yaml
uv run uvicorn workflow_open_ai.main:app --reload
```

### Docker

```bash
docker compose up --build
```

## Configuration

`config.yaml`:
```yaml
server:
  host: "0.0.0.0"
  port: 8340
auth:
  api_keys_file: "api_keys.yaml"
workflows_dir: "./workflows"
cors:
  allow_origins: ["*"]
```

`api_keys.yaml`:
```yaml
keys:
  - caller_key: "sk-abc123"
    openai_key: "sk-openai-xyz"
```

Generate key: `python -c "import secrets; print('sk-' + secrets.token_hex(32))"`

## API Reference

Health check:
```bash
curl http://localhost:8340/health
```

List models:
```bash
curl http://localhost:8340/v1/models \
  -H "Authorization: Bearer sk-your-api-key"
```

Chat completion (requires workflow implementation):
```bash
curl http://localhost:8340/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "default_workflow",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## Implementing Workflows

Drop Python file in `workflows/`. Module must export:

```python
from workflow_open_ai.context import WorkflowContext

async def run(ctx: WorkflowContext) -> str:
    # ctx.body: parsed JSON request body
    # ctx.headers: request headers
    # ctx.query_params: URL query params
    # ctx.caller_key: authenticated API key
    # ctx.key_entry: full key entry (dict)
    return "response"
```

Optional: `MODEL_NAME = "custom_name"` to override filename.

## Development

```bash
uv run pytest                          # Run tests
uv run mypy src tests                  # Type check
uv run ruff check src                  # Lint
uv run ruff format src                 # Format
uv run pre-commit run --all-files      # All hooks
```

## Environment

| Var | Default | Purpose |
|-----|---------|---------|
| `CONFIG_PATH` | `config.yaml` | Config file |
| `LOG_LEVEL` | `INFO` | Log level |

## License

MIT
