from pathlib import Path

import pytest

from scripts import assemble_licenses as licensing


@pytest.mark.parametrize(
    ("name", "same_bytes", "signed", "accepted"),
    [
        ("msvcp140.dll", True, True, True),
        ("vcruntime140_1.dll", True, True, True),
        ("msvcp140.dll", True, False, False),
        ("msvcp140.dll", False, True, False),
        ("unknown.dll", True, True, False),
    ],
)
def test_runtime_requires_known_name_exact_bytes_and_microsoft_signature(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    same_bytes: bool,
    signed: bool,
    accepted: bool,
) -> None:
    source = tmp_path / name
    source.write_bytes(b"synthetic runtime")
    monkeypatch.setattr(licensing.sys, "platform", "win32")
    monkeypatch.setattr(licensing, "windows_runtime_candidates", lambda _: [source])
    monkeypatch.setattr(licensing, "is_microsoft_signed", lambda _: signed)
    data = source.read_bytes() if same_bytes else b"changed runtime"
    origin = licensing.windows_runtime_origin(Path(name), licensing.sha(data))
    assert (origin is not None) == accepted
    if origin:
        assert origin[0] == "Microsoft-VC-Runtime"
        assert str(tmp_path) not in origin[1]
