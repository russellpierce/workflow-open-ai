import pytest
from fastapi.testclient import TestClient

from workflow_open_ai.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def valid_api_key() -> str:
    """Valid API key from api_keys.yaml example."""
    return "sk-your-caller-key-here"
