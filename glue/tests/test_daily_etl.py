import pathlib
import json
import subprocess
import sys
import pytest
from datetime import date, timedelta, datetime
from unittest.mock import Mock


SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.append(str(SCRIPTS_DIR))

import daily_etl  # noqa: E402


def test_iter_sql_statements_preserves_inline_data():
    lines = [
        "-- comment line\n",
        "SET NAMES utf8mb4;\n",
        "CREATE TABLE apartments (id int);\n",
        "INSERT INTO apartments VALUES (1, 'TOKYO -- B');\n",
    ]

    statements = daily_etl.iter_sql_statements(lines)

    assert len(statements) == 2
    assert statements[0].startswith("CREATE TABLE apartments")
    assert "TOKYO -- B" in statements[1]


def test_iter_sql_statements_skips_block_comments():
    lines = [
        "/* block comment start\n",
        "still comment */\n",
        "INSERT INTO apartments VALUES (2, 'TOKYO β 新井薬師前2');\n",
    ]

    statements = daily_etl.iter_sql_statements(lines)

    assert len(statements) == 1
    assert "INSERT INTO apartments" in statements[0]


def test_get_processed_dump_key_maps_dump_prefixes():
    assert daily_etl.get_processed_dump_key("dumps/gghouse_20260213.sql") == "processed/gghouse_20260213.sql"
    assert (
        daily_etl.get_processed_dump_key("raw/dumps/gghouse_20260213.sql.gz")
        == "raw/processed/gghouse_20260213.sql.gz"
    )
    assert daily_etl.get_processed_dump_key("gghouse_20260213.sql") == "processed/gghouse_20260213.sql"


def test_extract_dump_date_from_key_parses_sql_and_gz():
    assert daily_etl.extract_dump_date_from_key("dumps/gghouse_20260214.sql") == date(2026, 2, 14)
    assert daily_etl.extract_dump_date_from_key("raw/dumps/gghouse_20260214.sql.gz") == date(2026, 2, 14)
    assert daily_etl.extract_dump_date_from_key("gghouse_20260214.sql") == date(2026, 2, 14)
    assert daily_etl.extract_dump_date_from_key("dumps/not_a_dump.sql") is None


def test_get_latest_dump_key_selects_by_modified_date(monkeypatch):
    mock_s3 = Mock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "dumps/gghouse_20260205.sql", "LastModified": datetime(2026, 2, 5)},
            {"Key": "dumps/gghouse_20260207.sql", "LastModified": datetime(2026, 2, 7)},
            {"Key": "dumps/gghouse_20260206.sql", "LastModified": datetime(2026, 2, 6)},
        ]
    }
    monkeypatch.setattr(daily_etl, "s3", mock_s3)
    monkeypatch.setitem(daily_etl.args, "S3_SOURCE_BUCKET", "test-bucket")
    monkeypatch.setitem(daily_etl.args, "S3_SOURCE_PREFIX", "dumps/")

    assert daily_etl.get_latest_dump_key() == "dumps/gghouse_20260207.sql"
    mock_s3.list_objects_v2.assert_called_once_with(
        Bucket="test-bucket",
        Prefix="dumps/"
    )


def test_get_aurora_credentials_reads_legacy_and_standard_secret_keys(monkeypatch):
    daily_etl._AURORA_CREDENTIALS = None
    mock_sm = Mock()
    mock_sm.get_secret_value.return_value = {"SecretString": json.dumps({
        "username": "admin",
        "password": "secret-pass"
    })}

    creds = daily_etl.get_aurora_credentials(mock_sm, "secret-arn")

    assert creds == ("admin", "secret-pass")
    mock_sm.get_secret_value.assert_called_once_with(SecretId="secret-arn")


def test_get_aurora_credentials_falls_back_to_previous_version_if_current_invalid(monkeypatch):
    daily_etl._AURORA_CREDENTIALS = None
    mock_sm = Mock()
    mock_sm.get_secret_value.side_effect = [
        {"SecretString": json.dumps({"username": "admin"})},
        {"SecretString": json.dumps({"username": "admin", "password": "previous-pass"})},
    ]

    creds = daily_etl.get_aurora_credentials(mock_sm, "secret-arn")

    assert creds == ("admin", "previous-pass")
    assert mock_sm.get_secret_value.call_count == 2
    assert mock_sm.get_secret_value.call_args_list[0] == (({"SecretId": "secret-arn"},))


