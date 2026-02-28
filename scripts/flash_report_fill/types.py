from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class QuerySpec:
    """SQL specification for a single metric query."""

    metric_id: str
    sql: str
    source_layer: str
    result_mode: str  # scalar | split
    value_column: str = "value"
    type_column: str = "tenant_type"
    query_tag: str = ""


@dataclass(frozen=True)
class MetricRecord:
    """One metric row written to metrics CSV output."""

    metric_id: str
    sheet: str
    cell: str
    value: int
    month: str
    tenant_type: str
    window_start: str
    window_end: str
    asof_ts_jst: str
    source_layer: str
    query_tag: str
    query_sql: str


@dataclass(frozen=True)
class ReconciliationRecord:
    """One reconciliation row comparing output against silver/gold references."""

    reconciliation_id: str
    expected_value: int
    reference_value: int
    delta: int
    reference_source: str
    note: str
    asof_date: str


@dataclass(frozen=True)
class WarningRecord:
    """One warning entry emitted to console and optional logs."""

    code: str
    message: str
    count: int


@dataclass(frozen=True)
class RunContext:
    """Normalized runtime timestamps used in queries and output metadata."""

    snapshot_start_jst: datetime
    snapshot_asof_jst: datetime
    feb_end_jst: datetime
    mar_start_jst: datetime
    mar_end_jst: datetime
