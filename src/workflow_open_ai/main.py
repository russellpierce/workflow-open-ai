import logging
import os
from typing import Final

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from workflow_open_ai import __version__
from workflow_open_ai.auth import create_auth_dependency
from workflow_open_ai.config import AppConfig, load_config
from workflow_open_ai.discovery import discover_workflows
from workflow_open_ai.errors import register_error_handlers
from workflow_open_ai.key_config import build_key_lookup, load_api_keys_config
from workflow_open_ai.routes_chat import create_chat_router
from workflow_open_ai.routes_health import router as health_router
from workflow_open_ai.routes_models import create_models_router

# Configure logging
LOG_LEVEL: Final = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger: Final = logging.getLogger(__name__)

# Load configuration
CONFIG_PATH: Final = os.environ.get("CONFIG_PATH", "config.yaml")
config: AppConfig = load_config(CONFIG_PATH)

# Load API keys
keys_config = load_api_keys_config(config.auth.api_keys_file)
key_lookup = build_key_lookup(keys_config)
auth_dependency = create_auth_dependency(frozenset(key_lookup.keys()))

# Create FastAPI application
app: Final = FastAPI(
    title="Workflow OpenAI",
    description="Custom AI workflows behind an OpenAI-compatible interface",
    version=__version__,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register error handlers
register_error_handlers(app)

# Discover workflows
registry = discover_workflows(config.workflows_dir)

# Register routes
app.include_router(create_models_router(registry, auth_dependency))
app.include_router(create_chat_router(registry, key_lookup, auth_dependency))
app.include_router(health_router)

logger.info(f"Server configured: {config.server.host}:{config.server.port}")
logger.info(f"CORS origins: {config.cors.allow_origins}")
logger.info(f"Discovered workflows: {registry.model_names}")


def run() -> None:
    """Run the server using uvicorn."""
    import uvicorn

    uvicorn.run(
        "workflow_open_ai.main:app",
        host=config.server.host,
        port=config.server.port,
        log_level=LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    run()
