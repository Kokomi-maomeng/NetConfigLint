"""Bounded, loss-visible decoding for configuration and diagnostic exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from netconfiglint.core.analyzer.control import AnalysisLimitReached, AnalysisLimits


@dataclass(frozen=True, slots=True)
class DecodedNetworkText:
    text: str
    encoding: str
    newline_style: str
    recovered_bytes: int = 0

    @property
    def recovered(self) -> bool:
        return self.recovered_bytes > 0


def _newline_style(text: str) -> str:
    crlf = text.count("\r\n")
    bare_cr = text.count("\r") - crlf
    lf = text.count("\n") - crlf
    kinds = sum(bool(value) for value in (crlf, bare_cr, lf))
    if kinds > 1:
        return "mixed"
    if crlf:
        return "crlf"
    if bare_cr:
        return "cr"
    return "lf"


def decode_network_bytes(data: bytes, limits: AnalysisLimits | None = None) -> DecodedNetworkText:
    limits = limits or AnalysisLimits()
    if len(data) > limits.max_input_bytes:
        raise AnalysisLimitReached("Input byte budget exceeded")

    encoding = "utf-8-sig"
    recovered = 0
    try:
        decoded = data.decode(encoding)
    except UnicodeDecodeError:
        encoding = "gb18030"
        try:
            decoded = data.decode(encoding)
        except UnicodeDecodeError:
            decoded = data.decode(encoding, errors="surrogateescape")
            pieces: list[str] = []
            for character in decoded:
                value = ord(character)
                if 0xDC80 <= value <= 0xDCFF:
                    pieces.append(f"\u27e6{value - 0xDC00:02X}\u27e7")
                    recovered += 1
                else:
                    pieces.append(character)
            decoded = "".join(pieces)
            encoding = "gb18030-with-byte-markers"

    style = _newline_style(decoded)
    normalized = decoded.replace("\r\n", "\n").replace("\r", "\n")
    if len(normalized) > limits.max_characters:
        raise AnalysisLimitReached("Input character budget exceeded")
    lines = normalized.splitlines()
    if len(lines) > limits.max_lines or any(len(line) > limits.max_line_length for line in lines):
        raise AnalysisLimitReached("Input line budget exceeded")
    return DecodedNetworkText(normalized, encoding, style, recovered)


def read_network_text(path: Path, limits: AnalysisLimits | None = None) -> DecodedNetworkText:
    limits = limits or AnalysisLimits()
    with path.open("rb") as stream:
        data = stream.read(limits.max_input_bytes + 1)
    return decode_network_bytes(data, limits)
