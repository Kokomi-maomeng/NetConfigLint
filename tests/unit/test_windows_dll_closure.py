"""Synthetic import graphs verify packaging decisions, not binary validity."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import resolve_windows_dlls as dlls


def put(root: Path, name: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"synthetic PE placeholder")
    return path


@pytest.mark.parametrize("flattened", [False, True])
def test_keeps_transitive_and_dynamic_dependencies_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flattened: bool
) -> None:
    distribution = tmp_path / "dist" / "app.dist"
    wheel = tmp_path / "site-packages"
    prefix = "" if flattened else "PySide6/"
    for name in (
        "app.exe",
        "PySide6/QtCore.pyd",
        "PySide6/qml/QtQuick/quickplugin.dll",
        "PySide6/qt-plugins/platforms/qwindows.dll",
        "opengl32sw.dll",
        prefix + "qt6core.dll",
        prefix + "qt63danimation.dll",
        "unused-third-party.dll",
    ):
        put(distribution, name)
    put(wheel, "PySide6/Qt6Gui.dll")
    graph = {
        "app.exe": {"qt6core.dll", "api-ms-win-test.dll"},
        "qtcore.pyd": {"qt6core.dll"},
        "qt6core.dll": {"qt6gui.dll"},
        "qt6gui.dll": {"qt6core.dll"},
        "qwindows.dll": {"qt6gui.dll"},
        "qt63danimation.dll": {"unused-third-party.dll"},
    }
    monkeypatch.setenv("SYSTEMROOT", str(tmp_path / "no-system"))
    monkeypatch.setattr(dlls, "imports_for", lambda path: graph.get(path.name.lower(), set()))
    result = dlls.resolve(distribution, wheel)
    assert result["unresolved_non_system"] == []
    assert result["copied_count"] == 1
    assert result["removed_count"] == 2
    assert (distribution / prefix / "qt6core.dll").is_file()
    assert (distribution / "PySide6/Qt6Gui.dll").is_file()
    assert (distribution / "opengl32sw.dll").is_file()
    assert (distribution / "PySide6/qml/QtQuick/quickplugin.dll").is_file()
    assert (distribution / "PySide6/qt-plugins/platforms/qwindows.dll").is_file()


def test_unresolved_graph_does_not_prune(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    distribution = tmp_path / "dist" / "app.dist"
    put(distribution, "PySide6/QtCore.pyd")
    spare = put(distribution, "spare.dll")
    monkeypatch.setenv("SYSTEMROOT", str(tmp_path / "no-system"))
    monkeypatch.setattr(dlls, "imports_for", lambda _: {"missing.dll"})
    result = dlls.resolve(distribution, tmp_path / "site")
    assert result["unresolved_non_system"] == ["missing.dll"]
    assert result["removed_count"] == 0
    assert spare.is_file()


def test_refuses_non_distribution_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Refusing"):
        dlls.resolve(tmp_path, tmp_path)


def test_delay_imports_are_followed_and_pe_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    directories: list[int] = []
    closed: list[bool] = []
    pe = SimpleNamespace(
        parse_data_directories=lambda **kwargs: directories.extend(kwargs["directories"]),
        DIRECTORY_ENTRY_IMPORT=[SimpleNamespace(dll=b"Qt6Core.dll")],
        DIRECTORY_ENTRY_DELAY_IMPORT=[SimpleNamespace(dll=b"Qt6Gui.dll")],
        close=lambda: closed.append(True),
    )
    monkeypatch.setattr(dlls.pefile, "PE", lambda *args, **kwargs: pe)
    assert dlls.imports_for(Path("synthetic.dll")) == {"qt6core.dll", "qt6gui.dll"}
    assert dlls.pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"] in directories
    assert closed == [True]
