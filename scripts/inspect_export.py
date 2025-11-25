#!/usr/bin/env python3
"""
Inspect Excel Export
====================
Quick script to inspect the contents of the exported Excel file.
"""

import pandas as pd
import sys
from pathlib import Path

def inspect_excel(file_path):
    """Inspect the contents of an Excel file."""
    
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return
    
    print("\n" + "=" * 60)
    print(f"EXCEL FILE INSPECTION: {file_path.name}")
    print("=" * 60)
    print(f"\nFile size: {file_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    # Read Excel file
    xl_file = pd.ExcelFile(file_path)
    
    print(f"\nTotal sheets: {len(xl_file.sheet_names)}\n")
    
    print("Sheet Details:")
    print("-" * 60)
    
    total_rows = 0
    
    for sheet_name in xl_file.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        rows, cols = df.shape
        total_rows += rows
        
        print(f"\n📊 {sheet_name}")
        print(f"   Rows: {rows:,} | Columns: {cols}")
        
        if rows > 0:
            print(f"   Columns: {', '.join(df.columns[:10])}")
            if cols > 10:
                print(f"            ... and {cols - 10} more")
        else:
            print(f"   ⚠️  Empty sheet")
    
    print("\n" + "-" * 60)
    print(f"Total rows across all sheets: {total_rows:,}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Find most recent export
        export_dir = Path(__file__).parent.parent / 'data' / 'exports'
        excel_files = list(export_dir.glob('*.xlsx'))
        
        if not excel_files:
            print("No Excel files found in exports directory")
            sys.exit(1)
        
        # Get most recent file
        latest_file = max(excel_files, key=lambda p: p.stat().st_mtime)
        inspect_excel(latest_file)
    else:
        inspect_excel(sys.argv[1])
