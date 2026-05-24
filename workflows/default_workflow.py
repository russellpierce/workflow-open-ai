"""Default placeholder workflow. Demonstrates the workflow interface."""

from workflow_open_ai.context import WorkflowContext

MODEL_NAME = "default_workflow"


def run(ctx: WorkflowContext) -> str:
    """Echo the user's last message back as a placeholder response."""
    messages = ctx.body.get("messages", [])
    last_message = messages[-1]["content"] if messages else "No messages provided"

    return (
        f"This is a placeholder response from model '{ctx.body.get('model', 'unknown')}'. "
        f"Your message was: '{last_message}'. "
        f"Implement your workflow in the workflows/ directory."
    )
