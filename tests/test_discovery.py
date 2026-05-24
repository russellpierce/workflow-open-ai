import tempfile
from pathlib import Path

import pytest

from workflow_open_ai.discovery import discover_workflows


def test_discover_workflows_empty_dir() -> None:
    """Empty directory returns empty registry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = discover_workflows(tmpdir)
        assert registry.model_names == []


def test_discover_workflows_missing_dir() -> None:
    """Missing directory raises RuntimeError."""
    with pytest.raises(RuntimeError, match="Workflows directory not found"):
        discover_workflows("/nonexistent/path")


def test_discover_workflows_single_workflow() -> None:
    """Discovers single workflow file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wf_file = Path(tmpdir) / "simple.py"
        wf_file.write_text(
            "def run(ctx):\n    return 'test'\n"
        )
        registry = discover_workflows(tmpdir)
        assert registry.model_names == ["simple"]


def test_discover_workflows_with_model_name() -> None:
    """Uses MODEL_NAME attribute when present."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wf_file = Path(tmpdir) / "my_workflow.py"
        wf_file.write_text(
            'MODEL_NAME = "custom_name"\ndef run(ctx):\n    return "test"\n'
        )
        registry = discover_workflows(tmpdir)
        assert registry.model_names == ["custom_name"]


def test_discover_workflows_missing_run() -> None:
    """Missing run() function raises RuntimeError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wf_file = Path(tmpdir) / "bad.py"
        wf_file.write_text("def other_func():\n    pass\n")
        with pytest.raises(RuntimeError, match="missing required 'run' function"):
            discover_workflows(tmpdir)


def test_discover_workflows_invalid_model_name() -> None:
    """Invalid MODEL_NAME (non-string) raises RuntimeError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wf_file = Path(tmpdir) / "bad.py"
        wf_file.write_text(
            "MODEL_NAME = 123\ndef run(ctx):\n    return 'test'\n"
        )
        with pytest.raises(RuntimeError, match="MODEL_NAME must be a non-empty string"):
            discover_workflows(tmpdir)


def test_discover_workflows_duplicate_model_names() -> None:
    """Duplicate model names raise RuntimeError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wf1 = Path(tmpdir) / "a.py"
        wf1.write_text('MODEL_NAME = "shared"\ndef run(ctx):\n    return "a"\n')
        wf2 = Path(tmpdir) / "b.py"
        wf2.write_text('MODEL_NAME = "shared"\ndef run(ctx):\n    return "b"\n')
        with pytest.raises(RuntimeError, match="Duplicate model name 'shared'"):
            discover_workflows(tmpdir)


def test_discover_workflows_skips_init() -> None:
    """Skips __init__.py and __pycache__."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir).joinpath("__init__.py").write_text("")
        wf = Path(tmpdir) / "real.py"
        wf.write_text("def run(ctx):\n    return 'test'\n")
        registry = discover_workflows(tmpdir)
        assert registry.model_names == ["real"]


def test_registry_get_returns_module() -> None:
    """Registry.get() returns the workflow module."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wf = Path(tmpdir) / "test.py"
        wf.write_text("def run(ctx):\n    return 'hello'\n")
        registry = discover_workflows(tmpdir)
        module = registry.get("test")
        assert module is not None
        assert callable(module.run)


def test_registry_get_nonexistent_returns_none() -> None:
    """Registry.get() returns None for unknown model."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wf = Path(tmpdir) / "test.py"
        wf.write_text("def run(ctx):\n    return 'test'\n")
        registry = discover_workflows(tmpdir)
        assert registry.get("unknown") is None
