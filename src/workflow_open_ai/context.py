from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowContext:
    """Full request context passed to workflow run() functions."""

    endpoint_path: str
    body: dict[str, Any]
    headers: dict[str, str]
    query_params: dict[str, str]
    caller_key: str
    key_entry: dict[str, Any]
