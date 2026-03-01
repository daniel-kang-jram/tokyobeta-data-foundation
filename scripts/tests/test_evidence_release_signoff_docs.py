"""Contract tests for Evidence release sign-off documentation."""

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[2]
OPERATIONS_DOC = REPO_ROOT / "docs/OPERATIONS.md"
DEPLOYMENT_DOC = REPO_ROOT / "docs/DEPLOYMENT.md"

PRICING_FUNNEL_MARKERS = (
    "Overall Conversion Rate (%)",
    "Municipality Segment Parity (Applications vs Move-ins)",
    "Nationality Segment Parity (Applications vs Move-ins)",
    "Monthly Conversion Trend",
)


def test_deployment_doc_has_explicit_go_no_go_matrix_and_blockers() -> None:
    """Deployment runbook must define deterministic GO/NO-GO criteria."""
    source = DEPLOYMENT_DOC.read_text(encoding="utf-8")

    assert "GO only if" in source
    assert "NO-GO if" in source
    assert "route marker mismatch" in source
    assert "KPI Landing (Gold)" in source
    assert "/api//" in source
    assert "Unexpected token '<'" in source
    assert "application/json" in source


def test_deployment_doc_explicitly_lists_pricing_funnel_release_markers() -> None:
    """Release criteria must explicitly include deterministic pricing funnel markers."""
    source = DEPLOYMENT_DOC.read_text(encoding="utf-8")

    for marker in PRICING_FUNNEL_MARKERS:
        assert marker in source


def test_operations_doc_includes_auth_smoke_commands_and_rollback_trigger_steps() -> None:
    """Operations runbook must include auth smoke execution and rollback trigger checks."""
    source = OPERATIONS_DOC.read_text(encoding="utf-8")

    assert "scripts/evidence/evidence_auth_smoke.mjs" in source
    assert "--print-route-matrix" in source
    assert "summary.json" in source
    assert re.search(r"artifact", source, flags=re.IGNORECASE)
    assert re.search(r"rollback", source, flags=re.IGNORECASE)
    assert re.search(r"trigger", source, flags=re.IGNORECASE)
