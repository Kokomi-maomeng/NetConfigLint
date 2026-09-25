from pathlib import Path

import pytest

from scripts import prepare_linux_runtime as runtime


def _file(root: Path, relative: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(relative.encode())
    return path


def test_linux_runtime_prunes_broad_qt_payload_by_dependency_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    distribution = tmp_path / "dist/NetConfigLint.dist"
    app = _file(distribution, "NetConfigLint")
    extension = _file(distribution, "PySide6/QtCore.so")
    _file(distribution, "PySide6/Qt3DCore.so")
    plugin = _file(distribution, "PySide6/qt-plugins/platforms/libqxcb.so")
    _file(distribution, "PySide6/qt-plugins/platforms/libqwayland.so")
    _file(distribution, "PySide6/qt-plugins/qmltooling/libqmldbg_debugger.so")
    _file(distribution, "PySide6/qml/QtQuick/qmldir")
    _file(distribution, "PySide6/qml/QtQuick/Controls/Material/qmldir")
    _file(distribution, "PySide6/qml/QtQuick/Controls/Universal/qmldir")
    _file(distribution, "PySide6/qml/Qt3D/qmldir")
    core = _file(distribution, "libQt6Core.so.6")
    xcb = _file(distribution, "libQt6XcbQpa.so.6")
    unused = _file(distribution, "libQt63DCore.so.6")
    system_library = _file(distribution, "libbz2.so.1.0")
    uuid_library = _file(distribution, "libuuid.so.1")

    graph = {
        app: (None, ("libQt6Core.so.6",)),
        extension: (None, ("libQt6Core.so.6",)),
        plugin: (None, ("libQt6XcbQpa.so.6",)),
        core: ("libQt6Core.so.6", ()),
        xcb: ("libQt6XcbQpa.so.6", ("libQt6Core.so.6",)),
        unused: ("libQt63DCore.so.6", ("libQt6Core.so.6",)),
    }
    monkeypatch.setattr(runtime, "_elf_metadata", graph.get)

    result = runtime.prune(distribution)

    assert result["removed_count"] >= 6
    assert core.is_file()
    assert xcb.is_file()
    assert not unused.exists()
    assert not system_library.exists()
    assert not uuid_library.exists()
    assert not (distribution / "PySide6/Qt3DCore.so").exists()
    assert not (distribution / "PySide6/qml/Qt3D").exists()
    assert not (distribution / "PySide6/qml/QtQuick/Controls/Universal").exists()
    assert plugin.is_file()


def test_linux_runtime_refuses_unproven_qt_elf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    distribution = tmp_path / "dist/NetConfigLint.dist"
    (distribution / "PySide6").mkdir(parents=True)
    library = _file(distribution, "libQt6Core.so.6")
    monkeypatch.setattr(runtime, "_elf_metadata", lambda path: None)

    with pytest.raises(ValueError, match="Cannot prove Linux Qt dependency closure"):
        runtime.prune(distribution)
    assert library.is_file()


def test_linux_runtime_refuses_arbitrary_directory(tmp_path: Path) -> None:
    distribution = tmp_path / "NetConfigLint.dist"
    (distribution / "PySide6").mkdir(parents=True)
    with pytest.raises(ValueError, match="Refusing to prune"):
        runtime.prune(distribution)
