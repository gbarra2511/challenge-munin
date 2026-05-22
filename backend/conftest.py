"""Top-level pytest config — adds `app` to import path."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
