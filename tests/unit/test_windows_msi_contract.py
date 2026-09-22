"""Small static guard for the Windows installer OS compatibility check."""

from pathlib import Path
from xml.etree import ElementTree


def test_windows_msi_checks_actual_build_number() -> None:
    source = Path(__file__).resolve().parents[2] / "installer" / "NetConfigLint.wxs"
    root = ElementTree.parse(source).getroot()
    namespace = {"w": "http://schemas.microsoft.com/wix/2006/wi"}
    search = root.find(".//w:Property[@Id='OSBUILDNUMBER']/w:RegistrySearch", namespace)
    assert search is not None
    assert search.attrib["Name"] == "CurrentBuildNumber"
    assert search.attrib["Win64"] == "yes"
    conditions = root.findall(".//w:Product/w:Condition", namespace)
    assert any("OSBUILDNUMBER >= 10240" in (condition.text or "") for condition in conditions)
    assert all("WindowsBuild" not in (condition.text or "") for condition in conditions)


def test_per_machine_shortcuts_use_common_folders_and_machine_keypaths() -> None:
    source = Path(__file__).resolve().parents[2] / "installer" / "NetConfigLint.wxs"
    root = ElementTree.parse(source).getroot()
    namespace = {"w": "http://schemas.microsoft.com/wix/2006/wi"}
    assert root.find(".//w:Directory[@Id='ProgramMenuFolder']", namespace) is not None
    assert root.find(".//w:Directory[@Id='DesktopFolder']", namespace) is not None
    assert root.find(".//w:Directory[@Id='CommonProgramMenuFolder']", namespace) is None
    assert root.find(".//w:Directory[@Id='CommonDesktopFolder']", namespace) is None
    for component_id in ("StartMenuShortcuts", "DesktopShortcut"):
        value = root.find(f".//w:Component[@Id='{component_id}']/w:RegistryValue", namespace)
        assert value is not None
        assert value.attrib["Root"] == "HKLM"