def test_get_aurora_credentials_uses_valid_next_stage_when_current_password_blank(monkeypatch):
    daily_etl._AURORA_CREDENTIALS = None
    mock_sm = Mock()
    mock_sm.get_secret_value.side_effect = [
        {"SecretString": json.dumps({"username": "admin", "password": "   "})},
        {"SecretString": json.dumps({"username": "admin", "password": "current-pass"})},
    ]

    creds = daily_etl.get_aurora_credentials(mock_sm, "secret-arn")

    assert creds == ("admin", "current-pass")
    assert mock_sm.get_secret_value.call_count == 2


def test_get_aurora_credentials_raises_when_no_password_available(monkeypatch):
    daily_etl._AURORA_CREDENTIALS = None
    mock_sm = Mock()
    mock_sm.get_secret_value.return_value = {"SecretString": json.dumps({"username": "admin"})}

    with pytest.raises(RuntimeError, match="Failed to resolve Aurora credentials"):
        daily_etl.get_aurora_credentials(mock_sm, "secret-arn")


def test_create_aurora_connection_raises_on_empty_password(monkeypatch):
    daily_etl._AURORA_CREDENTIALS = None
    monkeypatch.setattr(daily_etl, "get_aurora_credentials", lambda: ("admin", ""))
    monkeypatch.setitem(daily_etl.args, "AURORA_SECRET_ARN", "arn:secret:test")

    with pytest.raises(RuntimeError, match="Empty Aurora password"):
        daily_etl.create_aurora_connection()


def test_recoverable_dbt_hook_auth_error_detected():
    output = """
Completed with 1 error and 0 warnings:
  on-run-end failed, error:
 1045 (28000): Access denied for user 'admin'@'10.0.10.213' (using password: YES)
Done. PASS=24 WARN=0 ERROR=1 SKIP=0 TOTAL=25
"""
    assert daily_etl.is_recoverable_dbt_hook_auth_error(output) is True


def test_recoverable_dbt_hook_auth_error_not_detected_for_model_failure():
    output = """
Completed with 1 error and 0 warnings:
  Database Error in model silver.tenant_status_history (models/silver/tenant_status_history.sql)
  1205 (HY000): Lock wait timeout exceeded; try restarting transaction
Done. PASS=23 WARN=0 ERROR=1 SKIP=0 TOTAL=24
"""
    assert daily_etl.is_recoverable_dbt_hook_auth_error(output) is False


def test_list_dump_candidates_filters_and_sorts(monkeypatch):
    mock_s3 = Mock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "dumps/gghouse_20260213.sql", "LastModified": datetime(2026, 2, 13)},
            {"Key": "dumps/gghouse_20260215.sql", "LastModified": datetime(2026, 2, 15)},
            {"Key": "dumps/gghouse_20260214.sql.gz", "LastModified": datetime(2026, 2, 14)},
            {"Key": "dumps/notes.txt", "LastModified": datetime(2026, 2, 16)},
        ]
    }
    monkeypatch.setattr(daily_etl, "s3", mock_s3)
    monkeypatch.setitem(daily_etl.args, "S3_SOURCE_BUCKET", "test-bucket")
    monkeypatch.setitem(daily_etl.args, "S3_SOURCE_PREFIX", "dumps/")

    candidates = daily_etl.list_dump_candidates()

    assert [f["Key"] for f in candidates] == [
        "dumps/gghouse_20260215.sql",
        "dumps/gghouse_20260214.sql.gz",
        "dumps/gghouse_20260213.sql",
    ]


def test_validate_dump_freshness_passes_within_tolerance():
    daily_etl.validate_dump_freshness(
        "dumps/gghouse_20260214.sql",
        date(2026, 2, 14),
        date(2026, 2, 15),
        max_stale_days=1,
    )


def test_validate_dump_freshness_fails_if_too_stale():
    with pytest.raises(
        ValueError,
        match="Dump freshness check failed: latest dump date=2026-02-14 is 2 day\\(s\\) older"
    ):
        daily_etl.validate_dump_freshness(
            "dumps/gghouse_20260214.sql",
            date(2026, 2, 14),
            date(2026, 2, 16),
            max_stale_days=1,
        )


def test_validate_dump_freshness_fails_without_parseable_date():
    with pytest.raises(ValueError, match="Could not extract date"):
        daily_etl.validate_dump_freshness(
            "dumps/unknown_backup.sql",
            None,
            date(2026, 2, 16),
            max_stale_days=1,
        )


