import sys
import os
from pathlib import Path
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

# Setup path and load env
PROJECT_ROOT = '/home/gusrodgs/Gus/cienciaDeDados/phdMutley'
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from config import DB_CONFIG

def inspect_schema():
    print("--- Inspecting Database Schema ---")
    try:
        # Construct URL from DB_CONFIG
        db_url = f"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        engine = create_engine(db_url)
        inspector = inspect(engine)
        
        if not inspector.has_table('cases'):
            print("❌ Table 'cases' does NOT exist.")
            return

        print("✅ Table 'cases' exists. Columns:")
        columns = inspector.get_columns('cases')
        col_names = [col['name'] for col in columns]
        
        required_cols = ['case_id', 'case_name_non_english', 'paragraph_count'] # paragraph_count is in extracted_text
        
        for col in columns:
            print(f"  - {col['name']} ({col['type']})")
            
        if 'case_name_non_english' in col_names:
            print("\n✅ 'case_name_non_english' found in 'cases'.")
        else:
            print("\n❌ 'case_name_non_english' NOT found in 'cases'.")

        print("\n--- Inspecting extracted_text ---")
        if inspector.has_table('extracted_text'):
             et_columns = inspector.get_columns('extracted_text')
             et_col_names = [col['name'] for col in et_columns]
             if 'paragraph_count' in et_col_names:
                 print("✅ 'paragraph_count' found in 'extracted_text'.")
             else:
                 print("❌ 'paragraph_count' NOT found in 'extracted_text'.")
        else:
            print("❌ Table 'extracted_text' does NOT exist.")

        print("\n--- Inspecting citation_sixfold_classification ---")
        try:
            columns = inspector.get_columns('citation_sixfold_classification')
            if columns:
                print("✅ View 'citation_sixfold_classification' exists. Columns:")
                for col in columns:
                    print(f"  - {col['name']} ({col['type']})")
            else:
                print("❌ View 'citation_sixfold_classification' not found or has no columns.")
        except Exception as e:
            print(f"❌ Error inspecting view: {e}")

    except Exception as e:
        print(f"❌ Error inspecting schema: {e}")

if __name__ == "__main__":
    inspect_schema()
