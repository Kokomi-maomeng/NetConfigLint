from __future__ import annotations

from collections.abc import Callable, Iterator

from netconfiglint.core.diagnostics import SourceRange
from netconfiglint.core.model import ConfigBlock, DeviceConfig


def all_commands(config: DeviceConfig) -> Iterator[tuple[str, SourceRange, ConfigBlock]]:
    """Yield block headers and child commands with stable source mapping."""
    for block in config.blocks:
        yield block.header, block.source, block
        for command in block.commands:
            yield command.text, command.source, block


def blocks_starting(config: DeviceConfig, prefix: str) -> Iterator[ConfigBlock]:
    lowered = prefix.lower()
    return (block for block in config.blocks if block.header.lower().startswith(lowered))


def first_command(config: DeviceConfig, predicate: Callable[[str], bool]) -> tuple[str, SourceRange] | None:
    for text, source, _block in all_commands(config):
        if predicate(text.lower()):
            return text, source
    return None


def has_command(config: DeviceConfig, predicate: Callable[[str], bool]) -> bool:
    return first_command(config, predicate) is not None
