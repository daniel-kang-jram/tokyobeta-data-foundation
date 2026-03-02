"""Contract tests for authenticated Evidence smoke route matrix and workflow wiring."""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE_SCRIPT = REPO_ROOT / "scripts/evidence/evidence_auth_smoke.mjs"
SMOKE_WORKFLOW = REPO_ROOT / ".github/workflows/evidence-auth-smoke.yml"

REQUIRED_ROUTES = ("/occupancy", "/moveins", "/moveouts", "/geography", "/pricing")
ROUTE_MATRIX_SCHEMA_FIELDS = (
    "h1",
    "kpi_markers",
    "time_context_markers",
    "coverage_markers",
    "funnel_markers",
)
ROUTE_RESULT_PASS_FAIL_FIELDS = (
    "status",
    "error",
    "failure_kind",
    "auth_redirect_detected",
)
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
PRIMARY_ROUTE_PAGES = (
    "evidence/pages/occupancy.md",
    "evidence/pages/moveins.md",
    "evidence/pages/moveouts.md",
    "evidence/pages/geography.md",
    "evidence/pages/pricing.md",
)


def load_route_matrix() -> dict[str, dict[str, object]]:
    """Load deterministic route matrix JSON from the smoke script."""
    output = subprocess.check_output(
        ["node", str(SMOKE_SCRIPT), "--print-route-matrix"],
        cwd=REPO_ROOT,
        text=True,
    )
    payload = json.loads(output)
    routes = payload.get("routes")
    assert isinstance(routes, dict)
    return routes


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


def test_route_matrix_requires_coverage_markers_for_release_routes() -> None:
    """Every release-gated route must expose deterministic coverage marker checks."""
    routes = load_route_matrix()

    for route_data in routes.values():
        route_contract = dict(route_data)
        route_path = route_contract["path"]
        if route_path in REQUIRED_ROUTES:
            assert "coverage_markers" in route_contract
            assert "Coverage:" in route_contract["coverage_markers"]


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


def test_smoke_script_tracks_auth_redirects_and_login_bounces_in_summary_contract() -> None:
    """Smoke summary contract must include deterministic auth redirect evidence."""
    assert SMOKE_SCRIPT.exists(), "expected smoke script at scripts/evidence/evidence_auth_smoke.mjs"
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert "auth_redirects" in source
    assert "/__auth/login" in source
    assert "redirect_chain" in source


def test_smoke_script_route_results_include_deterministic_redirect_failure_fields() -> None:
    """Route-level results must include deterministic fields for redirect vs marker failures."""
    assert SMOKE_SCRIPT.exists(), "expected smoke script at scripts/evidence/evidence_auth_smoke.mjs"
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    for field in ROUTE_RESULT_PASS_FAIL_FIELDS:
        assert field in source

    assert "failed-auth-redirect" in source


def test_primary_route_pages_include_time_and_coverage_markers_expected_by_smoke() -> None:
    """Route pages gated by smoke must expose explicit Time basis/Coverage/Freshness copy."""
    for relative_path in PRIMARY_ROUTE_PAGES:
        page_path = REPO_ROOT / relative_path
        source = page_path.read_text(encoding="utf-8")

        assert "Time basis:" in source, f"missing Time basis marker in {relative_path}"
        assert "Coverage:" in source, f"missing Coverage marker in {relative_path}"
        assert "Freshness:" in source, f"missing Freshness marker in {relative_path}"
