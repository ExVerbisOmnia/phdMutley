"""
Shared fixtures for phdMutley tests.
"""

import importlib.util
import os
import sys

# Ensure scripts/ is on the path so tests can import config, pipeline modules, etc.
_SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, _SCRIPTS_DIR)
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, "0-initialize-database"))
sys.path.insert(
    0, os.path.join(_SCRIPTS_DIR, "5-extract-citations", "citation_extraction_pipeline")
)

# Pre-import pandas to avoid a numpy lazy-loading crash on Python 3.14
# where importlib.util.exec_module triggers a different code path.
try:
    import pandas  # noqa: F401
except ImportError:
    pass

# The file extract_citations_v5.2.py has a dot in its name, making normal import
# impossible. Use importlib to register it as 'extract_citations_v5_2' so tests
# can do `from extract_citations_v5_2 import ...`.
_v52_path = os.path.join(
    _SCRIPTS_DIR, "5-extract-citations", "citation_extraction_pipeline", "extract_citations_v5.2.py"
)
if os.path.exists(_v52_path):
    _spec = importlib.util.spec_from_file_location("extract_citations_v5_2", _v52_path)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules["extract_citations_v5_2"] = _mod
    _spec.loader.exec_module(_mod)
