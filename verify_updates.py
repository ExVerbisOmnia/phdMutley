import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = '/home/gusrodgs/Gus/cienciaDeDados/phdMutley'
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'scripts', '0-initialize-database'))

print("--- Verifying Config ---")
try:
    # Mock dotenv if missing just for verification of file existence
    try:
        import dotenv
    except ImportError:
        print("⚠️  dotenv not installed, mocking load_dotenv")
        import types
        dotenv = types.ModuleType('dotenv')
        dotenv.load_dotenv = lambda: None
        sys.modules['dotenv'] = dotenv

    import config
    print(f"DATABASE_FILE: {config.DATABASE_FILE}")
    if config.DATABASE_FILE.exists():
        print("✅ Database file exists")
    else:
        print(f"❌ Database file NOT found at {config.DATABASE_FILE}")
except Exception as e:
    print(f"❌ Error importing config: {e}")

print("\n--- Verifying init_database.py ---")
try:
    import init_database
    if hasattr(init_database, 'CitationExtractionPhased'):
        print("✅ CitationExtractionPhased class found")
    else:
        print("❌ CitationExtractionPhased class NOT found")
        
    if hasattr(init_database, 'CitationExtractionPhasedSummary'):
        print("✅ CitationExtractionPhasedSummary class found")
    else:
        print("❌ CitationExtractionPhasedSummary class NOT found")
except ImportError as e:
    print(f"❌ Failed to import init_database: {e}")
except Exception as e:
    print(f"❌ Error checking init_database: {e}")
