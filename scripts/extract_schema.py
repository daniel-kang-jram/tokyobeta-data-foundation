#!/usr/bin/env python3
"""
Extract schema definitions from GGhouse SQL dump file.
Parses CREATE TABLE statements and generates JSON schema documentation.
"""

import re
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Key tables to extract
KEY_TABLES = ['movings', 'tenants', 'apartments', 'rooms', 'm_nationalities']


def parse_create_table(sql_content: str, table_name: str) -> Dict[str, Any]:
    """Extract CREATE TABLE statement for a specific table."""
    # Pattern to match CREATE TABLE statement
    pattern = rf'CREATE TABLE\s+[`"]?{table_name}[`"]?\s*\((.*?)\)\s*ENGINE'
    
    match = re.search(pattern, sql_content, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    
    table_def = match.group(1)
    
    # Parse column definitions
    columns = []
    lines = [line.strip() for line in table_def.split(',')]
    
    for line in lines:
        if not line or line.startswith('PRIMARY KEY') or line.startswith('KEY') or line.startswith('UNIQUE'):
            continue
        
        # Extract column name (first word, remove backticks)
        col_match = re.match(r'[`"]?(\w+)[`"]?\s+', line)
        if not col_match:
            continue
        
        col_name = col_match.group(1)
        
        # Extract data type
        type_match = re.search(r'(\w+(?:\([^)]+\))?)', line)
        col_type = type_match.group(1) if type_match else 'unknown'
        
        # Check for NOT NULL
        is_nullable = 'NOT NULL' not in line.upper()
        
        # Check for DEFAULT
        default_match = re.search(r"DEFAULT\s+([^,\s]+)", line, re.IGNORECASE)
        default_value = default_match.group(1) if default_match else None
        
        columns.append({
            'name': col_name,
            'type': col_type,
            'nullable': is_nullable,
            'default': default_value
        })
    
    return {
        'table_name': table_name,
        'columns': columns,
        'column_count': len(columns)
    }


def extract_all_tables(sql_content: str) -> Dict[str, Any]:
    """Extract schema for all key tables."""
    schemas = {}
    
    for table_name in KEY_TABLES:
        print(f"Extracting schema for {table_name}...")
        schema = parse_create_table(sql_content, table_name)
        if schema:
            schemas[table_name] = schema
            print(f"  Found {schema['column_count']} columns")
        else:
            print(f"  WARNING: Table {table_name} not found in dump")
            schemas[table_name] = None
    
    return schemas


def main():
    """Main extraction function."""
    if len(sys.argv) < 2:
        print("Usage: python extract_schema.py <sql_dump_file> [output_json]")
        print("Example: python extract_schema.py data/samples/gghouse_20260130.sql")
        sys.exit(1)
    
    dump_file = Path(sys.argv[1])
    if not dump_file.exists():
        print(f"ERROR: SQL dump file not found: {dump_file}")
        sys.exit(1)
    
    output_file = sys.argv[2] if len(sys.argv) > 2 else dump_file.parent / 'schema_definitions.json'
    
    print(f"Reading SQL dump: {dump_file}")
    with open(dump_file, 'r', encoding='utf-8', errors='ignore') as f:
        sql_content = f.read()
    
    print(f"File size: {len(sql_content):,} characters")
    
    # Extract schemas
    schemas = extract_all_tables(sql_content)
    
    # Add metadata
    result = {
        'source_file': str(dump_file),
        'extraction_date': str(Path(__file__).stat().st_mtime),
        'tables': schemas
    }
    
    # Write JSON output
    print(f"\nWriting schema definitions to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\nSchema extraction complete!")
    print(f"Extracted {len([s for s in schemas.values() if s])} tables")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
