#!/usr/bin/env python3
"""
Load full MySQL dump into staging schema (production).
Filters for key tables: movings, tenants, apartments, rooms, inquiries, m_nationalities
"""

import re
import sys
from pathlib import Path
import pymysql
from datetime import datetime

KEY_TABLES = {"movings", "tenants", "apartments", "rooms", "inquiries", "m_nationalities"}
SCHEMA = "staging"

DB_CONFIG = {
    "host": "tokyobeta-prod-aurora-cluster-public.cluster-cr46qo6y4bbb.ap-northeast-1.rds.amazonaws.com",
    "port": 3306,
    "user": "admin",
    "password": "K6ghcWTq4p-zlidRJ2<AJX<w$zN<a8dU",
    "database": "tokyobeta",
    "charset": "utf8mb4",
}


def normalize_statement(stmt: str) -> str:
    """Normalize statement by stripping whitespace and comments."""
    stmt = stmt.strip()
    if not stmt:
        return ""
    if re.match(r"^(SET|LOCK TABLES|UNLOCK TABLES)", stmt, re.IGNORECASE):
        return ""
    if stmt.startswith("/*") and "SET" in stmt.upper():
        return ""
    if stmt.upper().startswith("CREATE DATABASE") or stmt.upper().startswith("USE "):
        return ""
    return stmt


def extract_table_name(stmt: str) -> str | None:
    """Extract table name from CREATE TABLE or INSERT INTO."""
    match = re.match(r"^(CREATE TABLE|INSERT INTO|DROP TABLE IF EXISTS)\s+`?(\w+)`?", stmt, re.IGNORECASE)
    if not match:
        return None
    return match.group(2)


def rewrite_statement(stmt: str, table_name: str) -> str:
    """Rewrite statement to target the staging schema."""
    stmt = re.sub(
        rf"^(CREATE TABLE|INSERT INTO|DROP TABLE IF EXISTS)\s+`?{table_name}`?",
        rf"\1 `{SCHEMA}`.`{table_name}`",
        stmt,
        flags=re.IGNORECASE,
    )
    return stmt


def backup_table(cursor, table_name: str):
    """Create backup of table."""
    backup_name = f"{SCHEMA}.{table_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"  💾 Backing up to {backup_name}...")
    try:
        cursor.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM {SCHEMA}.{table_name}")
        return backup_name
    except Exception as e:
        print(f"  ⚠️  Backup skipped: {e}")
        return None


def load_dump(dump_path: Path) -> None:
    """Load key tables from full dump into staging schema."""
    print(f"\n📂 Loading dump: {dump_path}")
    print(f"   Size: {dump_path.stat().st_size / (1024*1024):.1f} MB")
    
    connection = pymysql.connect(**DB_CONFIG, autocommit=False)
    cursor = connection.cursor()

    cursor.execute("CREATE SCHEMA IF NOT EXISTS staging")
    cursor.execute("SET SESSION sql_mode = 'ALLOW_INVALID_DATES'")
    cursor.execute("SET NAMES utf8mb4")
    cursor.execute("SET autocommit = 0")

    created_tables = set()
    current_table = None
    statement = []
    statements_count = {table: 0 for table in KEY_TABLES}
    insert_count = {table: 0 for table in KEY_TABLES}
    start_time = datetime.now()

    print(f"\n🔄 Processing dump file...")
    line_count = 0
    
    with open(dump_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line_count += 1
            if line_count % 100000 == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                print(f"   Processed {line_count:,} lines ({elapsed:.0f}s)...")
            
            statement.append(line)
            if line.rstrip().endswith(";"):
                raw_stmt = "".join(statement)
                statement = []
                stmt = normalize_statement(raw_stmt)
                if not stmt:
                    continue

                table_name = extract_table_name(stmt)
                if not table_name or table_name.lower() not in KEY_TABLES:
                    continue

                table_name = table_name.lower()
                
                # Backup before first operation
                if table_name not in created_tables:
                    print(f"\n📋 Processing table: {table_name}")
                    backup_table(cursor, table_name)
                    cursor.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{table_name}")
                    print(f"   🗑️  Dropped existing table")
                    created_tables.add(table_name)
                    current_table = table_name

                stmt = rewrite_statement(stmt, table_name)

                try:
                    cursor.execute(stmt)
                    statements_count[table_name] += 1
                    
                    if stmt.upper().startswith("INSERT"):
                        insert_count[table_name] += 1
                        if insert_count[table_name] % 1000 == 0:
                            connection.commit()
                            print(f"   ✓ {insert_count[table_name]:,} inserts...")
                except Exception as e:
                    print(f"   ⚠️  Error: {e}")
                    print(f"      Statement: {stmt[:200]}...")

    connection.commit()
    
    # Print summary
    print(f"\n{'='*80}")
    print(f"✅ Load Complete!")
    print(f"{'='*80}")
    print(f"Time: {(datetime.now() - start_time).total_seconds():.1f}s")
    print(f"\nTables loaded:")
    
    for table in sorted(KEY_TABLES):
        if table in created_tables:
            cursor.execute(f"SELECT COUNT(*), MAX(updated_at) FROM {SCHEMA}.{table}")
            row_count, last_update = cursor.fetchone()
            print(f"  ✓ {table:15s} {row_count:8,} rows  (last update: {last_update})")
    
    connection.close()
    print(f"\n🎉 All done!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 load_full_dump_to_staging.py <dump_file>")
        sys.exit(1)
    
    dump_path = Path(sys.argv[1])
    if not dump_path.exists():
        print(f"Error: {dump_path} not found")
        sys.exit(1)
    
    load_dump(dump_path)
