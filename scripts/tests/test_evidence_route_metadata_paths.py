"""Regression tests for Evidence metadata route path normalization."""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYOUT_TEMPLATE = REPO_ROOT / "evidence/.evidence/template/src/pages/+layout.js"
EVIDENCE_BUILD = REPO_ROOT / "evidence/build"
ROUTE_PAGES = ("occupancy", "moveins", "moveouts", "geography", "pricing")


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
        assert malformed_path.search(html) is None, f"malformed metadata API path found for {route}"
