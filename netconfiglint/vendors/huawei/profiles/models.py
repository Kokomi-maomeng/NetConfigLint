from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProfileOverlay:
    name: str
    commands: tuple[tuple[str, ...], ...] = ()
    removed_commands: tuple[tuple[str, ...], ...] = ()


@dataclass(slots=True)
class CommandProfile:
    name: str
    base_commands: set[tuple[str, ...]] = field(default_factory=set)
    overlays: list[ProfileOverlay] = field(default_factory=list)

    def effective_commands(self) -> set[tuple[str, ...]]:
        commands = set(self.base_commands)
        for overlay in self.overlays:
            commands.update(overlay.commands)
            commands.difference_update(overlay.removed_commands)
        return commands
