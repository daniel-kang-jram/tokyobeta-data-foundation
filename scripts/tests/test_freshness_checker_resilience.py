"""Tests for monitoring freshness checker template resilience."""

import builtins
import io
import json
import re
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2]
    / "terraform/modules/monitoring/lambda/freshness_checker.py"
)
FRESHNESS_TF_PATH = (
    Path(__file__).resolve().parents[2]
    / "terraform/modules/monitoring/data_freshness_alarms.tf"
)


def _load_checker_module(monkeypatch, fail_pymysql_import: bool):
    """Load template as executable module for unit testing."""
    monkeypatch.setenv("AURORA_ENDPOINT", "example.cluster-123.ap-northeast-1.rds.amazonaws.com")
    monkeypatch.setenv("AURORA_SECRET_ARN", "arn:aws:secretsmanager:ap-northeast-1:123:secret:x")
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:ap-northeast-1:123:topic")
    monkeypatch.setenv("S3_BUCKET", "example-bucket")
    monkeypatch.setenv("S3_DUMP_PREFIXES", "dumps/")
    monkeypatch.setenv("S3_DUMP_ERROR_DAYS", "0")
    monkeypatch.setenv("S3_DUMP_MIN_BYTES", "1")
    monkeypatch.setenv("S3_DUMP_REQUIRE_ALL_PREFIXES", "true")

    source = TEMPLATE_PATH.read_text(encoding="utf-8").replace(
        "${jsonencode(tables)}",
        '["movings", "tenants"]',
    )

    module = types.ModuleType("freshness_checker_under_test")
    module.__file__ = str(TEMPLATE_PATH)

    original_import = builtins.__import__

    def _patched_import(name, globals=None, locals=None, fromlist=(), level=0):
        if fail_pymysql_import and name == "pymysql":
            raise ImportError("simulated missing pymysql")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=_patched_import):
        exec(compile(source, str(TEMPLATE_PATH), "exec"), module.__dict__)

    return module


def test_lambda_handler_fails_when_pymysql_missing(monkeypatch):
    """Missing DB dependency must fail fast (no silent partial success)."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=True)

    dump_check_calls = []

    def _fake_dump_check(prefix, date_str):
        dump_check_calls.append((prefix, date_str))
        return {
            "prefix": prefix,
            "key": f"{prefix.rstrip('/')}/gghouse_{date_str}.sql.gz",
            "size_bytes": 100,
            "ok": True,
            "missing": False,
            "error": None,
        }

    monkeypatch.setattr(checker, "check_dump_file", _fake_dump_check)
    monkeypatch.setattr(checker, "publish_dump_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "send_dump_alert", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "publish_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "send_alert", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        checker,
        "check_upstream_sync_staleness",
        lambda: {"manifest_key": None, "stale_entries": []},
    )
    runtime_alerts = []
    monkeypatch.setattr(checker, "send_runtime_alert", lambda msg: runtime_alerts.append(msg))

    with pytest.raises(RuntimeError):
        checker.lambda_handler({}, None)

    assert dump_check_calls == []
    assert runtime_alerts


def test_lambda_handler_reports_db_checks_enabled_with_pymysql(monkeypatch):
    """Should report DB checks enabled when pymysql import is available."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=False)

    class _DummyCursor:
        def execute(self, _sql):
            return None

        def fetchone(self):
            return (10, None, 0)

    class _DummyConn:
        def cursor(self):
            return _DummyCursor()

        def close(self):
            return None

    monkeypatch.setattr(checker, "get_db_credentials", lambda: {"username": "u", "password": "p"})
    monkeypatch.setattr(checker.pymysql, "connect", lambda **kwargs: _DummyConn())
    monkeypatch.setattr(checker, "check_dump_file", lambda prefix, date_str: {
        "prefix": prefix,
        "key": f"{prefix.rstrip('/')}/gghouse_{date_str}.sql.gz",
        "size_bytes": 100,
        "ok": True,
        "missing": False,
        "error": None,
    })
    monkeypatch.setattr(checker, "publish_dump_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "send_dump_alert", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "publish_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "send_alert", lambda *args, **kwargs: None)

    result = checker.lambda_handler({}, None)
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert body["db_checks_skipped"] is False


