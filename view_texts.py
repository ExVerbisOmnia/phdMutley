#!/usr/bin/env python3
"""Quick script to view extracted texts"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import os
import sys

# Add path to import database models
sys.path.insert(0, 'scripts/phase0')
from init_database_pg18 import Document, ExtractedText

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

# Connect to database
engine = create_engine(URL.create(**DB_CONFIG))
Session = sessionmaker(bind=engine)
session = Session()

# Query all documents with their texts
results = session.query(Document, ExtractedText)\
    .join(ExtractedText, Document.document_id == ExtractedText.document_id)\
    .all()

print(f"Found {len(results)} documents with extracted text\n")
print("="*80)

for doc, text in results:
    print(f"\nFile: {doc.pdf_file_path}")
    print(f"Pages: {doc.page_count}")
    print(f"Words: {text.word_count}")
    print(f"Quality: {text.extraction_quality}")
    print(f"Method: {text.extraction_method}")
    print(f"\nFirst 500 characters:")
    print("-"*80)
    print(text.raw_text[:500])
    print("-"*80)
    
    # Ask if user wants to see full text
    response = input("\nView full text? (y/n): ")
    if response.lower() == 'y':
        print("\n" + "="*80)
        print(text.raw_text)
        print("="*80)
    
    response = input("\nContinue to next document? (y/n): ")
    if response.lower() != 'y':
        break

session.close()
print("\n✓ Done!")
