"""Regression tests for Evidence release guardrail wiring in CI."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"
SMOKE_SCRIPT = REPO_ROOT / "scripts/evidence/evidence_auth_smoke.mjs"


def test_ci_runs_evidence_guardrail_tests() -> None:
    """CI must execute Evidence guardrail tests before merge."""
    source = CI_WORKFLOW.read_text(encoding="utf-8")

    assert (
        "python3 -m pytest scripts/tests/test_evidence_auth_asset_guard.py "
        "scripts/tests/test_evidence_release_guardrails.py -q"
    ) in source


def test_ci_runs_smoke_contract_drift_test() -> None:
    """CI must keep smoke contract drift checks in the Evidence guardrail flow."""
    source = CI_WORKFLOW.read_text(encoding="utf-8")

    assert (
        "python3 -m pytest scripts/tests/test_evidence_authenticated_smoke_contract.py -q"
    ) in source


def test_ci_runs_route_contract_verifier() -> None:
    """CI Evidence job must run route contract checks after build."""
    source = CI_WORKFLOW.read_text(encoding="utf-8")

    assert (
        "node scripts/evidence/verify_route_contract.mjs --build-dir evidence/build "
        "--routes occupancy moveins moveouts geography pricing"
    ) in source


def test_ci_detects_all_evidence_guardrail_paths() -> None:
    """Change detection must cover paths that impact route integrity guardrails."""
    source = CI_WORKFLOW.read_text(encoding="utf-8")

    for expected in (
        "evidence/",
        "scripts/evidence/",
        "scripts/tests/",
        ".github/workflows/",
        "evidence/buildspec.yml",
    ):
        assert expected in source


def test_release_contract_requires_coverage_marker_checks_in_smoke_matrix() -> None:
    """Release guardrails must include smoke contract checks for timestamp coverage markers."""
    source = SMOKE_SCRIPT.read_text(encoding="utf-8")

    assert "coverage_markers" in source
    assert "Coverage:" in source
