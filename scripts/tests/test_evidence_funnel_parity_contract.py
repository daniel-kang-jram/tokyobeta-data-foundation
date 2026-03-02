"""Contract tests for funnel/pricing parity and timestamp clarity."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FUNNEL_PAGE = REPO_ROOT / "evidence/pages/funnel.md"
PRICING_PAGE = REPO_ROOT / "evidence/pages/pricing.md"

DAILY_SOURCE = (
    REPO_ROOT / "evidence/sources/aurora_gold/funnel_application_to_movein_daily.sql"
)
PERIODIZED_SOURCE = (
    REPO_ROOT / "evidence/sources/aurora_gold/funnel_application_to_movein_periodized.sql"
)
SEGMENT_SHARE_SOURCE = (
    REPO_ROOT / "evidence/sources/aurora_gold/funnel_application_to_movein_segment_share.sql"
)
FUNNEL_SOURCES = (DAILY_SOURCE, PERIODIZED_SOURCE, SEGMENT_SHARE_SOURCE)

REQUIRED_FUNNEL_PARITY_MARKERS = (
    "Overall Conversion Rate (%)",
    "Municipality Segment Parity (Applications vs Move-ins)",
    "Nationality Segment Parity (Applications vs Move-ins)",
    "Monthly Conversion Trend",
)


def _read(path: Path) -> str:
    """Read UTF-8 text from a repository file."""
    return path.read_text(encoding="utf-8")


def test_funnel_sources_use_data_max_anchored_windows() -> None:
    """Funnel source contracts must anchor windows to dataset max date."""
    for source_path in FUNNEL_SOURCES:
        source = _read(source_path).lower()

        assert "current_date" not in source, f"wall-clock filter found in {source_path}"
        assert "curdate()" not in source, f"wall-clock filter found in {source_path}"
        assert "data_max" in source, f"data_max anchor missing in {source_path}"
        assert "max(" in source, f"max-date anchor missing in {source_path}"
        assert "date_sub(" in source, f"anchored lookback missing in {source_path}"


def test_funnel_page_contains_moveout_to_movein_snapshot_parity_section() -> None:
    """Funnel page must contain a gold-backed moveout->move-in parity section."""
    source = _read(FUNNEL_PAGE)

    assert "Moveout -> Move-in Snapshot Parity" in source
    assert "from aurora_gold.moveout_analysis_recent" in source
    assert "from aurora_gold.movein_analysis_recent" in source


def test_funnel_and_pricing_pages_include_timestamp_clarity_markers() -> None:
    """Funnel and pricing routes must expose explicit time context markers."""
    for page_path in (FUNNEL_PAGE, PRICING_PAGE):
        source = _read(page_path)

        assert "Time basis:" in source, f"missing Time basis marker in {page_path}"
        assert "Coverage:" in source, f"missing Coverage marker in {page_path}"
        assert "Freshness:" in source, f"missing Freshness marker in {page_path}"


def test_funnel_and_pricing_pages_keep_required_funnel_parity_markers() -> None:
    """Release funnel markers must remain deterministic on both pricing and funnel routes."""
    funnel_source = _read(FUNNEL_PAGE)
    pricing_source = _read(PRICING_PAGE)

    for marker in REQUIRED_FUNNEL_PARITY_MARKERS:
        assert marker in pricing_source
        assert marker in funnel_source
