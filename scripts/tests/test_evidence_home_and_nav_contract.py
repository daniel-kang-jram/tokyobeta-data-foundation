"""Contract tests for Home KPI readability markers and navigation route hygiene."""

from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[2]
HOME_PAGE = REPO_ROOT / "evidence/pages/index.md"
AUTH_TEST_PAGE = REPO_ROOT / "evidence/pages/auth-test.md"
PAGES_DIR = REPO_ROOT / "evidence/pages"


def _read(path: Path) -> str:
    """Read UTF-8 text from a repository file."""
    return path.read_text(encoding="utf-8")


def test_home_kpi_line_charts_use_explicit_y_axis_bounds() -> None:
    """Home KPI trend charts should declare bounded y-axis ranges."""
    source = _read(HOME_PAGE)

    section_match = re.search(
        r"## KPI Trends \(Month-end\)(.*?)## KPI Governance & Trace", source, flags=re.DOTALL
    )
    assert section_match, "KPI trends section markers are missing"

    chart_blocks = re.findall(r"<LineChart\b.*?/>", section_match.group(1), flags=re.DOTALL)
    assert len(chart_blocks) >= 3, "Expected three KPI trend charts"

    for chart in chart_blocks[:3]:
        assert "yMin=" in chart, "KPI trend chart is missing explicit yMin"
        assert "yMax=" in chart, "KPI trend chart is missing explicit yMax"


def test_home_kpi_section_includes_time_coverage_and_freshness_markers() -> None:
    """Home page should expose explicit time basis, coverage window, and freshness labels."""
    source = _read(HOME_PAGE)

    assert "Time basis:" in source
    assert "Coverage:" in source
    assert "Freshness:" in source
    assert re.search(r"Coverage:\s*\{[^}]+\}\s*to\s*\{[^}]+\}", source), (
        "Coverage marker must include explicit from/to query-backed values"
    )


def test_auth_test_route_source_is_removed_from_pages_contract() -> None:
    """Auth test route source must be absent from Evidence pages."""
    page_stems = {path.stem for path in PAGES_DIR.glob("*.md")}

    assert not AUTH_TEST_PAGE.exists()
    assert "auth-test" not in page_stems
