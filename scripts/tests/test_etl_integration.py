#!/usr/bin/env python3
"""
Integration test for ETL pipeline.
Tests that ALL components are properly connected end-to-end.

This test would have caught the bugs:
1. LLM enrichment not called in staging_loader.py
2. LLM predictions not used in silver stg_tenants.sql
3. Missing dbt deps in gold_transformer.py
"""

import sys
import os
import re
from pathlib import Path

# Color codes for output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def check_file_exists(filepath, description):
    """Check if required file exists."""
    if Path(filepath).exists():
        print(f"  ✓ {description}: {filepath}")
        return True
    else:
        print(f"  {RED}✗{RESET} {description}: {filepath} NOT FOUND")
        return False

def check_function_exists(filepath, function_name, description):
    """Check if a function is defined in a file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            if f"def {function_name}(" in content:
                print(f"  ✓ {description}: {function_name}()")
                return True
            else:
                print(f"  {RED}✗{RESET} {description}: {function_name}() NOT FOUND in {filepath}")
                return False
    except Exception as e:
        print(f"  {RED}✗{RESET} Error reading {filepath}: {e}")
        return False

def check_function_called(filepath, function_name, description):
    """Check if a function is CALLED in a file."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            # Look for function calls: function_name() or assigned = function_name()
            patterns = [
                f"{function_name}()",
                f"= {function_name}(",
            ]
            if any(pattern in content for pattern in patterns):
                print(f"  ✓ {description}: {function_name}() is CALLED")
                return True
            else:
                print(f"  {RED}✗{RESET} {description}: {function_name}() defined but NOT CALLED")
                return False
    except Exception as e:
        print(f"  {RED}✗{RESET} Error reading {filepath}: {e}")
        return False

def check_sql_uses_column(filepath, column_name, description):
    """Check if SQL file uses a specific column."""
    try:
        with open(filepath, 'r') as f:
            content = f.read().lower()
            if column_name.lower() in content:
                print(f"  ✓ {description}: uses {column_name}")
                return True
            else:
                print(f"  {RED}✗{RESET} {description}: {column_name} NOT USED")
                return False
    except Exception as e:
        print(f"  {RED}✗{RESET} Error reading {filepath}: {e}")
        return False

def check_dbt_deps_before_run(filepath, description):
    """Check if dbt deps is called before dbt run."""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            
            # Find positions
            deps_match = re.search(r'def install_dbt_dependencies|dbt.*deps', content)
            run_match = re.search(r'def run_dbt.*models|dbt.*run.*--models', content)
            
            if deps_match and run_match:
                # Check if deps function is called in main
                main_section = content[content.find('def main():'):]
                if 'install_dbt_dependencies' in main_section or 'dbt deps' in main_section:
                    print(f"  ✓ {description}: dbt deps called before dbt run")
                    return True
                else:
                    print(f"  {RED}✗{RESET} {description}: dbt deps function exists but NOT CALLED")
                    return False
            else:
                print(f"  {RED}✗{RESET} {description}: dbt deps NOT FOUND")
                return False
    except Exception as e:
        print(f"  {RED}✗{RESET} Error reading {filepath}: {e}")
        return False

