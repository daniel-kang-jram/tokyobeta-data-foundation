"""Contract tests for chart ergonomics on geography and pricing routes."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GEOGRAPHY_PAGE = REPO_ROOT / "evidence/pages/geography.md"
PRICING_PAGE = REPO_ROOT / "evidence/pages/pricing.md"
MOVEINS_PAGE = REPO_ROOT / "evidence/pages/moveins.md"
MOVEOUTS_PAGE = REPO_ROOT / "evidence/pages/moveouts.md"

ERGONOMIC_MAX_HEIGHT = 420
PRICING_MAX_HEIGHT = 520

REQUIRED_ROUTE_MARKERS = (
    (GEOGRAPHY_PAGE, "Tokyo Occupancy Map (Latest Snapshot)"),
    (GEOGRAPHY_PAGE, "Municipality hotspots (weekly, last 12 weeks)"),
    (PRICING_PAGE, "Segment Pressure Ranking"),
)


def _read(path: Path) -> str:
    """Read UTF-8 text from a repository file."""
    return path.read_text(encoding="utf-8")


def _all_chart_heights(source: str) -> list[int]:
    """Extract chartAreaHeight values from page source."""
    return [int(match) for match in re.findall(r"chartAreaHeight=\{(\d+)\}", source)]


def _section_text(source: str, heading: str) -> str:
    """Return markdown section body for a heading."""
    pattern = re.compile(
        rf"^## {re.escape(heading)}\n(?P<section>.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(source)
    assert match is not None, f"missing section heading: {heading}"
    return match.group("section")


def test_geography_and_pricing_keep_route_markers_and_time_context_prefixes() -> None:
    """Geography/pricing pages must keep deterministic route + time-context markers."""
    for path, marker in REQUIRED_ROUTE_MARKERS:
        source = _read(path)
        assert marker in source, f"missing route marker `{marker}` in {path}"
        assert "Time basis:" in source, f"missing Time basis marker in {path}"
        assert "Coverage:" in source, f"missing Coverage marker in {path}"
        assert "Freshness:" in source, f"missing Freshness marker in {path}"


def test_geography_hotspot_chart_heights_are_compact() -> None:
    """Geography hotspot bars should not exceed the ergonomics height cap."""
    source = _read(GEOGRAPHY_PAGE)
    hotspot_headings = re.findall(
        r"^## (.*hotspots \(weekly, last 12 weeks\))$",
        source,
        flags=re.MULTILINE,
    )
    heights: list[int] = []
    for heading in hotspot_headings:
        section = _section_text(source, heading)
        heights.extend(_all_chart_heights(section))

    assert hotspot_headings, "no geography hotspot sections found"
    assert heights, "no chartAreaHeight values found in geography hotspot sections"
    assert 900 not in heights
    assert max(heights) <= ERGONOMIC_MAX_HEIGHT


def test_pricing_segment_pressure_ranking_height_is_compact() -> None:
    """Pricing segment pressure ranking chart should stay within ergonomics cap."""
    source = _read(PRICING_PAGE)
    section = _section_text(source, "Segment Pressure Ranking")
    heights = _all_chart_heights(section)

    assert heights, "missing chartAreaHeight in Segment Pressure Ranking section"
    assert 900 not in heights
    assert max(heights) <= PRICING_MAX_HEIGHT


def test_move_profile_segment_bar_heights_are_compact() -> None:
    """Move-ins/move-outs cohort segment bars should use tighter vertical footprint."""
    section_heading = "Cohort and Segment View (Last 12 Months)"

    for page in (MOVEINS_PAGE, MOVEOUTS_PAGE):
        source = _read(page)
        section = _section_text(source, section_heading)
        heights = _all_chart_heights(section)

        assert heights, f"missing chartAreaHeight values in {page.name} segment section"
        assert 900 not in heights
        assert max(heights) <= ERGONOMIC_MAX_HEIGHT
