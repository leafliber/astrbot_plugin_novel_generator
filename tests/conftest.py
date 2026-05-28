from __future__ import annotations

import sys
from pathlib import Path

_plugin_parent = str(Path(__file__).resolve().parent.parent.parent)
if _plugin_parent not in sys.path:
    sys.path.insert(0, _plugin_parent)