def test_lambda_handler_continues_when_dump_metric_publish_fails(monkeypatch):
    """Should still send dump alerts if CloudWatch metric publish fails."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=False)

    class _DummyCursor:
        def execute(self, _sql):
            return None

        def fetchone(self):
            return (10, None, 0)

    class _DummyConn:
        def cursor(self):
            return _DummyCursor()

        def close(self):
            return None

    def _missing_dump(prefix, date_str):
        return {
            "prefix": prefix,
            "key": f"{prefix.rstrip('/')}/gghouse_{date_str}.sql",
            "size_bytes": 0,
            "ok": False,
            "missing": True,
            "error": "404",
        }

    sent_alerts = []

    monkeypatch.setattr(checker, "get_db_credentials", lambda: {"username": "u", "password": "p"})
    monkeypatch.setattr(checker.pymysql, "connect", lambda **kwargs: _DummyConn())
    monkeypatch.setattr(checker, "check_dump_file", _missing_dump)
    monkeypatch.setattr(
        checker,
        "publish_dump_metric",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("metric publish failed")),
    )
    monkeypatch.setattr(checker, "send_dump_alert", lambda stale_dumps: sent_alerts.append(stale_dumps))
    monkeypatch.setattr(checker, "publish_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "send_alert", lambda *args, **kwargs: None)

    result = checker.lambda_handler({}, None)
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert body["stale_dump_count"] == 1
    assert sent_alerts


def test_check_dump_file_prefers_plain_sql_when_present(monkeypatch):
    """Should accept .sql dump files (legacy primary path)."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=True)

    def _head_object(Bucket, Key):
        if Key.endswith(".sql"):
            return {"ContentLength": 123}
        raise checker.ClientError({"Error": {"Code": "404"}}, "HeadObject")

    monkeypatch.setattr(checker.s3, "head_object", _head_object)

    result = checker.check_dump_file("dumps/", "20260217")

    assert result["missing"] is False
    assert result["ok"] is True
    assert result["key"].endswith("gghouse_20260217.sql")


def test_check_dump_file_falls_back_to_gzip_when_plain_missing(monkeypatch):
    """Should fall back to .sql.gz when plain .sql is not present."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=True)

    def _head_object(Bucket, Key):
        if Key.endswith(".sql.gz"):
            return {"ContentLength": 456}
        raise checker.ClientError({"Error": {"Code": "404"}}, "HeadObject")

    monkeypatch.setattr(checker.s3, "head_object", _head_object)

    result = checker.check_dump_file("dumps/", "20260216")

    assert result["missing"] is False
    assert result["ok"] is True
    assert result["key"].endswith("gghouse_20260216.sql.gz")


def test_evaluate_upstream_sync_staleness_excludes_inquiries(monkeypatch):
    """Upstream staleness checks must exclude inquiries table from incident gating."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=False)

    now_jst = datetime(2026, 2, 21, 8, 0, tzinfo=timezone(timedelta(hours=9)))
    manifest = {
        "max_updated_at_by_table": {
            "movings": "2026-02-20T02:00:00+09:00",
            "tenants": "2026-02-20T09:30:00+09:00",
            "rooms": "2026-02-20T09:30:00+09:00",
            "apartments": "2026-02-20T09:30:00+09:00",
            "inquiries": "2026-02-10T00:00:00+09:00",
        }
    }

    stale = checker.evaluate_upstream_sync_staleness(
        manifest=manifest,
        now_jst=now_jst,
        stale_hours=24,
        tables=["movings", "tenants", "rooms", "apartments"],
    )

    assert [entry["table"] for entry in stale] == ["movings"]


