"""Contract tests for geography occupancy parity and timestamp clarity."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GEOGRAPHY_PAGE = REPO_ROOT / "evidence/pages/geography.md"

REQUIRED_OCCUPANCY_FIELD_MARKERS = (
    "occupancy_rate_pct",
    "occupancy_rate_delta_7d_pp",
    "occupied_rooms_num0",
    "total_rooms_num0",
)
REQUIRED_ROUTE_HEADINGS = (
    "Tokyo Occupancy Map (Latest Snapshot)",
    "Municipality hotspots (weekly, last 12 weeks)",
    "Property hotspots (weekly, last 12 weeks)",
)


def _read(path: Path) -> str:
    """Read UTF-8 text from a repository file."""
    return path.read_text(encoding="utf-8")


def test_geography_map_uses_red_to_green_scalar_palette() -> None:
    """Geography map should use deterministic scalar red->green coloring."""
    source = _read(GEOGRAPHY_PAGE)

    assert 'legendType="scalar"' in source
    assert "colorPalette={['#b91c1c', '#f59e0b', '#22c55e']}" in source


def test_geography_page_includes_time_coverage_and_freshness_markers() -> None:
    """Geography page should expose explicit timestamp context markers."""
    source = _read(GEOGRAPHY_PAGE)

    assert "Time basis:" in source
    assert "Coverage:" in source
    assert "Freshness:" in source
    assert "Coverage: {" in source
    assert "Freshness: {" in source


def test_geography_page_references_corrected_occupancy_metric_fields() -> None:
    """Geography page should keep occupancy metric fields required by parity contracts."""
    source = _read(GEOGRAPHY_PAGE)

    for marker in REQUIRED_OCCUPANCY_FIELD_MARKERS:
        assert marker in source


def test_geography_page_keeps_route_heading_markers() -> None:
    """Route heading markers should remain deterministic for smoke checks."""
    source = _read(GEOGRAPHY_PAGE)

    for heading in REQUIRED_ROUTE_HEADINGS:
        assert heading in source
