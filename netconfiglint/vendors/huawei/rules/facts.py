from __future__ import annotations

from collections.abc import Iterator

from netconfiglint.core.diagnostics import SourceRange
from netconfiglint.core.model import ConfigBlock, DeviceConfig


def all_commands(config: DeviceConfig) -> Iterator[tuple[str, SourceRange, ConfigBlock]]:
    """Yield block headers and child commands with stable source mapping."""
    for block in config.blocks:
        yield block.header, block.source, block
        for command in block.commands:
            yield command.text, command.source, block