def test_evaluate_upstream_sync_staleness_uses_manifest_generated_at(monkeypatch):
    """Staleness must be evaluated against manifest generated_at, not invoke time."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=False)

    invoke_time_jst = datetime(2026, 2, 22, 18, 24, tzinfo=timezone(timedelta(hours=9)))
    manifest = {
        "generated_at": "2026-02-22T05:30:01+09:00",
        "max_updated_at_by_table": {
            "rooms": "2026-02-21T18:20:31+09:00",
            "apartments": "2026-02-21T18:20:31+09:00",
        },
    }

    stale = checker.evaluate_upstream_sync_staleness(
        manifest=manifest,
        now_jst=invoke_time_jst,
        stale_hours=24,
        tables=["rooms", "apartments"],
    )

    assert stale == []


def test_lambda_handler_reports_upstream_sync_staleness(monkeypatch):
    """Lambda should return non-200 and alert when upstream sync is stale."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=False)

    class _DummyCursor:
        def execute(self, _sql):
            return None

        def fetchone(self):
            return (10, None, 0)

    class _DummyConn:
        def cursor(self):
            return _DummyCursor()

        def close(self):
            return None

    monkeypatch.setattr(checker, "get_db_credentials", lambda: {"username": "u", "password": "p"})
    monkeypatch.setattr(checker.pymysql, "connect", lambda **kwargs: _DummyConn())
    monkeypatch.setattr(checker, "check_dump_file", lambda prefix, date_str: {
        "prefix": prefix,
        "key": f"{prefix.rstrip('/')}/gghouse_{date_str}.sql.gz",
        "size_bytes": 100,
        "ok": True,
        "missing": False,
        "error": None,
    })
    monkeypatch.setattr(checker, "publish_dump_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "send_dump_alert", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "publish_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "send_alert", lambda *args, **kwargs: None)

    upstream_alerts = []
    monkeypatch.setattr(
        checker,
        "check_upstream_sync_staleness",
        lambda: {
            "manifest_key": "dumps-manifest/gghouse_20260221.json",
            "stale_entries": [
                {"table": "movings", "max_updated_at": "2026-02-19T00:00:00+09:00", "lag_hours": 36.0}
            ],
        },
    )
    monkeypatch.setattr(
        checker,
        "send_upstream_sync_alert",
        lambda stale_entries, manifest_key: upstream_alerts.append((manifest_key, stale_entries)),
    )

    result = checker.lambda_handler({}, None)
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert body["stale_upstream_count"] == 1
    assert body["stale_upstream"][0]["table"] == "movings"
    assert upstream_alerts


def test_lambda_handler_suppresses_notifications_when_requested(monkeypatch):
    """Smoke/manual invokes can suppress SNS fan-out while still evaluating freshness."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=False)

    class _DummyCursor:
        def execute(self, _sql):
            return None

        def fetchone(self):
            return (10, None, 0)

    class _DummyConn:
        def cursor(self):
            return _DummyCursor()

        def close(self):
            return None

    monkeypatch.setattr(checker, "get_db_credentials", lambda: {"username": "u", "password": "p"})
    monkeypatch.setattr(checker.pymysql, "connect", lambda **kwargs: _DummyConn())
    monkeypatch.setattr(
        checker,
        "check_dump_file",
        lambda prefix, date_str: {
            "prefix": prefix,
            "key": f"{prefix.rstrip('/')}/gghouse_{date_str}.sql",
            "size_bytes": 0,
            "ok": False,
            "missing": True,
            "error": "404",
        },
    )
    monkeypatch.setattr(checker, "publish_dump_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "publish_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        checker,
        "check_upstream_sync_staleness",
        lambda: {
            "manifest_key": "dumps-manifest/gghouse_20260222.json",
            "stale_entries": [
                {
                    "table": "rooms",
                    "max_updated_at": "2026-02-21T18:20:31+09:00",
                    "lag_hours": 24.06,
                    "reason": "stale_upstream_sync",
                }
            ],
        },
    )

    dump_alerts = []
    upstream_alerts = []
    table_alerts = []
    monkeypatch.setattr(checker, "send_dump_alert", lambda stale_dumps: dump_alerts.append(stale_dumps))
    monkeypatch.setattr(
        checker,
        "send_upstream_sync_alert",
        lambda stale_entries, manifest_key: upstream_alerts.append((manifest_key, stale_entries)),
    )
    monkeypatch.setattr(checker, "send_alert", lambda stale_tables: table_alerts.append(stale_tables))

    result = checker.lambda_handler({"suppress_notifications": True}, None)
    body = json.loads(result["body"])

    assert result["statusCode"] == 400
    assert body["stale_dump_count"] == 1
    assert body["stale_upstream_count"] == 1
    assert dump_alerts == []
    assert upstream_alerts == []
    assert table_alerts == []


def test_load_latest_dump_manifest_paginates_before_selecting_latest(monkeypatch):
    """Manifest scan must paginate S3 listings before picking latest key."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=True)

    first_key = "dumps-manifest/gghouse_20260220.json"
    second_key = "dumps-manifest/gghouse_20260221.json"

    pages = {
        None: {
            "Contents": [
                {
                    "Key": first_key,
                    "LastModified": datetime(2026, 2, 20, 0, 0, tzinfo=timezone.utc),
                }
            ],
            "IsTruncated": True,
            "NextContinuationToken": "next-page",
        },
        "next-page": {
            "Contents": [
                {
                    "Key": second_key,
                    "LastModified": datetime(2026, 2, 21, 0, 0, tzinfo=timezone.utc),
                }
            ],
            "IsTruncated": False,
        },
    }
    requested_tokens = []

    def _list_objects_v2(Bucket, Prefix, ContinuationToken=None):
        requested_tokens.append(ContinuationToken)
        return pages[ContinuationToken]

    manifests = {
        first_key: {"marker": "old"},
        second_key: {"marker": "new"},
    }

    def _get_object(Bucket, Key):
        payload = json.dumps(manifests[Key]).encode("utf-8")
        return {"Body": io.BytesIO(payload)}

    monkeypatch.setattr(checker.s3, "list_objects_v2", _list_objects_v2)
    monkeypatch.setattr(checker.s3, "get_object", _get_object)

    manifest_key, manifest = checker.load_latest_dump_manifest()

    assert manifest_key == second_key
    assert manifest == {"marker": "new"}
    assert requested_tokens == [None, "next-page"]