def test_validate_dump_continuity_passes_when_window_is_complete():
    daily_etl.validate_dump_continuity(
        available_dump_dates={
            date(2026, 2, 16),
            date(2026, 2, 15),
            date(2026, 2, 14),
        },
        expected_date=date(2026, 2, 16),
        max_stale_days=2,
    )


def test_validate_dump_continuity_fails_when_expected_dates_missing():
    with pytest.raises(
        ValueError,
        match="Dump continuity check failed: missing dump file\\(s\\) for date\\(s\\): 2026-02-16",
    ):
        daily_etl.validate_dump_continuity(
            available_dump_dates={date(2026, 2, 15)},
            expected_date=date(2026, 2, 16),
            max_stale_days=1,
        )


def test_validate_dump_continuity_fails_when_multiple_dates_missing():
    with pytest.raises(
        ValueError,
        match="Dump continuity check failed: missing dump file\\(s\\) for date\\(s\\): 2026-02-16, 2026-02-15",
    ):
        daily_etl.validate_dump_continuity(
            available_dump_dates={date(2026, 2, 14)},
            expected_date=date(2026, 2, 16),
            max_stale_days=2,
        )


def test_check_dump_continuity_warns_when_strict_disabled(capsys):
    """Continuity gaps should not block the run when strict mode is disabled."""
    missing = daily_etl.check_dump_continuity(
        available_dump_dates={date(2026, 2, 16), date(2026, 2, 14)},
        expected_date=date(2026, 2, 16),
        max_stale_days=2,
        strict=False,
    )
    assert missing == [date(2026, 2, 15)]

    out = capsys.readouterr().out
    assert "WARN" in out
    assert "2026-02-15" in out


def test_runtime_date_reads_valid_env(monkeypatch):
    monkeypatch.setenv("DAILY_TARGET_DATE", "2026-02-13")
    result = daily_etl.runtime_date("DAILY_TARGET_DATE", date(2026, 2, 1))
    assert result == date(2026, 2, 13)


def test_runtime_date_falls_back_on_invalid(monkeypatch):
    monkeypatch.setenv("DAILY_TARGET_DATE", "bad-date")
    result = daily_etl.runtime_date("DAILY_TARGET_DATE", date(2026, 2, 1))
    assert result == date(2026, 2, 1)


def test_runtime_int_reads_valid_env(monkeypatch):
    monkeypatch.setenv("DAILY_MAX_DUMP_STALE_DAYS", "0")
    result = daily_etl.runtime_int("DAILY_MAX_DUMP_STALE_DAYS", 1, minimum=0)
    assert result == 0


def test_runtime_int_reads_argv_when_env_missing(monkeypatch):
    monkeypatch.delenv("DAILY_MAX_DUMP_STALE_DAYS", raising=False)
    monkeypatch.setattr(
        daily_etl,
        "optional_argv_value",
        lambda name: "2" if name == "DAILY_MAX_DUMP_STALE_DAYS" else None,
    )
    result = daily_etl.runtime_int("DAILY_MAX_DUMP_STALE_DAYS", 1, minimum=0)
    assert result == 2


def test_runtime_int_enforces_minimum(monkeypatch):
    monkeypatch.delenv("DAILY_MAX_DUMP_STALE_DAYS", raising=False)
    monkeypatch.setattr(
        daily_etl,
        "optional_argv_value",
        lambda name: "-5" if name == "DAILY_MAX_DUMP_STALE_DAYS" else None,
    )
    result = daily_etl.runtime_int("DAILY_MAX_DUMP_STALE_DAYS", 1, minimum=0)
    assert result == 0


