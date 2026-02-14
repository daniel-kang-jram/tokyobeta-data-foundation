import pathlib
import subprocess
import sys
from datetime import date
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


def test_runtime_date_reads_valid_env(monkeypatch):
    monkeypatch.setenv("DAILY_TARGET_DATE", "2026-02-13")
    result = daily_etl.runtime_date("DAILY_TARGET_DATE", date(2026, 2, 1))
    assert result == date(2026, 2, 13)


def test_runtime_date_falls_back_on_invalid(monkeypatch):
    monkeypatch.setenv("DAILY_TARGET_DATE", "bad-date")
    result = daily_etl.runtime_date("DAILY_TARGET_DATE", date(2026, 2, 1))
    assert result == date(2026, 2, 1)


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
