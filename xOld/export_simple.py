#!/usr/bin/env python3
"""
Simple PostgreSQL to Excel Exporter
====================================
Quick export with default settings - no configuration needed.

Run from: /home/gusrodgs/Gus/cienciaDeDados/phdMutley
Command: python export_simple.py
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import pandas as pd
import os

# Load database config
load_dotenv()
DB_CONFIG = {
    'drivername': 'postgresql+psycopg2',
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'climate_litigation'),
    'username': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
}

print("Connecting to database...")
engine = create_engine(URL.create(**DB_CONFIG))

print("Exporting tables...")
output_file = 'database_export_simple.xlsx'

# Tables to export
tables = ['cases', 'documents', 'extracted_text', 'text_sections', 'keywords_tags']

with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    for table in tables:
        print(f"  • {table}")
        
        # For extracted_text, exclude the long text columns
        if table == 'extracted_text':
            query = """
            SELECT 
                text_id, document_id, extraction_date, extraction_method,
                extraction_quality, word_count, character_count,
                LEFT(raw_text, 500) as raw_text_preview,
                extraction_notes, language_detected, language_confidence,
                created_at, updated_at
            FROM extracted_text
            """
            df = pd.read_sql(query, engine)
        else:
            df = pd.read_sql(f"SELECT * FROM {table}", engine)
        
        # Convert UUIDs to strings
        for col in df.columns:
            if df[col].dtype == 'object' and df[col].notna().any():
                first_val = df[col].dropna().iloc[0] if len(df[col].dropna()) > 0 else None
                if first_val and hasattr(first_val, 'hex'):
                    df[col] = df[col].astype(str)
        
        # Write to Excel
        df.to_excel(writer, sheet_name=table[:31], index=False)

print(f"\n✓ Done! Created: {output_file}")
print(f"  File size: {os.path.getsize(output_file)/1024:.1f} KB")
