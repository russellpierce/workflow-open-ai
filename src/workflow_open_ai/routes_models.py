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
    """Create router for GET /v1/models endpoint."""
    router = APIRouter(tags=["models"])

    @router.get("/v1/models", response_model=ModelsListResponse)
    def list_models(_api_key: str = Depends(auth_dependency)) -> ModelsListResponse:
        """List discovered workflows as OpenAI-compatible models."""
        models = [ModelInfo(id=name, created=_SERVER_START_TIME) for name in registry.model_names]
        return ModelsListResponse(data=models)

    return router
