from pathlib import Path

import pytest

from netconfiglint.core.analyzer.control import AnalysisLimitReached, AnalysisLimits
from netconfiglint.core.input import decode_network_bytes, read_network_text


def test_decodes_utf8_and_gb18030_and_normalizes_newlines(tmp_path: Path) -> None:
    utf8 = decode_network_bytes("sysname 测试\r\n#\rreturn\n".encode())
    assert utf8.encoding == "utf-8-sig"
    assert utf8.newline_style == "mixed"
    assert utf8.text == "sysname 测试\n#\nreturn\n"

    path = tmp_path / "comware.cfg"
    path.write_bytes("sysname 华三\r\n".encode("gb18030"))
    gb = read_network_text(path)
    assert gb.encoding == "gb18030"
    assert gb.text == "sysname 华三\n"


def test_invalid_bytes_are_visible_and_limits_are_bounded() -> None:
    decoded = decode_network_bytes(b"description ok\xff\x81\n")
    assert decoded.recovered
    assert decoded.recovered_bytes == 2
    assert "\u27e6FF\u27e7" in decoded.text and "\u27e681\u27e7" in decoded.text

    with pytest.raises(AnalysisLimitReached, match="byte budget"):
        decode_network_bytes(b"12345", AnalysisLimits(max_input_bytes=4))
