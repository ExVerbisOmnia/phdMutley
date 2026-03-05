import os
from pathlib import Path

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

files = [
    str(_PROJECT_ROOT / "data" / "processed" / "baseDecisions.xlsx"),
    str(_PROJECT_ROOT / "data" / "raw" / "baseCompleta.xlsx"),
]

for f in files:
    print(f"\n{'=' * 50}")
    print(f"Inspecting: {f}")
    if not os.path.exists(f):
        print("❌ File does not exist")
        continue

    try:
        df = pd.read_excel(f, nrows=5)
        print(f"✅ Loaded successfully. Columns ({len(df.columns)}):")
        print(list(df.columns))

        # Check for trial batch specifically
        trial_cols = [c for c in df.columns if "trial" in c.lower() or "batch" in c.lower()]
        if trial_cols:
            print(f"🎯 Found potential trial batch columns: {trial_cols}")
        else:
            print("⚠️ No columns containing 'trial' or 'batch' found.")

    except Exception as e:
        print(f"❌ Error reading file: {e}")
