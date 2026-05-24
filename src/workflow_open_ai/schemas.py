from pydantic import BaseModel, Field


class ChatMessage(BaseModel):  # type: ignore[misc]
    role: str
    content: str


class Choice(BaseModel):  # type: ignore[misc]
    index: int
    message: ChatMessage
    finish_reason: str


class Usage(BaseModel):  # type: ignore[misc]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):  # type: ignore[misc]
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage = Field(default_factory=Usage)


class ModelInfo(BaseModel):  # type: ignore[misc]
    id: str
    object: str = "model"
    created: int
    owned_by: str = "workflow"


class ModelsListResponse(BaseModel):  # type: ignore[misc]
    object: str = "list"
    data: list[ModelInfo]
