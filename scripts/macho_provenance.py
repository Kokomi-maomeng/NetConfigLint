"""Match Mach-O executable sections while validating only supported loader relocation.

Nuitka changes install names/RPATH and macOS signing changes the code-signature
blob. CPU identity, all section bytes and every other load command must match.
Unknown formats and loader paths fail closed.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path, PurePosixPath


def _path(data: bytes, offset: int, *, library_id: bool = False) -> str:
    if not 8 <= offset < len(data):
        raise ValueError("Invalid Mach-O path offset")
    value = data[offset:].split(b"\0", 1)[0].decode("utf-8")
    if not value:
        raise ValueError("Unsafe Mach-O path")
    if value.startswith(("/System/Library/", "/usr/lib/")):
        return value
    # Nuitka's install_name_tool call sets LC_ID_DYLIB to the copied basename.
    # Bare names are permitted for identity only, never dependency search paths.
    bare_id = library_id and re.fullmatch(r"[\w.+-]+", value) is not None and value not in {".", ".."}
    if not bare_id and not value.startswith(("@rpath/", "@loader_path/", "@executable_path/", "/")):
        raise ValueError("Unsupported Mach-O loader path")
    if value.startswith("@") and PurePosixPath(value).parts.count("..") > 2:
        raise ValueError("Mach-O loader relocation escapes the qualified layout")
    name = PurePosixPath(value).name
    if library_id:
        name = re.sub(r"\.(?:abi3|cpython-\d+[^.]*)\.so$", ".so", name)
    return name


def _thin(data: bytes) -> tuple:
    if len(data) < 32 or data[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError("Only little-endian Mach-O64 is qualified")
    header = struct.unpack_from("<IiiIIIII", data)
    count, length = header[4:6]
    if count > 4096 or 32 + length > len(data):
        raise ValueError("Invalid Mach-O load commands")
    commands = []
    sections = []
    offset = 32
    for _ in range(count):
        command, size = struct.unpack_from("<II", data, offset)
        if size < 8 or offset + size > 32 + length:
            raise ValueError("Invalid Mach-O command size")
        raw = data[offset : offset + size]
        if command == 0x19:  # LC_SEGMENT_64
            segment = struct.unpack_from("<II16sQQQQiiII", raw)
            name = segment[2].rstrip(b"\0")
            if segment[9] > 4096 or 72 + segment[9] * 80 > size:
                raise ValueError("Invalid Mach-O section count")
            for index in range(segment[9]):
                row = struct.unpack_from("<16s16sQQIIIIIIII", raw, 72 + index * 80)
                section_name, segment_name, address, byte_count, file_offset = row[:5]
                kind = row[8] & 0xFF
                if kind in {1, 0xC, 0x12}:  # zero-fill sections have no bytes in the file.
                    content = b""
                else:
                    if file_offset + byte_count > len(data):
                        raise ValueError("Mach-O section extends beyond file")
                    content = data[file_offset : file_offset + byte_count]
                sections.append((section_name, segment_name, address, byte_count, row[5:6], row[8:], content))
            if name != b"__LINKEDIT":
                commands.append((command, name, segment[3:5], segment[7:]))
        elif command == 0x1D:  # LC_CODE_SIGNATURE: no executable sections live in this blob.
            if size != 16:
                raise ValueError("Invalid code signature command")
            signature_offset, signature_size = struct.unpack_from("<II", raw, 8)
            if signature_offset + signature_size > len(data):
                raise ValueError("Invalid code signature bounds")
        elif command == 0x8000001C:  # LC_RPATH
            value = raw[struct.unpack_from("<I", raw, 8)[0] :].split(b"\0", 1)[0].decode("utf-8")
            if not value.startswith(("@loader_path", "@executable_path")):
                raise ValueError("Unqualified Mach-O runtime search path")
        elif command in {0xC, 0xD, 0x80000018, 0x8000001F, 0x20, 0x80000023}:
            if size < 24:
                raise ValueError("Invalid dylib command")
            commands.append(
                (
                    command,
                    _path(raw, struct.unpack_from("<I", raw, 8)[0], library_id=command == 0xD),
                    raw[12:24],
                )
            )
        else:
            commands.append((command, raw))
        offset += size
    if offset != 32 + length or not sections:
        raise ValueError("Incomplete Mach-O section inventory")
    return header[1:4], header[6:], tuple(commands), tuple(sections)


def _snapshot(data: bytes) -> dict[tuple[int, int], tuple]:
    if data[:4] == b"\xcf\xfa\xed\xfe":
        result = _thin(data)
        return {result[0][:2]: result}
    if data[:4] not in {b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"}:
        raise ValueError("Unsupported Mach-O container")
    count = struct.unpack_from(">I", data, 4)[0]
    size = 32 if data[:4] == b"\xca\xfe\xba\xbf" else 20
    if not 1 <= count <= 16 or 8 + count * size > len(data):
        raise ValueError("Invalid universal Mach-O architecture table")
    result = {}
    for index in range(count):
        fmt = ">iiQQII" if size == 32 else ">iiIII"
        cpu, subtype, offset, length, *_ = struct.unpack_from(fmt, data, 8 + index * size)
        if offset + length > len(data) or (cpu, subtype) in result:
            raise ValueError("Invalid universal Mach-O slice")
        result[(cpu, subtype)] = _thin(data[offset : offset + length])
    return result


def deployment_match(source: Path, deployed: Path) -> bool:
    try:
        return _snapshot(source.read_bytes()) == _snapshot(deployed.read_bytes())
    except (ValueError, struct.error, UnicodeError, OSError):
        return False


def comparison_reason(source: Path, deployed: Path) -> str:
    """Bounded mismatch categories for build logs; no source paths or binary data."""
    try:
        original, copied = _snapshot(source.read_bytes()), _snapshot(deployed.read_bytes())
        if original.keys() != copied.keys():
            return "architecture inventory differs"
        for architecture, source_slice in original.items():
            destination = copied[architecture]
            if source_slice[:2] != destination[:2]:
                return "Mach-O header differs"
            if source_slice[2] != destination[2]:
                for before, after in zip(source_slice[2], destination[2], strict=False):
                    if before != after:
                        return f"load command 0x{before[0]:x} differs"
                return "load command inventory differs"
            if source_slice[3] != destination[3]:
                return "section metadata or bytes differ"
        return "matched"
    except (ValueError, struct.error, UnicodeError, OSError) as error:
        return f"invalid container: {type(error).__name__}: {error}"
