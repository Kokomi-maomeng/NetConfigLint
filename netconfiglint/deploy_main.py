"""Deployment entry point kept inside the package to constrain resource collection."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

def launch() -> int:
    # Check the OS before importing Qt: its DLLs may not load on older builds.
    if sys.platform == "win32" and sys.getwindowsversion().build < 17763:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            "NetConfigLint requires Windows 10 version 1809 (build 17763) or newer.",
            "NetConfigLint",
            0x10,
        )
        return 2
    from netconfiglint.gui.app.main import main

    return main()


raise SystemExit(launch())
