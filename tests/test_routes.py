from fastapi.testclient import TestClient


def test_health_check(client: TestClient) -> None:
    """Health endpoint works without auth."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_models_list_requires_auth(client: TestClient) -> None:
    """/v1/models requires Bearer token."""
    response = client.get("/v1/models")
    assert response.status_code == 401
    assert response.json()["error"]["type"] == "authentication_error"


def test_models_list_with_auth(client: TestClient, valid_api_key: str) -> None:
    """/v1/models returns list of discovered workflows."""
    response = client.get("/v1/models", headers={"Authorization": f"Bearer {valid_api_key}"})
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) > 0
    assert data["data"][0]["object"] == "model"
    assert data["data"][0]["owned_by"] == "workflow"


def test_models_list_has_default_workflow(client: TestClient, valid_api_key: str) -> None:
    """default_workflow is in the models list."""
    response = client.get("/v1/models", headers={"Authorization": f"Bearer {valid_api_key}"})
    assert response.status_code == 200
    model_ids = [m["id"] for m in response.json()["data"]]
    assert "default_workflow" in model_ids


def test_chat_completions_requires_auth(client: TestClient) -> None:
    """/v1/chat/completions requires Bearer token."""
    response = client.post(
        "/v1/chat/completions", json={"model": "default_workflow", "messages": []}
    )
    assert response.status_code == 401
    assert response.json()["error"]["type"] == "authentication_error"


def test_chat_completions_requires_model(client: TestClient, valid_api_key: str) -> None:
    """/v1/chat/completions requires 'model' field."""
    response = client.post(
        "/v1/chat/completions",
        json={"messages": []},
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"
    assert "model" in response.json()["error"]["message"].lower()


def test_chat_completions_invalid_model(client: TestClient, valid_api_key: str) -> None:
    """/v1/chat/completions returns 400 for unknown model."""
    response = client.post(
        "/v1/chat/completions",
        json={"model": "unknown_model", "messages": []},
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "model_not_found"


def test_chat_completions_invalid_json(client: TestClient, valid_api_key: str) -> None:
    """/v1/chat/completions returns 400 for invalid JSON."""
    response = client.post(
        "/v1/chat/completions",
        content="not json",
        headers={"Authorization": f"Bearer {valid_api_key}", "Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_chat_completions_success(client: TestClient, valid_api_key: str) -> None:
    """POST /v1/chat/completions with valid request returns chat.completion response."""
    response = client.post(
        "/v1/chat/completions",
        json={"model": "default_workflow", "messages": [{"role": "user", "content": "hello"}]},
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "default_workflow"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "placeholder" in data["choices"][0]["message"]["content"].lower()
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["usage"]["prompt_tokens"] == 0
    assert data["usage"]["completion_tokens"] == 0


def test_chat_completions_response_has_id(client: TestClient, valid_api_key: str) -> None:
    """Response ID starts with 'chatcmpl-'."""
    response = client.post(
        "/v1/chat/completions",
        json={"model": "default_workflow", "messages": [{"role": "user", "content": "test"}]},
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status_code == 200
    assert response.json()["id"].startswith("chatcmpl-")


def test_chat_completions_response_has_created(client: TestClient, valid_api_key: str) -> None:
    """Response has 'created' timestamp."""
    response = client.post(
        "/v1/chat/completions",
        json={"model": "default_workflow", "messages": [{"role": "user", "content": "test"}]},
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status_code == 200
    created = response.json()["created"]
    assert isinstance(created, int)
    assert created > 0


def test_chat_completions_workflow_receives_context(client: TestClient, valid_api_key: str) -> None:
    """Workflow receives user message in response."""
    user_msg = "my special message"
    response = client.post(
        "/v1/chat/completions",
        json={"model": "default_workflow", "messages": [{"role": "user", "content": user_msg}]},
        headers={"Authorization": f"Bearer {valid_api_key}"},
    )
    assert response.status_code == 200
    response_content = response.json()["choices"][0]["message"]["content"]
    assert user_msg in response_content