def test_lambda_handler_does_not_alert_for_warning_only_freshness(monkeypatch):
    """Warning-only table age should not trigger stale-table SNS alerts."""
    checker = _load_checker_module(monkeypatch, fail_pymysql_import=False)

    warning_updated_at = datetime.now(timezone.utc) - timedelta(hours=25)

    class _DummyCursor:
        def execute(self, _sql):
            return None

        def fetchone(self):
            return (10, warning_updated_at.replace(tzinfo=None), 1)

    class _DummyConn:
        def cursor(self):
            return _DummyCursor()

        def close(self):
            return None

    table_alerts = []

    monkeypatch.setattr(checker, "get_db_credentials", lambda: {"username": "u", "password": "p"})
    monkeypatch.setattr(checker.pymysql, "connect", lambda **kwargs: _DummyConn())
    monkeypatch.setattr(checker, "publish_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(checker, "publish_dump_metric", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        checker,
        "check_dump_file",
        lambda prefix, date_str: {
            "prefix": prefix,
            "key": f"{prefix.rstrip('/')}/gghouse_{date_str}.sql",
            "size_bytes": 1024 * 1024 * 100,
            "ok": True,
            "missing": False,
            "error": None,
        },
    )
    monkeypatch.setattr(
        checker,
        "check_upstream_sync_staleness",
        lambda: {"manifest_key": None, "stale_entries": []},
    )
    monkeypatch.setattr(checker, "send_alert", lambda stale: table_alerts.append(stale))
    monkeypatch.setattr(checker, "send_dump_alert", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(checker, "send_upstream_sync_alert", lambda *_args, **_kwargs: None)

    result = checker.lambda_handler({}, None)
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert body["stale_count"] == 0
    assert table_alerts == []


def test_freshness_checker_db_table_list_excludes_inquiries():
    """DB freshness checks should exclude legacy inquiries table."""
    tf_text = FRESHNESS_TF_PATH.read_text(encoding="utf-8")
    anchor = tf_text.find('templatefile("${path.module}/lambda/freshness_checker.py"')
    assert anchor != -1, "Could not find freshness_checker templatefile block"
    template_window = tf_text[anchor : anchor + 500]
    match = re.search(r'tables\s*=\s*\[(?P<body>[^\]]+)\]', template_window, re.DOTALL)
    assert match is not None, "Could not find freshness_checker template tables list"

    tables = re.findall(r'"([^"]+)"', match.group("body"))
    assert "inquiries" not in tables
    assert set(tables) == {"movings", "tenants", "rooms", "apartments"}
