import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from gcp_secrets import get_database_url_auto


def inspect_schema():
    print("--- Inspecting Database Schema ---")
    try:
        engine = create_engine(get_database_url_auto())
        inspector = inspect(engine)

        if not inspector.has_table("cases"):
            print("❌ Table 'cases' does NOT exist.")
            return

        print("✅ Table 'cases' exists. Columns:")
        columns = inspector.get_columns("cases")
        col_names = [col["name"] for col in columns]

        for col in columns:
            print(f"  - {col['name']} ({col['type']})")

        if "case_name_non_english" in col_names:
            print("\n✅ 'case_name_non_english' found in 'cases'.")
        else:
            print("\n❌ 'case_name_non_english' NOT found in 'cases'.")

        print("\n--- Inspecting extracted_text ---")
        if inspector.has_table("extracted_text"):
            et_columns = inspector.get_columns("extracted_text")
            et_col_names = [col["name"] for col in et_columns]
            if "paragraph_count" in et_col_names:
                print("✅ 'paragraph_count' found in 'extracted_text'.")
            else:
                print("❌ 'paragraph_count' NOT found in 'extracted_text'.")
        else:
            print("❌ Table 'extracted_text' does NOT exist.")

        print("\n--- Inspecting citation_sixfold_classification ---")
        try:
            columns = inspector.get_columns("citation_sixfold_classification")
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
