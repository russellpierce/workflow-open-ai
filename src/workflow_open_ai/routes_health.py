import logging
from typing import Final

from fastapi import APIRouter
from pydantic import BaseModel

logger: Final = logging.getLogger(__name__)
router: Final = APIRouter(tags=["health"])


class HealthResponse(BaseModel):  # type: ignore[misc]
    status: str = "healthy"


@router.get("/health", response_model=HealthResponse)  # type: ignore[untyped-decorator]
def health_check() -> HealthResponse:
    """Health check endpoint. No authentication required."""
    logger.debug("Health check requested")
    return HealthResponse(status="healthy")
