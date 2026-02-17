"""Contract type mapping consistency checks for silver models."""

from __future__ import annotations

import csv
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_PATH = REPO_ROOT / "dbt" / "seeds" / "code_contract_type.csv"
SNAPSHOT_MODEL_PATH = REPO_ROOT / "dbt" / "models" / "silver" / "tenant_room_snapshot_daily.sql"
TENANT_ROOM_INFO_MODEL_PATH = (
    REPO_ROOT / "dbt" / "models" / "silver" / "tokyo_beta_tenant_room_info.sql"
)
STG_MOVINGS_MODEL_PATH = REPO_ROOT / "dbt" / "models" / "silver" / "stg_movings.sql"


def _seed_label_for_code(code: int) -> str:
    """Return the Japanese label from the seed for a contract type code."""
    with SEED_PATH.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if int(row["code"]) == code:
                return row["label_ja"]
    raise AssertionError(f"Contract type code {code} not found in {SEED_PATH}")


def _model_label_for_code(model_sql: str, code: int) -> str:
    """Extract Japanese CASE label from SQL for a contract type code."""
    case_block = re.search(
        r"CASE\s+contract_type(.*?)END\s+as\s+contract_category",
        model_sql,
        re.DOTALL,
    )
    if not case_block:
        raise AssertionError("contract_type CASE block not found in model SQL")

    match = re.search(rf"WHEN\s+{code}\s+THEN\s+'([^']+)'", case_block.group(1))
    if not match:
        raise AssertionError(f"Code {code} CASE mapping not found in model SQL")
    return match.group(1)


def test_snapshot_contract_type_code_6_matches_seed_label() -> None:
    """Code 6 must match seed label (定期契約)."""
    expected = _seed_label_for_code(6)
    model_sql = SNAPSHOT_MODEL_PATH.read_text(encoding="utf-8")
    actual = _model_label_for_code(model_sql, 6)

    assert actual == expected


def test_tenant_room_info_contract_type_code_6_matches_seed_label() -> None:
    """Code 6 must match seed label (定期契約)."""
    expected = _seed_label_for_code(6)
    model_sql = TENANT_ROOM_INFO_MODEL_PATH.read_text(encoding="utf-8")
    actual = _model_label_for_code(model_sql, 6)

    assert actual == expected


def test_cancel_flag_filter_present_for_ui_parity_models() -> None:
    """Both tenant room models must exclude cancelled contracts."""
    expected_predicate = "COALESCE(m.cancel_flag, 0) = 0"
    snapshot_sql = SNAPSHOT_MODEL_PATH.read_text(encoding="utf-8")
    tenant_room_info_sql = TENANT_ROOM_INFO_MODEL_PATH.read_text(encoding="utf-8")

    assert expected_predicate in snapshot_sql
    assert expected_predicate in tenant_room_info_sql


def test_moveout_date_priority_matches_stg_movings() -> None:
    """Moveout priority must be integrated > plans > final_rent across models."""
    expected_pattern = (
        r"COALESCE\(\s*(?:m\.)?moveout_date_integrated\s*,\s*"
        r"(?:m\.)?moveout_plans_date\s*,\s*(?:m\.)?moveout_date\s*\)"
    )

    stg_movings_sql = STG_MOVINGS_MODEL_PATH.read_text(encoding="utf-8")
    snapshot_sql = SNAPSHOT_MODEL_PATH.read_text(encoding="utf-8")
    tenant_room_info_sql = TENANT_ROOM_INFO_MODEL_PATH.read_text(encoding="utf-8")

    assert re.search(expected_pattern, stg_movings_sql), "Reference pattern missing in stg_movings.sql"
    assert re.search(expected_pattern, snapshot_sql), (
        "tenant_room_snapshot_daily.sql has inconsistent moveout date priority"
    )
    assert re.search(expected_pattern, tenant_room_info_sql), (
        "tokyo_beta_tenant_room_info.sql has inconsistent moveout date priority"
    )
