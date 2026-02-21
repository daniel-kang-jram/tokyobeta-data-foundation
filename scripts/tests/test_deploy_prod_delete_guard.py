"""Regression tests for deploy-prod Terraform delete guard behavior."""

from pathlib import Path

DEPLOY_WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github/workflows/deploy-prod.yml"
)


def test_delete_guard_only_blocks_delete_without_create() -> None:
    """Deploy guard must allow replacement actions (delete+create)."""
    source = DEPLOY_WORKFLOW.read_text(encoding="utf-8")

    assert "DELETE_ONLY_ADDRESSES" in source
    assert 'index("delete")' in source
    assert 'index("create") | not' in source
