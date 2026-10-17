"""Evaluation harness for If I Disappear. Run `python -m evals.run` from the repo root.

Importing the package puts services/api on the import path, so the harness uses
exactly the same code as the app (`app.*`).
"""

import sys
from pathlib import Path

_API = Path(__file__).resolve().parents[1] / "services" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))
