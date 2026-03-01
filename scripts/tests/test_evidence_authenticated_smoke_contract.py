"""Contract tests for authenticated Evidence smoke route matrix and workflow wiring."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = REPO_ROOT / "scripts/evidence/evidence_auth_smoke.mjs"
SMOKE_WORKFLOW = REPO_ROOT / ".github/workflows/evidence-auth-smoke.yml"

REQUIRED_ROUTES = ("/occupancy", "/moveins", "/moveouts", "/geography", "/pricing")
ROUTE_MATRIX_SCHEMA_FIELDS = ("h1", "kpi_markers", "time_context_markers", "funnel_markers")
PRICING_FUNNEL_MARKERS = (
    "Overall Conversion Rate (%)",
    "Municipality Segment Parity (Applications vs Move-ins)",
    "Nationality Segment Parity (Applications vs Move-ins)",
    "Monthly Conversion Trend",
)
REQUIRED_ARTIFACT_MARKERS = (
    "screenshots",
    "console",
    "network",
    "summary.json",
)


def test_smoke_script_includes_all_release_routes() -> None:
    """Smoke contract must include all release-gated routes."""
    assert SMOKE_SCRIPT.exists(), "expected smoke script at scripts/evidence/evidence_auth_smoke.mjs"
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    for route in REQUIRED_ROUTES:
        assert route in source


def test_smoke_script_exposes_route_matrix_schema_and_print_flag() -> None:
    """Smoke contract must expose deterministic route matrix marker groups."""
    assert SMOKE_SCRIPT.exists(), "expected smoke script at scripts/evidence/evidence_auth_smoke.mjs"
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert "--print-route-matrix" in source
    for field in ROUTE_MATRIX_SCHEMA_FIELDS:
        assert field in source


def test_smoke_script_encodes_pricing_funnel_assertions() -> None:
    """Pricing route must assert all funnel markers required for release sign-off."""
    assert SMOKE_SCRIPT.exists(), "expected smoke script at scripts/evidence/evidence_auth_smoke.mjs"
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    for marker in PRICING_FUNNEL_MARKERS:
        assert marker in source


def test_smoke_script_asserts_metadata_json_and_rejects_malformed_api_paths() -> None:
    """Smoke contract must fail on malformed metadata paths and non-JSON metadata responses."""
    assert SMOKE_SCRIPT.exists(), "expected smoke script at scripts/evidence/evidence_auth_smoke.mjs"
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert "evidencemeta.json" in source
    assert "application/json" in source
    assert "/api//" in source


def test_smoke_artifact_outputs_and_workflow_upload_contract_exist() -> None:
    """Smoke contract must define artifact outputs and workflow artifact upload."""
    assert SMOKE_SCRIPT.exists(), "expected smoke script at scripts/evidence/evidence_auth_smoke.mjs"
    assert SMOKE_WORKFLOW.exists(), "expected workflow at .github/workflows/evidence-auth-smoke.yml"

    script_source = SMOKE_SCRIPT.read_text(encoding="utf-8")
    workflow_source = SMOKE_WORKFLOW.read_text(encoding="utf-8")

    for marker in REQUIRED_ARTIFACT_MARKERS:
        assert marker in script_source

    assert "workflow_dispatch" in workflow_source
    assert "schedule" in workflow_source
    assert "upload-artifact" in workflow_source
    assert "evidence_auth_smoke" in workflow_source
