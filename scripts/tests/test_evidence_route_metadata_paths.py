"""Regression tests for Evidence metadata route path normalization."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYOUT_TEMPLATE = REPO_ROOT / "evidence/.evidence/template/src/pages/+layout.js"
EVIDENCE_BUILD = REPO_ROOT / "evidence/build"
ROUTE_PAGES = ("occupancy", "moveins", "moveouts", "geography", "pricing")
ROUTE_CONTRACT_VERIFIER = REPO_ROOT / "scripts/evidence/verify_route_contract.mjs"


def test_layout_template_does_not_use_raw_route_id_composition() -> None:
    """Layout template should not compose metadata path with raw route.id."""
    source = LAYOUT_TEMPLATE.read_text(encoding="utf-8")

    assert "`/api/${route.id}/evidencemeta.json`" not in source


def test_root_route_metadata_path_is_canonical() -> None:
    """Root route metadata fetch path should not emit triple slash."""
    root_html = (EVIDENCE_BUILD / "index.html").read_text(encoding="utf-8")

    assert 'data-url="/api///evidencemeta.json"' not in root_html
    assert 'data-url="/api/evidencemeta.json"' in root_html


def test_built_route_pages_do_not_emit_double_slash_metadata_paths() -> None:
    """In-scope route pages should never include malformed metadata API paths."""
    malformed_path = re.compile(r'data-url="/api//[^"]+/evidencemeta\.json"')

    for route in ROUTE_PAGES:
        html = (EVIDENCE_BUILD / route / "index.html").read_text(encoding="utf-8")
        assert f'data-url="/api/{route}/evidencemeta.json"' in html
        assert malformed_path.search(html) is None, f"malformed metadata API path found for {route}"


def test_route_contract_verifier_script_exists_with_required_checks() -> None:
    """Route contract verifier should be present with route + metadata validation contract."""
    source = ROUTE_CONTRACT_VERIFIER.read_text(encoding="utf-8")

    assert "--build-dir" in source
    assert "--routes" in source
    assert "evidencemeta.json" in source
    assert "/api//" in source
