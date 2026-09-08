"""Canonical ACL identity shared by definitions and every supported consumer."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AclIdentity:
    family: str
    kind: str
    value: str

    @property
    def key(self) -> str:
        return f"{self.family}:{self.kind}:{self.value}"


def parse_acl_identity(tokens: tuple[str, ...], *, family: str = "ipv4") -> AclIdentity | None:
    if tokens and tokens[0].lower() in {"ipv4", "ipv6"}:
        family, tokens = tokens[0].lower(), tokens[1:]
    if not tokens:
        return None
    kind = "number" if tokens[0].isdigit() else "name"
    if tokens[0].lower() in {"name", "number"}:
        kind, tokens = tokens[0].lower(), tokens[1:]
    if not tokens or (kind == "number" and not tokens[0].isdigit()):
        return None
    value = str(int(tokens[0])) if kind == "number" else tokens[0]
    return AclIdentity(family, kind, value)


def acl_label(key: str) -> str:
    family, kind, value = key.split(":", 2)
    return value if family == "ipv4" else f"IPv6 {kind} {value}"
