from __future__ import annotations

from collections.abc import Iterator

from netconfiglint.core.analyzer.control import checkpoint
from netconfiglint.core.diagnostics import SourceRange
from netconfiglint.core.model import ConfigBlock, DeviceConfig


def all_commands(config: DeviceConfig) -> Iterator[tuple[str, SourceRange, ConfigBlock]]:
    """Yield block headers and child commands with stable source mapping."""
    for block in config.blocks:
        checkpoint()
        yield block.header, block.source, block
        for command in block.commands:
            checkpoint()
            known_bgp_view = block.header.lower().startswith("bgp ") and (
                (
                    len(command.views) == 1
                    and command.views[0].lower().startswith(("address-family ", "ip vpn-instance "))
                )
                or (
                    len(command.views) == 2
                    and command.views[0].lower().startswith("ip vpn-instance ")
                    and command.views[1].lower().startswith("address-family ")
                )
            )
            if command.views and not known_bgp_view:
                continue
            yield command.text, command.source, block