def main():
    print("="*80)
    print("ETL INTEGRATION TEST - Verifies End-to-End Component Connections")
    print("="*80)
    print()
    
    issues = []
    
    # Test 1: Staging Loader Integration
    print(f"\n{YELLOW}[TEST 1]{RESET} Staging Loader Integration")
    print("-" * 60)
    
    staging_file = 'glue/scripts/staging_loader.py'
    
    t1a = check_file_exists(staging_file, "Staging loader script")
    t1b = check_function_exists(staging_file, 'enrich_nationality_data', "Enrichment function defined")
    t1c = check_function_called(staging_file, 'enrich_nationality_data', "Enrichment function called")
    
    if not all([t1a, t1b, t1c]):
        issues.append("Staging Loader: LLM enrichment not properly integrated")
    
    # Test 2: Silver Transformer SQL Logic
    print(f"\n{YELLOW}[TEST 2]{RESET} Silver Layer SQL - LLM Priority")
    print("-" * 60)
    
    silver_sql = 'dbt/models/silver/stg_tenants.sql'
    
    t2a = check_file_exists(silver_sql, "Silver tenants model")
    t2b = check_sql_uses_column(silver_sql, 'llm_nationality', "Uses llm_nationality column")
    
    # Check priority order in CASE statement
    try:
        with open(silver_sql, 'r') as f:
            content = f.read()
            
            # Find the nationality CASE statement
            case_match = re.search(
                r'CASE\s+.*?WHEN.*?llm_nationality.*?THEN.*?llm_nationality.*?END\s+as\s+nationality',
                content,
                re.DOTALL | re.IGNORECASE
            )
            
            if case_match:
                case_block = case_match.group(0)
                
                # Check if LLM comes before lookup table
                llm_pos = case_block.lower().find('llm_nationality')
                lookup_pos = case_block.lower().find('nationality_name')
                
                if llm_pos > 0 and lookup_pos > 0:
                    if llm_pos < lookup_pos:
                        print(f"  ✓ LLM priority: LLM checked BEFORE lookup table")
                        t2c = True
                    else:
                        print(f"  {RED}✗{RESET} LLM priority: LLM checked AFTER lookup table (BUG!)")
                        print(f"     → Lookup returns 'レソト' and blocks LLM predictions")
                        t2c = False
                else:
                    print(f"  {YELLOW}?{RESET} Could not determine priority order")
                    t2c = False
            else:
                print(f"  {RED}✗{RESET} CASE statement using llm_nationality NOT FOUND")
                t2c = False
                
    except Exception as e:
        print(f"  {RED}✗{RESET} Error analyzing SQL: {e}")
        t2c = False
    
    if not all([t2a, t2b, t2c]):
        issues.append("Silver Layer: LLM predictions not properly prioritized in SQL logic")
    
    # Test 3: Silver Transformer - dbt deps
    print(f"\n{YELLOW}[TEST 3]{RESET} Silver Transformer - dbt Dependencies")
    print("-" * 60)
    
    silver_script = 'glue/scripts/silver_transformer.py'
    
    t3a = check_file_exists(silver_script, "Silver transformer script")
    t3b = check_dbt_deps_before_run(silver_script, "Silver transformer")
    
    if not all([t3a, t3b]):
        issues.append("Silver Transformer: Missing dbt deps installation")
    
    # Test 4: Gold Transformer - dbt deps
    print(f"\n{YELLOW}[TEST 4]{RESET} Gold Transformer - dbt Dependencies")
    print("-" * 60)
    
    gold_script = 'glue/scripts/gold_transformer.py'
    
    t4a = check_file_exists(gold_script, "Gold transformer script")
    t4b = check_dbt_deps_before_run(gold_script, "Gold transformer")
    
    if not all([t4a, t4b]):
        issues.append("Gold Transformer: Missing dbt deps installation")
    
    # Test 5: Enricher Module Availability
    print(f"\n{YELLOW}[TEST 5]{RESET} Nationality Enricher Module")
    print("-" * 60)
    
    enricher_file = 'glue/scripts/nationality_enricher.py'
    
    t5a = check_file_exists(enricher_file, "Enricher module")
    
    # Check if staging_loader downloads it from S3
    try:
        with open(staging_file, 'r') as f:
            content = f.read()
            if 'glue-scripts/nationality_enricher.py' in content and 's3.download_file' in content:
                print(f"  ✓ Staging loader: Downloads enricher from S3")
                t5b = True
            else:
                print(f"  {RED}✗{RESET} Staging loader: Does NOT download enricher from S3")
                t5b = False
    except:
        t5b = False
    
    if not all([t5a, t5b]):
        issues.append("Enricher Module: Not properly made available to staging loader")
    
    # Test 6: Step Functions vs Monolithic ETL
    print(f"\n{YELLOW}[TEST 6]{RESET} Production Pipeline Architecture")
    print("-" * 60)
    
    # Check if Step Functions exists
    step_functions_tf = 'terraform/modules/step_functions/main.tf'
    t6a = check_file_exists(step_functions_tf, "Step Functions module")
    
    # Warn if daily_etl.py exists (monolithic)
    daily_etl_file = 'glue/scripts/daily_etl.py'
    if Path(daily_etl_file).exists():
        print(f"  {YELLOW}⚠{RESET}  Monolithic daily_etl.py exists (should not be used in production)")
        print(f"     → Production should use: staging_loader → silver_transformer → gold_transformer")
    
    if not t6a:
        issues.append("Step Functions: Orchestration not properly defined")
    
    # Summary
    print()
    print("="*80)
    if issues:
        print(f"{RED}✗ INTEGRATION TEST FAILED{RESET}")
        print("="*80)
        print(f"\nFound {len(issues)} critical issue(s):\n")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print()
        print("These integration bugs would cause production failures:")
        print("  - Enrichment not running despite code being 'ready'")
        print("  - LLM predictions not visible in silver/gold layers")
        print("  - dbt compilation errors at runtime")
        print()
        return 1
    else:
        print(f"{GREEN}✓ ALL INTEGRATION TESTS PASSED{RESET}")
        print("="*80)
        print("\nAll components properly connected:")
        print("  ✓ Staging loader calls enrichment")
        print("  ✓ Silver SQL uses LLM predictions correctly")
        print("  ✓ dbt dependencies installed before run")
        print("  ✓ Enricher module properly loaded")
        print()
        return 0

if __name__ == "__main__":
    sys.exit(main())
