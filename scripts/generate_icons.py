"""Generate deterministic PNG and multi-resolution ICO assets from the icon master."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = tuple(size for size in SIZES if size <= 256)


def generate(root: Path) -> None:
    icons = root / "netconfiglint" / "resources" / "icons"
    source = icons / "app-master.png"
    master = QImage(str(source))
    if master.isNull() or not master.hasAlphaChannel() or min(master.width(), master.height()) < 1024:
        raise ValueError("app-master.png must be a transparent image of at least 1024 x 1024")

    generated = icons / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    payloads: dict[int, bytes] = {}
    for size in SIZES:
        image = master.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        target = generated / f"app-{size}.png"
        if not image.save(str(target), "PNG"):
            raise OSError(f"Could not write {target}")
        if size in ICO_SIZES:
            payloads[size] = target.read_bytes()

    header_size = 6 + 16 * len(ICO_SIZES)
    offset = header_size
    directory = bytearray(struct.pack("<HHH", 0, 1, len(ICO_SIZES)))
    body = bytearray()
    for size in ICO_SIZES:
        payload = payloads[size]
        encoded_size = 0 if size == 256 else size
        directory.extend(
            struct.pack("<BBBBHHII", encoded_size, encoded_size, 0, 0, 1, 32, len(payload), offset)
        )
        body.extend(payload)
        offset += len(payload)
    (icons / "app.ico").write_bytes(directory + body)


if __name__ == "__main__":
    project_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    generate(project_root)
