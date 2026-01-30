#!/usr/bin/env python3
"""
Load sample tables from SQL dump into local MySQL database.
Extracts CREATE TABLE and INSERT statements for key tables and loads them.
"""

import re
import sys
import subprocess
from pathlib import Path

# Key tables to load
KEY_TABLES = ['movings', 'tenants', 'apartments', 'rooms', 'm_nationalities']

# Database connection
DB_HOST = '127.0.0.1'
DB_PORT = '3307'
DB_USER = 'root'
DB_PASSWORD = 'localdev'
DB_NAME = 'tokyobeta'
SCHEMA = 'staging'

# Limit rows per table for testing (set to 0 for all rows)
DEFAULT_MAX_ROWS = 1000


def extract_table_ddl(sql_content: str, table_name: str) -> str:
    """Extract CREATE TABLE statement for a specific table."""
    pattern = re.compile(
        rf'CREATE TABLE\s+[`"]?{table_name}[`"]?\s*\(.*?\)\s*ENGINE.*?;',
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(sql_content)
    if not match:
        return None

    create_stmt = match.group(0)
    create_stmt = re.sub(
        rf'CREATE TABLE\s+[`"]?{table_name}[`"]?',
        f'CREATE TABLE `{SCHEMA}`.`{table_name}`',
        create_stmt,
        flags=re.IGNORECASE,
    )
    create_stmt = re.sub(r'(?im)^\s*SET\s+.*?;\s*', '', create_stmt)
    return create_stmt


def extract_insert_statements(
    sql_content: str, table_name: str, max_rows: int | None = DEFAULT_MAX_ROWS
) -> list:
    """Extract INSERT INTO statements for a specific table."""
    pattern = re.compile(
        rf"INSERT INTO\s+[`\"]?{table_name}[`\"]?\s+VALUES\s+.*?;",
        re.IGNORECASE | re.DOTALL,
    )
    statements = []
    total_rows = 0

    for match in pattern.finditer(sql_content):
        insert_stmt = match.group(0)
        insert_stmt = re.sub(
            rf"INSERT INTO\s+[`\"]?{table_name}[`\"]?",
            f"INSERT INTO `{SCHEMA}`.`{table_name}`",
            insert_stmt,
            flags=re.IGNORECASE,
        )

        if max_rows is None:
            statements.append(insert_stmt)
            continue

        values_block = insert_stmt.split('VALUES', 1)[1].strip().rstrip(';')
        rows = re.split(r'\),\s*\(', values_block)
        if rows:
            rows[0] = rows[0].lstrip('(')
            rows[-1] = rows[-1].rstrip(')')

        remaining = max_rows - total_rows
        if remaining <= 0:
            break
        rows = rows[:remaining]
        total_rows += len(rows)
        if rows:
            limited_stmt = f"INSERT INTO `{SCHEMA}`.`{table_name}` VALUES "
            limited_stmt += "(" + "),(".join(rows) + ");"
            statements.append(limited_stmt)

        if total_rows >= max_rows:
            break

    return statements


def execute_sql(statements: list):
    """Execute SQL statements using mysql client."""
    if not statements:
        return

    session_prelude = [
        "SET SESSION sql_mode = 'ALLOW_INVALID_DATES';",
        "SET NAMES utf8mb4;",
    ]
    sql = '\n'.join(session_prelude + statements)

    cmd = [
        'mysql',
        f'-h{DB_HOST}',
        f'-P{DB_PORT}',
        f'-u{DB_USER}',
        f'-p{DB_PASSWORD}',
        '--binary-mode=1',
        '--default-character-set=utf8mb4',
        DB_NAME
    ]
    
    try:
        result = subprocess.run(
            cmd,
            input=sql,
            text=True,
            capture_output=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR executing SQL: {e.stderr}")
        return False


def main():
    """Main loading function."""
    if len(sys.argv) < 2:
        print("Usage: python load_sample_tables.py <sql_dump_file>")
        sys.exit(1)
    
    dump_file = Path(sys.argv[1])
    if not dump_file.exists():
        print(f"ERROR: SQL dump file not found: {dump_file}")
        sys.exit(1)
    
    print(f"Reading SQL dump: {dump_file}")
    with open(dump_file, 'r', encoding='utf-8', errors='ignore') as f:
        sql_content = f.read()
    
    print(f"File size: {len(sql_content):,} characters\n")
    
    max_rows = DEFAULT_MAX_ROWS
    if len(sys.argv) > 2 and sys.argv[2].isdigit():
        max_rows = int(sys.argv[2])
    if max_rows == 0:
        max_rows = None

    # Load each table
    for table_name in KEY_TABLES:
        print(f"Loading {table_name}...")
        
        # Extract CREATE TABLE
        create_stmt = extract_table_ddl(sql_content, table_name)
        if not create_stmt:
            print(f"  WARNING: Could not find CREATE TABLE for {table_name}")
            continue
        
        # Extract INSERT statements
        insert_stmts = extract_insert_statements(sql_content, table_name, max_rows)
        
        # Execute
        drop_stmt = f"DROP TABLE IF EXISTS `{SCHEMA}`.`{table_name}`;"
        statements = [drop_stmt, create_stmt] + insert_stmts
        
        if execute_sql(statements):
            if max_rows is None:
                print(f"  ✅ Loaded {table_name} (all rows)")
            else:
                print(f"  ✅ Loaded {table_name} (up to {max_rows} rows)")
        else:
            print(f"  ❌ Failed to load {table_name}")
    
    print("\n✅ Sample tables loaded successfully!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
