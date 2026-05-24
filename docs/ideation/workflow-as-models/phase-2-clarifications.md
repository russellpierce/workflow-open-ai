# Phase 2 Clarifications

Questions + answers that come up during Phase 2 implementation.

---

## Q: Are workflows async or sync?

**Current spec shows `async def run(ctx)`. Does that matter?**

Decision: **Keep sync for now**. Workflows return strings immediately, no I/O reason to be async. Change to async if a workflow needs to call external APIs (Phase 3+).

Implication for routes:
- If workflow is **sync**: route handler can be sync or async (FastAPI handles both)
- If workflow is **async**: route handler must be async, call via `await workflow.run(ctx)`

For Phase 2: Implement workflows as **sync**, route handlers as **async** (more future-proof). If workflow is sync, call via `workflow.run(ctx)` (no await).

Example (default_workflow.py):
```python
def run(ctx: WorkflowContext) -> str:
    return "response"
```

Example (routes_chat.py):
```python
async def chat_completions(request: Request, api_key: str = Depends(...)):
    # ... construct ctx ...
    response_text = workflow.run(ctx)  # No await
    # ... wrap response ...
```

---

## Q: Is `run` a method or module-level function?

**The spec shows `async def run(ctx)` at module level, not a class method. Confirm?**

Answer: **Module-level function**, exported as `workflow.run`.

Example:
```python
# workflows/my_workflow.py
from workflow_open_ai.context import WorkflowContext

MODEL_NAME = "my_workflow"

def run(ctx: WorkflowContext) -> str:
    return "result"
```

Discovery validates: `callable(getattr(module, "run", None))`.

No class wrappers, no method binding — just a function.

---

## Q: What if a workflow file has a syntax error?

**Discovery tries to import. Does it fail at startup, or log and skip?**

Answer: **Fail at startup**. Don't catch ImportError.

Rationale: Bad code should fail loudly. If a workflow doesn't import, the server shouldn't come up half-working.

Error message:
```
Traceback (most recent call last):
  ...
  File "workflows/bad_workflow.py", line 5, in <module>
    x = 1 / 0
ZeroDivisionError: division by zero
```

User sees it and fixes it. Good.

---

## Q: How do we pass `key_entry` (a Pydantic model) to the workflow?

**The spec says `key_entry: dict[str, Any]` in WorkflowContext. How do we convert?**

Answer: In routes_chat.py, after looking up the key in key_lookup:

```python
key_entry = key_lookup[api_key]  # This is an ApiKeyEntry (Pydantic)
ctx = WorkflowContext(
    # ...
    key_entry=key_entry.model_dump(),  # Convert to dict
)
```

`model_dump()` returns dict with all fields (including `extra="allow"` fields).

Workflow receives plain dict, doesn't import ApiKeyEntry. Clean.

---

## Q: What happens if a workflow raises an exception?

**The spec says "unhandled, fail-fast". What does the client see?**

Answer: **500 error with traceback** (from FastAPI's default exception handler).

Example:
```python
# workflows/bad_workflow.py
def run(ctx: WorkflowContext) -> str:
    raise ValueError("Something broke")
```

Client gets:
```json
{
  "detail": "Internal server error"
}
```

Server logs full traceback.

Rationale: Workflows are user code. Bugs are user responsibility. No catching, no retries — fail fast and loud so the user sees it immediately.

---

## Q: Can a workflow have side effects (write files, call external APIs)?

**WorkflowContext is frozen, read-only. But can workflow code do I/O?**

Answer: **Yes, workflows can do whatever they want**. They're Python functions.

`frozen=True` on WorkflowContext just prevents `ctx.foo = bar`. Doesn't stop the function from:
- Writing files
- Calling external APIs
- Querying databases
- Modifying global state

Frozen context = "don't mutate this object", not "don't do I/O". Make sense?

---

## Q: What if `workflows_dir` is empty?

**No files in directory. Does discovery fail, or return empty registry?**

Answer: **Return empty registry**. No error.

```python
registry = discover_workflows("./workflows")
registry.model_names == []
```

This is fine. Server starts but has no workflows.

Next request to `/v1/chat/completions` will 404 (model not found), which is correct.

---

## Q: Can two workflows have the same MODEL_NAME?

**Workflow A exports MODEL_NAME = "shared", workflow B too. What happens?**

Answer: **Startup fails** with:
```
RuntimeError: Duplicate model name 'shared': already registered by workflows/a.py, conflict with workflows/b.py
```

Registry._register() checks for duplicates.

---

## Q: How do we handle workflows that take a long time?

**Some workflows might need 30s. Is there a timeout?**

Answer: **Use FastAPI timeout + workflow design**. Phase 2 has no timeout.

If you need one, set at deployment time (e.g., nginx, reverse proxy, or uvicorn `--timeout-keep-alive`).

For workflows that are slow: that's OK. Client waits. If you want async + streaming, that's Phase 3+.

---

## Q: Can we reload workflows without restarting the server?

**Developer adds a new workflow .py file. Does server see it without restart?**

Answer: **No, not in Phase 2**. Discovery runs once at startup.

Hot-reload is Phase 3+ (would need a file watcher + re-discovery).

For now: restart server to pick up new workflows.

---

## Q: What's in `ctx.query_params`?

**Example: `POST /v1/chat/completions?foo=bar`. Does workflow see `{"foo": "bar"}`?**

Answer: **Yes**. In routes_chat.py:

```python
query_params=dict(request.query_params)
```

Workflow gets all query string params in the context dict.

---

## Q: What if the JSON body is huge?

**1MB JSON payload. Memory OK?**

Answer: **Should be fine for Phase 2**. We parse the body once and pass it as a dict.

If you need streaming or chunked processing, that's Phase 3+.

No explicit size limits in Phase 2.

---

## Q: Does the workflow receive the full request, or just the chat/completions payload?

**If client sends custom headers or extra JSON fields, does workflow see them?**

Answer: **Yes to both**.

- Headers: `ctx.headers` = all request headers (dict)
- Body: `ctx.body` = full JSON body as parsed dict (including any extra fields)

Workflow can inspect anything the client sent.

---

## Q: What's the response ID format?

**The spec shows `f"chatcmpl-{uuid.uuid4().hex}"`. Any reason for that prefix?**

Answer: Matches OpenAI's format. Their IDs start with `chatcmpl-`.

We generate: `chatcmpl-abc123def456...`

Just for consistency. Any unique ID would work, but this matches the OpenAI convention.

---

## Q: Are timestamps in seconds or milliseconds?

**`"created": int(time.time())` — that's Unix seconds, right?**

Answer: **Yes, seconds**. OpenAI uses Unix timestamp (seconds since epoch).

```python
created = int(time.time())  # e.g., 1738900000
```

Not milliseconds.
