"""Install repository-local hooks shared by every worktree, without changing global Git settings."""

from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    subprocess.run(["git", "-C", str(root), "config", "core.hooksPath", str(root / ".githooks")], check=True)
    print("Privacy hooks installed for this repository and its worktrees.")


if __name__ == "__main__":
    main()