def test_run_dbt_transformations_pre_phase_then_main_phase(monkeypatch):
    calls = []

    monkeypatch.setattr(daily_etl, "get_aurora_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(daily_etl, "cleanup_dbt_tmp_tables", lambda: 0)
    monkeypatch.setitem(daily_etl.args, "S3_SOURCE_BUCKET", "unit-test-bucket")
    monkeypatch.setitem(daily_etl.args, "AURORA_ENDPOINT", "test.cluster.amazonaws.com")
    monkeypatch.setitem(daily_etl.args, "ENVIRONMENT", "prod")
    monkeypatch.setenv("DBT_EXCLUDE_MODELS", "")
    monkeypatch.setenv("DBT_PRE_RUN_MODELS", "silver.tenant_room_snapshot_daily")
    monkeypatch.setenv("DBT_POST_RUN_MODELS", "silver.tenant_status_history")
    monkeypatch.setenv("DAILY_TARGET_DATE", "2026-02-14")
    monkeypatch.setenv("DAILY_RUN_DBT_TESTS", "false")

    def fake_run(cmd, check=False, capture_output=False, text=False):
        calls.append(cmd)
        if check:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[1] == "seed":
            return subprocess.CompletedProcess(cmd, 0, "seed ok", "")
        if cmd[1] == "run" and "--select" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "pre run ok", "")
        if cmd[1] == "run":
            return subprocess.CompletedProcess(cmd, 0, "main run ok", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(daily_etl.subprocess, "run", fake_run)

    assert daily_etl.run_dbt_transformations() is True

    run_commands = [cmd for cmd in calls if len(cmd) > 1 and cmd[0].endswith("/dbt") and cmd[1] == "run"]
    assert len(run_commands) == 3

    pre_phase = run_commands[0]
    assert "--threads" in pre_phase
    assert "1" in pre_phase
    assert "--select" in pre_phase
    assert "silver.tenant_room_snapshot_daily" in pre_phase

    main_phase = run_commands[1]
    assert "--exclude" in main_phase
    assert "silver.tenant_room_snapshot_daily" in main_phase
    assert "silver.tenant_status_history" in main_phase

    post_phase = run_commands[2]
    assert "--threads" in post_phase
    assert "1" in post_phase
    assert "--select" in post_phase
    assert "silver.tenant_status_history" in post_phase
    assert "--vars" in pre_phase
    assert "--vars" in main_phase
    assert "--vars" in post_phase
    assert "daily_snapshot_date" in " ".join(pre_phase)
    assert "2026-02-14" in " ".join(pre_phase)


def test_run_dbt_transformations_default_skips_post_run(monkeypatch):
    calls = []

    monkeypatch.setattr(daily_etl, "get_aurora_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(daily_etl, "cleanup_dbt_tmp_tables", lambda: 0)
    monkeypatch.setitem(daily_etl.args, "S3_SOURCE_BUCKET", "unit-test-bucket")
    monkeypatch.setitem(daily_etl.args, "AURORA_ENDPOINT", "test.cluster.amazonaws.com")
    monkeypatch.setitem(daily_etl.args, "ENVIRONMENT", "prod")
    monkeypatch.setenv("DBT_EXCLUDE_MODELS", "")
    monkeypatch.setenv("DBT_PRE_RUN_MODELS", "silver.tenant_room_snapshot_daily")
    monkeypatch.delenv("DBT_POST_RUN_MODELS", raising=False)
    monkeypatch.setenv("DAILY_TARGET_DATE", "2026-02-14")
    monkeypatch.setenv("DAILY_RUN_DBT_TESTS", "false")

    def fake_run(cmd, check=False, capture_output=False, text=False):
        calls.append(cmd)
        if check:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    monkeypatch.setattr(daily_etl.subprocess, "run", fake_run)

    assert daily_etl.run_dbt_transformations() is True

    run_commands = [cmd for cmd in calls if len(cmd) > 1 and cmd[0].endswith("/dbt") and cmd[1] == "run"]
    assert len(run_commands) == 2
    assert "--vars" in run_commands[0]
    assert "2026-02-14" in " ".join(run_commands[0])


def test_run_dbt_transformations_retries_lock_wait(monkeypatch):
    calls = []
    pre_attempts = {"count": 0}
    cleanup_mock = Mock(return_value=1)

    monkeypatch.setattr(daily_etl, "get_aurora_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(daily_etl, "cleanup_dbt_tmp_tables", cleanup_mock)
    monkeypatch.setattr(daily_etl.time, "sleep", lambda *_: None)
    monkeypatch.setitem(daily_etl.args, "S3_SOURCE_BUCKET", "unit-test-bucket")
    monkeypatch.setitem(daily_etl.args, "AURORA_ENDPOINT", "test.cluster.amazonaws.com")
    monkeypatch.setitem(daily_etl.args, "ENVIRONMENT", "prod")
    monkeypatch.setenv("DBT_EXCLUDE_MODELS", "silver.tenant_status_history")
    monkeypatch.setenv("DBT_PRE_RUN_MODELS", "silver.tenant_room_snapshot_daily")
    monkeypatch.setenv("DBT_POST_RUN_MODELS", "")
    monkeypatch.setenv("DBT_PRE_RUN_RETRIES", "2")
    monkeypatch.setenv("DBT_PRE_RUN_RETRY_SLEEP_SECONDS", "0")
    monkeypatch.setenv("DAILY_TARGET_DATE", "2026-02-14")
    monkeypatch.setenv("DAILY_RUN_DBT_TESTS", "false")

    def fake_run(cmd, check=False, capture_output=False, text=False):
        calls.append(cmd)
        if check:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[1] == "seed":
            return subprocess.CompletedProcess(cmd, 0, "seed ok", "")
        if cmd[1] == "run" and "--select" in cmd:
            pre_attempts["count"] += 1
            if pre_attempts["count"] == 1:
                return subprocess.CompletedProcess(cmd, 1, "", "1205 (HY000): Lock wait timeout exceeded")
            return subprocess.CompletedProcess(cmd, 0, "pre run ok", "")
        if cmd[1] == "run":
            return subprocess.CompletedProcess(cmd, 0, "main run ok", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(daily_etl.subprocess, "run", fake_run)

    assert daily_etl.run_dbt_transformations() is True
    assert pre_attempts["count"] == 2
    cleanup_mock.assert_called_once()


def test_reset_staging_tables_drops_existing(monkeypatch):
    cursor = Mock()
    cursor.fetchall.return_value = [("tenants",), ("rooms",)]

    dropped = daily_etl.reset_staging_tables(cursor)

    assert dropped == 2
    executed_sql = [call.args[0] for call in cursor.execute.call_args_list]
    assert any("FROM information_schema.tables" in sql for sql in executed_sql)
    assert "SET FOREIGN_KEY_CHECKS = 0" in executed_sql
    assert "DROP TABLE IF EXISTS `staging`.`tenants`" in executed_sql
    assert "DROP TABLE IF EXISTS `staging`.`rooms`" in executed_sql
    assert "SET FOREIGN_KEY_CHECKS = 1" in executed_sql


def test_compute_occupancy_kpis_for_dates_future_projection_continues_from_previous_day(monkeypatch):
    """Future KPI rows should chain from prior day period_end_rooms (not reset to 0 after as-of+1)."""

    class FakeCursor:
        def __init__(self):
            self.as_of_snapshot_date = date(2026, 2, 13)
            self.snapshot_exists = {date(2026, 2, 13)}
            self.occupied_counts = {
                date(2026, 2, 12): 10_000,
                date(2026, 2, 13): 10_005,
                # No silver snapshot exists for future dates; treat as 0.
                date(2026, 2, 14): 0,
            }
            self.applications = {date(2026, 2, 13): 1}
            self.moveins = {
                date(2026, 2, 13): 10,
                date(2026, 2, 14): 7,
                date(2026, 2, 15): 3,
            }
            self.moveouts = {
                date(2026, 2, 13): 5,
                date(2026, 2, 14): 2,
                date(2026, 2, 15): 4,
            }

            self.inserted_rows = {}
            self._gold_period_end_rooms = {}
            self._next_fetchone = None

        def execute(self, sql, params=None):
            sql_compact = " ".join(sql.split())
            params = params or ()

            if "SELECT MAX(snapshot_date) AS max_snapshot_date" in sql_compact:
                self._next_fetchone = {"max_snapshot_date": self.as_of_snapshot_date}
                return

            if "SELECT 1 FROM silver.tenant_room_snapshot_daily" in sql_compact and "LIMIT 1" in sql_compact:
                snapshot_date = params[0]
                self._next_fetchone = ({"1": 1} if snapshot_date in self.snapshot_exists else None)
                return

            if "first_apps" in sql_compact:
                target_date = params[0]
                self._next_fetchone = {"count": self.applications.get(target_date, 0)}
                return

            if "AND move_in_date = %s" in sql_compact:
                target_date = params[1]
                self._next_fetchone = {"count": self.moveins.get(target_date, 0)}
                return

            if "AND moveout_plans_date = %s" in sql_compact:
                target_date = params[1]
                self._next_fetchone = {"count": self.moveouts.get(target_date, 0)}
                return

            if "AND moveout_date = %s" in sql_compact:
                target_date = params[1]
                self._next_fetchone = {"count": self.moveouts.get(target_date, 0)}
                return

            if (
                "FROM silver.tenant_room_snapshot_daily" in sql_compact
                and "management_status_code IN (4,5,6,7,9,10,11,12,13,14,15)" in sql_compact
            ):
                snapshot_date = params[0]
                self._next_fetchone = {"count": self.occupied_counts.get(snapshot_date, 0)}
                return

            if (
                "FROM gold.occupancy_daily_metrics" in sql_compact
                and "SELECT period_end_rooms" in sql_compact
            ):
                snapshot_date = params[0]
                period_end_rooms = self._gold_period_end_rooms.get(snapshot_date)
                self._next_fetchone = (
                    {"period_end_rooms": period_end_rooms} if period_end_rooms is not None else None
                )
                return

            if sql_compact.startswith("INSERT INTO gold.occupancy_daily_metrics"):
                (
                    snapshot_date,
                    applications,
                    new_moveins,
                    new_moveouts,
                    occupancy_delta,
                    period_start_rooms,
                    period_end_rooms,
                    occupancy_rate,
                ) = params
                self._gold_period_end_rooms[snapshot_date] = period_end_rooms
                self.inserted_rows[snapshot_date] = {
                    "snapshot_date": snapshot_date,
                    "applications": applications,
                    "new_moveins": new_moveins,
                    "new_moveouts": new_moveouts,
                    "occupancy_delta": occupancy_delta,
                    "period_start_rooms": period_start_rooms,
                    "period_end_rooms": period_end_rooms,
                    "occupancy_rate": occupancy_rate,
                }
                self._next_fetchone = None
                return

            raise AssertionError(f"Unexpected SQL executed: {sql_compact!r} params={params!r}")

        def fetchone(self):
            result = self._next_fetchone
            self._next_fetchone = None
            return result

    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 2, 14)

    monkeypatch.setattr(daily_etl, "date", FixedDate)

    cursor = FakeCursor()
    as_of = cursor.as_of_snapshot_date
    dates = [as_of, as_of + timedelta(days=1), as_of + timedelta(days=2)]

    processed = daily_etl.compute_occupancy_kpis_for_dates(cursor, dates)

    assert processed == 3
    assert cursor.inserted_rows[as_of + timedelta(days=1)]["period_end_rooms"] == 10_010
    # Critical: projection must continue from prior day's computed KPI (not reset to 0).
    assert (
        cursor.inserted_rows[as_of + timedelta(days=2)]["period_start_rooms"]
        == cursor.inserted_rows[as_of + timedelta(days=1)]["period_end_rooms"]
    )
    assert cursor.inserted_rows[as_of + timedelta(days=2)]["period_end_rooms"] == 10_009
    assert cursor.inserted_rows[as_of + timedelta(days=2)]["occupancy_rate"] > 0.6


def test_compute_occupancy_kpis_fact_day_uses_same_day_end_rooms_even_if_previous_day_missing(monkeypatch):
    """If the previous day's snapshot is missing, fact-day KPI should still be correct."""

    class FakeCursor:
        def __init__(self):
            self.as_of_snapshot_date = date(2026, 2, 16)
            self.snapshot_exists = {date(2026, 2, 16)}
            self.occupied_on_date = {date(2026, 2, 16): 10_005}
            self.applications = {date(2026, 2, 16): 2}
            self.moveins = {date(2026, 2, 16): 10}
            self.moveouts = {date(2026, 2, 16): 5}
            self.inserted_rows = {}
            self._next_fetchone = None

        def execute(self, sql, params=None):
            sql_compact = " ".join(sql.split())
            params = params or ()

            if "SELECT MAX(snapshot_date) AS max_snapshot_date" in sql_compact:
                self._next_fetchone = {"max_snapshot_date": self.as_of_snapshot_date}
                return

            if "SELECT 1 FROM silver.tenant_room_snapshot_daily" in sql_compact and "LIMIT 1" in sql_compact:
                snapshot_date = params[0]
                self._next_fetchone = ({"1": 1} if snapshot_date in self.snapshot_exists else None)
                return

            if "first_apps" in sql_compact:
                target_date = params[0]
                self._next_fetchone = {"count": self.applications.get(target_date, 0)}
                return

            if "AND move_in_date = %s" in sql_compact:
                target_date = params[1]
                self._next_fetchone = {"count": self.moveins.get(target_date, 0)}
                return

            if "AND moveout_plans_date = %s" in sql_compact:
                target_date = params[1]
                self._next_fetchone = {"count": self.moveouts.get(target_date, 0)}
                return

            if (
                "FROM silver.tenant_room_snapshot_daily" in sql_compact
                and "management_status_code IN (4,5,6,7,9,10,11,12,13,14,15)" in sql_compact
                and "snapshot_date = %s" in sql_compact
            ):
                snapshot_date = params[0]
                self._next_fetchone = {"count": self.occupied_on_date.get(snapshot_date, 0)}
                return

            if sql_compact.startswith("INSERT INTO gold.occupancy_daily_metrics"):
                (
                    snapshot_date,
                    applications,
                    new_moveins,
                    new_moveouts,
                    occupancy_delta,
                    period_start_rooms,
                    period_end_rooms,
                    occupancy_rate,
                ) = params
                self.inserted_rows[snapshot_date] = {
                    "snapshot_date": snapshot_date,
                    "applications": applications,
                    "new_moveins": new_moveins,
                    "new_moveouts": new_moveouts,
                    "occupancy_delta": occupancy_delta,
                    "period_start_rooms": period_start_rooms,
                    "period_end_rooms": period_end_rooms,
                    "occupancy_rate": occupancy_rate,
                }
                self._next_fetchone = None
                return

            raise AssertionError(f"Unexpected SQL executed: {sql_compact!r} params={params!r}")

        def fetchone(self):
            result = self._next_fetchone
            self._next_fetchone = None
            return result

    cursor = FakeCursor()
    processed = daily_etl.compute_occupancy_kpis_for_dates(cursor, [date(2026, 2, 16)])

    assert processed == 1
    assert cursor.inserted_rows[date(2026, 2, 16)]["period_end_rooms"] == 10_005
    # delta=+5 so start should be 10000
    assert cursor.inserted_rows[date(2026, 2, 16)]["period_start_rooms"] == 10_000
    assert cursor.inserted_rows[date(2026, 2, 16)]["occupancy_rate"] > 0.6


def test_compute_occupancy_kpis_forward_fills_missing_fact_day_from_next_snapshot(capsys, monkeypatch):
    """Missing fact-day snapshots should be forward-filled from the next available snapshot to avoid 0% spikes."""

    class FakeCursor:
        def __init__(self):
            self.as_of_snapshot_date = date(2026, 2, 16)
            self.snapshot_exists = {date(2026, 2, 16)}
            self.occupied_on_date = {date(2026, 2, 16): 10_005}
            self.inserted_rows = {}
            self._next_fetchone = None

        def execute(self, sql, params=None):
            sql_compact = " ".join(sql.split())
            params = params or ()

            if "SELECT MAX(snapshot_date) AS max_snapshot_date" in sql_compact:
                self._next_fetchone = {"max_snapshot_date": self.as_of_snapshot_date}
                return

            if "SELECT 1 FROM silver.tenant_room_snapshot_daily" in sql_compact and "LIMIT 1" in sql_compact:
                snapshot_date = params[0]
                self._next_fetchone = ({"1": 1} if snapshot_date in self.snapshot_exists else None)
                return

            if "SELECT MIN(snapshot_date) AS next_snapshot_date" in sql_compact:
                target_date = params[0]
                self._next_fetchone = (
                    {"next_snapshot_date": date(2026, 2, 16)} if target_date <= date(2026, 2, 16) else None
                )
                return

            if (
                "FROM silver.tenant_room_snapshot_daily" in sql_compact
                and "management_status_code IN (4,5,6,7,9,10,11,12,13,14,15)" in sql_compact
                and "snapshot_date = %s" in sql_compact
            ):
                snapshot_date = params[0]
                self._next_fetchone = {"count": self.occupied_on_date.get(snapshot_date, 0)}
                return

            if sql_compact.startswith("INSERT INTO gold.occupancy_daily_metrics"):
                (
                    snapshot_date,
                    applications,
                    new_moveins,
                    new_moveouts,
                    occupancy_delta,
                    period_start_rooms,
                    period_end_rooms,
                    occupancy_rate,
                ) = params
                self.inserted_rows[snapshot_date] = {
                    "applications": applications,
                    "new_moveins": new_moveins,
                    "new_moveouts": new_moveouts,
                    "occupancy_delta": occupancy_delta,
                    "period_start_rooms": period_start_rooms,
                    "period_end_rooms": period_end_rooms,
                    "occupancy_rate": occupancy_rate,
                }
                self._next_fetchone = None
                return

            if "first_apps" in sql_compact or "move_in_date" in sql_compact or "moveout_plans_date" in sql_compact:
                raise AssertionError("Did not expect movements/applications queries for missing snapshot day")

            raise AssertionError(f"Unexpected SQL executed: {sql_compact!r} params={params!r}")

        def fetchone(self):
            result = self._next_fetchone
            self._next_fetchone = None
            return result

    class FixedDate(date):
        @classmethod
        def today(cls):
            return date(2026, 2, 16)

    monkeypatch.setattr(daily_etl, "date", FixedDate)

    cursor = FakeCursor()
    processed = daily_etl.compute_occupancy_kpis_for_dates(cursor, [date(2026, 2, 15)])

    assert processed == 1
    assert cursor.inserted_rows[date(2026, 2, 15)]["period_end_rooms"] == 10_005
    assert cursor.inserted_rows[date(2026, 2, 15)]["period_start_rooms"] == 10_005
    assert cursor.inserted_rows[date(2026, 2, 15)]["occupancy_delta"] == 0
    assert cursor.inserted_rows[date(2026, 2, 15)]["new_moveins"] == 0
    assert cursor.inserted_rows[date(2026, 2, 15)]["new_moveouts"] == 0

    out = capsys.readouterr().out
    assert "WARN" in out
    assert "2026-02-15" in out


def test_update_gold_occupancy_kpis_repairs_stale_fact_dates_outside_primary_lookback(monkeypatch):
    """Repair window should include stale fact rows (e.g., 0-room artifacts) older than lookback."""

    class FakeCursor:
        def __init__(self):
            self._next_fetchone = None
            self._next_fetchall = []

        def execute(self, sql, params=None):
            sql_compact = " ".join(sql.split())

            if "SELECT MAX(snapshot_date) AS max_snapshot_date FROM silver.tenant_room_snapshot_daily" in sql_compact:
                self._next_fetchone = {"max_snapshot_date": date(2026, 2, 16)}
                return

            if (
                "SELECT DISTINCT snapshot_date FROM silver.tenant_room_snapshot_daily" in sql_compact
                and "WHERE snapshot_date BETWEEN %s AND %s" in sql_compact
            ):
                self._next_fetchall = [
                    {"snapshot_date": date(2026, 2, 11)},
                    {"snapshot_date": date(2026, 2, 13)},
                    {"snapshot_date": date(2026, 2, 14)},
                    {"snapshot_date": date(2026, 2, 16)},
                ]
                return

            if "SELECT snapshot_date FROM gold.occupancy_daily_metrics" in sql_compact:
                self._next_fetchall = [{"snapshot_date": date(2026, 2, 12)}]
                return

            raise AssertionError(f"Unexpected SQL: {sql_compact}")

        def fetchone(self):
            result = self._next_fetchone
            self._next_fetchone = None
            return result

        def fetchall(self):
            result = self._next_fetchall
            self._next_fetchall = []
            return result

        def close(self):
            return None

    class FakeConnection:
        def __init__(self):
            self.cursor_obj = FakeCursor()
            self.committed = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed = True

        def close(self):
            return None

    captured_dates = {}
    fake_connection = FakeConnection()

    monkeypatch.setenv("DAILY_OCCUPANCY_REPAIR_LOOKBACK_DAYS", "30")
    monkeypatch.setattr(daily_etl, "get_aurora_credentials", lambda: ("user", "pass"))
    monkeypatch.setattr(daily_etl.pymysql, "connect", lambda **kwargs: fake_connection)
    monkeypatch.setattr(daily_etl, "ensure_occupancy_kpi_table_exists", lambda cursor: None)

    def fake_compute(cursor, target_dates):
        captured_dates["dates"] = sorted(target_dates)
        return len(target_dates)

    monkeypatch.setattr(daily_etl, "compute_occupancy_kpis_for_dates", fake_compute)

    processed = daily_etl.update_gold_occupancy_kpis(
        target_date=date(2026, 2, 16),
        lookback_days=3,
        forward_days=1,
    )

    assert processed == len(captured_dates["dates"])
    assert date(2026, 2, 12) in captured_dates["dates"]
