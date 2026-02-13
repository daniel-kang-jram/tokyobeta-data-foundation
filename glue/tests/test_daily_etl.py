import pathlib
import sys
from unittest.mock import Mock

from botocore.exceptions import ClientError


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


def test_is_dump_already_processed_true(monkeypatch):
    mock_s3 = Mock()
    mock_s3.head_object.return_value = {}

    monkeypatch.setattr(daily_etl, "s3", mock_s3)
    monkeypatch.setitem(daily_etl.args, "S3_SOURCE_BUCKET", "unit-test-bucket")

    assert daily_etl.is_dump_already_processed("dumps/gghouse_20260213.sql") is True


def test_is_dump_already_processed_false_for_missing_key(monkeypatch):
    mock_s3 = Mock()
    mock_s3.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}},
        "HeadObject",
    )

    monkeypatch.setattr(daily_etl, "s3", mock_s3)
    monkeypatch.setitem(daily_etl.args, "S3_SOURCE_BUCKET", "unit-test-bucket")

    assert daily_etl.is_dump_already_processed("dumps/gghouse_20260213.sql") is False
