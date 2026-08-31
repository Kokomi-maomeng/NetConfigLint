"""Deployment entry point kept inside the package to constrain resource collection."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from netconfiglint.gui.app.main import main

raise SystemExit(main())
