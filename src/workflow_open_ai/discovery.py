import importlib.util
import logging
from pathlib import Path
from types import ModuleType

logger = logging.getLogger(__name__)


class WorkflowRegistry:
    """Maps model names to workflow modules."""

    def __init__(self) -> None:
        self._workflows: dict[str, ModuleType] = {}

    @property
    def model_names(self) -> list[str]:
        """Return sorted list of registered model names."""
        return sorted(self._workflows.keys())

    def get(self, model_name: str) -> ModuleType | None:
        """Get a workflow module by model name."""
        return self._workflows.get(model_name)

    def _register(self, model_name: str, module: ModuleType, source: Path) -> None:
        """Register a workflow. Raise on duplicate model names."""
        if model_name in self._workflows:
            existing = self._workflows[model_name]
            existing_file = getattr(existing, "__file__", "?")
            raise RuntimeError(
                f"Duplicate model name '{model_name}': "
                f"already registered by {existing_file}, "
                f"conflict with {source}"
            )
        self._workflows[model_name] = module


def discover_workflows(workflows_dir: str) -> WorkflowRegistry:
    """
    Scan workflows_dir for .py files, import them, validate, and build registry.

    Raises RuntimeError on:
    - workflows_dir doesn't exist
    - workflow file missing run() function
    - duplicate model names
    - syntax errors in workflow files
    """
    path = Path(workflows_dir)

    if not path.is_dir():
        raise RuntimeError(f"Workflows directory not found: {path.resolve()}")

    registry = WorkflowRegistry()

    for py_file in sorted(path.glob("*.py")):
        if py_file.name.startswith("__"):
            continue

        module = _import_workflow_file(py_file)

        run_fn = getattr(module, "run", None)
        if not callable(run_fn):
            raise RuntimeError(f"Workflow '{py_file.name}' missing required 'run' function")

        model_name = _resolve_model_name(module, py_file)

        registry._register(model_name, module, py_file)
        logger.info(f"Discovered workflow: {model_name} ({py_file.name})")

    return registry


def _import_workflow_file(py_file: Path) -> ModuleType:
    """Import a single .py file as a module."""
    module_name = f"workflows.{py_file.stem}"
    spec = importlib.util.spec_from_file_location(module_name, py_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load workflow: {py_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_model_name(module: ModuleType, py_file: Path) -> str:
    """Get model name from MODEL_NAME attribute or fall back to filename."""
    model_name = getattr(module, "MODEL_NAME", None)
    if model_name is not None:
        if not isinstance(model_name, str) or not model_name.strip():
            raise RuntimeError(f"Workflow '{py_file.name}': MODEL_NAME must be a non-empty string")
        return model_name.strip()
    return py_file.stem
