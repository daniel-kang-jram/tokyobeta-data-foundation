#!/usr/bin/env python3
"""
Extract sample data rows from GGhouse SQL dump file.
Extracts first 100 rows from each key table and saves as CSV.
"""

import re
import csv
import sys
from pathlib import Path
from typing import List, Dict, Any

# Key tables to extract
KEY_TABLES = ['movings', 'tenants', 'apartments', 'rooms', 'm_nationalities']
SAMPLE_SIZE = 100


def extract_insert_statements(sql_content: str, table_name: str) -> List[str]:
    """Extract all INSERT INTO statements for a specific table."""
    # Pattern to match INSERT INTO statements
    pattern = rf"INSERT INTO\s+[`\"]?{table_name}[`\"]?\s+VALUES\s+(.*?);"
    
    matches = re.finditer(pattern, sql_content, re.DOTALL | re.IGNORECASE)
    statements = []
    
    for match in matches:
        values_block = match.group(1)
        # Split by ),( to get individual rows
        rows = re.split(r'\),\s*\(', values_block)
        
        # Clean up first and last rows
        if rows:
            rows[0] = rows[0].lstrip('(')
            rows[-1] = rows[-1].rstrip(')')
        
        statements.extend(rows)
    
    return statements[:SAMPLE_SIZE]  # Limit to sample size


def parse_row_values(row_str: str) -> List[str]:
    """Parse a single row's values, handling NULL, strings, numbers."""
    values = []
    current_value = ""
    in_quotes = False
    quote_char = None
    i = 0
    
    while i < len(row_str):
        char = row_str[i]
        
        if not in_quotes:
            if char in ("'", '"'):
                in_quotes = True
                quote_char = char
                current_value += char
            elif char == ',':
                # End of value
                values.append(current_value.strip())
                current_value = ""
            elif char == '\\' and i + 1 < len(row_str):
                # Escape sequence
                current_value += char + row_str[i + 1]
                i += 1
            else:
                current_value += char
        else:
            if char == quote_char and (i == 0 or row_str[i - 1] != '\\'):
                # End of quoted string
                in_quotes = False
                quote_char = None
                current_value += char
            elif char == '\\' and i + 1 < len(row_str):
                # Escape sequence
                current_value += char + row_str[i + 1]
                i += 1
            else:
                current_value += char
        
        i += 1
    
    # Add last value
    if current_value.strip():
        values.append(current_value.strip())
    
    return values


def extract_table_samples(sql_content: str, table_name: str) -> List[List[str]]:
    """Extract sample rows from a table."""
    print(f"Extracting samples from {table_name}...")
    
    # First, try to get column names from CREATE TABLE
    col_pattern = rf'CREATE TABLE\s+[`"]?{table_name}[`"]?\s*\((.*?)\)\s*ENGINE'
    col_match = re.search(col_pattern, sql_content, re.DOTALL | re.IGNORECASE)
    
    if not col_match:
        print(f"  WARNING: Could not find CREATE TABLE for {table_name}")
        return []
    
    table_def = col_match.group(1)
    # Extract column names
    column_names = []
    for line in table_def.split(','):
        line = line.strip()
        if not line or line.startswith('PRIMARY KEY') or line.startswith('KEY') or line.startswith('UNIQUE'):
            continue
        col_match = re.match(r'[`"]?(\w+)[`"]?\s+', line)
        if col_match:
            column_names.append(col_match.group(1))
    
    print(f"  Found {len(column_names)} columns")
    
    # Extract INSERT statements
    insert_statements = extract_insert_statements(sql_content, table_name)
    print(f"  Found {len(insert_statements)} rows")
    
    if not insert_statements:
        print(f"  WARNING: No INSERT statements found for {table_name}")
        return []
    
    # Parse rows
    rows = []
    for stmt in insert_statements[:SAMPLE_SIZE]:
        try:
            values = parse_row_values(stmt)
            # Ensure we have the right number of values
            if len(values) == len(column_names):
                rows.append(values)
            elif len(values) > len(column_names):
                # Truncate if too many
                rows.append(values[:len(column_names)])
            else:
                # Pad if too few
                values.extend([''] * (len(column_names) - len(values)))
                rows.append(values)
        except Exception as e:
            print(f"  WARNING: Failed to parse row: {str(e)[:100]}")
            continue
    
    print(f"  Extracted {len(rows)} valid rows")
    return rows, column_names


def main():
    """Main extraction function."""
    if len(sys.argv) < 2:
        print("Usage: python extract_samples.py <sql_dump_file> [output_dir]")
        print("Example: python extract_samples.py data/samples/gghouse_20260130.sql")
        sys.exit(1)
    
    dump_file = Path(sys.argv[1])
    if not dump_file.exists():
        print(f"ERROR: SQL dump file not found: {dump_file}")
        sys.exit(1)
    
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else dump_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Reading SQL dump: {dump_file}")
    with open(dump_file, 'r', encoding='utf-8', errors='ignore') as f:
        sql_content = f.read()
    
    print(f"File size: {len(sql_content):,} characters\n")
    
    # Extract samples for each table
    for table_name in KEY_TABLES:
        try:
            rows, column_names = extract_table_samples(sql_content, table_name)
            
            if not rows:
                print(f"  Skipping {table_name} (no data)\n")
                continue
            
            # Write to CSV
            output_file = output_dir / f"{table_name}_sample.csv"
            with open(output_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                # Write header
                writer.writerow(column_names)
                # Write rows
                writer.writerows(rows)
            
            print(f"  Saved {len(rows)} rows to {output_file}\n")
            
        except Exception as e:
            print(f"  ERROR extracting {table_name}: {str(e)}\n")
            import traceback
            traceback.print_exc()
            continue
    
    print("Sample extraction complete!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
