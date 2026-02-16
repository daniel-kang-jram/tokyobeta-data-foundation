"""Tests for monitoring freshness checker template resilience."""

import builtins
import json
import types
from pathlib import Path
from unittest.mock import patch


TEMPLATE_PATH = (
    Path(__file__).resolve().parents[2]
    / "terraform/modules/monitoring/lambda/freshness_checker.py"
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


def test_lambda_handler_runs_dump_checks_when_pymysql_missing(monkeypatch):
    """Should continue dump checks even if DB dependency import fails."""
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

    result = checker.lambda_handler({}, None)
    body = json.loads(result["body"])

    assert result["statusCode"] == 200
    assert body["stale_dump_count"] == 0
    assert body["db_checks_skipped"] is True
    assert dump_check_calls


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
