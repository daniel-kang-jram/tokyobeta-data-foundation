#!/usr/bin/env python3
"""
Load key tables from a MySQL dump into local MySQL using PyMySQL.
Filters for the core analytics tables and loads into the staging schema.
"""

import re
import sys
from pathlib import Path

import pymysql

KEY_TABLES = {"movings", "tenants", "apartments", "rooms", "m_nationalities"}
SCHEMA = "staging"

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3307,
    "user": "root",
    "password": "localdev",
    "database": "tokyobeta",
    "charset": "utf8mb4",
    "autocommit": True,
}


def normalize_statement(stmt: str) -> str:
    """Normalize statement by stripping whitespace and comments."""
    stmt = stmt.strip()
    if not stmt:
        return ""
    # Skip SET, LOCK/UNLOCK, and other session-level statements
    if re.match(r"^(SET|LOCK TABLES|UNLOCK TABLES)", stmt, re.IGNORECASE):
        return ""
    if stmt.startswith("/*") and "SET" in stmt.upper():
        return ""
    return stmt


def extract_table_name(stmt: str) -> str | None:
    """Extract table name from CREATE TABLE or INSERT INTO."""
    match = re.match(r"^(CREATE TABLE|INSERT INTO)\s+`?(\w+)`?", stmt, re.IGNORECASE)
    if not match:
        return None
    return match.group(2)


def rewrite_statement(stmt: str, table_name: str) -> str:
    """Rewrite statement to target the staging schema."""
    stmt = re.sub(
        rf"^(CREATE TABLE|INSERT INTO)\s+`?{table_name}`?",
        rf"\1 `{SCHEMA}`.`{table_name}`",
        stmt,
        flags=re.IGNORECASE,
    )
    return stmt


def load_dump(dump_path: Path) -> None:
    """Load key tables from dump into staging schema."""
    connection = pymysql.connect(**DB_CONFIG)
    cursor = connection.cursor()

    cursor.execute("CREATE SCHEMA IF NOT EXISTS staging")
    cursor.execute("SET SESSION sql_mode = 'ALLOW_INVALID_DATES'")
    cursor.execute("SET NAMES utf8mb4")

    created_tables = set()
    statement = []

    with open(dump_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            statement.append(line)
            if line.rstrip().endswith(";"):
                raw_stmt = "".join(statement)
                statement = []
                stmt = normalize_statement(raw_stmt)
                if not stmt:
                    continue

                table_name = extract_table_name(stmt)
                if not table_name or table_name not in KEY_TABLES:
                    continue

                stmt = rewrite_statement(stmt, table_name)
                if stmt.upper().startswith("CREATE TABLE") and table_name not in created_tables:
                    cursor.execute(f"DROP TABLE IF EXISTS `{SCHEMA}`.`{table_name}`")
                    created_tables.add(table_name)

                try:
                    cursor.execute(stmt)
                except Exception as exc:
                    print(f"ERROR loading {table_name}: {exc}")
                    raise

    cursor.close()
    connection.close()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python load_dump_key_tables_pymysql.py <sql_dump_file>")
        return 1

    dump_file = Path(sys.argv[1])
    if not dump_file.exists():
        print(f"ERROR: SQL dump file not found: {dump_file}")
        return 1

    print(f"Loading key tables from: {dump_file}")
    load_dump(dump_file)
    print("✅ Key tables loaded successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
