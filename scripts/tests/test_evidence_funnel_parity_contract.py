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

REMOVED_FUNNEL_BREAKDOWN_MARKERS = (
    "Municipality Segment Parity (Applications vs Move-ins)",
    "Nationality Segment Parity (Applications vs Move-ins)",
    "Monthly Conversion Trend",
)

REQUIRED_REPLACEMENT_FLOW_MARKERS = (
    "Killer Chart: Replacement Failure Flow",
    "```sql replacement_flow_sankey",
    "```sql replacement_flow_summary",
    "type: 'sankey'",
    "d.link_type === 'out'",
    "d.link_type === 'in'",
    "Move-out planned flow (red)",
    "Move-in planned flow (green)",
)

REQUIRED_REPLACEMENT_FLOW_DIMENSIONS = (
    "municipality",
    "nationality",
    "tenant_type",
    "rent_band",
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


def test_funnel_page_contains_killer_replacement_flow_contract() -> None:
    """Funnel page must include deterministic replacement-flow chart contracts."""
    source = _read(FUNNEL_PAGE)

    for marker in REQUIRED_REPLACEMENT_FLOW_MARKERS:
        assert marker in source


def test_funnel_and_pricing_pages_include_timestamp_clarity_markers() -> None:
    """Funnel and pricing routes must expose explicit time context markers."""
    for page_path in (FUNNEL_PAGE, PRICING_PAGE):
        source = _read(page_path)

        assert "Time basis:" in source, f"missing Time basis marker in {page_path}"
        assert "Coverage:" in source, f"missing Coverage marker in {page_path}"
        assert "Freshness:" in source, f"missing Freshness marker in {page_path}"
        assert "Coverage: {" in source, f"Coverage must be query-backed in {page_path}"
        assert "Freshness: {" in source, f"Freshness must be query-backed in {page_path}"


def test_funnel_replacement_flow_preserves_municipality_nationality_and_cohort_dimensions() -> None:
    """Replacement-flow contracts must keep municipality/nationality/tenant_type dimensions."""
    funnel_source = _read(FUNNEL_PAGE)

    for marker in REQUIRED_REPLACEMENT_FLOW_DIMENSIONS:
        assert marker in funnel_source

    assert (
        "municipality || ' | ' || nationality || ' | ' || tenant_type || ' | ' || rent_band"
        in funnel_source
    )


def test_funnel_breakdown_markers_are_removed_but_pricing_parity_markers_stay() -> None:
    """Low-signal breakdown markers should be removed from funnel only."""
    funnel_source = _read(FUNNEL_PAGE)
    pricing_source = _read(PRICING_PAGE)

    for marker in REMOVED_FUNNEL_BREAKDOWN_MARKERS:
        assert marker not in funnel_source
        assert marker in pricing_source

    for marker in REQUIRED_FUNNEL_PARITY_MARKERS:
        assert marker in pricing_source
