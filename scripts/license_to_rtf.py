"""Convert the plain-text project license to conservative RTF for MSI UI."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    source, destination = map(Path, sys.argv[1:3])
    text = source.read_text(encoding="utf-8")
    escaped = text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
    escaped = escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\par " + "\n")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        r"{\rtf1\ansi\deff0{\fonttbl{\f0 Segoe UI;}}\fs18 " + escaped + "}",
        encoding="ascii",
        errors="backslashreplace",
    )


if __name__ == "__main__":
    main()
