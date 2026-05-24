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
    """Create router for POST /v1/chat/completions endpoint."""
    router = APIRouter(tags=["chat"])

    @router.post("/v1/chat/completions")
    async def chat_completions(
        request: Request,
        api_key: str = Depends(auth_dependency),
    ) -> JSONResponse:
        """Route chat completion request to discovered workflow."""
        raw_body = await request.body()
        try:
            body: dict[str, object] = json.loads(raw_body) if raw_body else {}
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise InvalidRequestError(
                message=f"Invalid JSON body: {e}",
                error_code="invalid_request",
            ) from e

        model = body.get("model", "")
        if not isinstance(model, str) or not model:
            raise InvalidRequestError(
                message="'model' field is required",
                error_code="invalid_request",
            )

        workflow = registry.get(model)
        if workflow is None:
            raise InvalidRequestError(
                message=f"Model '{model}' not found. Available: {registry.model_names}",
                error_code="model_not_found",
            )

        key_entry = key_lookup[api_key]
        ctx = WorkflowContext(
            endpoint_path="/v1/chat/completions",
            body=body,
            headers=dict(request.headers),
            query_params=dict(request.query_params),
            caller_key=api_key,
            key_entry=key_entry.model_dump(),
        )

        response_text = workflow.run(ctx)

        return JSONResponse(
            content={
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": response_text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
        )

    return router
